"""
server/migrate_to_sqlite.py — Migrate Leerio from filesystem JSON to SQLite.

Run as: python -m server.migrate_to_sqlite

Step 1: Scan books/ directory -> populate books + tracks tables
Step 2: Migrate per-user JSON data -> user_* tables
Step 3: Print verification counts
"""

import base64
import hashlib
import json
import logging
import sqlite3
from pathlib import Path

from .core import BOOKS_DIR, CATEGORIES, DATA_DIR, make_slug, normalize, parse_folder_name

logger = logging.getLogger("leerio.migrate")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ── Schema ──────────────────────────────────────────────────────────────────


def create_tables(conn: sqlite3.Connection):
    """Create all migration target tables (idempotent)."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            author TEXT NOT NULL DEFAULT '',
            reader TEXT DEFAULT '',
            category TEXT NOT NULL DEFAULT '',
            folder TEXT NOT NULL,
            s3_prefix TEXT NOT NULL DEFAULT '',
            has_cover INTEGER NOT NULL DEFAULT 0,
            mp3_count INTEGER NOT NULL DEFAULT 0,
            duration_hours REAL NOT NULL DEFAULT 0.0,
            size_mb REAL NOT NULL DEFAULT 0.0
        );

        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            idx INTEGER NOT NULL,
            filename TEXT NOT NULL,
            s3_key TEXT NOT NULL DEFAULT '',
            duration REAL NOT NULL DEFAULT 0.0,
            size_bytes INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS user_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            book_id INTEGER REFERENCES books(id) ON DELETE SET NULL,
            action TEXT NOT NULL,
            book_name TEXT NOT NULL DEFAULT '',
            detail TEXT NOT NULL DEFAULT '',
            rating INTEGER NOT NULL DEFAULT 0,
            ts TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            book_id INTEGER REFERENCES books(id) ON DELETE SET NULL,
            book_key TEXT NOT NULL DEFAULT '',
            note TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS user_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            book_id INTEGER REFERENCES books(id) ON DELETE SET NULL,
            book_key TEXT NOT NULL DEFAULT '',
            tag TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            book_id INTEGER REFERENCES books(id) ON DELETE SET NULL,
            book_key TEXT NOT NULL DEFAULT '',
            pct INTEGER NOT NULL DEFAULT 0,
            note TEXT NOT NULL DEFAULT '',
            updated TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS user_playback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            book_id INTEGER REFERENCES books(id) ON DELETE SET NULL,
            old_book_id TEXT NOT NULL DEFAULT '',
            track_index INTEGER NOT NULL DEFAULT 0,
            position REAL NOT NULL DEFAULT 0.0,
            filename TEXT NOT NULL DEFAULT '',
            updated TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS user_collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS collection_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id INTEGER NOT NULL REFERENCES user_collections(id) ON DELETE CASCADE,
            book_id INTEGER REFERENCES books(id) ON DELETE SET NULL,
            book_name TEXT NOT NULL DEFAULT '',
            position INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS user_book_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            book_id INTEGER REFERENCES books(id) ON DELETE SET NULL,
            old_book_id TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            updated TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS user_quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            book_id INTEGER REFERENCES books(id) ON DELETE SET NULL,
            text TEXT NOT NULL,
            book_name TEXT NOT NULL DEFAULT '',
            author TEXT NOT NULL DEFAULT '',
            ts TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            book_id INTEGER REFERENCES books(id) ON DELETE SET NULL,
            book_name TEXT NOT NULL DEFAULT '',
            start_ts TEXT NOT NULL,
            end_ts TEXT,
            minutes INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS user_bookmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            book_id INTEGER REFERENCES books(id) ON DELETE SET NULL,
            old_book_id TEXT NOT NULL DEFAULT '',
            track INTEGER NOT NULL DEFAULT 0,
            time REAL NOT NULL DEFAULT 0.0,
            note TEXT NOT NULL DEFAULT '',
            ts TEXT NOT NULL DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_books_slug ON books(slug);
        CREATE INDEX IF NOT EXISTS idx_books_folder ON books(folder);
        CREATE INDEX IF NOT EXISTS idx_tracks_book ON tracks(book_id);
        CREATE INDEX IF NOT EXISTS idx_user_history_user ON user_history(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_notes_user ON user_notes(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_tags_user ON user_tags(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_progress_user ON user_progress(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_playback_user ON user_playback(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_collections_user ON user_collections(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_book_status_user ON user_book_status(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_quotes_user ON user_quotes(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_bookmarks_user ON user_bookmarks(user_id);
    """
    )
    conn.commit()


