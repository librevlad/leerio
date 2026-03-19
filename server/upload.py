"""
server/upload.py — User book upload API.

Handles personal audiobook uploads (MP3 files) with metadata.
"""

import logging
import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .auth import get_current_user
from .core import UserData, count_mp3, estimate_duration_hours, folder_size_mb, make_slug

logger = logging.getLogger("leerio.upload")

MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB (matches nginx)
MAX_COVER_SIZE = 50 * 1024 * 1024  # 50 MB
FREE_BOOK_LIMIT = int(os.environ.get("FREE_BOOK_LIMIT", "10"))
VALID_IMAGE_HEADERS = [b"\xff\xd8\xff", b"\x89PNG"]
VALID_MP3_HEADERS = [b"\xff\xfb", b"\xff\xfa", b"\xff\xf3", b"\xff\xf2", b"ID3"]


def _sanitize_filename(name: str) -> str:
    """Strip path separators, traversal, and control chars from filename."""
    name = Path(name).name  # strip directory components
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)  # replace unsafe chars
    return name or "track.mp3"


router = APIRouter(prefix="/api/user/books", tags=["user-books"])


def _user_data(user: dict) -> UserData:
    return UserData(user["user_id"])


@router.get("")
def list_user_books(user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    books = ud.user_books_list()
    result = []
    for b in books:
        book_dir = Path(b["path"])
        book_id = f"ub:{user['user_id']}:{b['slug']}"
        result.append(
            {
                "id": book_id,
                "slug": b["slug"],
                "title": b.get("title", ""),
                "author": b.get("author", ""),
                "reader": b.get("reader", ""),
                "source": b.get("source", "upload"),
                "created_at": b.get("created_at", ""),
                "is_personal": True,
                "has_cover": (book_dir / "cover.jpg").exists(),
                "mp3_count": count_mp3(book_dir),
            }
        )
    return result


@router.post("")
async def upload_book(
    title: str = Form(...),
    author: str = Form(""),
    reader: str = Form(""),
    files: list[UploadFile] = File(...),
    cover: UploadFile | None = File(None),
    user: dict = Depends(get_current_user),
):
    ud = _user_data(user)

    # Check free plan book limit
    if user.get("plan", "free") == "free":
        current_count = len(ud.user_books_list())
        if current_count >= FREE_BOOK_LIMIT:
            raise HTTPException(
                403,
                {"error": "limit_reached", "limit": FREE_BOOK_LIMIT, "count": current_count},
            )

    # Validate files are MP3 (extension + magic bytes)
    for f in files:
        if not f.filename or not f.filename.lower().endswith(".mp3"):
            raise HTTPException(400, f"Only MP3 files allowed, got: {f.filename}")
        header = await f.read(4)
        await f.seek(0)
        if not any(header.startswith(h) for h in VALID_MP3_HEADERS):
            raise HTTPException(400, f"Invalid MP3 file: {f.filename}")

    slug = make_slug(title, author)

    # Ensure unique slug (atomic mkdir to avoid TOCTOU race)
    for attempt in range(100):
        candidate = slug if attempt == 0 else f"{slug}-{attempt + 1}"
        try:
            (ud.books_dir / candidate).mkdir(parents=True, exist_ok=False)
            slug = candidate
            break
        except FileExistsError:
            continue
    else:
        raise HTTPException(409, "Could not create unique book directory")

    book_dir = ud.user_book_create(slug, title, author, reader, source="upload")

    # Save MP3 files
    for i, f in enumerate(files, 1):
        safe_name = _sanitize_filename(f.filename or "track.mp3")
        filename = f"{i:02d}. {safe_name}"
        file_path = book_dir / filename
        content = await f.read(MAX_UPLOAD_SIZE + 1)
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(413, "File too large (max 500 MB)")
        file_path.write_bytes(content)
        logger.info("Saved track: %s (%d bytes)", filename, len(content))

    # Save cover if provided (validate type + size)
    if cover and cover.filename:
        cover_data = await cover.read(MAX_COVER_SIZE + 1)
        if len(cover_data) > MAX_COVER_SIZE:
            logger.warning("Cover too large (%d bytes), skipping", len(cover_data))
        elif cover_data and any(cover_data.startswith(h) for h in VALID_IMAGE_HEADERS):
            (book_dir / "cover.jpg").write_bytes(cover_data)

    book_id = f"ub:{user['user_id']}:{slug}"
    logger.info("Book uploaded: %s by user %s", book_id, user["user_id"])

    return {
        "id": book_id,
        "slug": slug,
        "title": title,
        "author": author,
        "reader": reader,
        "source": "upload",
        "is_personal": True,
    }


@router.get("/{slug}")
def get_user_book(slug: str, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    meta = ud.user_book_get(slug)
    if not meta:
        raise HTTPException(404, "Book not found")

    book_dir = Path(meta["path"])
    book_id = f"ub:{user['user_id']}:{slug}"

    dur = estimate_duration_hours(book_dir)

    return {
        "id": book_id,
        "slug": slug,
        "title": meta.get("title", ""),
        "author": meta.get("author", ""),
        "reader": meta.get("reader", ""),
        "source": meta.get("source", "upload"),
        "created_at": meta.get("created_at", ""),
        "is_personal": True,
        "has_cover": (book_dir / "cover.jpg").exists(),
        "mp3_count": count_mp3(book_dir),
        "size_mb": round(folder_size_mb(book_dir), 1),
        "duration_hours": dur,
    }


@router.delete("/{slug}")
def delete_user_book(slug: str, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    if not ud.user_book_delete(slug):
        raise HTTPException(404, "Book not found")
    logger.info("Book deleted: %s by user %s", slug, user["user_id"])
    return {"ok": True}


@router.get("/{slug}/tracks")
def get_user_book_tracks(slug: str, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    meta = ud.user_book_get(slug)
    if not meta:
        raise HTTPException(404, "Book not found")

    book_dir = Path(meta["path"])
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

    book_id = f"ub:{user['user_id']}:{slug}"
    return {"book_id": book_id, "count": len(tracks), "tracks": tracks}


@router.get("/{slug}/cover")
def get_user_book_cover(slug: str, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    meta = ud.user_book_get(slug)
    if not meta:
        raise HTTPException(404, "Book not found")

    cover = Path(meta["path"]) / "cover.jpg"
    if not cover.exists():
        raise HTTPException(404, "No cover")
    return FileResponse(str(cover), media_type="image/jpeg")
