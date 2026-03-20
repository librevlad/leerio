"""
server/api.py — FastAPI web server for the audiobook library.

All data access goes through server.db (SQLite).
Audio streaming uses S3 presigned URLs with filesystem fallback.

Run:
  uvicorn server.api:app --reload
"""

import logging
import os
import random
import re
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.requests import Request

from . import db
from .auth import (
    check_jwt_secret,
    clear_auth_cookie,
    get_current_user,
    get_optional_user,
    require_admin,
    set_auth_cookie,
    verify_google_token,
)
from .core import (
    ACTION_LABELS,
    ACTION_STYLES,
    BOOK_STATUSES,
    BOOKS_DIR,
    FOLDER_TO_LABEL,
    LABEL_TO_FOLDER,
    LIST_TO_STATUS,
    STATUS_STYLE,
    compute_achievements,
    count_mp3,
    estimate_duration_hours,
    find_similar,
    fmt_duration,
    folder_size_mb,
    normalize,
    reading_velocity,
)
from .ingest_api import router as ingest_router
from .payments import router as payments_router
from .storage import get_presigned_url, get_s3_object, s3_object_exists
from .tts_api import router as tts_router
from .upload import router as upload_router
from .youtube_api import router as youtube_router

logging.basicConfig(
    level=getattr(logging, os.environ.get("LEERIO_LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("leerio")


# ── Helpers ─────────────────────────────────────────────────────────────────


def _parse_book_id(book_id: str) -> int:
    """Parse book_id string to integer. Raises 404 if invalid."""
    try:
        return int(book_id)
    except ValueError:
        raise HTTPException(404, "Book not found")


def _book_path(book: dict) -> Path:
    """Resolve filesystem path for a catalog book."""
    return BOOKS_DIR / book["category"] / book["folder"]


def _resolve_user_book_path(book_id: str, user: dict | None = None) -> Path | None:
    """If book_id starts with 'ub:', resolve to user book directory."""
    if not book_id.startswith("ub:"):
        return None
    parts = book_id.split(":", 2)
    if len(parts) != 3:
        return None
    _, uid, slug = parts
    if ".." in slug or "/" in slug or "\\" in slug:
        return None
    if user and uid != user["user_id"]:
        return None
    books_dir = (
        Path(os.environ.get("LEERIO_DATA", str(Path(__file__).resolve().parent.parent / "data")))
        / "users"
        / uid
        / "books"
    )
    book_dir = books_dir / slug
    # Ensure resolved path stays within books directory
    try:
        resolved = book_dir.resolve()
        if not str(resolved).startswith(str(books_dir.resolve())):
            return None
    except (OSError, ValueError):
        return None
    return book_dir if book_dir.exists() else None


_CATEGORY_MAP = {
    "books": "Художественная",
    ".": "Другое",
    "": "Другое",
}


def _normalize_category(cat: str) -> str:
    return _CATEGORY_MAP.get(cat, cat) if cat in _CATEGORY_MAP else cat


def _enrich_catalog_book(
    b: dict,
    *,
    progress_map: dict | None = None,
    tags_map: dict | None = None,
    notes_map: dict | None = None,
    statuses_map: dict | None = None,
    cats_map: dict | None = None,
    rating: int = 0,
) -> dict:
    """Convert a DB book row to the API response shape."""
    book_id = b["id"]
    pct = (progress_map or {}).get(book_id, {}).get("pct", 0) if progress_map else 0
    tags = (tags_map or {}).get(book_id, []) if tags_map else []
    note = (notes_map or {}).get(book_id, "") if notes_map else ""

    cat_name = _normalize_category(b["category"])
    cat_info = (cats_map or {}).get(cat_name) if cats_map else db.get_category_by_name(cat_name)

    result = {
        "id": str(book_id),
        "folder": b["folder"],
        "category": cat_name,
        "category_color": cat_info["color"] if cat_info else "#94a3b8",
        "category_gradient": cat_info["gradient"] if cat_info else "linear-gradient(135deg, #334155 0%, #64748b 100%)",
        "author": b["author"],
        "title": b["title"],
        "reader": b.get("reader", ""),
        "progress": pct,
        "tags": tags,
        "note": note,
        "has_cover": bool(b.get("has_cover")),
        "mp3_count": b.get("mp3_count", 0),
        "description": b.get("description", ""),
    }

    if rating:
        result["rating"] = rating

    if statuses_map and book_id in statuses_map:
        result["book_status"] = statuses_map[book_id]["status"]

    return result


def _db_history_to_legacy(db_hist: list[dict]) -> list[dict]:
    """Convert DB history rows to the legacy format expected by core.py helpers."""
    return [
        {
            "ts": h.get("ts", ""),
            "action": h.get("action", ""),
            "book": h.get("book_title", ""),
            "detail": h.get("detail", ""),
            "rating": h.get("rating", 0),
        }
        for h in db_hist
    ]


def _db_books_to_legacy(db_books: list[dict]) -> list[dict]:
    """Convert DB book rows to the legacy format expected by core.py helpers."""
    return [
        {
            "path": _book_path(b),
            "folder": b["folder"],
            "category": b["category"],
            "author": b["author"],
            "title": b["title"],
            "reader": b.get("reader", ""),
        }
        for b in db_books
    ]


def _stream_from_filesystem(book_path: Path, track_index: int, request: Request):
    """Stream an audio file from the local filesystem with Range support."""
    mp3s = sorted(book_path.rglob("*.mp3"), key=lambda f: str(f))
    if track_index < 0 or track_index >= len(mp3s):
        raise HTTPException(404, "Track not found")

    file_path = mp3s[track_index]
    file_size = file_path.stat().st_size

    range_header = request.headers.get("range")
    if range_header:
        m = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if not m:
            raise HTTPException(416, "Invalid Range header")
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else file_size - 1
        end = min(end, file_size - 1)
        length = end - start + 1

        def iter_range():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(8192, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type="audio/mpeg",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
            },
        )

    def iter_file():
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                yield chunk

    return StreamingResponse(
        iter_file(),
        media_type="audio/mpeg",
        headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size)},
    )


# ── Pydantic models ────────────────────────────────────────────────────────


class NoteRequest(BaseModel):
    text: str


class TagsRequest(BaseModel):
    tags: list[str]


class ProgressRequest(BaseModel):
    pct: int
    note: str = ""


class QuoteRequest(BaseModel):
    text: str
    book: str
    author: str = ""