# ── Helpers ─────────────────────────────────────────────────────────────────


def _load_json(path: Path, default_factory=dict):
    """Load a JSON file, returning default on missing/corrupt."""
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default_factory()


def decode_old_id(book_id: str) -> str:
    """Decode old base64-encoded path to folder name."""
    try:
        path = Path(base64.urlsafe_b64decode(book_id.encode("ascii")).decode("utf-8"))
        return path.name  # folder name like "Author - Title [Reader]"
    except Exception:
        return ""


def build_lookup(conn: sqlite3.Connection) -> tuple[dict[str, int], dict[str, int]]:
    """Build lookup dicts for matching old data to new book IDs.

    Returns:
        folder_lookup: {folder_name: book_id}
        norm_lookup: {normalized_key: book_id} — includes normalized title,
            normalized folder, and normalized "author - title"
    """
    rows = conn.execute("SELECT id, folder, title, author FROM books").fetchall()
    folder_lookup: dict[str, int] = {}
    norm_lookup: dict[str, int] = {}
    for row in rows:
        book_id, folder, title, author = row["id"], row["folder"], row["title"], row["author"]
        folder_lookup[folder] = book_id
        # Multiple normalized keys for fuzzy matching
        norm_lookup[normalize(title)] = book_id
        norm_lookup[normalize(folder)] = book_id
        if author:
            norm_lookup[normalize(f"{author} - {title}")] = book_id
            norm_lookup[normalize(f"{author} {title}")] = book_id
    return folder_lookup, norm_lookup


def resolve_old_base64_id(
    old_id: str,
    folder_lookup: dict[str, int],
    norm_lookup: dict[str, int],
) -> int | None:
    """Resolve an old base64-encoded book ID to a new integer book ID."""
    folder = decode_old_id(old_id)
    if not folder:
        return None
    # Direct folder match
    if folder in folder_lookup:
        return folder_lookup[folder]
    # Normalized folder match
    nf = normalize(folder)
    if nf in norm_lookup:
        return norm_lookup[nf]
    return None


def resolve_normalized_key(
    key: str,
    norm_lookup: dict[str, int],
) -> int | None:
    """Resolve a normalized text key (used in notes, tags, progress) to a book ID."""
    if key in norm_lookup:
        return norm_lookup[key]
    # The key is already normalized in the JSON files
    return norm_lookup.get(key)


def resolve_book_name(
    name: str,
    folder_lookup: dict[str, int],
    norm_lookup: dict[str, int],
) -> int | None:
    """Resolve a book name (from history, sessions, quotes) to a book ID."""
    # Try direct folder match
    if name in folder_lookup:
        return folder_lookup[name]
    # Try normalized
    nk = normalize(name)
    if nk in norm_lookup:
        return norm_lookup[nk]
    return None


def resolve_collection_book(
    name: str,
    folder_lookup: dict[str, int],
    norm_lookup: dict[str, int],
) -> int | None:
    """Resolve a collection book entry (title only) to a book ID."""
    nk = normalize(name)
    if nk in norm_lookup:
        return norm_lookup[nk]
    return None


# ── Step 1: Migrate books ──────────────────────────────────────────────────


