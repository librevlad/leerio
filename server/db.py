"""
server/db.py — SQLite database for authentication and all app data.

Manages users, books, tracks, and per-user data (statuses, progress,
playback, notes, tags, history, quotes, sessions, bookmarks, collections).
"""

import hashlib
import json
import logging
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("leerio.db")

# Resolve DATA_DIR here to avoid circular import with core.py
_BASE = Path(os.environ.get("LEERIO_BASE", str(Path(__file__).resolve().parent.parent)))
DATA_DIR = Path(os.environ.get("LEERIO_DATA", str(_BASE / "data")))

DB_PATH = DATA_DIR / "leerio.db"

SEED_EMAIL = "librevlad@gmail.com"
SEED_ROLE = "admin"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------


def init_db():
    """Create all tables and ensure seed data exists."""
    conn = _get_conn()
    try:
        # --- Auth tables ---
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL DEFAULT '',
                picture TEXT NOT NULL DEFAULT '',
                password_hash TEXT,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_login TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS allowed_emails (
                email TEXT PRIMARY KEY,
                added_by TEXT NOT NULL DEFAULT '',
                added_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        # --- Book catalogue ---
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY,
                slug TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                reader TEXT DEFAULT '',
                category TEXT DEFAULT '',
                folder TEXT NOT NULL,
                s3_prefix TEXT NOT NULL,
                has_cover BOOLEAN DEFAULT 0,
                mp3_count INTEGER DEFAULT 0,
                duration_hours REAL DEFAULT 0,
                size_mb REAL DEFAULT 0,
                language TEXT DEFAULT 'ru',
                source TEXT DEFAULT 'manual',
                external_id TEXT,
                fingerprint TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY,
                book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
                idx INTEGER NOT NULL,
                filename TEXT NOT NULL,
                s3_key TEXT NOT NULL,
                duration REAL DEFAULT 0,
                size_bytes INTEGER DEFAULT 0,
                UNIQUE(book_id, idx)
            )
            """
        )

        # --- Per-user data ---
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_book_status (
                user_id TEXT NOT NULL,
                book_id INTEGER NOT NULL REFERENCES books(id),
                status TEXT NOT NULL,
                updated TEXT DEFAULT (datetime('now')),
                PRIMARY KEY(user_id, book_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_progress (
                user_id TEXT NOT NULL,
                book_id INTEGER NOT NULL REFERENCES books(id),
                percent INTEGER DEFAULT 0,
                updated TEXT DEFAULT (datetime('now')),
                PRIMARY KEY(user_id, book_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_playback (
                user_id TEXT NOT NULL,
                book_id INTEGER NOT NULL,
                track_index INTEGER DEFAULT 0,
                position REAL DEFAULT 0,
                filename TEXT DEFAULT '',
                updated TEXT DEFAULT (datetime('now')),
                PRIMARY KEY(user_id, book_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_notes (
                user_id TEXT NOT NULL,
                book_id INTEGER NOT NULL REFERENCES books(id),
                note TEXT DEFAULT '',
                PRIMARY KEY(user_id, book_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_tags (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                book_id INTEGER NOT NULL REFERENCES books(id),
                tag TEXT NOT NULL,
                UNIQUE(user_id, book_id, tag)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_history (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                ts TEXT DEFAULT (datetime('now')),
                action TEXT NOT NULL,
                book_id INTEGER,
                book_title TEXT DEFAULT '',
                detail TEXT DEFAULT '',
                rating INTEGER DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_quotes (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                text TEXT NOT NULL,
                author TEXT DEFAULT '',
                book TEXT DEFAULT '',
                ts TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                book_title TEXT NOT NULL,
                started TEXT NOT NULL,
                ended TEXT,
                duration_min REAL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_bookmarks (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                book_id INTEGER NOT NULL,
                track_index INTEGER NOT NULL,
                position REAL NOT NULL,
                note TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_collections (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS collection_books (
                collection_id INTEGER REFERENCES user_collections(id) ON DELETE CASCADE,
                book_id INTEGER REFERENCES books(id),
                PRIMARY KEY(collection_id, book_id)
            )
            """
        )

        # --- Ingestion pipeline ---
        conn.execute(
            """
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
            """
        )

        conn.commit()
        _migrate_password_column(conn)
        _ensure_seed_user(conn)
        _seed_allowed_emails(conn)
    finally:
        conn.close()
    logger.info("Database initialized at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Auth helpers (unchanged)
# ---------------------------------------------------------------------------


def _migrate_password_column(conn: sqlite3.Connection):
    """Add password_hash column if missing (existing DBs)."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "password_hash" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        conn.commit()
        logger.info("Added password_hash column to users table")


def _hash_password(password: str) -> str:
    """Hash a password with a random salt using PBKDF2."""
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"{salt}:{h}"


def _verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored hash."""
    salt, h = stored.split(":", 1)
    check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return secrets.compare_digest(h, check)


def _ensure_seed_user(conn: sqlite3.Connection):
    """Create seed admin user if not exists."""
    row = conn.execute("SELECT user_id FROM users WHERE email = ?", (SEED_EMAIL,)).fetchone()
    if not row:
        user_id = hashlib.sha256(SEED_EMAIL.encode()).hexdigest()[:16]
        pw_hash = _hash_password(SEED_EMAIL)
        conn.execute(
            "INSERT INTO users (user_id, email, name, password_hash, role) VALUES (?, ?, ?, ?, ?)",
            (user_id, SEED_EMAIL, "Vlad", pw_hash, SEED_ROLE),
        )
        conn.commit()
        logger.info("Seed user created: %s (%s)", SEED_EMAIL, SEED_ROLE)
    else:
        # Ensure seed user has a password
        full = conn.execute("SELECT password_hash FROM users WHERE email = ?", (SEED_EMAIL,)).fetchone()
        if not full["password_hash"]:
            pw_hash = _hash_password(SEED_EMAIL)
            conn.execute("UPDATE users SET password_hash = ? WHERE email = ?", (pw_hash, SEED_EMAIL))
            conn.commit()
            logger.info("Seed user password set")


def _seed_allowed_emails(conn: sqlite3.Connection):
    """Seed allowed_emails from ALLOWED_EMAILS env var."""
    raw = os.environ.get("ALLOWED_EMAILS", "")
    if not raw:
        return
    for email in raw.split(","):
        email = email.strip()
        if email:
            conn.execute(
                "INSERT OR IGNORE INTO allowed_emails (email, added_by) VALUES (?, ?)",
                (email, "env"),
            )
    conn.commit()


def is_email_allowed(email: str) -> bool:
    """Check if email is allowed to register.

    Returns True if:
    - User already exists (returning users always allowed)
    - No entries in allowed_emails table (open registration)
    - Email is in allowed_emails table
    """
    conn = _get_conn()
    try:
        # Existing users always allowed
        row = conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            return True
        # If no restrictions configured, allow all
        count = conn.execute("SELECT COUNT(*) FROM allowed_emails").fetchone()[0]
        if count == 0:
            return True
        # Check allowlist
        row = conn.execute("SELECT 1 FROM allowed_emails WHERE email = ?", (email,)).fetchone()
        return row is not None
    finally:
        conn.close()


def add_allowed_email(email: str, added_by: str = "admin") -> bool:
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO allowed_emails (email, added_by) VALUES (?, ?)",
            (email, added_by),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def remove_allowed_email(email: str) -> bool:
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM allowed_emails WHERE email = ?", (email,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_allowed_emails() -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT email, added_by, added_at FROM allowed_emails ORDER BY added_at").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def verify_user_password(email: str, password: str) -> dict | None:
    """Verify email/password and return user dict, or None if invalid."""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row:
            return None
        user = dict(row)
        if not user.get("password_hash"):
            return None
        if not _verify_password(password, user["password_hash"]):
            return None
        # Update last_login
        conn.execute("UPDATE users SET last_login = datetime('now') WHERE email = ?", (email,))
        conn.commit()
        return user
    finally:
        conn.close()


