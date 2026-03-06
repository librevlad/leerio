# Content Ingestion Pipeline — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a content ingestion pipeline that normalizes audio quality, detects chapters, extracts metadata, and stores books in a clean S3 layout. Support batch normalization of existing 194 books and ingestion from external sources.

**Architecture:** Inline async worker inside FastAPI (same pattern as TTS jobs). SQLite job queue with watchdog. ffmpeg for audio normalization. New S3 layout: `books/{id}/audio/*.mp3` + metadata/tracks/chapters JSON files.

**Tech Stack:** Python 3.12, FastAPI, asyncio, ffmpeg (subprocess), mutagen, boto3, SQLite

---

## Phase 1: Foundation (DB, Jobs, Normalize)

### Task 1: Database Schema — Add new columns and ingestion_jobs table

**Files:**
- Modify: `server/db.py:74-104` (books table schema)
- Modify: `server/db.py:36-46` (init_db function)
- Test: `server/tests/test_ingest/test_jobs.py`

**Step 1: Write the failing test**

Create `server/tests/test_ingest/__init__.py` (empty) and `server/tests/test_ingest/test_jobs.py`:

```python
"""Tests for ingestion job queue."""
import sqlite3
from server import db


def test_books_table_has_language_column(tmp_data_dir):
    db.init_db()
    conn = db._get_conn()
    row = conn.execute("PRAGMA table_info(books)").fetchall()
    columns = [r[1] for r in row]
    assert "language" in columns
    assert "source" in columns
    assert "external_id" in columns
    assert "fingerprint" in columns
    conn.close()


def test_ingestion_jobs_table_exists(tmp_data_dir):
    db.init_db()
    conn = db._get_conn()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ingestion_jobs'"
    ).fetchone()
    assert row is not None
    conn.close()


def test_ingestion_jobs_columns(tmp_data_dir):
    db.init_db()
    conn = db._get_conn()
    row = conn.execute("PRAGMA table_info(ingestion_jobs)").fetchall()
    columns = [r[1] for r in row]
    assert "source" in columns
    assert "status" in columns
    assert "input_data" in columns
    assert "result" in columns
    assert "retries" in columns
    assert "timeout_seconds" in columns
    assert "started_at" in columns
    assert "heartbeat_at" in columns
    conn.close()
```

**Step 2: Run test to verify it fails**

Run: `pytest server/tests/test_ingest/test_jobs.py -v`
Expected: FAIL — missing columns

**Step 3: Write implementation**

In `server/db.py`, update the books CREATE TABLE (around line 74) to add new columns:

```python
# Add after size_mb column in books table:
language TEXT DEFAULT 'ru',
source TEXT DEFAULT 'manual',
external_id TEXT,
fingerprint TEXT,
```

Add new table creation in `init_db()` (after collection_books):

```python
cur.execute("""
    CREATE TABLE IF NOT EXISTS ingestion_jobs (
        id INTEGER PRIMARY KEY,
        source TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        input_data TEXT,
        result TEXT,
        retries INTEGER DEFAULT 0,
        timeout_seconds INTEGER DEFAULT 600,
        started_at TEXT,
        heartbeat_at TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )
""")
```

**Step 4: Run test to verify it passes**

Run: `pytest server/tests/test_ingest/test_jobs.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add server/db.py server/tests/test_ingest/
git commit -m "feat(ingest): add ingestion_jobs table and books language/source columns"
```

---

### Task 2: Job Queue CRUD — create, update, heartbeat, recover

**Files:**
- Modify: `server/db.py` (add functions at end)
- Test: `server/tests/test_ingest/test_jobs.py` (extend)

**Step 1: Write failing tests**

Append to `server/tests/test_ingest/test_jobs.py`:

```python
import json
import time


def test_create_ingestion_job(tmp_data_dir):
    db.init_db()
    job_id = db.create_ingestion_job("librivox", {"lang": "ru", "limit": 10})
    assert job_id > 0
    job = db.get_ingestion_job(job_id)
    assert job["source"] == "librivox"
    assert job["status"] == "pending"
    assert json.loads(job["input_data"]) == {"lang": "ru", "limit": 10}


def test_update_ingestion_job_status(tmp_data_dir):
    db.init_db()
    job_id = db.create_ingestion_job("normalize", {})
    db.update_ingestion_job(job_id, status="processing")
    job = db.get_ingestion_job(job_id)
    assert job["status"] == "processing"
    assert job["started_at"] is not None


def test_heartbeat_ingestion_job(tmp_data_dir):
    db.init_db()
    job_id = db.create_ingestion_job("normalize", {})
    db.update_ingestion_job(job_id, status="processing")
    db.heartbeat_ingestion_job(job_id)
    job = db.get_ingestion_job(job_id)
    assert job["heartbeat_at"] is not None


def test_list_ingestion_jobs(tmp_data_dir):
    db.init_db()
    db.create_ingestion_job("librivox", {})
    db.create_ingestion_job("normalize", {})
    jobs = db.list_ingestion_jobs()
    assert len(jobs) == 2
    jobs_pending = db.list_ingestion_jobs(status="pending")
    assert len(jobs_pending) == 2


def test_recover_stalled_jobs(tmp_data_dir):
    db.init_db()
    job_id = db.create_ingestion_job("normalize", {}, timeout_seconds=1)
    db.update_ingestion_job(job_id, status="processing")
    db.heartbeat_ingestion_job(job_id)
    # Simulate stalled: set heartbeat to past
    conn = db._get_conn()
    conn.execute(
        "UPDATE ingestion_jobs SET heartbeat_at = datetime('now', '-10 seconds') WHERE id = ?",
        (job_id,),
    )
    conn.commit()
    conn.close()
    recovered = db.recover_stalled_jobs()
    assert recovered == 1
    job = db.get_ingestion_job(job_id)
    assert job["status"] == "pending"


def test_update_job_result(tmp_data_dir):
    db.init_db()
    job_id = db.create_ingestion_job("normalize", {})
    result = {"book_id": 42, "tracks_processed": 10}
    db.update_ingestion_job(job_id, status="done", result=result)
    job = db.get_ingestion_job(job_id)
    assert job["status"] == "done"
    assert json.loads(job["result"])["book_id"] == 42
```

**Step 2: Run test to verify it fails**

Run: `pytest server/tests/test_ingest/test_jobs.py -v`
Expected: FAIL — `db.create_ingestion_job` not found

**Step 3: Write implementation**

Add to `server/db.py` (at end of file):

```python
# ── Ingestion Jobs ─────────────────────────────────────────────────────────


def create_ingestion_job(
    source: str, input_data: dict, timeout_seconds: int = 600
) -> int:
    conn = _get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO ingestion_jobs (source, input_data, timeout_seconds) VALUES (?, ?, ?)",
            (source, json.dumps(input_data, ensure_ascii=False), timeout_seconds),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_ingestion_job(job_id: int) -> dict | None:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM ingestion_jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_ingestion_jobs(status: str | None = None, limit: int = 100) -> list[dict]:
    conn = _get_conn()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM ingestion_jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ingestion_jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_ingestion_job(
    job_id: int,
    status: str | None = None,
    result: dict | None = None,
) -> None:
    conn = _get_conn()
    try:
        parts = ["updated_at = datetime('now')"]
        params: list = []
        if status:
            parts.append("status = ?")
            params.append(status)
            if status == "processing":
                parts.append("started_at = datetime('now')")
                parts.append("heartbeat_at = datetime('now')")
        if result is not None:
            parts.append("result = ?")
            params.append(json.dumps(result, ensure_ascii=False))
        params.append(job_id)
        conn.execute(
            f"UPDATE ingestion_jobs SET {', '.join(parts)} WHERE id = ?",
            params,
        )
        conn.commit()
    finally:
        conn.close()


def heartbeat_ingestion_job(job_id: int) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE ingestion_jobs SET heartbeat_at = datetime('now') WHERE id = ?",
            (job_id,),
        )
        conn.commit()
    finally:
        conn.close()


def recover_stalled_jobs() -> int:
    conn = _get_conn()
    try:
        cur = conn.execute("""
            UPDATE ingestion_jobs
            SET status = 'pending', retries = retries + 1, updated_at = datetime('now')
            WHERE status = 'processing'
              AND heartbeat_at IS NOT NULL
              AND (julianday('now') - julianday(heartbeat_at)) * 86400 > timeout_seconds
        """)
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
```