def migrate_books(conn: sqlite3.Connection, books_dir: Path):
    """Scan filesystem and insert books + tracks into SQLite."""
    book_count = 0
    track_count = 0

    for cat in CATEGORIES:
        cat_dir = books_dir / cat
        if not cat_dir.is_dir():
            continue
        for book_dir in sorted(cat_dir.iterdir()):
            if not book_dir.is_dir() or book_dir.name.startswith("_"):
                continue

            author, title, reader = parse_folder_name(book_dir.name)
            slug = make_slug(title, author)
            s3_prefix = str(book_dir.relative_to(books_dir))
            has_cover = (book_dir / "cover.jpg").exists()

            # Enumerate MP3s
            mp3s = sorted(book_dir.rglob("*.mp3"), key=lambda f: str(f))
            mp3_count = len(mp3s)

            # Get duration per track
            total_duration = 0.0
            track_data: list[tuple[int, str, str, float, int]] = []
            for i, mp3 in enumerate(mp3s):
                dur = 0.0
                try:
                    from mutagen.mp3 import MP3

                    audio = MP3(str(mp3))
                    dur = audio.info.length
                except Exception:
                    pass
                total_duration += dur
                s3_key = s3_prefix + "/" + str(mp3.relative_to(book_dir))
                try:
                    file_size = mp3.stat().st_size
                except OSError:
                    file_size = 0
                track_data.append((i, mp3.name, s3_key, dur, file_size))

            size_mb = sum(f.stat().st_size for f in book_dir.rglob("*") if f.is_file()) / (1024 * 1024)

            # Handle duplicate slugs
            existing = conn.execute("SELECT id FROM books WHERE slug = ?", (slug,)).fetchone()
            if existing:
                slug = slug + "-" + hashlib.md5(str(book_dir).encode()).hexdigest()[:6]

            conn.execute(
                """
                INSERT INTO books (slug, title, author, reader, category, folder, s3_prefix,
                                   has_cover, mp3_count, duration_hours, size_mb)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    slug,
                    title,
                    author,
                    reader or "",
                    cat,
                    book_dir.name,
                    s3_prefix,
                    int(has_cover),
                    mp3_count,
                    round(total_duration / 3600, 2),
                    round(size_mb, 1),
                ),
            )
            book_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            book_count += 1

            for idx, filename, s3_key, dur, size in track_data:
                conn.execute(
                    """
                    INSERT INTO tracks (book_id, idx, filename, s3_key, duration, size_bytes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (book_id, idx, filename, s3_key, round(dur, 2), size),
                )
                track_count += 1

            if book_count % 50 == 0:
                logger.info("  ... %d books scanned", book_count)

    conn.commit()
    logger.info("Books: %d, Tracks: %d", book_count, track_count)


# ── Step 2: Migrate user data ──────────────────────────────────────────────


def migrate_user_data(conn: sqlite3.Connection, data_dir: Path):
    """Migrate all per-user JSON files into SQLite tables."""
    users_dir = data_dir / "users"
    if not users_dir.exists():
        logger.warning("No users directory found at %s", users_dir)
        return

    folder_lookup, norm_lookup = build_lookup(conn)

    user_dirs = [d for d in users_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
    logger.info("Found %d user directories", len(user_dirs))

    for user_dir in sorted(user_dirs):
        user_id = user_dir.name
        logger.info("  Migrating user: %s", user_id)

        _migrate_history(conn, user_id, user_dir, folder_lookup, norm_lookup)
        _migrate_notes(conn, user_id, user_dir, norm_lookup)
        _migrate_tags(conn, user_id, user_dir, norm_lookup)
        _migrate_progress(conn, user_id, user_dir, norm_lookup)
        _migrate_playback(conn, user_id, user_dir, folder_lookup, norm_lookup)
        _migrate_collections(conn, user_id, user_dir, folder_lookup, norm_lookup)
        _migrate_book_status(conn, user_id, user_dir, folder_lookup, norm_lookup)
        _migrate_quotes(conn, user_id, user_dir, folder_lookup, norm_lookup)
        _migrate_sessions(conn, user_id, user_dir, folder_lookup, norm_lookup)
        _migrate_bookmarks(conn, user_id, user_dir, folder_lookup, norm_lookup)

    conn.commit()


def _migrate_history(
    conn: sqlite3.Connection,
    user_id: str,
    user_dir: Path,
    folder_lookup: dict[str, int],
    norm_lookup: dict[str, int],
):
    """history.json: list of {ts, action, book, detail, rating?}"""
    data = _load_json(user_dir / "history.json", list)
    count = 0
    for entry in data:
        book_name = entry.get("book", "")
        book_id = resolve_book_name(book_name, folder_lookup, norm_lookup)
        conn.execute(
            """
            INSERT INTO user_history (user_id, book_id, action, book_name, detail, rating, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                book_id,
                entry.get("action", ""),
                book_name,
                entry.get("detail", ""),
                entry.get("rating", 0),
                entry.get("ts", ""),
            ),
        )
        count += 1
    if count:
        logger.info("    history: %d entries", count)


def _migrate_notes(
    conn: sqlite3.Connection,
    user_id: str,
    user_dir: Path,
    norm_lookup: dict[str, int],
):
    """notes.json: {normalized_title: note_text}"""
    data = _load_json(user_dir / "notes.json", dict)
    count = 0
    for key, note in data.items():
        book_id = resolve_normalized_key(key, norm_lookup)
        conn.execute(
            """
            INSERT INTO user_notes (user_id, book_id, book_key, note)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, book_id, key, note),
        )
        count += 1
    if count:
        logger.info("    notes: %d entries", count)


def _migrate_tags(
    conn: sqlite3.Connection,
    user_id: str,
    user_dir: Path,
    norm_lookup: dict[str, int],
):
    """tags.json: {normalized_title: [tag1, tag2, ...]}"""
    data = _load_json(user_dir / "tags.json", dict)
    count = 0
    for key, tags in data.items():
        book_id = resolve_normalized_key(key, norm_lookup)
        for tag in tags:
            conn.execute(
                """
                INSERT INTO user_tags (user_id, book_id, book_key, tag)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, book_id, key, tag),
            )
            count += 1
    if count:
        logger.info("    tags: %d entries", count)


def _migrate_progress(
    conn: sqlite3.Connection,
    user_id: str,
    user_dir: Path,
    norm_lookup: dict[str, int],
):
    """progress.json: {normalized_title: {pct, updated, note}}"""
    data = _load_json(user_dir / "progress.json", dict)
    count = 0
    for key, entry in data.items():
        book_id = resolve_normalized_key(key, norm_lookup)
        conn.execute(
            """
            INSERT INTO user_progress (user_id, book_id, book_key, pct, note, updated)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                book_id,
                key,
                entry.get("pct", 0),
                entry.get("note", ""),
                entry.get("updated", ""),
            ),
        )
        count += 1
    if count:
        logger.info("    progress: %d entries", count)