def get_user_by_email(email: str) -> dict | None:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: str) -> dict | None:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_or_update_user(email: str, name: str, picture: str) -> dict:
    """Find existing user or create new one. Updates name/picture on login."""
    import hashlib

    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row:
            conn.execute(
                "UPDATE users SET name = ?, picture = ?, last_login = datetime('now') WHERE email = ?",
                (name, picture, email),
            )
            conn.commit()
            return dict(conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone())
        else:
            user_id = hashlib.sha256(email.encode()).hexdigest()[:16]
            conn.execute(
                "INSERT INTO users (user_id, email, name, picture, role, last_login) VALUES (?, ?, ?, ?, 'user', datetime('now'))",
                (user_id, email, name, picture),
            )
            conn.commit()
            logger.info("New user created: %s", email)
            return dict(conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone())
    finally:
        conn.close()


# ===========================================================================
# Books — sync from S3 or filesystem
# ===========================================================================


def sync_books():
    """Sync books into the database from S3 bucket (primary) or local filesystem (fallback).

    Existing books (matched by slug) are skipped. Safe to call on every startup.
    """
    from .storage import _get_client

    client = _get_client()
    if client:
        _sync_books_from_s3(client)
    else:
        _sync_books_from_filesystem()


def _sync_books_from_s3(client):
    """Scan S3 bucket and insert any new books into the database."""
    import os

    from .core import make_slug, parse_folder_name

    bucket = os.environ.get("S3_BUCKET", "leerio-books")

    conn = _get_conn()
    try:
        existing_slugs = {r[0] for r in conn.execute("SELECT slug FROM books").fetchall()}
        inserted = 0

        # List top-level prefixes (categories)
        cat_resp = client.list_objects_v2(Bucket=bucket, Delimiter="/")
        categories = [p["Prefix"].rstrip("/") for p in cat_resp.get("CommonPrefixes", [])]

        for cat in categories:
            # List all objects in category, collect mp3s and covers per folder
            paginator = client.get_paginator("list_objects_v2")
            book_mp3s: dict[str, list[str]] = {}  # folder -> [mp3 keys]
            book_covers: set[str] = set()  # folders that have a cover file

            for page in paginator.paginate(Bucket=bucket, Prefix=f"{cat}/"):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    # key looks like "Бизнес/Author - Title [Reader]/file.mp3"
                    parts = key.split("/", 2)
                    if len(parts) < 3:
                        continue
                    folder = parts[1]
                    filename = parts[2].lower()
                    if filename.endswith(".mp3"):
                        book_mp3s.setdefault(folder, []).append(key)
                    elif filename.startswith("cover"):
                        book_covers.add(folder)

            for folder, mp3_keys in sorted(book_mp3s.items()):
                author, title, reader = parse_folder_name(folder)
                slug = make_slug(title, author)

                s3_prefix = f"{cat}/{folder}"
                has_cover = int(folder in book_covers)

                if slug in existing_slugs:
                    # Update has_cover for existing books (may have been wrong on first sync)
                    conn.execute(
                        "UPDATE books SET has_cover = ? WHERE slug = ?",
                        (has_cover, slug),
                    )
                    continue

                conn.execute(
                    """INSERT INTO books (slug, title, author, reader, category, folder,
                       s3_prefix, has_cover, mp3_count)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (slug, title, author, reader or "", cat, folder, s3_prefix, has_cover, len(mp3_keys)),
                )
                existing_slugs.add(slug)
                inserted += 1

                # Insert tracks
                book_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                for idx, s3_key in enumerate(sorted(mp3_keys)):
                    filename = s3_key.rsplit("/", 1)[-1]
                    conn.execute(
                        "INSERT INTO tracks (book_id, idx, filename, s3_key) VALUES (?, ?, ?, ?)",
                        (book_id, idx, filename, s3_key),
                    )

        conn.commit()
        if inserted:
            logger.info("Synced %d new books from S3", inserted)
    finally:
        conn.close()


def _sync_books_from_filesystem():
    """Scan BOOKS_DIR and insert any new books into the database (fallback when S3 not configured)."""
    from .core import (
        BOOKS_DIR,
        CATEGORIES,
        count_mp3,
        estimate_duration_hours,
        folder_size_mb,
        make_slug,
        parse_folder_name,
    )

    conn = _get_conn()
    try:
        existing_slugs = {r[0] for r in conn.execute("SELECT slug FROM books").fetchall()}
        inserted = 0

        for cat in CATEGORIES:
            cat_dir = BOOKS_DIR / cat
            if not cat_dir.is_dir():
                continue
            for book_dir in sorted(cat_dir.iterdir()):
                if not book_dir.is_dir():
                    continue
                folder = book_dir.name
                author, title, reader = parse_folder_name(folder)
                slug = make_slug(title, author)

                if slug in existing_slugs:
                    continue

                mp3_count = count_mp3(book_dir)
                if mp3_count == 0:
                    continue

                has_cover = any(book_dir.glob("cover.*"))
                duration_hours = estimate_duration_hours(book_dir) or 0.0
                size_mb = folder_size_mb(book_dir)
                s3_prefix = f"{cat}/{folder}"

                conn.execute(
                    """INSERT INTO books (slug, title, author, reader, category, folder,
                       s3_prefix, has_cover, mp3_count, duration_hours, size_mb)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        slug,
                        title,
                        author,
                        reader or "",
                        cat,
                        folder,
                        s3_prefix,
                        int(has_cover),
                        mp3_count,
                        duration_hours,
                        size_mb,
                    ),
                )
                existing_slugs.add(slug)
                inserted += 1

                book_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                mp3s = sorted(book_dir.rglob("*.mp3"), key=lambda f: str(f))
                for idx, mp3 in enumerate(mp3s):
                    conn.execute(
                        "INSERT INTO tracks (book_id, idx, filename, s3_key) VALUES (?, ?, ?, ?)",
                        (book_id, idx, mp3.name, f"{s3_prefix}/{mp3.name}"),
                    )

        conn.commit()
        if inserted:
            logger.info("Synced %d new books from filesystem", inserted)
    finally:
        conn.close()


