# Leerio Content Ingestion Pipeline — Design Document

**Date:** 2026-03-06
**Goal:** Normalize content quality (audio format, chapters, covers, metadata) for all books. Secondary: auto-ingestion from external sources.

---

## 1. Architecture: Inline Worker with Watchdog

Pipeline runs inside the existing FastAPI server. ffmpeg added to Dockerfile. Tasks run as asyncio background tasks (same pattern as TTS). Queue stored in SQLite table `ingestion_jobs`.

**Parallelism:** `CPU_CORES / 2` concurrent workers (e.g., 4 cores = 2 workers).

**Watchdog:** Worker updates `heartbeat_at` every 10 seconds. If `heartbeat_at` is older than `timeout_seconds`, job is considered stalled. `leerio ingest recover` resets stalled jobs to `pending`.

### File Structure

```
server/
  ingest/
    __init__.py
    pipeline.py      # Main: download -> normalize -> upload -> register
    normalize.py     # ffmpeg (128kbps, mono, 44.1kHz, loudnorm)
    chapters.py      # Chapter detection (embedded, cue, silence, fallback)
    metadata.py      # Metadata extraction (mutagen, covers, Google Books)
    jobs.py          # Job queue, runner, watchdog
    cli.py           # CLI entry point
    sources/
      __init__.py
      librivox.py    # LibriVox API catalog fetcher
      archive.py     # Archive.org audiobook fetcher
      url.py         # Direct URL / RSS / YouTube (private only)
```

---

## 2. S3 Storage Layout (new)

```
leerio-books/
  books/
    {book_id}/
      audio/
        01.mp3
        02.mp3
      cover.jpg
      metadata.json
      tracks.json
      chapters.json
```

### metadata.json

```json
{
  "version": 1,
  "title": "...",
  "author": "...",
  "reader": "...",
  "category": "...",
  "language": "ru",
  "source": "manual",
  "duration_hours": 12.3
}
```

### tracks.json

```json
[
  {"track": 1, "file": "01.mp3", "duration": 1830},
  {"track": 2, "file": "02.mp3", "duration": 1920}
]
```

### chapters.json

```json
[
  {"title": "Chapter 1", "start": 0, "track": 0},
  {"title": "Chapter 2", "start": 1830, "track": 3}
]
```

### Migration

`leerio ingest migrate` moves existing 194 books from `{Category}/{Author - Title [Reader]}/` to `books/{book_id}/`. Supports `--dry-run`, `--book-id N`, `--all`.

---

## 3. Pipeline Flow

```
Source -> /tmp/leerio/ingest/{job_id}/ -> Normalize -> Upload to S3 -> Register DB -> Cleanup
```

1. **Download** — fetch audio files to temp dir
2. **Detect format** — mp3, m4b, m4a, opus. Convert non-mp3 via ffmpeg
3. **Normalize** — `ffmpeg -i input -vn -ar 44100 -ac 1 -b:a 128k -af loudnorm output.mp3`
4. **Chapter detection** — embedded chapters -> cue file -> silence detection -> fallback (10 min splits)
5. **Metadata extraction** — mutagen for title/author/duration/cover. Google Books API for missing covers
6. **Generate tracks.json** — ordered list with durations
7. **Upload to S3** — `books/{book_id}/audio/*.mp3` + cover.jpg + metadata.json + tracks.json + chapters.json
8. **Register** — insert into `books` + `tracks` tables. Dedup check before insert
9. **Cleanup** — delete `/tmp/leerio/ingest/{job_id}/`. Cleanup daemon deletes dirs older than 24h

### Quick Mode (`--fast`)

Skip chapter detection and loudnorm. Just: download -> convert to mp3 (128k/mono/44.1k) -> upload. For rapid content addition.

---

## 4. Content Sources

### LibriVox
- API: `https://librivox.org/api/feed/audiobooks?format=json&limit=50&offset=N`
- Filter by language (ru, en, de, etc.)
- Direct MP3 URLs from API response

### Archive.org
- API: `https://archive.org/advancedsearch.php`
- Filter: `mediatype:audio AND subject:audiobook AND format:MP3`
- Metadata from `_meta.xml`

### External URL
- Direct mp3 link — download
- RSS feed — parse `<enclosure>` tags, download episodes
- YouTube — `yt-dlp` for audio extraction. **Private user import only**, not added to public catalog

### Admin Upload (enhanced)
- Extend formats: mp3, m4b, m4a, opus
- Auto-conversion + chapter detection from m4b embedded chapters

### Deduplication

```python
fingerprint = sha1(normalize(title) + normalize(author) + round(duration_hours))
```

Where `normalize()` lowercases, strips whitespace, removes punctuation. Including `duration_hours` (rounded) reduces false positives from different translations or readers.

---

## 5. Database Schema Changes

### books table — new columns

```sql
ALTER TABLE books ADD COLUMN language TEXT DEFAULT 'ru';
ALTER TABLE books ADD COLUMN source TEXT DEFAULT 'manual';
ALTER TABLE books ADD COLUMN external_id TEXT;
ALTER TABLE books ADD COLUMN fingerprint TEXT;
```

### New table: ingestion_jobs