def _migrate_playback(
    conn: sqlite3.Connection,
    user_id: str,
    user_dir: Path,
    folder_lookup: dict[str, int],
    norm_lookup: dict[str, int],
):
    """playback.json: {old_base64_id: {track_index, position, filename, updated}}"""
    data = _load_json(user_dir / "playback.json", dict)
    count = 0
    for old_id, entry in data.items():
        book_id = resolve_old_base64_id(old_id, folder_lookup, norm_lookup)
        conn.execute(
            """
            INSERT INTO user_playback (user_id, book_id, old_book_id, track_index, position, filename, updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                book_id,
                old_id,
                entry.get("track_index", 0),
                entry.get("position", 0.0),
                entry.get("filename", ""),
                entry.get("updated", ""),
            ),
        )
        count += 1
    if count:
        logger.info("    playback: %d entries", count)


def _migrate_collections(
    conn: sqlite3.Connection,
    user_id: str,
    user_dir: Path,
    folder_lookup: dict[str, int],
    norm_lookup: dict[str, int],
):
    """collections.json: [{name, books: [title1, title2, ...], description, created}]"""
    data = _load_json(user_dir / "collections.json", list)
    count = 0
    for coll in data:
        conn.execute(
            """
            INSERT INTO user_collections (user_id, name, description, created)
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                coll.get("name", ""),
                coll.get("description", ""),
                coll.get("created", ""),
            ),
        )
        coll_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        books = coll.get("books", [])
        for pos, book_name in enumerate(books):
            book_id = resolve_collection_book(book_name, folder_lookup, norm_lookup)
            conn.execute(
                """
                INSERT INTO collection_books (collection_id, book_id, book_name, position)
                VALUES (?, ?, ?, ?)
                """,
                (coll_id, book_id, book_name, pos),
            )
        count += 1
    if count:
        logger.info("    collections: %d", count)


def _migrate_book_status(
    conn: sqlite3.Connection,
    user_id: str,
    user_dir: Path,
    folder_lookup: dict[str, int],
    norm_lookup: dict[str, int],
):
    """book_status.json: {old_base64_id: {status, updated}}"""
    data = _load_json(user_dir / "book_status.json", dict)
    count = 0
    for old_id, entry in data.items():
        book_id = resolve_old_base64_id(old_id, folder_lookup, norm_lookup)
        conn.execute(
            """
            INSERT INTO user_book_status (user_id, book_id, old_book_id, status, updated)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                book_id,
                old_id,
                entry.get("status", ""),
                entry.get("updated", ""),
            ),
        )
        count += 1
    if count:
        logger.info("    book_status: %d entries", count)


def _migrate_quotes(
    conn: sqlite3.Connection,
    user_id: str,
    user_dir: Path,
    folder_lookup: dict[str, int],
    norm_lookup: dict[str, int],
):
    """quotes.json: [{text, book, author, ts}]"""
    data = _load_json(user_dir / "quotes.json", list)
    count = 0
    for entry in data:
        book_name = entry.get("book", "")
        book_id = resolve_book_name(book_name, folder_lookup, norm_lookup)
        conn.execute(
            """
            INSERT INTO user_quotes (user_id, book_id, text, book_name, author, ts)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                book_id,
                entry.get("text", ""),
                book_name,
                entry.get("author", ""),
                entry.get("ts", ""),
            ),
        )
        count += 1
    if count:
        logger.info("    quotes: %d entries", count)


