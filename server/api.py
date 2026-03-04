"""
server/api.py — FastAPI web server for the audiobook library.

Thin wrapper over server.core: serves JSON via REST API.

Run:
  uvicorn server.api:app --reload
"""

import base64
import json
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
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.requests import Request

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
    CACHE_PATH,
    CATEGORIES,
    FOLDER_TO_LABEL,
    LABEL_TO_FOLDER,
    LIST_TO_STATUS,
    STATUS_STYLE,
    Library,
    TrelloClient,
    UserData,
    best_card_match,
    compute_achievements,
    count_mp3,
    estimate_duration_hours,
    find_similar,
    fmt_duration,
    folder_size_mb,
    fuzzy_match,
    load_config,
    normalize,
    parse_folder_name,
    reading_velocity,
)
from .db import (
    add_allowed_email,
    create_or_update_user,
    init_db,
    is_email_allowed,
    list_allowed_emails,
    remove_allowed_email,
)

logging.basicConfig(
    level=getattr(logging, os.environ.get("LEERIO_LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("leerio")

# ── Helpers ─────────────────────────────────────────────────────────────────


def _book_id(path: Path) -> str:
    """Encode full path to URL-safe base64 (Cyrillic-safe)."""
    return base64.urlsafe_b64encode(str(path).encode("utf-8")).decode("ascii")


def _book_from_id(book_id: str) -> Path:
    """Decode book ID back to path."""
    return Path(base64.urlsafe_b64decode(book_id.encode("ascii")).decode("utf-8"))


def _enrich_book(
    b: dict,
    hist: list[dict] | None = None,
    progress_data: dict | None = None,
    tags_data: dict | None = None,
    notes_data: dict | None = None,
    ud: UserData | None = None,
) -> dict:
    """Convert internal book dict to JSON-serializable API response."""
    book_id = _book_id(b["path"])
    key = normalize(b["title"])

    if progress_data is not None:
        pct = (progress_data.get(key) or {}).get("pct", 0)
    elif ud:
        pct = ud.progress_get(b["title"])
    else:
        pct = 0

    if tags_data is not None:
        book_tags = tags_data.get(key, [])
    elif ud:
        book_tags = ud.tags_get(b["title"])
    else:
        book_tags = []

    if notes_data is not None:
        note = notes_data.get(key, "")
    elif ud:
        note = ud.note_get(b["title"])
    else:
        note = ""

    result = {
        "id": book_id,
        "folder": b["folder"],
        "category": b["category"],
        "author": b["author"],
        "title": b["title"],
        "reader": b["reader"] or "",
        "path": str(b["path"]),
        "progress": pct,
        "tags": book_tags,
        "note": note,
        "has_cover": (b["path"] / "cover.jpg").exists(),
    }

    if hist is not None:
        nf = normalize(b["folder"])
        nt = normalize(b["title"])
        for h in reversed(hist):
            if h["action"] == "done":
                hn = normalize(h["book"])
                if hn == nf or hn == nt:
                    result["rating"] = h.get("rating", 0)
                    break

    return result


def _card_to_dict(card: dict, lmap: dict, trello: TrelloClient | None) -> dict:
    """Convert Trello card to API dict."""
    list_name = lmap.get(card["idList"], "?")
    a, t, r = parse_folder_name(card["name"])
    category = trello.category(card) if trello else None
    return {
        "id": card["id"],
        "name": card["name"],
        "list": list_name,
        "status": LIST_TO_STATUS.get(list_name, list_name),
        "author": a,
        "title": t,
        "reader": r or "",
        "category": category or "",
        "labels": trello.label_names(card) if trello else [],
        "desc": card.get("desc", ""),
    }


# ── Pydantic models ────────────────────────────────────────────────────────


class MoveCardRequest(BaseModel):
    target: str
    rating: int = 0
    detail: str = ""


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
    books: list[str] = []
    description: str = ""


class CreateCardRequest(BaseModel):
    name: str
    list_name: str = "Прочесть"
    label: str | None = None
    desc: str = ""


class PlaybackPositionRequest(BaseModel):
    track_index: int
    position: float
    filename: str = ""


class SessionStartRequest(BaseModel):
    book: str


class GoogleAuthRequest(BaseModel):
    id_token: str


class BookStatusRequest(BaseModel):
    status: str


# ── App state ───────────────────────────────────────────────────────────────

lib = Library()
trello: TrelloClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global trello
    init_db()
    config = load_config()
    key = config.get("trello_api_key", "")
    tok = config.get("trello_token", "")
    bid = config.get("board_id", "62d4e11502252b7a4dc11d7f")

    if key and tok:
        t = TrelloClient(key, tok, bid)
        try:
            t.get_lists()
            t.get_cards()
            t.get_labels()
            t.save_cache()
            trello = t
            logger.info("Trello connected")
        except Exception as e:
            logger.warning("Trello API error: %s", e)
            if t.load_from_cache():
                trello = t
                logger.info("Trello loaded from cache")
            else:
                logger.warning("No Trello cache available")
    else:
        t = TrelloClient("", "", bid)
        if t.load_from_cache():
            trello = t
            logger.info("Trello loaded from cache (no API keys)")
        else:
            logger.info("Trello not configured")

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


# ── Helper to get trello data ──────────────────────────────────────────────


def _lmap() -> dict:
    if not trello:
        return {}
    return {l["id"]: l["name"] for l in trello.get_lists()}


def _cards_in(*names) -> list[dict]:
    if not trello:
        return []
    ids = {trello.list_id(n) for n in names}
    return [c for c in trello.get_cards() if c["idList"] in ids]


# ── Helper: get per-user data accessor ─────────────────────────────────────


def _user_data(user: dict) -> UserData:
    return UserData(user["user_id"])


# ── Auth endpoints ─────────────────────────────────────────────────────────


class AllowedEmailRequest(BaseModel):
    email: str


@app.post("/api/auth/google")
def auth_google(req: GoogleAuthRequest):
    info = verify_google_token(req.id_token)
    if not is_email_allowed(info["email"]):
        raise HTTPException(403, "Registration is not allowed for this email")
    user = create_or_update_user(info["email"], info["name"], info["picture"])
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
    return list_allowed_emails()


@app.post("/api/admin/allowed-emails")
def add_email(req: AllowedEmailRequest, user: dict = Depends(get_current_user)):
    require_admin(user)
    add_allowed_email(req.email, user["email"])
    return {"ok": True}


@app.delete("/api/admin/allowed-emails/{email}")
def delete_email(email: str, user: dict = Depends(get_current_user)):
    require_admin(user)
    removed = remove_allowed_email(email)
    if not removed:
        raise HTTPException(404, "Email not found")
    return {"ok": True}


# ── Config endpoint ─────────────────────────────────────────────────────────


@app.get("/api/config/constants")
def get_constants():
    return {
        "categories": CATEGORIES,
        "status_style": STATUS_STYLE,
        "action_styles": ACTION_STYLES,
        "action_labels": ACTION_LABELS,
        "list_to_status": LIST_TO_STATUS,
        "label_to_folder": LABEL_TO_FOLDER,
        "folder_to_label": FOLDER_TO_LABEL,
        "trello_connected": trello is not None,
        "book_statuses": BOOK_STATUSES,
    }


# ── Dashboard ───────────────────────────────────────────────────────────────


@app.get("/api/dashboard")
def get_dashboard(user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    books = lib.find_all_books()
    hist = ud.history_load()
    done = [h for h in hist if h["action"] == "done"]
    velocity = reading_velocity(hist)

    is_admin = user.get("role") == "admin"

    active_cards = []
    if is_admin:
        lmap = _lmap()
        if trello:
            for c in trello.get_cards():
                ln = lmap.get(c["idList"], "")
                if ln in ("В процессе", "В телефоне"):
                    cd = _card_to_dict(c, lmap, trello)
                    cd["progress"] = ud.progress_get(cd["title"])
                    active_cards.append(cd)
    else:
        # Non-admin: show books with status="reading"
        statuses = ud.book_status_load()
        for book_id, info in statuses.items():
            if info.get("status") == "reading":
                try:
                    path = _book_from_id(book_id)
                    if path.exists():
                        a, t, r = parse_folder_name(path.name)
                        b = {
                            "path": path,
                            "folder": path.name,
                            "category": path.parent.name,
                            "author": a,
                            "title": t,
                            "reader": r,
                        }
                        enriched = _enrich_book(b, hist, ud=ud)
                        enriched["list"] = "В процессе"
                        enriched["name"] = b["folder"]
                        active_cards.append(enriched)
                except Exception:
                    pass

    recent = []
    for h in reversed(hist[-8:]):
        recent.append(
            {
                "ts": h["ts"],
                "action": h["action"],
                "book": h["book"],
                "detail": h.get("detail", ""),
                "rating": h.get("rating", 0),
                "action_label": ACTION_LABELS.get(h["action"], h["action"]),
                "action_style": ACTION_STYLES.get(h["action"], "white"),
            }
        )

    day_counts: dict[str, int] = Counter()
    for h in hist:
        if h["action"] in ("listen", "phone", "done", "inbox"):
            day_counts[h["ts"][:10]] = day_counts.get(h["ts"][:10], 0) + 1

    quotes = ud.quotes_load()
    quote = random.choice(quotes) if quotes else None

    year = str(datetime.now().year)
    this_year_done = sum(1 for h in done if h["ts"].startswith(year))

    cat_counts = {}
    for b in books:
        cat_counts[b["category"]] = cat_counts.get(b["category"], 0) + 1

    return {
        "total_books": len(books),
        "total_done": len(done),
        "active_count": len(active_cards),
        "velocity": velocity,
        "active_books": active_cards,
        "recent": recent,
        "heatmap": dict(day_counts),
        "quote": quote,
        "this_year_done": this_year_done,
        "yearly_goal": 24,
        "category_counts": cat_counts,
    }


# ── Books ───────────────────────────────────────────────────────────────────


@app.get("/api/books")
def get_books(
    category: str | None = Query(None),
    search: str | None = Query(None),
    tag: str | None = Query(None),
    sort: str = Query("title"),
    user: dict = Depends(get_current_user),
):
    ud = _user_data(user)
    is_admin = user.get("role") == "admin"
    books = lib.find_all_books()
    hist = ud.history_load()
    pd = ud.progress_load()
    td = ud.tags_load()
    nd = ud.notes_load()
    book_statuses = ud.book_status_load()

    card_map: dict[str, tuple[dict, str]] = {}
    if is_admin and trello:
        lmap = _lmap()
        for c in trello.get_cards():
            _, ct, _ = parse_folder_name(c["name"])
            ln = lmap.get(c["idList"], "")
            card_map[normalize(c["name"])] = (c, ln)
            if ct:
                card_map[normalize(ct)] = (c, ln)

    result = []
    for b in books:
        if category and b["category"] != category:
            continue
        if search:
            q = search.lower()
            if q not in b["author"].lower() and q not in b["title"].lower() and q not in b["folder"].lower():
                continue

        enriched = _enrich_book(b, hist, progress_data=pd, tags_data=td, notes_data=nd)

        if tag and tag not in enriched["tags"]:
            continue

        # Attach book status for current user
        bs = book_statuses.get(enriched["id"])
        if bs:
            enriched["book_status"] = bs["status"]

        if is_admin and card_map:
            key = normalize(b["title"])
            fkey = normalize(b["folder"])
            match = card_map.get(key) or card_map.get(fkey)
            if match:
                card, ln = match
                enriched["status"] = ln
                enriched["card_id"] = card["id"]

        result.append(enriched)

    if sort == "title":
        result.sort(key=lambda x: x["title"].lower())
    elif sort == "author":
        result.sort(key=lambda x: (x["author"].lower(), x["title"].lower()))
    elif sort == "category":
        result.sort(key=lambda x: (x["category"], x["title"].lower()))
    elif sort == "progress":
        result.sort(key=lambda x: -x["progress"])
    elif sort == "rating":
        result.sort(key=lambda x: -(x.get("rating") or 0))

    return result


@app.get("/api/books/{book_id}")
def get_book(book_id: str, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    is_admin = user.get("role") == "admin"
    path = _book_from_id(book_id)
    if not path.exists():
        raise HTTPException(404, "Book not found")

    category = path.parent.name
    a, t, r = parse_folder_name(path.name)
    b = {"path": path, "folder": path.name, "category": category, "author": a, "title": t, "reader": r}

    hist = ud.history_load()
    enriched = _enrich_book(b, hist, ud=ud)

    enriched["size_mb"] = round(folder_size_mb(path), 1)
    enriched["mp3_count"] = count_mp3(path)

    dur = estimate_duration_hours(path)
    enriched["duration_hours"] = dur
    enriched["duration_fmt"] = fmt_duration(dur)

    # Attach user's book status
    bs = ud.book_status_get(book_id)
    if bs:
        enriched["book_status"] = bs["status"]

    if is_admin and trello:
        lmap = _lmap()
        card, score = best_card_match(a, t, trello.get_cards())
        if card and score > 0.5:
            ln = lmap.get(card["idList"], "")
            enriched["status"] = ln
            enriched["card_id"] = card["id"]

    timeline = []
    nf = normalize(path.name)
    nt = normalize(t)
    for h in hist:
        hn = normalize(h["book"])
        if hn == nf or hn == nt or (t and fuzzy_match(hn, nt) > 0.6):
            timeline.append(
                {
                    "ts": h["ts"],
                    "action": h["action"],
                    "detail": h.get("detail", ""),
                    "rating": h.get("rating", 0),
                    "action_label": ACTION_LABELS.get(h["action"], h["action"]),
                }
            )

    enriched["timeline"] = timeline
    return enriched


@app.get("/api/books/{book_id}/similar")
def get_similar(book_id: str, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    path = _book_from_id(book_id)
    if not path.exists():
        raise HTTPException(404, "Book not found")

    category = path.parent.name
    a, t, r = parse_folder_name(path.name)
    target = {"path": path, "folder": path.name, "category": category, "author": a, "title": t, "reader": r}

    books = lib.find_all_books()
    hist = ud.history_load()
    similar = find_similar(target, books, hist, top_n=6)

    return [{**_enrich_book(b, ud=ud), "score": round(score, 1)} for b, score in similar]


# ── Audio / Playback ──────────────────────────────────────────────────────


@app.get("/api/books/{book_id}/tracks")
def get_book_tracks(book_id: str):
    path = _book_from_id(book_id)
    if not path.exists():
        raise HTTPException(404, "Book not found")

    mp3s = sorted(path.rglob("*.mp3"), key=lambda f: str(f))
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
                "path": str(f.relative_to(path)),
                "duration": round(dur, 2),
                "size_bytes": f.stat().st_size,
            }
        )

    return {"book_id": book_id, "count": len(tracks), "tracks": tracks}


@app.get("/api/books/{book_id}/cover")
def get_book_cover(book_id: str):
    path = _book_from_id(book_id)
    if not path.exists():
        raise HTTPException(404, "Book not found")
    cover = path / "cover.jpg"
    if not cover.exists():
        raise HTTPException(404, "No cover")
    return FileResponse(str(cover), media_type="image/jpeg")


@app.get("/api/audio/{book_id}/{track_index}")
def stream_audio(book_id: str, track_index: int, request: Request):
    path = _book_from_id(book_id)
    if not path.exists():
        raise HTTPException(404, "Book not found")

    mp3s = sorted(path.rglob("*.mp3"), key=lambda f: str(f))
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
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
        },
    )


@app.get("/api/books/{book_id}/playback")
def get_playback(book_id: str, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    pos = ud.playback_get(book_id)
    if pos:
        return pos
    return {"track_index": 0, "position": 0, "filename": "", "updated": None}


@app.put("/api/books/{book_id}/playback")
def set_playback(book_id: str, req: PlaybackPositionRequest, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    ud.playback_set(book_id, req.track_index, req.position, req.filename)
    return {"ok": True}


# ── Trello ──────────────────────────────────────────────────────────────────


@app.get("/api/trello/status")
def get_trello_status(user: dict = Depends(get_current_user)):
    require_admin(user)
    if not trello:
        raise HTTPException(503, "Trello not connected")
    lmap = _lmap()
    cards = trello.get_cards()
    list_counts: dict[str, int] = {}
    for c in cards:
        ln = lmap.get(c["idList"], "?")
        list_counts[ln] = list_counts.get(ln, 0) + 1

    cache_ts = None
    cache_age_min = None
    if CACHE_PATH.exists():
        try:
            data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            cache_ts = data.get("ts")
            if cache_ts:
                dt = datetime.fromisoformat(cache_ts)
                cache_age_min = int((datetime.now() - dt).total_seconds() / 60)
        except Exception:
            pass

    return {
        "total_cards": len(cards),
        "list_counts": list_counts,
        "cache_ts": cache_ts,
        "cache_age_min": cache_age_min,
    }


@app.get("/api/trello/cards")
def get_trello_cards(list_name: str | None = Query(None), user: dict = Depends(get_current_user)):
    require_admin(user)
    if not trello:
        raise HTTPException(503, "Trello not connected")
    lmap = _lmap()
    cards = trello.get_cards()
    result = []
    for c in cards:
        cd = _card_to_dict(c, lmap, trello)
        if list_name and cd["list"] != list_name:
            continue
        ud = _user_data(user)
        cd["progress"] = ud.progress_get(cd["title"])
        result.append(cd)
    return result


@app.get("/api/trello/lists")
def get_trello_lists(user: dict = Depends(get_current_user)):
    require_admin(user)
    if not trello:
        raise HTTPException(503, "Trello not connected")
    return [{"id": l["id"], "name": l["name"]} for l in trello.get_lists()]


@app.post("/api/trello/cards/{card_id}/move")
def move_trello_card(card_id: str, req: MoveCardRequest, user: dict = Depends(get_current_user)):
    require_admin(user)
    if not trello:
        raise HTTPException(503, "Trello not connected")

    card = None
    for c in trello.get_cards():
        if c["id"] == card_id:
            card = c
            break
    if not card:
        raise HTTPException(404, "Card not found")

    lmap = _lmap()
    old_list = lmap.get(card["idList"], "?")

    action_map = {
        "В процессе": "listen",
        "В телефоне": "phone",
        "Прочитано": "done",
        "На Паузе": "pause",
        "Забраковано": "reject",
        "Прочесть": "move",
    }
    action = action_map.get(req.target, "move")
    detail = req.detail or f"{old_list} → {req.target}"

    ud = _user_data(user)
    trello.move_card(card_id, req.target)
    ud.history_add(action, card["name"], detail, req.rating)

    if req.target == "Прочитано":
        _, t, _ = parse_folder_name(card["name"])
        ud.progress_set(t, 100)

    trello.save_cache()

    return {"ok": True, "action": action, "from": old_list, "to": req.target}


@app.post("/api/trello/cards")
def create_trello_card(req: CreateCardRequest, user: dict = Depends(get_current_user)):
    require_admin(user)
    if not trello:
        raise HTTPException(503, "Trello not connected")
    try:
        ud = _user_data(user)
        card = trello.create_card(req.name, req.list_name, req.label, req.desc)
        trello.save_cache()
        ud.history_add("inbox", req.name, f"Создана карточка → {req.list_name}")
        return {"ok": True, "card_id": card["id"]}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/trello/sync")
def sync_trello(user: dict = Depends(get_current_user)):
    require_admin(user)
    if not trello:
        raise HTTPException(503, "Trello not connected")
    try:
        trello.reload()
        trello.get_lists()
        trello.get_cards()
        trello.get_labels()
        trello.save_cache()

        lmap = _lmap()
        rows = []
        for c in trello.get_cards():
            ln = lmap.get(c["idList"], "?")
            a, t, r = parse_folder_name(c["name"])
            rows.append(
                {
                    "Автор": a,
                    "Название": t,
                    "Чтец": r or "",
                    "Категория": trello.category(c) or "",
                    "Статус": LIST_TO_STATUS.get(ln, ln),
                }
            )
        rows.sort(key=lambda r: (r["Категория"], r["Автор"].lower(), r["Название"].lower()))
        lib.save_tracker(rows)

        lmap = _lmap()
        list_counts: dict[str, int] = {}
        for c in trello.get_cards():
            ln = lmap.get(c["idList"], "?")
            list_counts[ln] = list_counts.get(ln, 0) + 1

        return {
            "ok": True,
            "cards": len(trello.get_cards()),
            "list_counts": list_counts,
            "synced_at": datetime.now().isoformat(timespec="seconds"),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


# ── History ─────────────────────────────────────────────────────────────────


@app.get("/api/history")
def get_history(
    action: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(100),
    user: dict = Depends(get_current_user),
):
    ud = _user_data(user)
    hist = ud.history_load()
    result = []
    for h in reversed(hist):
        if action and h["action"] != action:
            continue
        if search and search.lower() not in h["book"].lower():
            continue
        result.append(
            {
                "ts": h["ts"],
                "action": h["action"],
                "book": h["book"],
                "detail": h.get("detail", ""),
                "rating": h.get("rating", 0),
                "action_label": ACTION_LABELS.get(h["action"], h["action"]),
                "action_style": ACTION_STYLES.get(h["action"], "white"),
            }
        )
        if len(result) >= limit:
            break
    return result


# ── Notes ───────────────────────────────────────────────────────────────────


@app.get("/api/notes/{title}")
def get_note(title: str, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    return {"title": title, "text": ud.note_get(title)}


@app.put("/api/notes/{title}")
def set_note(title: str, req: NoteRequest, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    ud.note_set(title, req.text)
    return {"ok": True}


@app.delete("/api/notes/{title}")
def delete_note(title: str, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    ud.note_set(title, "")
    return {"ok": True}


# ── Tags ────────────────────────────────────────────────────────────────────


@app.get("/api/tags")
def get_tags_for_title(title: str = Query(...), user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    return ud.tags_get(title)


@app.get("/api/tags/all")
def get_all_tags(user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    return ud.tags_all()


@app.put("/api/tags/{title}")
def set_tags_for_title(title: str, req: TagsRequest, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    ud.tags_set(title, req.tags)
    return {"ok": True}


# ── Progress ────────────────────────────────────────────────────────────────


@app.get("/api/progress")
def get_all_progress(user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    return ud.progress_load()


@app.put("/api/progress/{title}")
def set_progress_for_title(title: str, req: ProgressRequest, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    ud.progress_set(title, req.pct, req.note)
    return {"ok": True}


# ── Quotes ──────────────────────────────────────────────────────────────────


@app.get("/api/quotes")
def get_quotes(user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    return ud.quotes_load()


@app.post("/api/quotes")
def add_quote(req: QuoteRequest, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    ud.quotes_add(req.text, req.book, req.author)
    return {"ok": True}


@app.delete("/api/quotes/{idx}")
def delete_quote(idx: int, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    data = ud.quotes_load()
    if 0 <= idx < len(data):
        data.pop(idx)
        ud.quotes_save(data)
        return {"ok": True}
    raise HTTPException(404, "Quote not found")


# ── Collections ─────────────────────────────────────────────────────────────


@app.get("/api/collections")
def get_collections(user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    return ud.collections_load()


@app.post("/api/collections")
def create_collection(req: CollectionRequest, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    data = ud.collections_load()
    data.append(
        {
            "name": req.name,
            "books": req.books,
            "description": req.description,
            "created": datetime.now().isoformat(timespec="seconds"),
        }
    )
    ud.collections_save(data)
    return {"ok": True}


@app.put("/api/collections/{idx}")
def update_collection(idx: int, req: CollectionRequest, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    data = ud.collections_load()
    if 0 <= idx < len(data):
        data[idx]["name"] = req.name
        data[idx]["books"] = req.books
        data[idx]["description"] = req.description
        ud.collections_save(data)
        return {"ok": True}
    raise HTTPException(404, "Collection not found")


@app.delete("/api/collections/{idx}")
def delete_collection(idx: int, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    data = ud.collections_load()
    if 0 <= idx < len(data):
        data.pop(idx)
        ud.collections_save(data)
        return {"ok": True}
    raise HTTPException(404, "Collection not found")


# ── Sessions ────────────────────────────────────────────────────────────────


@app.get("/api/sessions/stats")
def get_session_stats(days: int = Query(7), user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    return ud.session_stats(days)


@app.post("/api/sessions/start")
def start_session(req: SessionStartRequest, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    entry = ud.session_start(req.book)
    return entry


@app.post("/api/sessions/stop")
def stop_session(req: SessionStartRequest, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    minutes = ud.session_stop(req.book)
    return {"minutes": minutes}


# ── Book Status (per-user simple status) ───────────────────────────────────


@app.get("/api/user/book-status")
def get_all_book_statuses(user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    return ud.book_status_load()


@app.get("/api/user/book-status/{book_id}")
def get_book_status(book_id: str, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    status = ud.book_status_get(book_id)
    return status or {"status": None}


@app.put("/api/user/book-status/{book_id}")
def set_book_status(book_id: str, req: BookStatusRequest, user: dict = Depends(get_current_user)):
    if req.status not in BOOK_STATUSES:
        raise HTTPException(400, f"Invalid status. Must be one of: {BOOK_STATUSES}")
    ud = _user_data(user)
    ud.book_status_set(book_id, req.status)

    # Log to user's history
    status_labels = {
        "want_to_read": "Хочу прочесть",
        "reading": "Слушаю",
        "paused": "На паузе",
        "done": "Прослушано",
        "rejected": "Забраковано",
    }
    action_map = {"reading": "listen", "paused": "pause", "done": "done", "rejected": "reject", "want_to_read": "inbox"}
    path = _book_from_id(book_id)
    book_name = path.name if path.exists() else book_id
    ud.history_add(action_map.get(req.status, "move"), book_name, status_labels.get(req.status, req.status))

    if req.status == "done":
        a, t, r = parse_folder_name(path.name) if path.exists() else ("", "", "")
        if t:
            ud.progress_set(t, 100)

    return {"ok": True}


@app.delete("/api/user/book-status/{book_id}")
def remove_book_status(book_id: str, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    ud.book_status_remove(book_id)
    return {"ok": True}


# ── Analytics ───────────────────────────────────────────────────────────────


@app.get("/api/analytics")
def get_analytics(user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    books = lib.find_all_books()
    hist = ud.history_load()
    done = [h for h in hist if h["action"] == "done"]
    velocity = reading_velocity(hist)

    cat_counts = Counter()
    for b in books:
        cat_counts[b["category"]] += 1

    done_by_cat = Counter()
    book_by_norm = {}
    for b in books:
        book_by_norm[normalize(b["folder"])] = b
        book_by_norm[normalize(b["title"])] = b
    for h in done:
        b = book_by_norm.get(normalize(h["book"]))
        if b:
            done_by_cat[b["category"]] += 1

    monthly = Counter()
    for h in done:
        monthly[h["ts"][:7]] += 1
    monthly_sorted = sorted(monthly.items())

    ratings = Counter()
    for h in done:
        r = h.get("rating", 0)
        if r:
            ratings[r] += 1

    day_counts: dict[str, int] = Counter()
    for h in hist:
        if h["action"] in ("listen", "phone", "done", "inbox"):
            day_counts[h["ts"][:10]] += 1

    author_counts = Counter()
    for b in books:
        if b["author"]:
            author_counts[b["author"]] += 1
    top_authors = author_counts.most_common(10)

    return {
        "total_books": len(books),
        "total_done": len(done),
        "category_counts": dict(cat_counts),
        "done_by_category": dict(done_by_cat),
        "monthly_trend": monthly_sorted,
        "rating_distribution": dict(ratings),
        "velocity": velocity,
        "heatmap": dict(day_counts),
        "top_authors": [{"author": a, "count": c} for a, c in top_authors],
    }


@app.get("/api/analytics/achievements")
def get_achievements(user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    books = lib.find_all_books()
    hist = ud.history_load()
    return compute_achievements(hist, books, notes_data=ud.notes_load())


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