# ===========================================================================
# Books CRUD
# ===========================================================================


def get_all_books() -> list[dict]:
    """Return all books."""
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT * FROM books ORDER BY title").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_book_by_id(book_id: int) -> dict | None:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_book_by_slug(slug: str) -> dict | None:
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM books WHERE slug = ?", (slug,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def search_books(category: str | None = None, search: str | None = None, sort: str = "title") -> list[dict]:
    """Search books with optional category filter, text search, and sort."""
    conn = _get_conn()
    try:
        clauses: list[str] = []
        params: list[str] = []
        if category:
            clauses.append("category = ?")
            params.append(category)
        if search:
            clauses.append("(title LIKE ? OR author LIKE ? OR reader LIKE ?)")
            q = f"%{search}%"
            params.extend([q, q, q])
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        allowed_sorts = {"title": "title", "author": "author", "created_at": "created_at"}
        order = allowed_sorts.get(sort, "title")
        rows = conn.execute(f"SELECT * FROM books{where} ORDER BY {order}", params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_book_tracks(book_id: int) -> list[dict]:
    """Return tracks for a book ordered by index."""
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT * FROM tracks WHERE book_id = ? ORDER BY idx", (book_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ===========================================================================
# User Book Status
# ===========================================================================


def get_user_book_status(user_id: str, book_id: int) -> dict | None:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT status, updated FROM user_book_status WHERE user_id = ? AND book_id = ?",
            (user_id, book_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_user_book_status(user_id: str, book_id: int, status: str):
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO user_book_status (user_id, book_id, status, updated)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(user_id, book_id) DO UPDATE SET status=excluded.status, updated=excluded.updated""",
            (user_id, book_id, status),
        )
        conn.commit()
    finally:
        conn.close()


def remove_user_book_status(user_id: str, book_id: int):
    conn = _get_conn()
    try:
        conn.execute(
            "DELETE FROM user_book_status WHERE user_id = ? AND book_id = ?",
            (user_id, book_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_user_book_statuses(user_id: str) -> dict:
    """Return {book_id: {status, updated}} for the user."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT book_id, status, updated FROM user_book_status WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        return {r["book_id"]: {"status": r["status"], "updated": r["updated"]} for r in rows}
    finally:
        conn.close()


# ===========================================================================
# User Progress
# ===========================================================================


def get_user_progress(user_id: str, book_id: int) -> int:
    """Return progress percent (0 if not set)."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT percent FROM user_progress WHERE user_id = ? AND book_id = ?",
            (user_id, book_id),
        ).fetchone()
        return row["percent"] if row else 0
    finally:
        conn.close()


def set_user_progress(user_id: str, book_id: int, percent: int):
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO user_progress (user_id, book_id, percent, updated)
               VALUES (?, ?, ?, datetime('now'))
               ON CONFLICT(user_id, book_id) DO UPDATE SET percent=excluded.percent, updated=excluded.updated""",
            (user_id, book_id, percent),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_user_progress(user_id: str) -> dict:
    """Return {book_id: {pct, updated}}."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT book_id, percent, updated FROM user_progress WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        return {r["book_id"]: {"pct": r["percent"], "updated": r["updated"]} for r in rows}
    finally:
        conn.close()


# ===========================================================================
# User Playback
# ===========================================================================


def get_user_playback(user_id: str, book_id: int) -> dict | None:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT track_index, position, filename, updated FROM user_playback WHERE user_id = ? AND book_id = ?",
            (user_id, book_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_user_playback(user_id: str, book_id: int, track_index: int, position: float, filename: str = ""):
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO user_playback (user_id, book_id, track_index, position, filename, updated)
               VALUES (?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(user_id, book_id) DO UPDATE
               SET track_index=excluded.track_index, position=excluded.position,
                   filename=excluded.filename, updated=excluded.updated""",
            (user_id, book_id, track_index, position, filename),
        )
        conn.commit()
    finally:
        conn.close()


# ===========================================================================
# User Notes
# ===========================================================================


def get_user_note(user_id: str, book_id: int) -> str:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT note FROM user_notes WHERE user_id = ? AND book_id = ?",
            (user_id, book_id),
        ).fetchone()
        return row["note"] if row else ""
    finally:
        conn.close()