```sql
CREATE TABLE ingestion_jobs (
  id INTEGER PRIMARY KEY,
  source TEXT NOT NULL,           -- librivox|archive|url|upload|normalize|migrate
  status TEXT DEFAULT 'pending',  -- pending|processing|done|failed|partial|skipped
  input_data TEXT,                -- JSON
  result TEXT,                    -- JSON
  retries INTEGER DEFAULT 0,
  timeout_seconds INTEGER DEFAULT 600,
  started_at TEXT,
  heartbeat_at TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);
```

---

## 6. CLI and API

### CLI (`python -m server.ingest.cli`)

```bash
# Sources
leerio ingest librivox --lang ru --limit 50
leerio ingest archive --query "audiobook russian" --limit 20
leerio ingest url https://example.com/book.mp3 --title "..." --author "..." --lang en
leerio ingest url https://feed.rss --type rss
leerio ingest url https://youtube.com/watch?v=... --type youtube  # private only

# Normalize existing
leerio ingest normalize --all
leerio ingest normalize --book-id 42
leerio ingest normalize --all --fast  # skip loudnorm + chapters

# Migrate to new S3 layout
leerio ingest migrate --dry-run
leerio ingest migrate --all
leerio ingest migrate --book-id 42

# Operations
leerio ingest status
leerio ingest retry --job-id 15
leerio ingest recover            # reset stalled jobs
leerio ingest report             # summary for last N days
```

### API (admin-only)

```
POST /api/admin/ingest           — create ingestion job
GET  /api/admin/ingest/jobs      — list jobs (filter by status)
GET  /api/admin/ingest/jobs/:id  — job details with progress
POST /api/admin/ingest/retry/:id — retry failed job
GET  /api/admin/ingest/stats     — aggregated metrics
```

### Scheduler

System cron on VPS (not built-in):

```
0 */6 * * * cd /opt/leerio && docker exec leerio-server leerio ingest librivox --lang ru --limit 10
```

---

## 7. Feedback and Observability

### CLI Feedback
- Progress bar: `[========..] 8/20 tracks — normalizing...`
- Per-track: `+ 01.mp3 (3.2MB -> 1.8MB, 2.1s)` / `x 05.mp3 — download timeout`
- Job summary: books ingested, skipped, failed, total time
- `leerio ingest status` — table of jobs with progress
- `leerio ingest report` — summary for last N days

### API Feedback
```json
{
  "id": 15,
  "status": "processing",
  "progress": {"current": 8, "total": 20, "phase": "normalizing"},
  "tracks_done": ["01.mp3", "02.mp3"],
  "tracks_failed": [],
  "started_at": "...",
  "heartbeat_at": "...",
  "elapsed_seconds": 45
}
```

### Logging
- Logger: `leerio.ingest`
- Structured result in job:
```json
{
  "book_id": 42,
  "tracks_processed": 20,
  "tracks_failed": 0,
  "original_size_mb": 450,
  "normalized_size_mb": 280,
  "duration_seconds": 120,
  "source_url": "https://librivox.org/..."
}
```

### Metrics
- `GET /api/admin/ingest/stats`: books_ingested_total, failures_total, avg processing time
- Computed from `ingestion_jobs` table (no external metrics system)

---

## 8. Error Handling

- **Retry:** 3 attempts, backoff 10s -> 60s -> 300s
- **Partial failure:** if some tracks fail, job status = `partial`, book created with available tracks. Failed tracks listed in `result` JSON
- **Timeouts:** 60s per file download, 300s per ffmpeg conversion
- **S3 upload:** retry 3x per file
- **Dedup conflict:** skip, status = `skipped`
- **Stalled jobs:** watchdog detects via `heartbeat_at` > `timeout_seconds`. `leerio ingest recover` resets to `pending`
- **Temp cleanup:** daemon deletes `/tmp/leerio/ingest/` dirs older than 24h

---

## 9. Testing

### Unit Tests (`server/tests/test_ingest/`)
- `test_normalize.py` — ffmpeg command formation, mock subprocess
- `test_chapters.py` — embedded, silence detection, fallback
- `test_metadata.py` — mutagen extraction, cover detection
- `test_dedup.py` — fingerprint generation, collision detection
- `test_jobs.py` — status transitions, retry logic, watchdog

### Integration Tests
- `test_pipeline.py` — full flow with moto (mock S3) + real SQLite
- Test mp3 fixture (~5 seconds) in `server/tests/fixtures/`

### E2E Tests (2 scenarios)
1. **Ingest -> Play:** ingest book, verify in catalog, play track, seek, resume
2. **Normalize migration:** run migrate, verify tracks, metadata, streaming works

---

## 10. Dependencies

### New Python packages
```
yt-dlp>=2024.0
feedparser>=6.0
```

### Dockerfile addition
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
```

---

## 11. Streaming Compatibility

Existing endpoint `GET /api/audio/{book_id}/{track_index}` already supports per-track streaming with Range headers. `tracks.json` in S3 simplifies track resolution — no need to list S3 prefixes at runtime.

Cover endpoint `GET /api/books/{book_id}/cover` updated to read from `books/{book_id}/cover.jpg`.

---

## 12. Language Support

- `language` field in `books` table and `metadata.json`
- LibriVox/Archive.org: language from API metadata
- Admin upload / URL: specified manually (default: `ru`)
- Catalog UI: language filter (when non-Russian books appear)
- Language is orthogonal to category
