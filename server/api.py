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

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.requests import Request

from . import db
from .auth import (
    clear_auth_cookie,
    get_current_user,
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
from .storage import get_presigned_url, get_s3_object
from .tts_api import router as tts_router
from .upload import router as upload_router

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
    if user and uid != user["user_id"]:
        return None
    book_dir = (
        Path(os.environ.get("LEERIO_DATA", str(Path(__file__).resolve().parent.parent / "data")))
        / "users"
        / uid
        / "books"
        / slug
    )
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
    rating: int = 0,
) -> dict:
    """Convert a DB book row to the API response shape."""
    book_id = b["id"]
    pct = (progress_map or {}).get(book_id, {}).get("pct", 0) if progress_map else 0
    tags = (tags_map or {}).get(book_id, []) if tags_map else []
    note = (notes_map or {}).get(book_id, "") if notes_map else ""

    cat_name = _normalize_category(b["category"])
    cat_info = db.get_category_by_name(cat_name)

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


# ── App lifecycle ──────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── Include routers ──────────────────────────────────────────────────────────
app.include_router(upload_router)
app.include_router(tts_router)
app.include_router(ingest_router)


# ── Auth endpoints ─────────────────────────────────────────────────────────


@app.post("/api/auth/google")
def auth_google(req: GoogleAuthRequest):
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
def auth_login(req: LoginRequest):
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
    }


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


# ── Config endpoint ─────────────────────────────────────────────────────────