def set_user_note(user_id: str, book_id: int, note: str):
    conn = _get_conn()
    try:
        if not note:
            conn.execute(
                "DELETE FROM user_notes WHERE user_id = ? AND book_id = ?",
                (user_id, book_id),
            )
        else:
            conn.execute(
                """INSERT INTO user_notes (user_id, book_id, note)
                   VALUES (?, ?, ?)
                   ON CONFLICT(user_id, book_id) DO UPDATE SET note=excluded.note""",
                (user_id, book_id, note),
            )
        conn.commit()
    finally:
        conn.close()


# ===========================================================================
# User Tags
# ===========================================================================


def get_user_tags(user_id: str, book_id: int) -> list[str]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT tag FROM user_tags WHERE user_id = ? AND book_id = ?",
            (user_id, book_id),
        ).fetchall()
        return [r["tag"] for r in rows]
    finally:
        conn.close()


def set_user_tags(user_id: str, book_id: int, tags: list[str]):
    """Replace all tags for a user/book with the given list."""
    conn = _get_conn()
    try:
        conn.execute(
            "DELETE FROM user_tags WHERE user_id = ? AND book_id = ?",
            (user_id, book_id),
        )
        for tag in tags:
            tag = tag.strip()
            if tag:
                conn.execute(
                    "INSERT OR IGNORE INTO user_tags (user_id, book_id, tag) VALUES (?, ?, ?)",
                    (user_id, book_id, tag),
                )
        conn.commit()
    finally:
        conn.close()