class CollectionRequest(BaseModel):
    name: str
    books: list[int] = []
    description: str = ""


class PlaybackPositionRequest(BaseModel):
    track_index: int
    position: float
    filename: str = ""


class SessionStartRequest(BaseModel):
    book: str


class GoogleAuthRequest(BaseModel):
    id_token: str


class LoginRequest(BaseModel):
    email: str
    password: str


class BookStatusRequest(BaseModel):
    status: str


class BookmarkRequest(BaseModel):
    track: int
    time: float
    note: str = ""


class AllowedEmailRequest(BaseModel):
    email: str


class CategoryUpdateRequest(BaseModel):
    name: str | None = None
    color: str | None = None
    gradient: str | None = None
    sort_order: int | None = None


class CategoryCreateRequest(BaseModel):
    name: str
    color: str = "#94a3b8"
    gradient: str = "linear-gradient(135deg, #334155 0%, #64748b 100%)"
    sort_order: int = 0


class BookCategoryRequest(BaseModel):
    category: str


class BookLanguageRequest(BaseModel):
    language: str


class SettingsUpdate(BaseModel):
    yearly_goal: int | None = None
    playback_speed: float | None = None


# ── App lifecycle ──────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    check_jwt_secret()
    db.init_db()
    db.sync_books()
    yield


# ── FastAPI app ─────────────────────────────────────────────────────────────

app = FastAPI(title="Audiobook Library", lifespan=lifespan)

_cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:80").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Content-Type", "Accept"],
)

# ── Rate limiting ─────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many requests"})


# ── CSRF protection ──────────────────────────────────────────────────────
@app.middleware("http")
async def csrf_protect(request: Request, call_next):
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        origin = request.headers.get("origin")
        if origin:
            allowed = {o.strip() for o in _cors_origins}
            if origin not in allowed:
                return JSONResponse(status_code=403, content={"detail": "Origin not allowed"})
    return await call_next(request)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── Include routers ──────────────────────────────────────────────────────────
app.include_router(upload_router)
app.include_router(tts_router)
app.include_router(ingest_router)
app.include_router(payments_router)
app.include_router(youtube_router)


# ── Auth endpoints ─────────────────────────────────────────────────────────


@app.post("/api/auth/google")
@limiter.limit("10/minute")
def auth_google(request: Request, req: GoogleAuthRequest):
    info = verify_google_token(req.id_token)
    if not db.is_email_allowed(info["email"]):
        raise HTTPException(403, "Registration is not allowed for this email")
    user = db.create_or_update_user(info["email"], info["name"], info["picture"])
    response = JSONResponse(
        content={
            "user_id": user["user_id"],
            "email": user["email"],
            "name": user["name"],
            "picture": user["picture"],
            "role": user["role"],
        }
    )
    set_auth_cookie(response, user["user_id"])
    return response


@app.post("/api/auth/login")
@limiter.limit("5/minute")
def auth_login(request: Request, req: LoginRequest):
    user = db.verify_user_password(req.email, req.password)
    if not user:
        raise HTTPException(401, "Invalid email or password")
    response = JSONResponse(
        content={
            "user_id": user["user_id"],
            "email": user["email"],
            "name": user["name"],
            "picture": user["picture"],
            "role": user["role"],
        }
    )
    set_auth_cookie(response, user["user_id"])
    return response


@app.get("/api/auth/me")
def auth_me(user: dict = Depends(get_current_user)):
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "picture": user["picture"],
        "role": user["role"],
        "plan": user.get("plan", "free"),
    }


@app.post("/api/telemetry")
async def telemetry(request: Request):
    """Fire-and-forget telemetry. Logs events for analytics."""
    try:
        data = await request.json()
        logger.info("telemetry: %s %s", data.get("event", "?"), {k: v for k, v in data.items() if k != "event"})
    except Exception:
        pass
    return {"ok": True}


@app.post("/api/auth/logout")
def auth_logout():
    response = JSONResponse(content={"ok": True})
    clear_auth_cookie(response)
    return response


# ── Admin: Allowed Emails ──────────────────────────────────────────────────


@app.get("/api/admin/allowed-emails")
def get_allowed_emails(user: dict = Depends(get_current_user)):
    require_admin(user)
    return db.list_allowed_emails()


@app.post("/api/admin/allowed-emails")
def add_email(req: AllowedEmailRequest, user: dict = Depends(get_current_user)):
    require_admin(user)
    db.add_allowed_email(req.email, user["email"])
    return {"ok": True}


@app.delete("/api/admin/allowed-emails/{email}")
def delete_email(email: str, user: dict = Depends(get_current_user)):
    require_admin(user)
    removed = db.remove_allowed_email(email)
    if not removed:
        raise HTTPException(404, "Email not found")
    return {"ok": True}


# ── Categories ─────────────────────────────────────────────────────────────


@app.get("/api/categories")
def list_categories():
    """Public: returns all categories with their styling info."""
    return db.get_all_categories()


@app.post("/api/admin/categories")
def create_category(req: CategoryCreateRequest, user: dict = Depends(get_current_user)):
    """Admin only: create a new category."""
    require_admin(user)
    try:
        cat = db.create_category(req.name, req.color, req.gradient, req.sort_order)
    except Exception:
        raise HTTPException(409, "Category with this name already exists")
    return cat


@app.put("/api/admin/categories/{cat_id}")
def update_category(cat_id: int, req: CategoryUpdateRequest, user: dict = Depends(get_current_user)):
    """Admin only: update a category's name, color, gradient, sort_order."""
    require_admin(user)
    updated = db.update_category_by_id(
        cat_id,
        name=req.name,
        color=req.color,
        gradient=req.gradient,
        sort_order=req.sort_order,
    )
    if not updated:
        raise HTTPException(404, "Category not found")
    return updated


@app.delete("/api/admin/categories/{cat_id}")
def delete_category_endpoint(cat_id: int, user: dict = Depends(get_current_user)):
    """Admin only: delete a category."""
    require_admin(user)
    deleted = db.delete_category(cat_id)
    if not deleted:
        raise HTTPException(404, "Category not found")
    return {"ok": True}


@app.put("/api/admin/books/{book_id}/category")
def update_book_category(book_id: int, req: BookCategoryRequest, user: dict = Depends(get_current_user)):
    """Admin only: reassign a book to a different category."""
    require_admin(user)
    updated = db.update_book_category(book_id, req.category)
    if not updated:
        raise HTTPException(404, "Book not found")
    return {"ok": True}


