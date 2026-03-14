"""S3 layout migration -- move books from old to new layout."""

import logging
import os
import shutil
import tempfile
from pathlib import Path

from .. import db
from ..storage import upload_file_to_s3, upload_json_to_s3

logger = logging.getLogger("leerio.ingest")


def get_old_s3_files(s3_prefix: str) -> list[dict]:
    """List all files under old S3 prefix."""
    from ..storage import _get_client

    client = _get_client()
    if not client:
        return []

    bucket = os.environ.get("S3_BUCKET", "leerio-books")
    paginator = client.get_paginator("list_objects_v2")
    files = []
    for page in paginator.paginate(Bucket=bucket, Prefix=s3_prefix):
        for obj in page.get("Contents", []):
            files.append(
                {
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "name": obj["Key"].split("/")[-1],
                }
            )
    return files


def download_s3_file(s3_key: str, dest: Path) -> None:
    """Download a file from S3."""
    from ..storage import _get_client

    client = _get_client()
    bucket = os.environ.get("S3_BUCKET", "leerio-books")
    client.download_file(bucket, s3_key, str(dest))


def migrate_book(book_id: int, dry_run: bool = False) -> dict:
    """Migrate a single book from old to new S3 layout.

    Returns result dict with status and details.
    """
    conn = db._get_conn()
    book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()

    if not book:
        return {"status": "error", "reason": f"Book {book_id} not found"}

    book = dict(book)
    old_prefix = book["s3_prefix"]
    new_prefix = f"books/{book_id}"

    # Check if already migrated
    if old_prefix.startswith("books/"):
        return {"status": "skipped", "reason": "Already migrated"}

    # List old files
    old_files = get_old_s3_files(old_prefix)
    mp3_files = [f for f in old_files if f["name"].lower().endswith(".mp3")]
    mp3_files.sort(key=lambda f: f["name"])

    if not mp3_files:
        return {"status": "error", "reason": "No MP3 files found"}

    if dry_run:
        return {
            "status": "dry_run",
            "book_id": book_id,
            "title": book["title"],
            "old_prefix": old_prefix,
            "new_prefix": new_prefix,
            "track_count": len(mp3_files),
        }

    # Download, rename, re-upload
    work_dir = Path(tempfile.mkdtemp(prefix=f"leerio-migrate-{book_id}-"))
    try:
        tracks_json = []
        for i, f in enumerate(mp3_files, 1):
            new_name = f"{i:02d}.mp3"
            local_path = work_dir / new_name
            download_s3_file(f["key"], local_path)

            # Get duration (best effort)
            try:
                from .extract_metadata import extract_track_duration

                duration = extract_track_duration(local_path)
            except Exception:
                duration = 0

            # Upload to new location
            new_key = f"{new_prefix}/audio/{new_name}"
            upload_file_to_s3(str(local_path), new_key)
            tracks_json.append({"track": i, "file": new_name, "duration": duration})

        # Build and upload metadata
        total_duration = sum(t["duration"] for t in tracks_json)
        duration_hours = round(total_duration / 3600, 2) if total_duration else book.get("duration_hours", 0)

        metadata = {
            "version": 1,
            "title": book["title"],
            "author": book["author"],
            "reader": book.get("reader", ""),
            "category": book.get("category", ""),
            "language": book.get("language", "ru"),
            "source": "migrated",
            "duration_hours": duration_hours,
        }

        upload_json_to_s3(metadata, f"{new_prefix}/metadata.json")
        upload_json_to_s3(tracks_json, f"{new_prefix}/tracks.json")

        # Simple chapters (one per track)
        from .chapters import detect_chapters_fallback

        chapters = detect_chapters_fallback(tracks_json)
        upload_json_to_s3(chapters, f"{new_prefix}/chapters.json")

        # Handle cover
        cover_files = [f for f in old_files if f["name"].lower() in ("cover.jpg", "cover.png", "folder.jpg")]
        if cover_files:
            cover_local = work_dir / "cover.jpg"
            download_s3_file(cover_files[0]["key"], cover_local)
            upload_file_to_s3(str(cover_local), f"{new_prefix}/cover.jpg")

        # Update DB
        conn = db._get_conn()
        conn.execute(
            "UPDATE books SET s3_prefix = ? WHERE id = ?",
            (new_prefix, book_id),
        )
        # Update tracks
        for t in tracks_json:
            conn.execute(
                "UPDATE tracks SET s3_key = ? WHERE book_id = ? AND idx = ?",
                (f"{new_prefix}/audio/{t['file']}", book_id, t["track"]),
            )
        conn.commit()

        return {
            "status": "done",
            "book_id": book_id,
            "title": book["title"],
            "tracks_migrated": len(tracks_json),
            "duration_hours": duration_hours,
        }

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def migrate_all(dry_run: bool = False) -> list[dict]:
    """Migrate all books that haven't been migrated yet."""
    conn = db._get_conn()
    books = conn.execute("SELECT id FROM books WHERE s3_prefix NOT LIKE 'books/%' ORDER BY id").fetchall()

    results = []
    for book in books:
        result = migrate_book(book["id"], dry_run=dry_run)
        results.append(result)
        logger.info("Migrate book %d: %s", book["id"], result.get("status"))

    return results