Also add `import json` at top of db.py if not already imported.

**Step 4: Run test to verify it passes**

Run: `pytest server/tests/test_ingest/test_jobs.py -v`
Expected: PASS (all 9 tests)

**Step 5: Commit**

```bash
git add server/db.py server/tests/test_ingest/test_jobs.py
git commit -m "feat(ingest): add job queue CRUD with heartbeat and recovery"
```

---

### Task 3: Audio Normalization Module

**Files:**
- Create: `server/ingest/__init__.py`
- Create: `server/ingest/normalize.py`
- Test: `server/tests/test_ingest/test_normalize.py`

**Step 1: Write failing tests**

Create `server/ingest/__init__.py` (empty) and `server/tests/test_ingest/test_normalize.py`:

```python
"""Tests for audio normalization via ffmpeg."""
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

from server.ingest.normalize import build_ffmpeg_cmd, normalize_file, is_mp3


def test_build_ffmpeg_cmd_default():
    cmd = build_ffmpeg_cmd(Path("/tmp/input.mp3"), Path("/tmp/output.mp3"))
    assert "ffmpeg" in cmd[0]
    assert "-ar" in cmd
    assert "44100" in cmd
    assert "-ac" in cmd
    assert "1" in cmd
    assert "-b:a" in cmd
    assert "128k" in cmd
    assert "loudnorm" in cmd[cmd.index("-af") + 1]


def test_build_ffmpeg_cmd_fast_mode():
    cmd = build_ffmpeg_cmd(Path("/tmp/in.m4b"), Path("/tmp/out.mp3"), fast=True)
    assert "-af" not in cmd  # no loudnorm in fast mode
    assert "128k" in cmd


def test_is_mp3():
    assert is_mp3(Path("book.mp3")) is True
    assert is_mp3(Path("book.m4b")) is False
    assert is_mp3(Path("book.M4A")) is False
    assert is_mp3(Path("book.opus")) is False


@patch("subprocess.run")
def test_normalize_file_calls_ffmpeg(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    src = Path("/tmp/test.m4a")
    out = Path("/tmp/test_out.mp3")
    normalize_file(src, out, fast=False)
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert call_args[0] == "ffmpeg"
    assert str(src) in call_args
    assert str(out) in call_args


@patch("subprocess.run")
def test_normalize_file_raises_on_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stderr="codec error")
    import pytest
    with pytest.raises(RuntimeError, match="ffmpeg"):
        normalize_file(Path("/tmp/in.mp3"), Path("/tmp/out.mp3"))
```

**Step 2: Run test to verify it fails**

Run: `pytest server/tests/test_ingest/test_normalize.py -v`
Expected: FAIL — module not found

**Step 3: Write implementation**

Create `server/ingest/normalize.py`:

```python
"""Audio normalization via ffmpeg."""
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("leerio.ingest")

AUDIO_EXTENSIONS = {".mp3", ".m4b", ".m4a", ".opus", ".ogg", ".flac", ".wav", ".wma"}


def is_mp3(path: Path) -> bool:
    return path.suffix.lower() == ".mp3"


def build_ffmpeg_cmd(
    input_path: Path, output_path: Path, *, fast: bool = False, timeout: int = 300
) -> list[str]:
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vn",
        "-ar", "44100",
        "-ac", "1",
        "-b:a", "128k",
    ]
    if not fast:
        cmd.extend(["-af", "loudnorm"])
    cmd.append(str(output_path))
    return cmd


def normalize_file(
    input_path: Path, output_path: Path, *, fast: bool = False, timeout: int = 300
) -> None:
    cmd = build_ffmpeg_cmd(input_path, output_path, fast=fast)
    logger.info("ffmpeg: %s -> %s (fast=%s)", input_path.name, output_path.name, fast)
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({result.returncode}): {result.stderr[:500]}")
```

**Step 4: Run test to verify it passes**

Run: `pytest server/tests/test_ingest/test_normalize.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add server/ingest/ server/tests/test_ingest/test_normalize.py
git commit -m "feat(ingest): add ffmpeg audio normalization module"
```

---

### Task 4: Deduplication — Fingerprint generation

**Files:**
- Create: `server/ingest/dedup.py`
- Test: `server/tests/test_ingest/test_dedup.py`

