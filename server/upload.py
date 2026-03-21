"""
server/upload.py — User book upload API.

Handles personal audiobook uploads (MP3 files) with metadata.
"""

import io
import logging
import re
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .auth import get_current_user
from .constants import (
    FREE_BOOK_LIMIT,
    MAX_COVER_SIZE,
    MAX_UPLOAD_SIZE,
    VALID_AUDIO_EXTENSIONS,
    VALID_AUDIO_HEADERS,
    VALID_IMAGE_HEADERS,
)
from .core import UserData, count_mp3, estimate_duration_hours, folder_size_mb, make_slug

logger = logging.getLogger("leerio.upload")


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

    # Extract audio from ZIP files, validate all others
    audio_files: list[tuple[str, bytes]] = []  # (filename, content)
    for f in files:
        if not f.filename:
            raise HTTPException(400, "Missing filename")
        ext = "." + f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""

        if ext == ".zip":
            # Extract audio files from ZIP
            zip_data = await f.read(MAX_UPLOAD_SIZE + 1)
            if len(zip_data) > MAX_UPLOAD_SIZE:
                raise HTTPException(413, "ZIP too large (max 500 MB)")
            try:
                with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                    for info in sorted(zf.infolist(), key=lambda i: i.filename):
                        if info.is_dir():
                            continue
                        name = Path(info.filename).name
                        zext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
                        if zext in VALID_AUDIO_EXTENSIONS:
                            audio_files.append((name, zf.read(info)))
            except zipfile.BadZipFile:
                raise HTTPException(400, f"Invalid ZIP file: {f.filename}")
        elif ext in VALID_AUDIO_EXTENSIONS:
            header = await f.read(12)
            await f.seek(0)
            if not any(header[offset:].startswith(h) for h in VALID_AUDIO_HEADERS for offset in (0, 4)):
                raise HTTPException(400, f"Invalid audio file: {f.filename}")
            content = await f.read(MAX_UPLOAD_SIZE + 1)
            if len(content) > MAX_UPLOAD_SIZE:
                raise HTTPException(413, "File too large (max 500 MB)")
            audio_files.append((_sanitize_filename(f.filename or "track.mp3"), content))
        else:
            raise HTTPException(400, f"Unsupported format: {f.filename}. Allowed: MP3, M4A, M4B, OGG, FLAC, WAV, ZIP")

    if not audio_files:
        raise HTTPException(400, "No audio files found")

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

    # Save audio files
    for i, (name, content) in enumerate(audio_files, 1):
        safe_name = _sanitize_filename(name)
        filename = f"{i:02d}. {safe_name}"
        file_path = book_dir / filename
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


@router.post("/cloud-sync")
async def cloud_sync_book(
    title: str = Form(...),
    author: str = Form(""),
    files: list[UploadFile] = File(...),
    cover: UploadFile | None = File(None),
    user: dict = Depends(get_current_user),
):
    """Upload a local book to cloud for sync. Premium only, no free-tier limit."""
    if user.get("plan", "free") != "premium":
        raise HTTPException(403, {"error": "premium_required"})

    ud = _user_data(user)

    # Same validation as upload_book but without plan limit check
    audio_files: list[tuple[str, bytes]] = []
    for f in files:
        if not f.filename:
            raise HTTPException(400, "Missing filename")
        ext = "." + f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""

        if ext == ".zip":
            zip_data = await f.read(MAX_UPLOAD_SIZE + 1)
            if len(zip_data) > MAX_UPLOAD_SIZE:
                raise HTTPException(413, "ZIP too large (max 500 MB)")
            try:
                with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                    for info in sorted(zf.infolist(), key=lambda i: i.filename):
                        if info.is_dir():
                            continue
                        name = Path(info.filename).name
                        zext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
                        if zext in VALID_AUDIO_EXTENSIONS:
                            audio_files.append((name, zf.read(info)))
            except zipfile.BadZipFile:
                raise HTTPException(400, f"Invalid ZIP file: {f.filename}")
        elif ext in VALID_AUDIO_EXTENSIONS:
            header = await f.read(12)
            await f.seek(0)
            if not any(header[offset:].startswith(h) for h in VALID_AUDIO_HEADERS for offset in (0, 4)):
                raise HTTPException(400, f"Invalid audio file: {f.filename}")
            content = await f.read(MAX_UPLOAD_SIZE + 1)
            if len(content) > MAX_UPLOAD_SIZE:
                raise HTTPException(413, "File too large (max 500 MB)")
            audio_files.append((_sanitize_filename(f.filename or "track.mp3"), content))
        else:
            raise HTTPException(400, f"Unsupported format: {f.filename}")

    if not audio_files:
        raise HTTPException(400, "No audio files found")

    slug = make_slug(title, author)

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

    book_dir = ud.user_book_create(slug, title, author, "", source="cloud-sync")

    for i, (name, content) in enumerate(audio_files, 1):
        safe_name = _sanitize_filename(name)
        filename = f"{i:02d}. {safe_name}"
        file_path = book_dir / filename
        file_path.write_bytes(content)

    if cover and cover.filename:
        cover_data = await cover.read(MAX_COVER_SIZE + 1)
        if len(cover_data) > MAX_COVER_SIZE:
            logger.warning("Cover too large (%d bytes), skipping", len(cover_data))
        elif cover_data and any(cover_data.startswith(h) for h in VALID_IMAGE_HEADERS):
            (book_dir / "cover.jpg").write_bytes(cover_data)

    book_id = f"ub:{user['user_id']}:{slug}"
    logger.info("Cloud-sync book uploaded: %s by user %s", book_id, user["user_id"])

    return {
        "id": book_id,
        "slug": slug,
        "title": title,
        "author": author,
        "source": "cloud-sync",
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
    audio_exts = {".mp3", ".m4a", ".m4b", ".ogg", ".opus", ".flac", ".wav"}
    audio_files = sorted(
        (f for f in book_dir.rglob("*") if f.suffix.lower() in audio_exts),
        key=lambda f: str(f),
    )
    tracks = []
    for i, f in enumerate(audio_files):
        dur = 0.0
        try:
            from mutagen import File as MutagenFile

            audio = MutagenFile(str(f))
            if audio and audio.info:
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