@app.get("/api/config/constants")
def get_constants():
    return {
        "categories": db.get_all_categories(),
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
    all_books = db.get_all_books()
    book_by_id = {b["id"]: b for b in all_books}

    # Count personal user books too
    from .core import UserData

    ud = UserData(uid)
    user_books_count = len(ud.user_books_list())

    hist = db.get_user_history(uid, limit=500)
    statuses = db.get_all_user_book_statuses(uid)
    progress = db.get_all_user_progress(uid)
    quotes = db.get_user_quotes(uid)

    # Active books (reading)
    active_cards = []
    for book_id, info in statuses.items():
        if info["status"] == "reading" and book_id in book_by_id:
            b = book_by_id[book_id]
            pct = progress.get(book_id, {}).get("pct", 0)
            active_cards.append(
                {
                    "id": str(book_id),
                    "folder": b["folder"],
                    "category": b["category"],
                    "author": b["author"],
                    "title": b["title"],
                    "reader": b.get("reader", ""),
                    "progress": pct,
                    "has_cover": bool(b.get("has_cover")),
                    "list": "В процессе",
                    "name": b["folder"],
                }
            )

    # Recent activity — resolve real title from books table
    recent = []
    for h in hist[:8]:
        bid = h.get("book_id")
        book_title = book_by_id[bid]["title"] if bid and bid in book_by_id else h.get("book_title", "")
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

    done = [h for h in hist if h.get("action") == "done"]
    quote = random.choice(quotes) if quotes else None
    year = str(datetime.now().year)
    this_year_done = sum(1 for h in done if (h.get("ts") or "").startswith(year))

    cat_counts = Counter(_normalize_category(b["category"]) for b in all_books)

    return {
        "total_books": len(all_books) + user_books_count,
        "total_done": len(done),
        "active_count": len(active_cards),
        "active_books": active_cards,
        "now_playing": None,
        "recent": recent,
        "heatmap": dict(day_counts),
        "quote": quote,
        "this_year_done": this_year_done,
        "yearly_goal": 24,
        "category_counts": dict(cat_counts),
    }


# ── Book Shelves (category carousels for home page) ────────────────────────


@app.get("/api/books/shelves")
def get_book_shelves(user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    all_books = db.get_all_books()
    statuses = db.get_all_user_book_statuses(uid)
    progress = db.get_all_user_progress(uid)

    # Group by category, pick up to 12 per category (random)
    by_cat: dict[str, list[dict]] = {}
    for b in all_books:
        cat = b.get("category", "")
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(b)

    shelves = []
    for cat in sorted(by_cat.keys()):
        books = by_cat[cat]
        sample = random.sample(books, min(12, len(books)))
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


# ── Books ───────────────────────────────────────────────────────────────────


@app.get("/api/books")
def get_books(
    category: str | None = Query(None),
    search: str | None = Query(None),
    tag: str | None = Query(None),
    sort: str = Query("title"),
    user: dict = Depends(get_current_user),
):
    uid = user["user_id"]
    books = db.search_books(category=category, search=search, sort=sort)
    statuses = db.get_all_user_book_statuses(uid)
    progress = db.get_all_user_progress(uid)
    tags_map = db.get_all_user_tags_map(uid)
    notes_map = db.get_all_user_notes_map(uid)

    result = []
    for b in books:
        enriched = _enrich_catalog_book(
            b,
            progress_map=progress,
            tags_map=tags_map,
            notes_map=notes_map,
            statuses_map=statuses,
        )
        if tag and tag not in enriched["tags"]:
            continue
        result.append(enriched)

    # Add personal user books
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

    return result


@app.get("/api/books/{book_id}")
def get_book(book_id: str, user: dict = Depends(get_current_user)):
    uid = user["user_id"]

    # Handle user book IDs
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

    bid = _parse_book_id(book_id)
    b = db.get_book_by_id(bid)
    if not b:
        raise HTTPException(404, "Book not found")

    tags = db.get_user_tags(uid, bid)
    note = db.get_user_note(uid, bid)
    pct = db.get_user_progress(uid, bid)
    rating = db.get_user_rating(uid, bid)
    status = db.get_user_book_status(uid, bid)

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

    # Timeline from history
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

    return enriched


@app.get("/api/books/{book_id}/similar")
def get_similar(book_id: str, user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    bid = _parse_book_id(book_id)
    b = db.get_book_by_id(bid)
    if not b:
        raise HTTPException(404, "Book not found")

    all_books = db.get_all_books()
    hist = db.get_user_history(uid, limit=500)

    target = {
        "path": _book_path(b),
        "folder": b["folder"],
        "category": b["category"],
        "author": b["author"],
        "title": b["title"],
        "reader": b.get("reader", ""),
    }
    legacy_books = _db_books_to_legacy(all_books)
    legacy_hist = _db_history_to_legacy(hist)
    similar = find_similar(target, legacy_books, legacy_hist, top_n=6)

    # Map similar results back to DB books for enrichment
    folder_to_db = {bk["folder"]: bk for bk in all_books}
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
def get_book_tracks(book_id: str):
    # User books
    ub_path = _resolve_user_book_path(book_id)
    if ub_path:
        mp3s = sorted(ub_path.rglob("*.mp3"), key=lambda f: str(f))
        tracks = []
        for i, f in enumerate(mp3s):
            dur = 0.0
            try:
                from mutagen.mp3 import MP3

                audio = MP3(str(f))
                dur = audio.info.length
            except Exception:
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


@app.get("/api/books/{book_id}/cover")
def get_book_cover(book_id: str):
    # User books
    ub_path = _resolve_user_book_path(book_id)
    if ub_path:
        cover = ub_path / "cover.jpg"
        if not cover.exists():
            raise HTTPException(404, "No cover")
        return FileResponse(str(cover), media_type="image/jpeg")

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
            return FileResponse(str(cover), media_type=f"image/{ext}")

    # Fallback to S3 — redirect to presigned URL
    s3_prefix = b.get("s3_prefix", "")
    if s3_prefix and b.get("has_cover"):
        url = get_presigned_url(f"{s3_prefix}/cover.jpg", expires=86400)
        if url:
            return RedirectResponse(url)

    raise HTTPException(404, "No cover")


@app.get("/api/audio/{book_id}/{track_index}")
def stream_audio(book_id: str, track_index: int, request: Request):
    # User books — always filesystem
    ub_path = _resolve_user_book_path(book_id)
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
                s3_resp["body"].iter_chunks(chunk_size=64 * 1024),
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


# ── Bookmarks ──────────────────────────────────────────────────────────────


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

    # Rating distribution
    ratings: dict[int, int] = Counter()
    for h in done:
        r = h.get("rating", 0)
        if r:
            ratings[r] += 1

    # Heatmap
    day_counts: dict[str, int] = Counter()
    for h in hist:
        if h.get("action") in ("listen", "phone", "done", "inbox"):
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
        except Exception:
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
    return FileResponse(str(cover), media_type="image/jpeg")


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