**Step 1: Write failing tests**

Create `server/tests/test_ingest/test_dedup.py`:

```python
"""Tests for deduplication fingerprinting."""
from server.ingest.dedup import make_fingerprint, normalize_text


def test_normalize_text():
    assert normalize_text("  Hello, World!  ") == "hello world"
    assert normalize_text("Стивен Кинг") == "стивен кинг"
    assert normalize_text("Author's Name.") == "authors name"


def test_fingerprint_deterministic():
    fp1 = make_fingerprint("Зелёная миля", "Стивен Кинг", 12.3)
    fp2 = make_fingerprint("Зелёная миля", "Стивен Кинг", 12.3)
    assert fp1 == fp2


def test_fingerprint_includes_duration():
    fp1 = make_fingerprint("Same Title", "Same Author", 5.0)
    fp2 = make_fingerprint("Same Title", "Same Author", 10.0)
    assert fp1 != fp2


def test_fingerprint_case_insensitive():
    fp1 = make_fingerprint("THE BOOK", "AUTHOR", 5.0)
    fp2 = make_fingerprint("the book", "author", 5.0)
    assert fp1 == fp2


def test_fingerprint_ignores_punctuation():
    fp1 = make_fingerprint("Hello, World!", "Author's Name.", 3.0)
    fp2 = make_fingerprint("Hello World", "Authors Name", 3.0)
    assert fp1 == fp2
```

**Step 2: Run test to verify it fails**

Run: `pytest server/tests/test_ingest/test_dedup.py -v`

**Step 3: Write implementation**

Create `server/ingest/dedup.py`:

```python
"""Deduplication via content fingerprinting."""
import hashlib
import re
import unicodedata


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text.lower().strip())
    text = re.sub(r"[^\w\s]", "", text)  # remove punctuation
    text = re.sub(r"\s+", " ", text).strip()
    return text


def make_fingerprint(title: str, author: str, duration_hours: float) -> str:
    key = normalize_text(title) + "|" + normalize_text(author) + "|" + str(round(duration_hours))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()
```

**Step 4: Run test to verify it passes**

Run: `pytest server/tests/test_ingest/test_dedup.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add server/ingest/dedup.py server/tests/test_ingest/test_dedup.py
git commit -m "feat(ingest): add dedup fingerprinting module"
```

---

### Task 5: Chapter Detection Module

**Files:**
- Create: `server/ingest/chapters.py`
- Test: `server/tests/test_ingest/test_chapters.py`

**Step 1: Write failing tests**

Create `server/tests/test_ingest/test_chapters.py`:

```python
"""Tests for chapter detection."""
from server.ingest.chapters import detect_chapters_fallback, parse_embedded_chapters


def test_fallback_splits_by_duration():
    # 3 tracks of 600s each = 1800s total; fallback at 600s = 3 chapters
    tracks = [
        {"track": 1, "file": "01.mp3", "duration": 600},
        {"track": 2, "file": "02.mp3", "duration": 600},
        {"track": 3, "file": "03.mp3", "duration": 600},
    ]
    chapters = detect_chapters_fallback(tracks, interval_seconds=600)
    assert len(chapters) == 3
    assert chapters[0] == {"title": "Часть 1", "start": 0, "track": 0}
    assert chapters[1] == {"title": "Часть 2", "start": 600, "track": 1}
    assert chapters[2] == {"title": "Часть 3", "start": 1200, "track": 2}


def test_fallback_single_track():
    tracks = [{"track": 1, "file": "01.mp3", "duration": 300}]
    chapters = detect_chapters_fallback(tracks, interval_seconds=600)
    assert len(chapters) == 1
    assert chapters[0]["title"] == "Часть 1"


def test_parse_embedded_chapters_empty():
    # No chapters found
    assert parse_embedded_chapters([]) == []
```

**Step 2: Run test to verify it fails**

Run: `pytest server/tests/test_ingest/test_chapters.py -v`

**Step 3: Write implementation**

Create `server/ingest/chapters.py`:

```python
"""Chapter detection for audiobooks."""
import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("leerio.ingest")

DEFAULT_INTERVAL = 600  # 10 minutes


def detect_chapters_fallback(
    tracks: list[dict], interval_seconds: int = DEFAULT_INTERVAL
) -> list[dict]:
    """Split tracks into chapters by cumulative duration."""
    chapters = []
    cumulative = 0
    next_split = 0
    for i, t in enumerate(tracks):
        if cumulative >= next_split:
            chapters.append({
                "title": f"Часть {len(chapters) + 1}",
                "start": int(cumulative),
                "track": i,
            })
            next_split = cumulative + interval_seconds
        cumulative += t["duration"]
    if not chapters and tracks:
        chapters.append({"title": "Часть 1", "start": 0, "track": 0})
    return chapters


def parse_embedded_chapters(raw_chapters: list) -> list[dict]:
    """Parse ffprobe chapter output into standard format."""
    result = []
    for ch in raw_chapters:
        title = ch.get("tags", {}).get("title", f"Chapter {len(result) + 1}")
        start = float(ch.get("start_time", 0))
        result.append({"title": title, "start": int(start), "track": 0})
    return result


def detect_chapters_from_file(file_path: Path) -> list[dict]:
    """Try to extract embedded chapters from m4b/mp3 via ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_chapters",
                str(file_path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            chapters = data.get("chapters", [])
            if chapters:
                return parse_embedded_chapters(chapters)
    except Exception:
        logger.warning("Failed to extract chapters from %s", file_path.name)
    return []
```

**Step 4: Run test to verify it passes**

Run: `pytest server/tests/test_ingest/test_chapters.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add server/ingest/chapters.py server/tests/test_ingest/test_chapters.py
git commit -m "feat(ingest): add chapter detection module"
```

---

### Task 6: S3 Upload Functions

**Files:**
- Modify: `server/storage.py` (add upload functions)
- Test: `server/tests/test_ingest/test_storage.py`

**Step 1: Write failing tests**

Create `server/tests/test_ingest/test_storage.py`:

```python
"""Tests for S3 upload functions."""
from unittest.mock import patch, MagicMock
from server.storage import upload_file_to_s3, upload_json_to_s3


@patch("server.storage._get_client")
def test_upload_file_to_s3(mock_client_fn):
    mock_client = MagicMock()
    mock_client_fn.return_value = mock_client
    upload_file_to_s3("/tmp/test.mp3", "books/1/audio/01.mp3")
    mock_client.upload_file.assert_called_once_with(
        "/tmp/test.mp3", "leerio-books", "books/1/audio/01.mp3"
    )


@patch("server.storage._get_client")
def test_upload_json_to_s3(mock_client_fn):
    mock_client = MagicMock()
    mock_client_fn.return_value = mock_client
    upload_json_to_s3({"title": "Test"}, "books/1/metadata.json")
    mock_client.put_object.assert_called_once()
    call_kwargs = mock_client.put_object.call_args[1]
    assert call_kwargs["Key"] == "books/1/metadata.json"
    assert call_kwargs["ContentType"] == "application/json"
```

**Step 2: Run test to verify it fails**

Run: `pytest server/tests/test_ingest/test_storage.py -v`

**Step 3: Write implementation**

Add to `server/storage.py` (at end):

```python
def upload_file_to_s3(local_path: str, s3_key: str) -> None:
    """Upload a local file to S3."""
    client = _get_client()
    if not client:
        raise RuntimeError("S3 not configured")
    bucket = os.environ.get("S3_BUCKET", "leerio-books")
    client.upload_file(local_path, bucket, s3_key)


def upload_json_to_s3(data: dict | list, s3_key: str) -> None:
    """Upload a JSON object to S3."""
    client = _get_client()
    if not client:
        raise RuntimeError("S3 not configured")
    bucket = os.environ.get("S3_BUCKET", "leerio-books")
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    client.put_object(Bucket=bucket, Key=s3_key, Body=body, ContentType="application/json")


def delete_s3_prefix(prefix: str) -> int:
    """Delete all objects under a prefix. Returns count deleted."""
    client = _get_client()
    if not client:
        return 0
    bucket = os.environ.get("S3_BUCKET", "leerio-books")
    paginator = client.get_paginator("list_objects_v2")
    deleted = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
        if objects:
            client.delete_objects(Bucket=bucket, Delete={"Objects": objects})
            deleted += len(objects)
    return deleted
```

Also add `import json` at top of storage.py if not present.

**Step 4: Run test to verify it passes**