@app.put("/api/admin/books/{book_id}/language")
def update_book_language(book_id: int, req: BookLanguageRequest, user: dict = Depends(get_current_user)):
    """Admin only: set a book's language (ru, en, uk)."""
    require_admin(user)
    if req.language not in ("ru", "en", "uk"):
        raise HTTPException(400, "Language must be ru, en, or uk")
    updated = db.update_book_language(book_id, req.language)
    if not updated:
        raise HTTPException(404, "Book not found")
    return {"ok": True}


# ── Config endpoint ─────────────────────────────────────────────────────────


@app.get("/api/config/constants")
def get_constants():
    all_cats = [c for c in db.get_all_categories() if c["name"] != "Личные"]
    return {
        "categories": all_cats,
        "status_style": STATUS_STYLE,
        "action_styles": ACTION_STYLES,
        "action_labels": ACTION_LABELS,
        "list_to_status": LIST_TO_STATUS,
        "label_to_folder": LABEL_TO_FOLDER,
        "folder_to_label": FOLDER_TO_LABEL,
        "book_statuses": BOOK_STATUSES,
    }


# ── Dashboard ───────────────────────────────────────────────────────────────


@app.get("/api/dashboard")
def get_dashboard(user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    year = str(datetime.now().year)

    # Single batched call replaces 7 separate DB queries
    data = db.get_dashboard_data(uid, year)
    hist = data["history"]
    counts = data["counts"]

    # Count personal user books too
    from .core import UserData

    ud = UserData(uid)
    user_books_count = len(ud.user_books_list())

    # Active books — already joined with progress in the query
    active_cards = [
        {
            "id": str(b["id"]),
            "folder": b["folder"],
            "category": b["category"],
            "author": b["author"],
            "title": b["title"],
            "reader": b.get("reader", ""),
            "progress": b["progress"],
            "has_cover": bool(b.get("has_cover")),
            "duration_hours": b.get("duration_hours", 0),
            "list": "В процессе",
            "name": b["folder"],
        }
        for b in data["active"]
    ]

    # book_titles built from all_books below (avoid N+1 per-book queries)
    book_titles: dict = {}

    # Recent activity
    recent = []
    for h in hist[:8]:
        bid = h.get("book_id")
        book_title = book_titles.get(bid, h.get("book_title", "")) if bid else h.get("book_title", "")
        recent.append(
            {
                "ts": h.get("ts", ""),
                "action": h.get("action", ""),
                "book": book_title,
                "detail": h.get("detail", ""),
                "rating": h.get("rating", 0),
                "action_label": ACTION_LABELS.get(h.get("action", ""), h.get("action", "")),
                "action_style": ACTION_STYLES.get(h.get("action", ""), "white"),
                "book_id": str(bid) if bid else None,
            }
        )

    # Heatmap
    day_counts: dict[str, int] = Counter()
    for h in hist:
        if h.get("action") in ("listen", "phone", "done", "inbox"):
            day = (h.get("ts") or "")[:10]
            if day:
                day_counts[day] += 1

    # All books — used for category counts and book_titles lookup
    all_books = db.get_all_books()
    book_titles = {b["id"]: b["title"] for b in all_books}
    cat_counts = Counter(_normalize_category(b["category"]) for b in all_books)

    return {
        "total_books": int(counts.get("total_books", 0)) + user_books_count,
        "total_done": int(counts.get("total_done", 0)),
        "total_hours": round(float(counts.get("total_hours", 0)), 1),
        "active_count": len(active_cards),
        "active_books": active_cards,
        "now_playing": None,
        "recent": recent,
        "heatmap": dict(day_counts),
        "quote": data["quote"],
        "this_year_done": int(counts.get("this_year_done", 0)),
        "yearly_goal": data["settings"].get("yearly_goal", 24),
        "category_counts": dict(cat_counts),
    }


# ── Book Shelves (category carousels for home page) ────────────────────────


@app.get("/api/books/shelves")
def get_book_shelves(user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    all_books = db.get_all_books()
    statuses = db.get_all_user_book_statuses(uid)
    progress = db.get_all_user_progress(uid)

    # Build category sort_order map from DB
    cats_db = db.get_all_categories()
    cat_order = {c["name"]: c["sort_order"] for c in cats_db}

    # Group by category (exclude personal uploads and low-quality entries)
    by_cat: dict[str, list[dict]] = {}
    for b in all_books:
        cat = b.get("category", "")
        if cat == "Личные":
            continue
        # Exclude low-quality entries (no cover and no author)
        if not b.get("has_cover") and not b.get("author"):
            continue
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(b)

    # Count active books per category (reading/paused)
    active_cats: set[str] = set()
    for b in all_books:
        bid = str(b["id"])
        st = statuses.get(bid, {}).get("status")
        if st in ("reading", "paused"):
            active_cats.add(b.get("category", ""))

    # Sort: categories with active books first, then by sort_order
    sorted_cats = sorted(
        by_cat.keys(),
        key=lambda c: (0 if c in active_cats else 1, cat_order.get(c, 99)),
    )

    shelves = []
    for cat in sorted_cats:
        books = by_cat[cat]
        # Prefer books with covers in sample
        with_cover = [b for b in books if b.get("has_cover")]
        without_cover = [b for b in books if not b.get("has_cover")]
        n = min(12, len(books))
        if len(with_cover) >= n:
            sample = random.sample(with_cover, n)
        else:
            sample = with_cover + random.sample(without_cover, min(n - len(with_cover), len(without_cover)))
        shelf_books = []
        for b in sample:
            bid = str(b["id"])
            pct = progress.get(bid, {}).get("pct", 0)
            st = statuses.get(bid, {}).get("status")
            shelf_books.append(
                {
                    "id": bid,
                    "title": b["title"],
                    "author": b["author"],
                    "category": b["category"],
                    "has_cover": bool(b.get("has_cover")),
                    "progress": pct,
                    "book_status": st,
                }
            )
        shelves.append({"category": cat, "count": len(books), "books": shelf_books})

    return shelves


# ── Recommendations ─────────────────────────────────────────────────────────


@app.get("/api/recommendations")
def get_recommendations(user: dict = Depends(get_current_user)):
    """Return 6 recommended books based on user's listening history."""
    uid = user["user_id"]
    all_books = db.get_all_books()
    statuses = db.get_all_user_book_statuses(uid)

    # Gather user's active/done categories for preference weighting
    user_cats: Counter = Counter()
    user_book_ids: set[str] = set()
    for bid, info in statuses.items():
        user_book_ids.add(bid)
        if info["status"] in ("reading", "done"):
            for b in all_books:
                if str(b["id"]) == bid:
                    user_cats[b["category"]] += 1
                    break

    # Candidate books: not already in user's library (no status set)
    candidates = []
    for b in all_books:
        bid = str(b["id"])
        if bid not in user_book_ids and (b.get("has_cover") or b.get("author")):
            # Exclude low-quality entries (no cover and no author)
            # Score: prefer user's favorite categories, then random
            cat_score = user_cats.get(b["category"], 0)
            candidates.append((b, cat_score + random.random()))

    # Sort by score desc, pick top 6
    candidates.sort(key=lambda x: x[1], reverse=True)
    recs = []
    for b, _ in candidates[:6]:
        bid = str(b["id"])
        recs.append(
            {
                "id": bid,
                "title": b["title"],
                "author": b["author"],
                "category": b["category"],
                "has_cover": bool(b.get("has_cover")),
                "progress": 0,
                "book_status": None,
                "duration_hours": b.get("duration_hours"),
            }
        )
    return recs


# ── Books ───────────────────────────────────────────────────────────────────


@app.get("/api/books")
def get_books(
    category: str | None = Query(None),
    search: str | None = Query(None),
    tag: str | None = Query(None),
    sort: str = Query("title"),
    language: str | None = Query(None),
    limit: int | None = Query(None),
    user: dict | None = Depends(get_optional_user),
):
    uid = user["user_id"] if user else None
    books = db.search_books(category=category, search=search, sort=sort, language=language)

    if uid:
        statuses = db.get_all_user_book_statuses(uid)
        progress = db.get_all_user_progress(uid)
        tags_map = db.get_all_user_tags_map(uid)
        notes_map = db.get_all_user_notes_map(uid)
    else:
        statuses = {}
        progress = {}
        tags_map = {}
        notes_map = {}

    cats_map = {c["name"]: c for c in db.get_all_categories()}
    result = []
    search_lower = search.lower() if search else None
    for b in books:
        enriched = _enrich_catalog_book(
            b,
            progress_map=progress,
            tags_map=tags_map,
            notes_map=notes_map,
            statuses_map=statuses,
            cats_map=cats_map,
        )
        if tag and tag not in enriched["tags"]:
            continue
        result.append(enriched)

    # If search is active, also include books matching by user tags
    # (SQL search only covers title/author/reader, tags are user-specific)
    if search_lower and uid:
        matched_ids = {b["id"] for b in result}
        all_books = db.search_books(category=category, sort=sort, language=language)
        for b in all_books:
            enriched = _enrich_catalog_book(
                b,
                progress_map=progress,
                tags_map=tags_map,
                notes_map=notes_map,
                statuses_map=statuses,
                cats_map=cats_map,
            )
            if str(enriched["id"]) in matched_ids or enriched["id"] in matched_ids:
                continue
            if any(search_lower in t.lower() for t in enriched["tags"]):
                if tag and tag not in enriched["tags"]:
                    continue
                result.append(enriched)

    # Add personal user books (only for authenticated users)
    if uid:
        from .core import UserData

        ud = UserData(uid)
        user_books = ud.user_books_list()
        for ub in user_books:
            book_id = f"ub:{uid}:{ub['slug']}"
            ub_title = ub.get("title", "")
            ub_author = ub.get("author", "")
            if category and category != "Личные":
                continue
            if search:
                q = search.lower()
                if q not in ub_title.lower() and q not in ub_author.lower():
                    continue
            book_dir = Path(ub["path"])
            enriched = {
                "id": book_id,
                "folder": ub["slug"],
                "category": "Личные",
                "author": ub_author,
                "title": ub_title,
                "reader": ub.get("reader", ""),
                "path": ub["path"],
                "progress": 0,
                "tags": [],
                "note": "",
                "has_cover": (book_dir / "cover.jpg").exists(),
                "is_personal": True,
                "source": ub.get("source", "upload"),
                "mp3_count": count_mp3(book_dir),
            }
            result.append(enriched)

    if sort == "progress":
        result.sort(key=lambda x: -x["progress"])
    elif sort == "rating":
        result.sort(key=lambda x: -(x.get("rating") or 0))

    if limit and limit > 0:
        result = result[:limit]

    return result


@app.get("/api/books/{book_id}")
def get_book(book_id: str, user: dict | None = Depends(get_optional_user)):
    uid = user["user_id"] if user else None

    # Handle user book IDs (requires auth)
    if book_id.startswith("ub:") and user:
        ub_path = _resolve_user_book_path(book_id, user)
        if ub_path:
            from .core import _load_json

            meta = _load_json(ub_path / "meta.json", dict)
            slug = ub_path.name
            enriched = {
                "id": book_id,
                "slug": slug,
                "folder": slug,
                "category": "Личные",
                "author": meta.get("author", ""),
                "title": meta.get("title", ""),
                "reader": meta.get("reader", ""),
                "path": str(ub_path),
                "progress": 0,
                "tags": [],
                "note": "",
                "has_cover": (ub_path / "cover.jpg").exists(),
                "is_personal": True,
                "source": meta.get("source", "upload"),
                "created_at": meta.get("created_at", ""),
                "size_mb": round(folder_size_mb(ub_path), 1),
                "mp3_count": count_mp3(ub_path),
                "duration_hours": estimate_duration_hours(ub_path),
                "duration_fmt": fmt_duration(estimate_duration_hours(ub_path)),
                "timeline": [],
            }
            return enriched
    elif book_id.startswith("ub:"):
        raise HTTPException(401, "Not authenticated")

    bid = _parse_book_id(book_id)
    b = db.get_book_by_id(bid)
    if not b:
        raise HTTPException(404, "Book not found")

    # User-specific data (only if authenticated)
    tags = db.get_user_tags(uid, bid) if uid else []
    note = db.get_user_note(uid, bid) if uid else ""
    pct = db.get_user_progress(uid, bid) if uid else 0
    rating = db.get_user_rating(uid, bid) if uid else None
    status = db.get_user_book_status(uid, bid) if uid else None

    cat_name = _normalize_category(b["category"])
    cat_info = db.get_category_by_name(cat_name)

    enriched = {
        "id": str(bid),
        "folder": b["folder"],
        "category": cat_name,
        "category_color": cat_info["color"] if cat_info else "#94a3b8",
        "category_gradient": cat_info["gradient"] if cat_info else "linear-gradient(135deg, #334155 0%, #64748b 100%)",
        "author": b["author"],
        "title": b["title"],
        "reader": b.get("reader", ""),
        "progress": pct,
        "tags": tags,
        "note": note,
        "has_cover": bool(b.get("has_cover")),
        "size_mb": b.get("size_mb", 0),
        "mp3_count": b.get("mp3_count", 0),
        "duration_hours": b.get("duration_hours", 0),
        "duration_fmt": fmt_duration(b.get("duration_hours", 0)),
        "description": b.get("description", ""),
    }

    if rating:
        enriched["rating"] = rating
    if status:
        enriched["book_status"] = status["status"]

    # Timeline from history (only if authenticated)
    if uid:
        timeline_entries = db.get_user_history_for_book(uid, bid)
        enriched["timeline"] = [
            {
                "ts": h.get("ts", ""),
                "action": h.get("action", ""),
                "detail": h.get("detail", ""),
                "rating": h.get("rating", 0),
                "action_label": ACTION_LABELS.get(h.get("action", ""), h.get("action", "")),
            }
            for h in timeline_entries
        ]
    else:
        enriched["timeline"] = []

    return enriched


@app.get("/api/books/{book_id}/similar")
def get_similar(book_id: str, user: dict | None = Depends(get_optional_user)):
    uid = user["user_id"] if user else None
    bid = _parse_book_id(book_id)
    b = db.get_book_by_id(bid)
    if not b:
        raise HTTPException(404, "Book not found")

    all_books = db.get_all_books()
    hist = db.get_user_history(uid, limit=500) if uid else []

    # Include user tags for better similarity matching
    user_tags = db.get_all_user_tags_map(uid) if uid else {}
    target_tags = user_tags.get(bid, [])

    target = {
        "path": _book_path(b),
        "folder": b["folder"],
        "category": b["category"],
        "author": b["author"],
        "title": b["title"],
        "reader": b.get("reader", ""),
        "user_tags": target_tags,
    }
    folder_to_db = {bk["folder"]: bk for bk in all_books}
    legacy_books = _db_books_to_legacy(all_books)
    # Inject user tags into legacy books for similarity scoring
    for lb in legacy_books:
        db_book = folder_to_db.get(lb["folder"])
        if db_book:
            lb["user_tags"] = user_tags.get(db_book["id"], [])
    legacy_hist = _db_history_to_legacy(hist)
    similar = find_similar(target, legacy_books, legacy_hist, top_n=6)

    # Map similar results back to DB books for enrichment
    result = []
    for legacy_b, score in similar:
        db_book = folder_to_db.get(legacy_b["folder"])
        if db_book:
            enriched = _enrich_catalog_book(db_book)
            enriched["score"] = round(score, 1)
            result.append(enriched)

    return result


# ── Audio / Playback ──────────────────────────────────────────────────────


@app.get("/api/books/{book_id}/tracks")
def get_book_tracks(book_id: str, user: dict = Depends(get_current_user)):
    # User books
    ub_path = _resolve_user_book_path(book_id, user)
    if ub_path:
        mp3s = sorted(ub_path.rglob("*.mp3"), key=lambda f: str(f))
        tracks = []
        for i, f in enumerate(mp3s):
            dur = 0.0
            try:
                from mutagen.mp3 import MP3

                audio = MP3(str(f))
                dur = audio.info.length
            except (OSError, Exception):
                pass
            tracks.append(
                {
                    "index": i,
                    "filename": f.name,
                    "path": str(f.relative_to(ub_path)),
                    "duration": round(dur, 2),
                    "size_bytes": f.stat().st_size,
                }
            )
        return {"book_id": book_id, "count": len(tracks), "tracks": tracks}

    # Catalog books
    bid = _parse_book_id(book_id)
    db_tracks = db.get_book_tracks(bid)
    tracks = [
        {
            "index": t["idx"],
            "filename": t["filename"],
            "path": t.get("s3_key", ""),
            "duration": t.get("duration", 0),
            "size_bytes": t.get("size_bytes", 0),
        }
        for t in db_tracks
    ]
    return {"book_id": book_id, "count": len(tracks), "tracks": tracks}


def _cover_placeholder(title: str = "", category: str = "") -> Response:
    """Return a simple SVG placeholder for books without covers."""
    letter = title[0].upper() if title else "?"
    # Category-based colors (match frontend catGradient)
    colors = {
        "Бизнес": ("#92400e", "#d97706"),
        "Отношения": ("#9d174d", "#db2777"),
        "Саморазвитие": ("#9a5c16", "#E8923A"),
        "Художественная": ("#155e75", "#0891b2"),
        "Языки": ("#064e3b", "#059669"),
    }
    c1, c2 = colors.get(category, ("#334155", "#64748b"))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="{c1}"/>
    <stop offset="100%" stop-color="{c2}"/>
  </linearGradient></defs>
  <rect width="300" height="300" fill="url(#g)"/>
  <text x="150" y="170" text-anchor="middle" font-size="120" font-family="sans-serif" fill="rgba(255,255,255,0.3)">{letter}</text>
</svg>'''
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/api/books/{book_id}/cover")
def get_book_cover(book_id: str):
    # User books
    ub_path = _resolve_user_book_path(book_id)
    if ub_path:
        cover = ub_path / "cover.jpg"
        if not cover.exists():
            return _cover_placeholder(ub_path.name)
        return FileResponse(
            str(cover),
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=604800"},
        )

    # Catalog books
    bid = _parse_book_id(book_id)
    b = db.get_book_by_id(bid)
    if not b:
        raise HTTPException(404, "Book not found")

    # Try local filesystem first
    book_path = _book_path(b)
    for ext in ("jpg", "jpeg", "png", "webp"):
        cover = book_path / f"cover.{ext}"
        if cover.exists():
            return FileResponse(
                str(cover),
                media_type=f"image/{ext}",
                headers={"Cache-Control": "public, max-age=604800"},
            )

    # Fallback to S3 — redirect to presigned URL
    s3_prefix = b.get("s3_prefix", "")
    if s3_prefix and b.get("has_cover"):
        for cover_ext in ("jpg", "jpeg", "png", "webp"):
            cover_key = f"{s3_prefix}/cover.{cover_ext}"
            if s3_object_exists(cover_key):
                url = get_presigned_url(cover_key, expires=86400)
                if url:
                    return RedirectResponse(url)

    return _cover_placeholder(b.get("title", ""), b.get("category", ""))


def _s3_stream(body, chunk_size=64 * 1024):
    """Wrap S3 body stream to ensure cleanup on error or early disconnect."""
    try:
        yield from body.iter_chunks(chunk_size=chunk_size)
    finally:
        body.close()


@app.get("/api/audio/{book_id}/{track_index}")
def stream_audio(book_id: str, track_index: int, request: Request, user: dict = Depends(get_current_user)):
    # User books — always filesystem
    ub_path = _resolve_user_book_path(book_id, user)
    if ub_path:
        return _stream_from_filesystem(ub_path, track_index, request)

    # Catalog books — try S3, fallback to filesystem
    bid = _parse_book_id(book_id)
    db_tracks = db.get_book_tracks(bid)
    if track_index < 0 or track_index >= len(db_tracks):
        raise HTTPException(404, "Track not found")

    track = db_tracks[track_index]

    # Try S3 streaming proxy
    s3_key = track.get("s3_key", "")
    if s3_key:
        range_header = request.headers.get("range")
        s3_resp = get_s3_object(s3_key, range_header=range_header)
        if s3_resp:
            headers: dict[str, str] = {
                "Content-Type": s3_resp["content_type"],
                "Accept-Ranges": "bytes",
            }
            if s3_resp["content_range"]:
                headers["Content-Range"] = s3_resp["content_range"]
            if s3_resp["content_length"]:
                headers["Content-Length"] = str(s3_resp["content_length"])
            status = 206 if range_header and s3_resp["status"] == 206 else 200
            return StreamingResponse(
                _s3_stream(s3_resp["body"]),
                status_code=status,
                headers=headers,
            )

    # Fallback to filesystem
    b = db.get_book_by_id(bid)
    if not b:
        raise HTTPException(404, "Book not found")
    return _stream_from_filesystem(_book_path(b), track_index, request)


@app.get("/api/books/{book_id}/playback")
def get_playback(book_id: str, user: dict = Depends(get_current_user)):
    bid = _parse_book_id(book_id)
    pos = db.get_user_playback(user["user_id"], bid)
    if pos:
        return pos
    return {"track_index": 0, "position": 0, "filename": "", "updated": None}


@app.put("/api/books/{book_id}/playback")
def set_playback(book_id: str, req: PlaybackPositionRequest, user: dict = Depends(get_current_user)):
    bid = _parse_book_id(book_id)
    db.set_user_playback(user["user_id"], bid, req.track_index, req.position, req.filename)
    return {"ok": True}


# ── History ─────────────────────────────────────────────────────────────────


@app.get("/api/history")
def get_history(
    action: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(100),
    user: dict = Depends(get_current_user),
):
    hist = db.get_user_history(user["user_id"], action=action, search=search, limit=limit)
    # Build book title lookup from DB for accurate display
    all_books = db.search_books()
    title_by_id = {b["id"]: b["title"] for b in all_books}
    return [
        {
            "ts": h.get("ts", ""),
            "action": h.get("action", ""),
            "book": title_by_id.get(h.get("book_id"), h.get("book_title", "")),
            "detail": h.get("detail", ""),
            "rating": h.get("rating", 0),
            "action_label": ACTION_LABELS.get(h.get("action", ""), h.get("action", "")),
            "action_style": ACTION_STYLES.get(h.get("action", ""), "white"),
            "book_id": str(h["book_id"]) if h.get("book_id") else None,
        }
        for h in hist
    ]


# ── Notes ───────────────────────────────────────────────────────────────────


@app.get("/api/books/{book_id}/notes")
def get_note(book_id: str, user: dict = Depends(get_current_user)):
    bid = _parse_book_id(book_id)
    note = db.get_user_note(user["user_id"], bid)
    b = db.get_book_by_id(bid)
    title = b["title"] if b else ""
    return {"title": title, "text": note}


@app.put("/api/books/{book_id}/notes")
def set_note(book_id: str, req: NoteRequest, user: dict = Depends(get_current_user)):
    bid = _parse_book_id(book_id)
    db.set_user_note(user["user_id"], bid, req.text)
    return {"ok": True}


@app.delete("/api/books/{book_id}/notes")
def delete_note(book_id: str, user: dict = Depends(get_current_user)):
    bid = _parse_book_id(book_id)
    db.set_user_note(user["user_id"], bid, "")
    return {"ok": True}


# ── Tags ────────────────────────────────────────────────────────────────────


@app.get("/api/books/{book_id}/tags")
def get_tags_for_book(book_id: str, user: dict = Depends(get_current_user)):
    bid = _parse_book_id(book_id)
    return db.get_user_tags(user["user_id"], bid)


@app.get("/api/tags/all")
def get_all_tags(user: dict = Depends(get_current_user)):
    return db.get_all_user_tags(user["user_id"])


@app.put("/api/books/{book_id}/tags")
def set_tags_for_book(book_id: str, req: TagsRequest, user: dict = Depends(get_current_user)):
    bid = _parse_book_id(book_id)
    db.set_user_tags(user["user_id"], bid, req.tags)
    return {"ok": True}


# ── Progress ────────────────────────────────────────────────────────────────


@app.get("/api/progress")
def get_all_progress(user: dict = Depends(get_current_user)):
    return db.get_all_user_progress(user["user_id"])


@app.put("/api/books/{book_id}/progress")
def set_progress(book_id: str, req: ProgressRequest, user: dict = Depends(get_current_user)):
    bid = _parse_book_id(book_id)
    db.set_user_progress(user["user_id"], bid, req.pct)
    return {"ok": True}


# ── Quotes ──────────────────────────────────────────────────────────────────


@app.get("/api/quotes")
def get_quotes(user: dict = Depends(get_current_user)):
    return db.get_user_quotes(user["user_id"])


@app.post("/api/quotes")
def add_quote(req: QuoteRequest, user: dict = Depends(get_current_user)):
    db.add_user_quote(user["user_id"], req.text, req.book, req.author)
    return {"ok": True}


@app.delete("/api/quotes/{quote_id}")
def delete_quote(quote_id: int, user: dict = Depends(get_current_user)):
    db.delete_user_quote(user["user_id"], quote_id)
    return {"ok": True}


# ── Collections ─────────────────────────────────────────────────────────────


@app.get("/api/collections")
def get_collections(user: dict = Depends(get_current_user)):
    return db.get_user_collections(user["user_id"])


@app.post("/api/collections")
def create_collection(req: CollectionRequest, user: dict = Depends(get_current_user)):
    coll_id = db.create_user_collection(user["user_id"], req.name, req.books, req.description)
    return {"ok": True, "id": coll_id}


@app.put("/api/collections/{collection_id}")
def update_collection(collection_id: int, req: CollectionRequest, user: dict = Depends(get_current_user)):
    db.update_user_collection(user["user_id"], collection_id, req.name, req.books, req.description)
    return {"ok": True}


@app.delete("/api/collections/{collection_id}")
def delete_collection(collection_id: int, user: dict = Depends(get_current_user)):
    if not db.delete_user_collection(user["user_id"], collection_id):
        raise HTTPException(404, "Collection not found")
    return {"ok": True}


# ── Sessions ────────────────────────────────────────────────────────────────


@app.get("/api/sessions/stats")
def get_session_stats(days: int = Query(7), user: dict = Depends(get_current_user)):
    return db.get_session_stats(user["user_id"], days)


@app.post("/api/sessions/start")
def start_session(req: SessionStartRequest, user: dict = Depends(get_current_user)):
    entry = db.start_user_session(user["user_id"], req.book)
    return entry


@app.post("/api/sessions/stop")
def stop_session(req: SessionStartRequest, user: dict = Depends(get_current_user)):
    minutes = db.stop_user_session(user["user_id"], req.book)
    return {"minutes": minutes}


# ── User Settings ──────────────────────────────────────────────────────────


@app.get("/api/user/settings")
def get_settings(user: dict = Depends(get_current_user)):
    return db.get_user_settings(user["user_id"])


@app.put("/api/user/settings")
def update_settings(req: SettingsUpdate, user: dict = Depends(get_current_user)):
    return db.update_user_settings(user["user_id"], **req.model_dump(exclude_none=True))


@app.get("/api/user/streak")
def get_streak(user: dict = Depends(get_current_user)):
    """Return current listening streak (consecutive days with history entries)."""
    uid = user["user_id"]
    history = db.get_user_history(uid)
    if not history:
        return {"current": 0, "best": 0}
    # Collect unique dates with activity
    from datetime import date, timedelta

    active_dates: set[date] = set()
    for h in history:
        ts = h.get("ts", "")
        if ts:
            try:
                active_dates.add(date.fromisoformat(ts[:10]))
            except ValueError:
                pass
    if not active_dates:
        return {"current": 0, "best": 0}
    # Calculate current streak from today backwards
    today = date.today()
    current = 0
    d = today
    while d in active_dates:
        current += 1
        d -= timedelta(days=1)
    # If today has no activity yet, check from yesterday
    if current == 0:
        d = today - timedelta(days=1)
        while d in active_dates:
            current += 1
            d -= timedelta(days=1)
    # Best streak
    sorted_dates = sorted(active_dates)
    best = 1
    run = 1
    for i in range(1, len(sorted_dates)):
        if sorted_dates[i] - sorted_dates[i - 1] == timedelta(days=1):
            run += 1
            best = max(best, run)
        else:
            run = 1
    return {"current": current, "best": best}


# ── Book Status ─────────────────────────────────────────────────────────────


@app.get("/api/user/book-status")
def get_all_book_statuses(user: dict = Depends(get_current_user)):
    statuses = db.get_all_user_book_statuses(user["user_id"])
    # Return with string keys for frontend compatibility
    return {str(k): v for k, v in statuses.items()}


@app.get("/api/user/book-status/{book_id}")
def get_book_status(book_id: str, user: dict = Depends(get_current_user)):
    bid = _parse_book_id(book_id)
    status = db.get_user_book_status(user["user_id"], bid)
    return status or {"status": None}


@app.put("/api/user/book-status/{book_id}")
def set_book_status(book_id: str, req: BookStatusRequest, user: dict = Depends(get_current_user)):
    if req.status not in BOOK_STATUSES:
        raise HTTPException(400, f"Invalid status. Must be one of: {BOOK_STATUSES}")

    uid = user["user_id"]
    bid = _parse_book_id(book_id)
    db.set_user_book_status(uid, bid, req.status)

    # Log to user's history
    status_labels = {
        "want_to_read": "Хочу прочесть",
        "reading": "Слушаю",
        "paused": "На паузе",
        "done": "Прослушано",
        "rejected": "Забраковано",
    }
    action_map = {"reading": "listen", "paused": "pause", "done": "done", "rejected": "reject", "want_to_read": "inbox"}

    b = db.get_book_by_id(bid)
    db.add_user_history(
        uid,
        action=action_map.get(req.status, "move"),
        book_id=bid,
        book_title=b["title"] if b else str(bid),
        detail=status_labels.get(req.status, req.status),
    )

    if req.status == "done" and b:
        db.set_user_progress(uid, bid, 100)

    return {"ok": True}


@app.delete("/api/user/book-status/{book_id}")
def remove_book_status(book_id: str, user: dict = Depends(get_current_user)):
    bid = _parse_book_id(book_id)
    db.remove_user_book_status(user["user_id"], bid)
    return {"ok": True}


# ── Rating ─────────────────────────────────────────────────────────────────


@app.put("/api/user/rating/{book_id}")
def set_rating(book_id: str, rating: int = Body(..., ge=0, le=5, embed=True), user: dict = Depends(get_current_user)):
    bid = _parse_book_id(book_id)
    db.set_user_rating(user["user_id"], bid, rating)
    return {"ok": True, "rating": rating}


# ── Bookmarks ──────────────────────────────────────────────────────────────


@app.get("/api/user/bookmarks/all")
def get_all_bookmarks(user: dict = Depends(get_current_user)):
    return db.get_all_user_bookmarks_map(user["user_id"])


@app.get("/api/user/notes/all")
def get_all_notes(user: dict = Depends(get_current_user)):
    return db.get_all_user_notes_map(user["user_id"])


@app.get("/api/user/tags/all")
def get_all_tags_map(user: dict = Depends(get_current_user)):
    return db.get_all_user_tags_map(user["user_id"])


@app.get("/api/user/bookmarks/{book_id}")
def get_bookmarks(book_id: str, user: dict = Depends(get_current_user)):
    bid = _parse_book_id(book_id)
    return db.get_user_bookmarks(user["user_id"], bid)


@app.post("/api/user/bookmarks/{book_id}")
def add_bookmark(book_id: str, req: BookmarkRequest, user: dict = Depends(get_current_user)):
    bid = _parse_book_id(book_id)
    entry = db.add_user_bookmark(user["user_id"], bid, req.track, req.time, req.note)
    return entry


@app.delete("/api/user/bookmarks/{bookmark_id}")
def remove_bookmark(bookmark_id: int, user: dict = Depends(get_current_user)):
    if not db.remove_user_bookmark(user["user_id"], bookmark_id):
        raise HTTPException(404, "Bookmark not found")
    return {"ok": True}


# ── Analytics ───────────────────────────────────────────────────────────────


@app.get("/api/analytics")
def get_analytics(user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    all_books = db.get_all_books()
    hist = db.get_user_history(uid, limit=10000)

    # Count personal user books
    from .core import UserData

    user_books_count = len(UserData(uid).user_books_list())

    legacy_hist = _db_history_to_legacy(hist)
    done = [h for h in hist if h.get("action") == "done"]
    velocity = reading_velocity(legacy_hist)

    cat_counts = Counter(_normalize_category(b["category"]) for b in all_books)

    # Done by category
    book_by_id = {b["id"]: b for b in all_books}
    done_by_cat: dict[str, int] = Counter()
    for h in done:
        b = book_by_id.get(h.get("book_id"))
        if b:
            done_by_cat[_normalize_category(b["category"])] += 1

    # Monthly trend
    monthly: dict[str, int] = Counter()
    for h in done:
        ts = h.get("ts", "")
        if len(ts) >= 7:
            monthly[ts[:7]] += 1
    monthly_sorted = sorted(monthly.items())

    # Rating distribution (from both 'done' and standalone 'rated' entries)
    ratings: dict[int, int] = Counter()
    for h in hist:
        if h.get("action") in ("done", "rated"):
            r = h.get("rating", 0)
            if r:
                ratings[r] += 1

    # Heatmap
    day_counts: dict[str, int] = Counter()
    for h in hist:
        if h.get("action") in ("listen", "phone", "done", "inbox", "rated"):
            day = (h.get("ts") or "")[:10]
            if day:
                day_counts[day] += 1

    # Top authors
    author_counts: dict[str, int] = Counter()
    for b in all_books:
        if b.get("author"):
            author_counts[b["author"]] += 1
    top_authors = author_counts.most_common(10)

    return {
        "total_books": len(all_books) + user_books_count,
        "total_done": len(done),
        "category_counts": dict(cat_counts),
        "done_by_category": dict(done_by_cat),
        "monthly_trend": monthly_sorted,
        "rating_distribution": {str(k): v for k, v in ratings.items()},
        "velocity": velocity,
        "heatmap": dict(day_counts),
        "top_authors": [{"author": a, "count": c} for a, c in top_authors],
    }


@app.get("/api/analytics/achievements")
def get_achievements(user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    all_books = db.get_all_books()

    # Include personal user books in achievement counts
    from .core import UserData

    for ub in UserData(uid).user_books_list():
        all_books.append(
            {
                "id": f"ub:{uid}:{ub['slug']}",
                "folder": ub["slug"],
                "category": "Личные",
                "author": ub.get("author", ""),
                "title": ub.get("title", ""),
            }
        )
    hist = db.get_user_history(uid, limit=10000)
    notes_map = db.get_all_user_notes_map(uid)

    legacy_hist = _db_history_to_legacy(hist)
    legacy_books = _db_books_to_legacy(all_books)
    # Convert notes_map {book_id: note} to {normalized_title: note} for legacy compat
    book_by_id = {b["id"]: b for b in all_books}
    legacy_notes = {}
    for bid, note in notes_map.items():
        b = book_by_id.get(bid)
        if b:
            legacy_notes[normalize(b["title"])] = note

    return compute_achievements(legacy_hist, legacy_books, notes_data=legacy_notes)


# ── User Books (personal — still filesystem) ─────────────────────────────


@app.get("/api/user/books")
def get_user_books(user: dict = Depends(get_current_user)):
    from .core import UserData

    ud = UserData(user["user_id"])
    return ud.user_books_list()


@app.get("/api/user/books/{slug}")
def get_user_book(slug: str, user: dict = Depends(get_current_user)):
    from .core import UserData

    ud = UserData(user["user_id"])
    book = ud.user_book_get(slug)
    if not book:
        raise HTTPException(404, "Book not found")
    return book


@app.delete("/api/user/books/{slug}")
def delete_user_book(slug: str, user: dict = Depends(get_current_user)):
    from .core import UserData

    ud = UserData(user["user_id"])
    if not ud.user_book_delete(slug):
        raise HTTPException(404, "Book not found")
    return {"ok": True}


@app.get("/api/user/books/{slug}/tracks")
def get_user_book_tracks(slug: str, user: dict = Depends(get_current_user)):
    from .core import UserData

    ud = UserData(user["user_id"])
    book = ud.user_book_get(slug)
    if not book:
        raise HTTPException(404, "Book not found")
    book_dir = Path(book["path"])
    mp3s = sorted(book_dir.rglob("*.mp3"), key=lambda f: str(f))
    tracks = []
    for i, f in enumerate(mp3s):
        dur = 0.0
        try:
            from mutagen.mp3 import MP3

            audio = MP3(str(f))
            dur = audio.info.length
        except (OSError, Exception):
            pass
        tracks.append(
            {
                "index": i,
                "filename": f.name,
                "path": str(f.relative_to(book_dir)),
                "duration": round(dur, 2),
                "size_bytes": f.stat().st_size,
            }
        )
    return {"book_id": f"ub:{user['user_id']}:{slug}", "count": len(tracks), "tracks": tracks}


@app.get("/api/user/books/{slug}/cover")
def get_user_book_cover(slug: str, user: dict = Depends(get_current_user)):
    from .core import UserData

    ud = UserData(user["user_id"])
    book = ud.user_book_get(slug)
    if not book:
        raise HTTPException(404, "Book not found")
    cover = Path(book["path"]) / "cover.jpg"
    if not cover.exists():
        raise HTTPException(404, "No cover")
    return FileResponse(
        str(cover),
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=604800"},
    )


# ── Serve static files in production ────────────────────────────────────────

app_dist = Path(__file__).resolve().parent.parent / "app" / "dist"
if app_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(app_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = app_dist / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(app_dist / "index.html"))


# ── Run ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