def _migrate_sessions(
    conn: sqlite3.Connection,
    user_id: str,
    user_dir: Path,
    folder_lookup: dict[str, int],
    norm_lookup: dict[str, int],
):
    """sessions.json: [{book, start, end, minutes}]"""
    data = _load_json(user_dir / "sessions.json", list)
    count = 0
    for entry in data:
        book_name = entry.get("book", "")
        book_id = resolve_book_name(book_name, folder_lookup, norm_lookup)
        conn.execute(
            """
            INSERT INTO user_sessions (user_id, book_id, book_name, start_ts, end_ts, minutes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                book_id,
                book_name,
                entry.get("start", ""),
                entry.get("end"),
                entry.get("minutes", 0),
            ),
        )
        count += 1
    if count:
        logger.info("    sessions: %d entries", count)


def _migrate_bookmarks(
    conn: sqlite3.Connection,
    user_id: str,
    user_dir: Path,
    folder_lookup: dict[str, int],
    norm_lookup: dict[str, int],
):
    """bookmarks.json: {old_base64_id: [{track, time, note, ts}]}"""
    data = _load_json(user_dir / "bookmarks.json", dict)
    count = 0
    for old_id, bookmarks in data.items():
        book_id = resolve_old_base64_id(old_id, folder_lookup, norm_lookup)
        for bm in bookmarks:
            conn.execute(
                """
                INSERT INTO user_bookmarks (user_id, book_id, old_book_id, track, time, note, ts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    book_id,
                    old_id,
                    bm.get("track", 0),
                    bm.get("time", 0.0),
                    bm.get("note", ""),
                    bm.get("ts", ""),
                ),
            )
            count += 1
    if count:
        logger.info("    bookmarks: %d entries", count)


# ── Step 3: Verify ─────────────────────────────────────────────────────────


def verify(conn: sqlite3.Connection):
    """Print table row counts for verification."""
    tables = [
        "books",
        "tracks",
        "user_history",
        "user_notes",
        "user_tags",
        "user_progress",
        "user_playback",
        "user_collections",
        "collection_books",
        "user_book_status",
        "user_quotes",
        "user_sessions",
        "user_bookmarks",
    ]
    print("\n--- Verification ---")
    for table in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
        print(f"  {table}: {count}")

    # Count unresolved references (book_id IS NULL)
    unresolved_tables = [
        ("user_history", "book_id"),
        ("user_notes", "book_id"),
        ("user_tags", "book_id"),
        ("user_progress", "book_id"),
        ("user_playback", "book_id"),
        ("user_book_status", "book_id"),
        ("user_quotes", "book_id"),
        ("user_sessions", "book_id"),
        ("user_bookmarks", "book_id"),
        ("collection_books", "book_id"),
    ]
    print("\n--- Unresolved book references (NULL book_id) ---")
    for table, col in unresolved_tables:
        total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
        null_count = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL").fetchone()[0]  # noqa: S608
        if total > 0:
            pct = (null_count / total * 100) if total else 0
            print(f"  {table}: {null_count}/{total} unresolved ({pct:.0f}%)")


# ── Main ────────────────────────────────────────────────────────────────────


def main():
    from .db import DB_PATH, _get_conn, init_db

    print(f"Database: {DB_PATH}")
    print(f"Books dir: {BOOKS_DIR}")
    print(f"Data dir: {DATA_DIR}")
    print()

    # Initialize existing users table
    init_db()

    conn = _get_conn()
    conn.execute("PRAGMA foreign_keys=ON")

    # Create migration tables
    create_tables(conn)

    print("=== Step 1: Migrating books ===")
    migrate_books(conn, BOOKS_DIR)

    print("\n=== Step 2: Migrating user data ===")
    migrate_user_data(conn, DATA_DIR)

    print("\n=== Step 3: Verification ===")
    verify(conn)

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
