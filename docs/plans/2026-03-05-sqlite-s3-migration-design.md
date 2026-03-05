# SQLite + S3 Migration Design

## Problem

Books are stored on the filesystem (scanned at runtime), user data in JSON files, audio streamed from local disk. This doesn't scale, is fragile, and ties deployment to having books on the VPS.

## Target Architecture

- **SQLite** = single source of truth for books, tracks, and ALL user data
- **Vultr S3** (ams1.vultrobjects.com) = audio file storage, served via presigned URLs
- **VPS** = covers only (small files, served directly)
- **No more** filesystem scanning, JSON files, or base64 path-encoded book IDs

## S3 Details

- Bucket: `leerio-books` on `ams1.vultrobjects.com`
- Access Key: M54LI6PK2O4N357MB02B
- Env vars: `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`
- Audio endpoint returns 302 redirect to presigned URL (1hr TTL)

## Database Schema

### Books & Tracks

```sql
CREATE TABLE books (
    id             INTEGER PRIMARY KEY,
    slug           TEXT UNIQUE NOT NULL,
    title          TEXT NOT NULL,
    author         TEXT NOT NULL,
    reader         TEXT DEFAULT '',
    category       TEXT DEFAULT '',
    folder         TEXT NOT NULL,
    s3_prefix      TEXT NOT NULL,
    has_cover      BOOLEAN DEFAULT 0,
    mp3_count      INTEGER DEFAULT 0,
    duration_hours REAL DEFAULT 0,
    size_mb        REAL DEFAULT 0,
    created_at     TEXT DEFAULT (datetime('now'))
);

CREATE TABLE tracks (
    id         INTEGER PRIMARY KEY,
    book_id    INTEGER REFERENCES books(id) ON DELETE CASCADE,
    idx        INTEGER NOT NULL,
    filename   TEXT NOT NULL,
    s3_key     TEXT NOT NULL,
    duration   INTEGER DEFAULT 0,
    size_bytes INTEGER DEFAULT 0,
    UNIQUE(book_id, idx)
);
```

### Per-User Data (replaces all JSON files)

```sql
CREATE TABLE user_book_status (
    user_id TEXT, book_id INTEGER REFERENCES books(id),
    status TEXT, PRIMARY KEY(user_id, book_id)
);

CREATE TABLE user_progress (
    user_id TEXT, book_id INTEGER REFERENCES books(id),
    percent INTEGER DEFAULT 0, PRIMARY KEY(user_id, book_id)
);

CREATE TABLE user_playback (
    user_id TEXT, book_id TEXT,
    track_index INTEGER, position REAL, updated TEXT,
    PRIMARY KEY(user_id, book_id)
);

CREATE TABLE user_notes (
    user_id TEXT, book_id INTEGER REFERENCES books(id),
    note TEXT, PRIMARY KEY(user_id, book_id)
);

CREATE TABLE user_tags (
    id INTEGER PRIMARY KEY, user_id TEXT,
    book_id INTEGER REFERENCES books(id), tag TEXT
);

CREATE TABLE user_history (
    id INTEGER PRIMARY KEY, user_id TEXT,
    ts TEXT, action TEXT, book_id INTEGER, detail TEXT, rating INTEGER
);

CREATE TABLE user_quotes (
    id INTEGER PRIMARY KEY, user_id TEXT,
    text TEXT, author TEXT, book TEXT
);

CREATE TABLE user_sessions (
    id INTEGER PRIMARY KEY, user_id TEXT,
    book TEXT, started TEXT, duration_min REAL
);

CREATE TABLE user_bookmarks (
    id INTEGER PRIMARY KEY, user_id TEXT,
    book_id TEXT, track_index INTEGER, position REAL,
    note TEXT, created_at TEXT
);

CREATE TABLE user_collections (
    id INTEGER PRIMARY KEY, user_id TEXT,
    name TEXT, description TEXT
);

CREATE TABLE collection_books (
    collection_id INTEGER REFERENCES user_collections(id) ON DELETE CASCADE,
    book_id INTEGER REFERENCES books(id),
    PRIMARY KEY(collection_id, book_id)
);
```

## Book IDs

Old: base64-encoded filesystem paths (e.g. `L2Jvb2tzL0...`)
New: integer IDs from SQLite (e.g. `42`)

Frontend URLs change: `/book/42` instead of `/book/L2Jvb2tzL0...`

## Audio Streaming

Old: `GET /api/audio/{book_id}/{track}` → reads file from disk, streams bytes
New: `GET /api/audio/{book_id}/{track}` → returns 302 redirect to presigned S3 URL (1hr TTL)

Uses boto3 to generate presigned URLs. S3 client configured via env vars.

## Cover Serving

Stays on VPS filesystem for now. Covers are small (~100KB each).
Could move to S3 later but not priority.

## Migration Script

One-time `server/migrate_to_sqlite.py`:

1. Scan `books/` folders → build `books` + `tracks` tables
   - Parse folder name: `Author - Title [Reader]`
   - Category from parent folder
   - s3_prefix = relative path from books root
   - Enumerate mp3 files → tracks with s3_key
   - Extract cover.jpg existence → has_cover

2. Read `data/users/{user_id}/*.json` → insert into user tables
   - Map old title-based keys to new book IDs via title matching
   - history.json → user_history
   - notes.json → user_notes
   - tags.json → user_tags
   - progress.json → user_progress
   - playback.json → user_playback
   - collections.json → user_collections + collection_books
   - book_status.json → user_book_status
   - quotes.json → user_quotes
   - sessions.json → user_sessions
   - bookmarks.json → user_bookmarks

3. Verify counts match between old and new data

## Server Changes

### New module: `server/storage.py`
- S3 client (boto3) initialization
- `get_presigned_url(s3_key, expires=3600)` function
- Configured via env vars

### Modified: `server/db.py`
- Add all CREATE TABLE statements
- Add CRUD functions for books, tracks, user data

### Modified: `server/core.py`
- Remove filesystem scanning (`Library` class)
- Remove JSON file read/write (`UserData` class)
- Replace with DB queries

### Modified: `server/api.py`
- `stream_audio` → redirect to presigned URL
- All endpoints use DB instead of core.py filesystem logic
- Book IDs are integers, not base64 strings

### Modified: `docker-compose.yml`
- Add S3 env vars
- Remove `./books:/books:ro` volume mount (eventually)

### Modified: Frontend
- Book IDs change from base64 strings to integers
- API response shapes stay the same (backward compatible)

## Implementation Order

1. Schema + migration script (can test independently)
2. `server/storage.py` (S3 client)
3. New `db.py` functions for books + user data
4. Rewrite `core.py` to use DB
5. Update `api.py` endpoints
6. Frontend: update book ID handling
7. Run migration on production data
8. Remove filesystem dependencies
9. Remove books volume from docker-compose

## Env Vars (new)

```
S3_ENDPOINT=https://ams1.vultrobjects.com
S3_ACCESS_KEY=M54LI6PK2O4N357MB02B
S3_SECRET_KEY=JBdzrXuOE89oCQgAhHjyBpNzVBo7RVlvBPkClQHs
S3_BUCKET=leerio-books
```