def get_all_user_tags(user_id: str) -> list[str]:
    """Return all unique tags for a user across all books."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT DISTINCT tag FROM user_tags WHERE user_id = ? ORDER BY tag",
            (user_id,),
        ).fetchall()
        return [r["tag"] for r in rows]
    finally:
        conn.close()


# ===========================================================================
# User History
# ===========================================================================


def get_user_history(
    user_id: str, action: str | None = None, search: str | None = None, limit: int = 100
) -> list[dict]:
    conn = _get_conn()
    try:
        clauses = ["user_id = ?"]
        params: list = [user_id]
        if action:
            clauses.append("action = ?")
            params.append(action)
        if search:
            clauses.append("(book_title LIKE ? OR detail LIKE ?)")
            q = f"%{search}%"
            params.extend([q, q])
        where = " WHERE " + " AND ".join(clauses)
        params.append(limit)
        rows = conn.execute(f"SELECT * FROM user_history{where} ORDER BY ts DESC LIMIT ?", params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_user_history(
    user_id: str, action: str, book_id: int | None = None, book_title: str = "", detail: str = "", rating: int = 0
):
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO user_history (user_id, action, book_id, book_title, detail, rating) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, action, book_id, book_title, detail, rating),
        )
        conn.commit()
    finally:
        conn.close()


# ===========================================================================
# User Quotes
# ===========================================================================


def get_user_quotes(user_id: str) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM user_quotes WHERE user_id = ? ORDER BY ts DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_user_quote(user_id: str, text: str, book: str = "", author: str = ""):
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO user_quotes (user_id, text, book, author) VALUES (?, ?, ?, ?)",
            (user_id, text, book, author),
        )
        conn.commit()
    finally:
        conn.close()


def delete_user_quote(user_id: str, quote_id: int):
    conn = _get_conn()
    try:
        conn.execute(
            "DELETE FROM user_quotes WHERE id = ? AND user_id = ?",
            (quote_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()


# ===========================================================================
# User Sessions
# ===========================================================================


def get_user_sessions(user_id: str) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM user_sessions WHERE user_id = ? ORDER BY started DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def start_user_session(user_id: str, book_title: str) -> dict:
    """Start a listening session. Returns the created session dict."""
    conn = _get_conn()
    try:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.execute(
            "INSERT INTO user_sessions (user_id, book_title, started) VALUES (?, ?, ?)",
            (user_id, book_title, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM user_sessions WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def stop_user_session(user_id: str, book_title: str) -> float:
    """Stop the most recent open session for this book. Returns duration in minutes."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT id, started FROM user_sessions WHERE user_id = ? AND book_title = ? AND ended IS NULL ORDER BY started DESC LIMIT 1",
            (user_id, book_title),
        ).fetchone()
        if not row:
            return 0.0
        started = datetime.strptime(row["started"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        duration_min = (now - started).total_seconds() / 60.0
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE user_sessions SET ended = ?, duration_min = ? WHERE id = ?",
            (now_str, round(duration_min, 2), row["id"]),
        )
        conn.commit()
        return round(duration_min, 2)
    finally:
        conn.close()


def get_session_stats(user_id: str, days: int = 7) -> dict:
    """Return {total_hours, today_min, week_hours, peak_hour}."""
    conn = _get_conn()
    try:
        # Total hours across all time
        total_row = conn.execute(
            "SELECT COALESCE(SUM(duration_min), 0) as total FROM user_sessions WHERE user_id = ? AND duration_min > 0",
            (user_id,),
        ).fetchone()
        total_hours = round(total_row["total"] / 60.0, 2)

        # Today's minutes
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_row = conn.execute(
            "SELECT COALESCE(SUM(duration_min), 0) as total FROM user_sessions WHERE user_id = ? AND started LIKE ?",
            (user_id, f"{today_str}%"),
        ).fetchone()
        today_min = round(today_row["total"], 1)

        # Last N days hours
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        week_row = conn.execute(
            "SELECT COALESCE(SUM(duration_min), 0) as total FROM user_sessions WHERE user_id = ? AND started >= ?",
            (user_id, cutoff),
        ).fetchone()
        week_hours = round(week_row["total"] / 60.0, 2)

        # Peak hour (most sessions started)
        peak_row = conn.execute(
            """SELECT CAST(strftime('%H', started) AS INTEGER) as hour, COUNT(*) as cnt
               FROM user_sessions WHERE user_id = ?
               GROUP BY hour ORDER BY cnt DESC LIMIT 1""",
            (user_id,),
        ).fetchone()
        peak_hour = peak_row["hour"] if peak_row else 0

        return {
            "total_hours": total_hours,
            "today_min": today_min,
            "week_hours": week_hours,
            "peak_hour": peak_hour,
        }
    finally:
        conn.close()


# ===========================================================================
# User Bookmarks
# ===========================================================================


def get_user_bookmarks(user_id: str, book_id: int) -> list[dict]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM user_bookmarks WHERE user_id = ? AND book_id = ? ORDER BY created_at",
            (user_id, book_id),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_user_bookmark(user_id: str, book_id: int, track_index: int, position: float, note: str = "") -> dict:
    conn = _get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO user_bookmarks (user_id, book_id, track_index, position, note) VALUES (?, ?, ?, ?, ?)",
            (user_id, book_id, track_index, position, note),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM user_bookmarks WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def remove_user_bookmark(user_id: str, bookmark_id: int) -> bool:
    conn = _get_conn()
    try:
        cur = conn.execute(
            "DELETE FROM user_bookmarks WHERE id = ? AND user_id = ?",
            (bookmark_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ===========================================================================
# User Collections
# ===========================================================================


def get_user_collections(user_id: str) -> list[dict]:
    """Return collections with their book lists."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM user_collections WHERE user_id = ? ORDER BY created_at",
            (user_id,),
        ).fetchall()
        result = []
        for r in rows:
            c = dict(r)
            book_rows = conn.execute(
                "SELECT book_id FROM collection_books WHERE collection_id = ?",
                (c["id"],),
            ).fetchall()
            c["books"] = [br["book_id"] for br in book_rows]
            result.append(c)
        return result
    finally:
        conn.close()


def create_user_collection(user_id: str, name: str, book_ids: list[int] | None = None, description: str = "") -> int:
    """Create a collection and return its id."""
    conn = _get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO user_collections (user_id, name, description) VALUES (?, ?, ?)",
            (user_id, name, description),
        )
        coll_id = cur.lastrowid
        for bid in book_ids or []:
            conn.execute(
                "INSERT OR IGNORE INTO collection_books (collection_id, book_id) VALUES (?, ?)",
                (coll_id, bid),
            )
        conn.commit()
        return coll_id
    finally:
        conn.close()


def update_user_collection(user_id: str, collection_id: int, name: str, book_ids: list[int], description: str):
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE user_collections SET name = ?, description = ? WHERE id = ? AND user_id = ?",
            (name, description, collection_id, user_id),
        )
        conn.execute("DELETE FROM collection_books WHERE collection_id = ?", (collection_id,))
        for bid in book_ids:
            conn.execute(
                "INSERT OR IGNORE INTO collection_books (collection_id, book_id) VALUES (?, ?)",
                (collection_id, bid),
            )
        conn.commit()
    finally:
        conn.close()


def delete_user_collection(user_id: str, collection_id: int) -> bool:
    conn = _get_conn()
    try:
        cur = conn.execute(
            "DELETE FROM user_collections WHERE id = ? AND user_id = ?",
            (collection_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ===========================================================================
# Batch queries (for list views — avoid N+1)
# ===========================================================================


def get_all_user_notes_map(user_id: str) -> dict[int, str]:
    """Return {book_id: note} for all books with notes."""
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT book_id, note FROM user_notes WHERE user_id = ?", (user_id,)).fetchall()
        return {r["book_id"]: r["note"] for r in rows}
    finally:
        conn.close()


def get_all_user_tags_map(user_id: str) -> dict[int, list[str]]:
    """Return {book_id: [tag1, tag2, ...]} for all books with tags."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT book_id, tag FROM user_tags WHERE user_id = ? ORDER BY book_id", (user_id,)
        ).fetchall()
        result: dict[int, list[str]] = {}
        for r in rows:
            result.setdefault(r["book_id"], []).append(r["tag"])
        return result
    finally:
        conn.close()


def get_user_history_for_book(user_id: str, book_id: int) -> list[dict]:
    """Return history entries for a specific book."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM user_history WHERE user_id = ? AND book_id = ? ORDER BY ts DESC",
            (user_id, book_id),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_user_rating(user_id: str, book_id: int) -> int:
    """Return the rating from the most recent 'done' history entry for a book."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT rating FROM user_history WHERE user_id = ? AND book_id = ? AND action = 'done' AND rating > 0 ORDER BY ts DESC LIMIT 1",
            (user_id, book_id),
        ).fetchone()
        return row["rating"] if row else 0
    finally:
        conn.close()


def get_categories() -> list[str]:
    """Return distinct categories from the books table."""
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT DISTINCT category FROM books WHERE category != '' ORDER BY category").fetchall()
        return [r["category"] for r in rows]
    finally:
        conn.close()


# ── Ingestion Jobs ─────────────────────────────────────────────────────────


def create_ingestion_job(source: str, input_data: dict, timeout_seconds: int = 600) -> int:
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


def update_ingestion_job(job_id: int, status: str | None = None, result: dict | None = None) -> None:
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