Run: `pytest server/tests/test_ingest/test_storage.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add server/storage.py server/tests/test_ingest/test_storage.py
git commit -m "feat(ingest): add S3 upload and delete functions"
```

---

### Task 7: Metadata Extraction Module

**Files:**
- Create: `server/ingest/extract_metadata.py`
- Test: `server/tests/test_ingest/test_metadata.py`

**Step 1: Write failing tests**

Create `server/tests/test_ingest/test_metadata.py`:

```python
"""Tests for metadata extraction."""
from pathlib import Path
from unittest.mock import patch, MagicMock

from server.ingest.extract_metadata import (
    extract_track_duration,
    build_tracks_json,
    build_metadata_json,
)


def test_build_tracks_json():
    files = [Path("/tmp/01.mp3"), Path("/tmp/02.mp3")]
    durations = {"/tmp/01.mp3": 600.5, "/tmp/02.mp3": 720.3}
    with patch("server.ingest.extract_metadata.extract_track_duration", side_effect=lambda p: durations[str(p)]):
        result = build_tracks_json(files)
    assert len(result) == 2
    assert result[0] == {"track": 1, "file": "01.mp3", "duration": 600.5}
    assert result[1] == {"track": 2, "file": "02.mp3", "duration": 720.3}


def test_build_metadata_json():
    meta = build_metadata_json(
        title="Test Book",
        author="Author",
        reader="Reader",
        category="Бизнес",
        language="ru",
        source="librivox",
        duration_hours=5.2,
    )
    assert meta["version"] == 1
    assert meta["title"] == "Test Book"
    assert meta["language"] == "ru"
    assert meta["duration_hours"] == 5.2
```

**Step 2: Run test to verify it fails**

Run: `pytest server/tests/test_ingest/test_metadata.py -v`

**Step 3: Write implementation**

Create `server/ingest/extract_metadata.py`:

```python
"""Metadata extraction from audio files."""
import logging
from pathlib import Path

from mutagen.mp3 import MP3

logger = logging.getLogger("leerio.ingest")


def extract_track_duration(path: Path) -> float:
    """Get duration in seconds from an MP3 file."""
    try:
        audio = MP3(str(path))
        return audio.info.length
    except Exception:
        logger.warning("Cannot read duration: %s", path.name)
        return 0.0


def extract_cover_from_mp3(path: Path) -> bytes | None:
    """Extract embedded cover art from MP3 ID3 tags."""
    try:
        from mutagen.id3 import ID3
        tags = ID3(str(path))
        for key in tags:
            if key.startswith("APIC"):
                return tags[key].data
    except Exception:
        pass
    return None


def build_tracks_json(mp3_files: list[Path]) -> list[dict]:
    """Build tracks.json from ordered list of MP3 files."""
    result = []
    for i, f in enumerate(sorted(mp3_files), 1):
        duration = extract_track_duration(f)
        result.append({"track": i, "file": f.name, "duration": duration})
    return result


def build_metadata_json(
    *,
    title: str,
    author: str,
    reader: str = "",
    category: str = "",
    language: str = "ru",
    source: str = "manual",
    duration_hours: float = 0,
) -> dict:
    """Build metadata.json content."""
    return {
        "version": 1,
        "title": title,
        "author": author,
        "reader": reader,
        "category": category,
        "language": language,
        "source": source,
        "duration_hours": round(duration_hours, 2),
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest server/tests/test_ingest/test_metadata.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add server/ingest/extract_metadata.py server/tests/test_ingest/test_metadata.py
git commit -m "feat(ingest): add metadata extraction module"
```

---

## Phase 2: Pipeline Core

### Task 8: Pipeline — Main orchestrator

**Files:**
- Create: `server/ingest/pipeline.py`
- Test: `server/tests/test_ingest/test_pipeline.py`

**Step 1: Write failing test**

Create `server/tests/test_ingest/test_pipeline.py`:

```python
"""Tests for the main ingestion pipeline."""
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from server.ingest.pipeline import IngestPipeline


@pytest.fixture
def pipeline(tmp_path):
    return IngestPipeline(
        work_dir=tmp_path,
        title="Test Book",
        author="Test Author",
        reader="Test Reader",
        category="Бизнес",
        language="ru",
        source="url",
        fast=False,
    )


def test_pipeline_init(pipeline, tmp_path):
    assert pipeline.work_dir == tmp_path
    assert pipeline.title == "Test Book"
    assert pipeline.fast is False


def test_pipeline_normalize_creates_output(pipeline, tmp_path):
    # Create a fake mp3 in work_dir
    src = tmp_path / "input.m4a"
    src.write_bytes(b"fake audio")
    out = tmp_path / "output.mp3"

    with patch("server.ingest.pipeline.normalize_file") as mock_norm:
        pipeline._normalize_single(src, out)
        mock_norm.assert_called_once_with(src, out, fast=False, timeout=300)


def test_pipeline_build_s3_key():
    key = IngestPipeline.s3_audio_key(42, "01.mp3")
    assert key == "books/42/audio/01.mp3"

    key = IngestPipeline.s3_metadata_key(42)
    assert key == "books/42/metadata.json"
```

**Step 2: Run test to verify it fails**

Run: `pytest server/tests/test_ingest/test_pipeline.py -v`

**Step 3: Write implementation**

Create `server/ingest/pipeline.py`:

```python
"""Main ingestion pipeline: normalize -> upload -> register."""
import logging
import os
import shutil
from pathlib import Path

from . import normalize as norm
from .chapters import detect_chapters_fallback, detect_chapters_from_file
from .dedup import make_fingerprint
from .extract_metadata import build_tracks_json, build_metadata_json, extract_cover_from_mp3

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
        from ..storage import upload_file_to_s3, upload_json_to_s3
        from ..core import make_slug, estimate_duration_hours

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
        existing = conn.execute(
            "SELECT id FROM books WHERE fingerprint = ?", (fingerprint,)
        ).fetchone()
        conn.close()
        if existing:
            return {"status": "skipped", "reason": "duplicate", "existing_id": existing[0]}

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
```

Also add `insert_book_for_ingest` and `insert_tracks_for_ingest` functions to `server/db.py`:

```python
def insert_book_for_ingest(
    *, slug, title, author, reader, category, language, source,
    fingerprint, mp3_count, duration_hours, size_mb, has_cover,
) -> int:
    conn = _get_conn()
    try:
        cur = conn.execute(
            """INSERT INTO books
            (slug, title, author, reader, category, folder, s3_prefix,
             language, source, fingerprint, has_cover, mp3_count, duration_hours, size_mb)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (slug, title, author, reader, category, slug, f"books/{slug}",
             language, source, fingerprint, has_cover, mp3_count, duration_hours, size_mb),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def insert_tracks_for_ingest(book_id: int, tracks: list[dict]) -> None:
    conn = _get_conn()
    try:
        for t in tracks:
            conn.execute(
                "INSERT INTO tracks (book_id, idx, filename, s3_key, duration) VALUES (?, ?, ?, ?, ?)",
                (book_id, t["track"], t["file"], f"books/{book_id}/audio/{t['file']}", t["duration"]),
            )
        conn.commit()
    finally:
        conn.close()
```

**Step 4: Run test to verify it passes**

Run: `pytest server/tests/test_ingest/test_pipeline.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add server/ingest/pipeline.py server/db.py server/tests/test_ingest/test_pipeline.py
git commit -m "feat(ingest): add main pipeline orchestrator"
```

---

## Phase 3: Job Runner & CLI

### Task 9: Async Job Runner with Heartbeat

**Files:**
- Create: `server/ingest/jobs.py`
- Test: `server/tests/test_ingest/test_runner.py`

This task creates the async runner that pulls jobs from SQLite, runs the pipeline with heartbeat updates, and handles retries. Follow TTS pattern from `server/tts.py:539-603`.

**Key implementation points:**
- `async def run_job(job_id)` — main loop: update status→processing, start heartbeat task, run pipeline, update status→done/failed
- `async def heartbeat_loop(job_id, interval=10)` — updates `heartbeat_at` every N seconds
- `async def process_queue()` — pulls pending jobs, runs with semaphore
- Semaphore size: `max(1, os.cpu_count() // 2)`

**Commit:** `feat(ingest): add async job runner with heartbeat watchdog`

---

### Task 10: CLI Entry Point

**Files:**
- Create: `server/ingest/cli.py`
- Modify: `pyproject.toml` (add `[project.scripts]` entry)

