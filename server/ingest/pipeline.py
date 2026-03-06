"""Main ingestion pipeline: normalize -> upload -> register."""

import logging
import shutil
from pathlib import Path

from . import normalize as norm
from .chapters import detect_chapters_fallback, detect_chapters_from_file
from .dedup import make_fingerprint
from .extract_metadata import (
    build_metadata_json,
    build_tracks_json,
    extract_cover_from_mp3,
)

logger = logging.getLogger("leerio.ingest")


class IngestPipeline:
    """Orchestrates: normalize audio -> upload S3 -> register DB."""

    def __init__(
        self,
        work_dir: Path,
        title: str,
        author: str,
        reader: str = "",
        category: str = "",
        language: str = "ru",
        source: str = "manual",
        fast: bool = False,
    ):
        self.work_dir = work_dir
        self.title = title
        self.author = author
        self.reader = reader
        self.category = category
        self.language = language
        self.source = source
        self.fast = fast

    @staticmethod
    def s3_audio_key(book_id: int, filename: str) -> str:
        return f"books/{book_id}/audio/{filename}"

    @staticmethod
    def s3_metadata_key(book_id: int) -> str:
        return f"books/{book_id}/metadata.json"

    @staticmethod
    def s3_tracks_key(book_id: int) -> str:
        return f"books/{book_id}/tracks.json"

    @staticmethod
    def s3_chapters_key(book_id: int) -> str:
        return f"books/{book_id}/chapters.json"

    @staticmethod
    def s3_cover_key(book_id: int) -> str:
        return f"books/{book_id}/cover.jpg"

    def _normalize_single(self, src: Path, out: Path) -> None:
        norm.normalize_file(src, out, fast=self.fast, timeout=300)

    def collect_audio_files(self) -> list[Path]:
        """Find all audio files in work_dir, sorted."""
        exts = norm.AUDIO_EXTENSIONS
        files = [f for f in sorted(self.work_dir.iterdir()) if f.suffix.lower() in exts]
        return files

    def normalize_all(self, on_progress=None) -> list[Path]:
        """Normalize all audio files to MP3. Returns list of output paths."""
        audio_dir = self.work_dir / "normalized"
        audio_dir.mkdir(exist_ok=True)
        raw_files = self.collect_audio_files()
        results = []
        for i, src in enumerate(raw_files, 1):
            out_name = f"{i:02d}.mp3"
            out = audio_dir / out_name
            if norm.is_mp3(src) and self.fast:
                shutil.copy2(src, out)
            else:
                self._normalize_single(src, out)
            results.append(out)
            if on_progress:
                on_progress(i, len(raw_files), "normalizing")
        return results

    def run(self, job_id: int | None = None, on_progress=None) -> dict:
        """Execute full pipeline. Returns result dict."""
        from .. import db
        from ..core import make_slug
        from ..storage import upload_file_to_s3, upload_json_to_s3

        # 1. Normalize
        mp3_files = self.normalize_all(on_progress=on_progress)
        if not mp3_files:
            raise RuntimeError("No audio files found")

        # 2. Build metadata
        tracks_json = build_tracks_json(mp3_files)
        total_duration = sum(t["duration"] for t in tracks_json)
        duration_hours = round(total_duration / 3600, 2)

        # 3. Dedup check
        fingerprint = make_fingerprint(self.title, self.author, duration_hours)
        conn = db._get_conn()
        existing = conn.execute("SELECT id FROM books WHERE fingerprint = ?", (fingerprint,)).fetchone()
        conn.close()
        if existing:
            return {
                "status": "skipped",
                "reason": "duplicate",
                "existing_id": existing[0],
            }

        # 4. Chapters
        if not self.fast:
            chapters = detect_chapters_from_file(mp3_files[0])
            if not chapters:
                chapters = detect_chapters_fallback(tracks_json)
        else:
            chapters = detect_chapters_fallback(tracks_json)

        # 5. Cover
        cover_bytes = None
        cover_path = self.work_dir / "cover.jpg"
        if cover_path.exists():
            cover_bytes = cover_path.read_bytes()
        else:
            for f in mp3_files:
                cover_bytes = extract_cover_from_mp3(f)
                if cover_bytes:
                    break

        # 6. Metadata JSON
        metadata = build_metadata_json(
            title=self.title,
            author=self.author,
            reader=self.reader,
            category=self.category,
            language=self.language,
            source=self.source,
            duration_hours=duration_hours,
        )

        # 7. Register in DB
        slug = make_slug(self.title, self.author)
        size_mb = sum(f.stat().st_size for f in mp3_files) / (1024 * 1024)
        book_id = db.insert_book_for_ingest(
            slug=slug,
            title=self.title,
            author=self.author,
            reader=self.reader,
            category=self.category,
            language=self.language,
            source=self.source,
            fingerprint=fingerprint,
            mp3_count=len(mp3_files),
            duration_hours=duration_hours,
            size_mb=round(size_mb, 2),
            has_cover=cover_bytes is not None,
        )

        # 8. Upload to S3
        for i, f in enumerate(mp3_files, 1):
            s3_key = self.s3_audio_key(book_id, f.name)
            upload_file_to_s3(str(f), s3_key)
            if on_progress:
                on_progress(i, len(mp3_files), "uploading")

        upload_json_to_s3(metadata, self.s3_metadata_key(book_id))
        upload_json_to_s3(tracks_json, self.s3_tracks_key(book_id))
        upload_json_to_s3(chapters, self.s3_chapters_key(book_id))

        if cover_bytes:
            cover_tmp = self.work_dir / "_cover_upload.jpg"
            cover_tmp.write_bytes(cover_bytes)
            upload_file_to_s3(str(cover_tmp), self.s3_cover_key(book_id))

        # 9. Insert tracks in DB
        db.insert_tracks_for_ingest(book_id, tracks_json)

        return {
            "status": "done",
            "book_id": book_id,
            "tracks_processed": len(mp3_files),
            "duration_hours": duration_hours,
            "size_mb": round(size_mb, 2),
        }