Implement CLI using `argparse` with subcommands:

```bash
leerio ingest librivox --lang ru --limit 50
leerio ingest normalize --all [--fast] [--book-id N]
leerio ingest migrate --all [--dry-run] [--book-id N]
leerio ingest url URL --title T --author A [--type rss|youtube]
leerio ingest status
leerio ingest retry --job-id N
leerio ingest recover
leerio ingest report [--days 7]
```

Progress output: use `print()` with `\r` for inline progress bars. Rich library optional — keep it simple.

**Commit:** `feat(ingest): add CLI entry point`

---

## Phase 4: Sources

### Task 11: LibriVox Source

**Files:**
- Create: `server/ingest/sources/librivox.py`
- Create: `server/ingest/sources/__init__.py`
- Test: `server/tests/test_ingest/test_librivox.py`

Fetch from `https://librivox.org/api/feed/audiobooks?format=json`. Parse response, create ingestion jobs per book. Use `httpx` for downloads.

**Commit:** `feat(ingest): add LibriVox source`

---

### Task 12: Archive.org Source

**Files:**
- Create: `server/ingest/sources/archive.py`
- Test: `server/tests/test_ingest/test_archive.py`

Search `https://archive.org/advancedsearch.php` with filter `mediatype:audio AND subject:audiobook AND format:MP3`. Parse results, download via `https://archive.org/download/{id}/{file}`.

**Commit:** `feat(ingest): add Archive.org source`

---

### Task 13: URL/RSS/YouTube Source

**Files:**
- Create: `server/ingest/sources/url.py`
- Test: `server/tests/test_ingest/test_url.py`
- Modify: `server/requirements.txt` (add `yt-dlp`, `feedparser`)

Three modes: direct mp3 download, RSS feed parsing, YouTube audio extraction (private only, via `yt-dlp`).

**Commit:** `feat(ingest): add URL/RSS/YouTube source`

---

## Phase 5: Admin API & Migration

### Task 14: Admin Ingest API Endpoints

**Files:**
- Create: `server/ingest_api.py` (FastAPI router)
- Modify: `server/api.py` (include router)
- Test: `server/tests/test_ingest/test_api.py`

Endpoints (admin-only via `Depends(get_current_user)` + role check):

```
POST /api/admin/ingest
GET  /api/admin/ingest/jobs
GET  /api/admin/ingest/jobs/:id
POST /api/admin/ingest/retry/:id
GET  /api/admin/ingest/stats
```

**Commit:** `feat(ingest): add admin API endpoints`

---

### Task 15: S3 Migration — Old Layout to New

**Files:**
- Create: `server/ingest/migrate.py`
- Test: `server/tests/test_ingest/test_migrate.py`

For each existing book: download from old S3 path → normalize → upload to `books/{id}/` → generate metadata/tracks/chapters JSON → update DB → delete old prefix.

**Commit:** `feat(ingest): add S3 layout migration tool`

---

## Phase 6: Integration & Streaming Updates

### Task 16: Update Audio Streaming for New S3 Layout

**Files:**
- Modify: `server/api.py:820-860` (audio endpoint)
- Modify: `server/api.py` (cover endpoint)
- Modify: `server/db.py:450-525` (sync_books — support new layout)

Update `get_book_tracks` resolution to use `books/{id}/audio/{idx}.mp3` pattern. Cover endpoint reads from `books/{id}/cover.jpg`. Sync reads `metadata.json` from S3 for new-format books.

**Commit:** `feat(ingest): update streaming and sync for new S3 layout`

---

### Task 17: Integration Test — Full Pipeline

**Files:**
- Create: `server/tests/test_ingest/test_integration.py`
- Create: `server/tests/fixtures/test_audio.mp3` (5-second silent MP3)

Full flow test with mocked S3 (moto): create job → run pipeline → verify DB records → verify S3 objects. Generate the fixture MP3 via ffmpeg in CI setup.

**Commit:** `test(ingest): add integration test for full pipeline`

---

Plan complete and saved to `docs/plans/2026-03-06-content-ingestion-pipeline.md`. Two execution options:

**1. Subagent-Driven (this session)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** — Open new session with executing-plans, batch execution with checkpoints

Which approach?