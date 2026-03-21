"""
server/db.py — SQLite database for authentication and all app data.

Manages users, books, tracks, and per-user data (statuses, progress,
playback, notes, tags, history, quotes, sessions, bookmarks, collections).
"""

import hashlib
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger("leerio.db")

# Resolve DATA_DIR here to avoid circular import with core.py
_BASE = Path(os.environ.get("LEERIO_BASE", str(Path(__file__).resolve().parent.parent)))
DATA_DIR = Path(os.environ.get("LEERIO_DATA", str(_BASE / "data")))

DB_PATH = DATA_DIR / "leerio.db"

SEED_EMAIL = "librevlad@gmail.com"
SEED_ROLE = "admin"


_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


def _fresh_conn() -> sqlite3.Connection:
    """Create a new connection (for init_db and one-off setup tasks)."""
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
    # Clear any thread-local connection (DB_PATH may have changed)
    _local.conn = None
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _fresh_conn()
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
                plan TEXT NOT NULL DEFAULT 'free',
                paddle_customer_id TEXT,
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
                description TEXT DEFAULT '',
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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_history_user_ts ON user_history(user_id, ts)")
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

        # --- User settings ---
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id TEXT PRIMARY KEY,
                yearly_goal INTEGER DEFAULT 24,
                playback_speed REAL DEFAULT 1.0
            )
            """
        )

        # --- Categories ---
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                color TEXT NOT NULL DEFAULT '#94a3b8',
                gradient TEXT NOT NULL DEFAULT 'linear-gradient(135deg, #334155 0%, #64748b 100%)',
                sort_order INTEGER NOT NULL DEFAULT 0
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

        # --- Verification codes ---
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS verification_codes (
                email TEXT NOT NULL,
                code TEXT NOT NULL,
                type TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at TEXT NOT NULL
            )
            """
        )

        conn.commit()
        _migrate_password_column(conn)
        _migrate_active_column(conn)
        _migrate_categories(conn)
        _migrate_history_titles(conn)
        _ensure_seed_user(conn)
        _seed_allowed_emails(conn)
        _seed_categories(conn)
    finally:
        conn.close()
    logger.info("Database initialized at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Auth helpers (unchanged)
# ---------------------------------------------------------------------------


def _migrate_categories(conn: sqlite3.Connection):
    """Normalize bad category values from S3 sync (e.g. 'books' -> 'Художественная', '.' -> 'Художественная')."""
    mapping = {
        "books": "Художественная",
        "Другое": "Художественная",
        ".": "Художественная",
        "": "Художественная",
    }
    total = 0
    for old_cat, new_cat in mapping.items():
        updated = conn.execute("UPDATE books SET category = ? WHERE category = ?", (new_cat, old_cat)).rowcount
        total += updated
    if total:
        conn.commit()
        logger.info("Fixed %d books with bad category values", total)


def _migrate_history_titles(conn: sqlite3.Connection):
    """Fix history entries where book_title was stored as folder/slug instead of real title."""
    updated = conn.execute(
        """
        UPDATE user_history SET book_title = (
            SELECT b.title FROM books b WHERE b.id = user_history.book_id
        )
        WHERE book_id IS NOT NULL
          AND book_id IN (SELECT id FROM books)
          AND book_title != (SELECT b.title FROM books b WHERE b.id = user_history.book_id)
        """
    ).rowcount
    if updated:
        conn.commit()
        logger.info("Fixed %d history entries with incorrect book_title", updated)


def _migrate_password_column(conn: sqlite3.Connection):
    """Add password_hash column if missing (existing DBs)."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if "password_hash" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        conn.commit()
        logger.info("Added password_hash column to users table")


def _migrate_active_column(conn: sqlite3.Connection):
    """Add active column if missing (existing DBs)."""
    try:
        conn.execute("ALTER TABLE users ADD COLUMN active INTEGER DEFAULT 1")
        conn.commit()
        logger.info("Added active column to users table")
    except Exception:
        pass  # Column already exists


def _hash_password(password: str) -> str:
    """Hash a password with a random salt using PBKDF2."""
    from .constants import PBKDF2_ALGORITHM, PBKDF2_ITERATIONS

    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac(PBKDF2_ALGORITHM, password.encode(), salt.encode(), PBKDF2_ITERATIONS).hex()
    return f"{salt}:{h}"


def _verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored hash."""
    from .constants import PBKDF2_ALGORITHM, PBKDF2_ITERATIONS

    try:
        salt, h = stored.split(":", 1)
    except ValueError:
        return False
    check = hashlib.pbkdf2_hmac(PBKDF2_ALGORITHM, password.encode(), salt.encode(), PBKDF2_ITERATIONS).hex()
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


def add_allowed_email(email: str, added_by: str = "admin") -> bool:
    conn = _get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO allowed_emails (email, added_by) VALUES (?, ?)",
        (email, added_by),
    )
    conn.commit()
    return True


def remove_allowed_email(email: str) -> bool:
    conn = _get_conn()
    cur = conn.execute("DELETE FROM allowed_emails WHERE email = ?", (email,))
    conn.commit()
    return cur.rowcount > 0


def list_allowed_emails() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT email, added_by, added_at FROM allowed_emails ORDER BY added_at").fetchall()
    return [dict(r) for r in rows]


def verify_user_password(email: str, password: str) -> dict | None:
    """Verify email/password and return user dict, or None if invalid."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not row:
        return None
    user = dict(row)
    if not user.get("active", 1):
        return None  # Inactive users can't login
    if not user.get("password_hash"):
        return None
    if not _verify_password(password, user["password_hash"]):
        return None
    # Update last_login
    conn.execute("UPDATE users SET last_login = datetime('now') WHERE email = ?", (email,))
    conn.commit()
    return user


def get_user_by_email(email: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def register_user(email: str, name: str, password: str) -> str:
    """Create inactive user with hashed password. Returns user_id."""
    user_id = secrets.token_hex(8)
    pw_hash = _hash_password(password)
    conn = _get_conn()
    conn.execute(
        "INSERT INTO users (user_id, email, name, password_hash, role, plan, active) VALUES (?, ?, ?, ?, 'user', 'free', 0)",
        (user_id, email, name, pw_hash),
    )
    conn.commit()
    return user_id


def activate_user(email: str):
    """Mark user as active (email verified)."""
    conn = _get_conn()
    conn.execute("UPDATE users SET active = 1 WHERE email = ?", (email,))
    conn.commit()


def create_verification_code(email: str, code_type: str) -> str:
    """Generate 6-digit code, store in DB, return code string."""
    code = str(secrets.randbelow(900000) + 100000)
    expires = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
    conn = _get_conn()
    conn.execute("DELETE FROM verification_codes WHERE expires_at < datetime('now')")
    conn.execute("DELETE FROM verification_codes WHERE email = ? AND type = ?", (email, code_type))
    conn.execute(
        "INSERT INTO verification_codes (email, code, type, expires_at) VALUES (?, ?, ?, ?)",
        (email, code, code_type, expires),
    )
    conn.commit()
    return code


def verify_code(email: str, code: str, code_type: str) -> bool:
    """Check code validity. Increments attempts on failure. Returns True if valid."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT code, attempts FROM verification_codes WHERE email = ? AND type = ? AND expires_at > datetime('now')",
        (email, code_type),
    ).fetchone()
    if not row:
        return False
    if row[1] >= 5:
        return False
    if row[0] != code:
        conn.execute(
            "UPDATE verification_codes SET attempts = attempts + 1 WHERE email = ? AND type = ?",
            (email, code_type),
        )
        conn.commit()
        return False
    conn.execute("DELETE FROM verification_codes WHERE email = ? AND type = ?", (email, code_type))
    conn.commit()
    return True


def update_user_password(email: str, password: str):
    """Update password hash for existing user."""
    pw_hash = _hash_password(password)
    conn = _get_conn()
    conn.execute("UPDATE users SET password_hash = ? WHERE email = ?", (pw_hash, email))
    conn.commit()


def create_or_update_user(email: str, name: str, picture: str) -> dict:
    """Find existing user or create new one. Updates name/picture on login."""
    conn = _get_conn()
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
        # Check for hash collision — different email producing same user_id
        existing = conn.execute("SELECT email FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if existing and existing["email"] != email:
            raise RuntimeError(f"User ID collision: {email!r} collides with {existing['email']!r} (id={user_id})")
        conn.execute(
            "INSERT INTO users (user_id, email, name, picture, role, last_login) VALUES (?, ?, ?, ?, 'user', datetime('now'))",
            (user_id, email, name, picture),
        )
        conn.commit()
        logger.info("New user created: %s", email)
        return dict(conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone())


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
    existing_slugs = {r[0] for r in conn.execute("SELECT slug FROM books").fetchall()}
    existing_prefixes = {
        r[0]
        for r in conn.execute("SELECT s3_prefix FROM books WHERE s3_prefix IS NOT NULL AND s3_prefix != ''").fetchall()
    }
    inserted = 0

    # List top-level prefixes (categories)
    cat_resp = client.list_objects_v2(Bucket=bucket, Delimiter="/")
    categories = [p["Prefix"].rstrip("/") for p in cat_resp.get("CommonPrefixes", [])]

    # Normalize category names from S3 prefixes
    cat_norm = {
        "books": "Художественная",
        "Другое": "Художественная",
        ".": "Художественная",
        "": "Художественная",
    }

    for cat in categories:
        # List all objects in category, collect mp3s and covers per folder
        paginator = client.get_paginator("list_objects_v2")
        book_mp3s: dict[str, list[str]] = {}  # folder -> [mp3 keys]
        book_covers: dict[str, str] = {}  # folder -> cover S3 key
        _cover_names = {"cover.jpg", "cover.jpeg", "cover.png", "cover.webp"}

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
                elif filename in _cover_names:
                    book_covers[folder] = key

        display_cat = cat_norm.get(cat, cat)

        for folder, mp3_keys in sorted(book_mp3s.items()):
            author, title, reader = parse_folder_name(folder)
            slug = make_slug(title, author)

            # Detect language by title+author characters:
            # є, ї, ґ → Ukrainian (unique letters);
            # ё, ъ, ы or any Cyrillic → Russian;
            # Only Latin → English
            text = f"{title} {author}"
            has_cyrillic = bool(re.search(r"[а-яА-ЯёЁіІєЄїЇґҐъЪыЫ]", text))
            if re.search(r"[єЄїЇґҐ]", text):
                lang = "uk"
            elif has_cyrillic:
                lang = "ru"
            elif re.search(r"[a-zA-Z]", text):
                lang = "en"
            else:
                lang = "ru"

            s3_prefix = f"{cat}/{folder}"
            has_cover = int(folder in book_covers)

            if s3_prefix in existing_prefixes:
                # Update has_cover for existing books (don't overwrite manual language)
                conn.execute(
                    "UPDATE books SET has_cover = ? WHERE s3_prefix = ?",
                    (has_cover, s3_prefix),
                )
                continue

            # For same title+author with different reader, append reader to slug
            if slug in existing_slugs and reader:
                slug = f"{slug}-{make_slug(reader)}"

            conn.execute(
                """INSERT INTO books (slug, title, author, reader, category, folder,
                   s3_prefix, has_cover, mp3_count, language)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (slug, title, author, reader or "", display_cat, folder, s3_prefix, has_cover, len(mp3_keys), lang),
            )
            existing_slugs.add(slug)
            existing_prefixes.add(s3_prefix)
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
    existing_slugs = {r[0] for r in conn.execute("SELECT slug FROM books").fetchall()}
    existing_prefixes = {
        r[0]
        for r in conn.execute("SELECT s3_prefix FROM books WHERE s3_prefix IS NOT NULL AND s3_prefix != ''").fetchall()
    }
    inserted = 0

    for cat in CATEGORIES:
        cat_dir = BOOKS_DIR / cat
        if not cat_dir.is_dir():
            continue
        for book_dir in sorted(cat_dir.iterdir()):
            if not book_dir.is_dir():
                continue
            folder = book_dir.name
            s3_prefix = f"{cat}/{folder}"

            # Deduplicate by s3_prefix (folder path) — prevents double insert on re-sync
            if s3_prefix in existing_prefixes:
                continue

            author, title, reader = parse_folder_name(folder)
            slug = make_slug(title, author)
            if slug in existing_slugs and reader:
                slug = f"{slug}-{make_slug(reader)}"

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


# ===========================================================================
# User Settings
# ===========================================================================


def get_user_settings(user_id: str) -> dict:
    """Return user settings, creating defaults if missing."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
    if row:
        return dict(row)
    # Create defaults
    conn.execute("INSERT INTO user_settings (user_id) VALUES (?)", (user_id,))
    conn.commit()
    return {"user_id": user_id, "yearly_goal": 24, "playback_speed": 1.0}


def update_user_settings(user_id: str, **kwargs) -> dict:
    """Update specific user settings fields."""
    allowed = {"yearly_goal", "playback_speed"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return get_user_settings(user_id)
    conn = _get_conn()
    # Ensure row exists
    conn.execute("INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)", (user_id,))
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [user_id]
    conn.execute(f"UPDATE user_settings SET {sets} WHERE user_id = ?", vals)
    conn.commit()
    return get_user_settings(user_id)


# ===========================================================================
# Books CRUD
# ===========================================================================


def _ghost_filter() -> str:
    """SQL clause to exclude ghost books (numeric-only title, no author)."""
    return "NOT (author = '' AND title GLOB '[0-9]*' AND length(title) <= 4)"


def get_all_books() -> list[dict]:
    """Return all books (excluding ghost books)."""
    conn = _get_conn()
    rows = conn.execute(f"SELECT * FROM books WHERE {_ghost_filter()} ORDER BY title").fetchall()
    return [dict(r) for r in rows]


def get_book_by_id(book_id: int) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    return dict(row) if row else None


def get_book_by_slug(slug: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM books WHERE slug = ?", (slug,)).fetchone()
    return dict(row) if row else None


def search_books(
    category: str | None = None, search: str | None = None, sort: str = "title", language: str | None = None
) -> list[dict]:
    """Search books with optional category filter, text search, and sort."""
    conn = _get_conn()
    clauses: list[str] = []
    params: list[str] = []
    # Exclude ghost books: numeric-only title with no author
    clauses.append(_ghost_filter())
    if category:
        clauses.append("category = ?")
        params.append(category)
    if language:
        clauses.append("language = ?")
        params.append(language)
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        clauses.append("(title LIKE ? ESCAPE '\\' OR author LIKE ? ESCAPE '\\' OR reader LIKE ? ESCAPE '\\')")
        q = f"%{escaped}%"
        params.extend([q, q, q])
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    allowed_sorts = {"title": "title", "author": "author", "created_at": "created_at", "recent": "id DESC"}
    order = allowed_sorts.get(sort, "title")
    rows = conn.execute(f"SELECT * FROM books{where} ORDER BY {order}", params).fetchall()
    return [dict(r) for r in rows]


def get_book_tracks(book_id: int) -> list[dict]:
    """Return tracks for a book ordered by index."""
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM tracks WHERE book_id = ? ORDER BY idx", (book_id,)).fetchall()
    return [dict(r) for r in rows]


# ===========================================================================
# User Book Status
# ===========================================================================


def get_user_book_status(user_id: str, book_id: int) -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT status, updated FROM user_book_status WHERE user_id = ? AND book_id = ?",
        (user_id, book_id),
    ).fetchone()
    return dict(row) if row else None


def set_user_book_status(user_id: str, book_id: int, status: str):
    conn = _get_conn()
    conn.execute(
        """INSERT INTO user_book_status (user_id, book_id, status, updated)
           VALUES (?, ?, ?, datetime('now'))
           ON CONFLICT(user_id, book_id) DO UPDATE SET status=excluded.status, updated=excluded.updated""",
        (user_id, book_id, status),
    )
    conn.commit()


def remove_user_book_status(user_id: str, book_id: int):
    conn = _get_conn()
    conn.execute(
        "DELETE FROM user_book_status WHERE user_id = ? AND book_id = ?",
        (user_id, book_id),
    )
    conn.commit()


def get_all_user_book_statuses(user_id: str) -> dict:
    """Return {book_id: {status, updated}} for the user."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT book_id, status, updated FROM user_book_status WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return {str(r["book_id"]): {"status": r["status"], "updated": r["updated"]} for r in rows}


# ===========================================================================
# User Progress
# ===========================================================================


def get_user_progress(user_id: str, book_id: int) -> int:
    """Return progress percent (0 if not set)."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT percent FROM user_progress WHERE user_id = ? AND book_id = ?",
        (user_id, book_id),
    ).fetchone()
    return row["percent"] if row else 0


def set_user_progress(user_id: str, book_id: int, percent: int):
    conn = _get_conn()
    conn.execute(
        """INSERT INTO user_progress (user_id, book_id, percent, updated)
           VALUES (?, ?, ?, datetime('now'))
           ON CONFLICT(user_id, book_id) DO UPDATE SET percent=excluded.percent, updated=excluded.updated""",
        (user_id, book_id, percent),
    )
    conn.commit()


def get_all_user_progress(user_id: str) -> dict:
    """Return {book_id: {pct, updated}}."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT book_id, percent, updated FROM user_progress WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return {str(r["book_id"]): {"pct": r["percent"], "updated": r["updated"]} for r in rows}


# ===========================================================================
# User Playback
# ===========================================================================


def get_user_playback(user_id: str, book_id: int) -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT track_index, position, filename, updated FROM user_playback WHERE user_id = ? AND book_id = ?",
        (user_id, book_id),
    ).fetchone()
    return dict(row) if row else None


def set_user_playback(user_id: str, book_id: int, track_index: int, position: float, filename: str = ""):
    conn = _get_conn()
    conn.execute(
        """INSERT INTO user_playback (user_id, book_id, track_index, position, filename, updated)
           VALUES (?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(user_id, book_id) DO UPDATE
           SET track_index=excluded.track_index, position=excluded.position,
               filename=excluded.filename, updated=excluded.updated""",
        (user_id, book_id, track_index, position, filename),
    )
    conn.commit()


# ===========================================================================
# User Notes
# ===========================================================================


def get_user_note(user_id: str, book_id: int) -> str:
    conn = _get_conn()
    row = conn.execute(
        "SELECT note FROM user_notes WHERE user_id = ? AND book_id = ?",
        (user_id, book_id),
    ).fetchone()
    return row["note"] if row else ""


def set_user_note(user_id: str, book_id: int, note: str):
    conn = _get_conn()
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


# ===========================================================================
# User Tags
# ===========================================================================


def get_user_tags(user_id: str, book_id: int) -> list[str]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT tag FROM user_tags WHERE user_id = ? AND book_id = ?",
        (user_id, book_id),
    ).fetchall()
    return [r["tag"] for r in rows]


def set_user_tags(user_id: str, book_id: int, tags: list[str]):
    """Replace all tags for a user/book with the given list."""
    conn = _get_conn()
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


def get_all_user_tags(user_id: str) -> list[str]:
    """Return all unique tags for a user across all books."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT DISTINCT tag FROM user_tags WHERE user_id = ? ORDER BY tag",
        (user_id,),
    ).fetchall()
    return [r["tag"] for r in rows]


# ===========================================================================
# User History
# ===========================================================================


def get_user_history(
    user_id: str, action: str | None = None, search: str | None = None, limit: int = 100
) -> list[dict]:
    conn = _get_conn()
    clauses = ["user_id = ?"]
    params: list = [user_id]
    if action:
        clauses.append("action = ?")
        params.append(action)
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        clauses.append("(book_title LIKE ? ESCAPE '\\' OR detail LIKE ? ESCAPE '\\')")
        q = f"%{escaped}%"
        params.extend([q, q])
    where = " WHERE " + " AND ".join(clauses)
    params.append(limit)
    rows = conn.execute(f"SELECT * FROM user_history{where} ORDER BY ts DESC LIMIT ?", params).fetchall()
    return [dict(r) for r in rows]


def add_user_history(
    user_id: str, action: str, book_id: int | None = None, book_title: str = "", detail: str = "", rating: int = 0
):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO user_history (user_id, action, book_id, book_title, detail, rating) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, action, book_id, book_title, detail, rating),
    )
    conn.commit()


# ===========================================================================
# User Quotes
# ===========================================================================


def get_user_quotes(user_id: str) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM user_quotes WHERE user_id = ? ORDER BY ts DESC",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def add_user_quote(user_id: str, text: str, book: str = "", author: str = ""):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO user_quotes (user_id, text, book, author) VALUES (?, ?, ?, ?)",
        (user_id, text, book, author),
    )
    conn.commit()


def delete_user_quote(user_id: str, quote_id: int):
    conn = _get_conn()
    conn.execute(
        "DELETE FROM user_quotes WHERE id = ? AND user_id = ?",
        (quote_id, user_id),
    )
    conn.commit()


# ===========================================================================
# User Sessions
# ===========================================================================


def get_user_sessions(user_id: str) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM user_sessions WHERE user_id = ? ORDER BY started DESC",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def start_user_session(user_id: str, book_title: str) -> dict:
    """Start a listening session. Returns the created session dict."""
    conn = _get_conn()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        "INSERT INTO user_sessions (user_id, book_title, started) VALUES (?, ?, ?)",
        (user_id, book_title, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM user_sessions WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def stop_user_session(user_id: str, book_title: str) -> float:
    """Stop the most recent open session for this book. Returns duration in minutes."""
    conn = _get_conn()
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


def get_total_listening_hours(user_id: str) -> float:
    """Return total listening hours for a user."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT COALESCE(SUM(duration_min), 0) as total FROM user_sessions WHERE user_id = ? AND duration_min > 0",
        (user_id,),
    ).fetchone()
    return round(row["total"] / 60.0, 1)


def get_dashboard_data(user_id: str, year: str) -> dict:
    """Fetch all dashboard data in minimal DB round-trips.

    Returns dict with keys: active, history, counts, settings, quote.
    Replaces 7+ separate queries with 5 focused ones on one connection.
    """
    conn = _get_conn()
    ghost = _ghost_filter()

    # 1. Active books: JOIN status + progress + books in one query
    active = conn.execute(
        f"""
        SELECT b.id, b.title, b.author, b.reader, b.folder, b.category,
               b.has_cover, b.duration_hours,
               COALESCE(p.percent, 0) AS progress
        FROM books b
        JOIN user_book_status s ON s.book_id = b.id AND s.user_id = ?
        LEFT JOIN user_progress p ON p.book_id = b.id AND p.user_id = ?
        WHERE s.status = 'reading' AND {ghost}
        """,
        (user_id, user_id),
    ).fetchall()

    # 2. History (already indexed on user_id, ts)
    history = conn.execute(
        """
        SELECT h.id, h.user_id, h.ts, h.action, h.book_id, h.book_title,
               h.detail, h.rating
        FROM user_history h
        WHERE h.user_id = ?
        ORDER BY h.ts DESC LIMIT 500
        """,
        (user_id,),
    ).fetchall()

    # 3. Aggregate counts in a single query
    counts = conn.execute(
        f"""
        SELECT
            (SELECT COUNT(*) FROM books WHERE {ghost}) AS total_books,
            (SELECT COUNT(*) FROM user_history
             WHERE user_id = ? AND action = 'done') AS total_done,
            (SELECT COALESCE(SUM(duration_min), 0) / 60.0
             FROM user_sessions
             WHERE user_id = ? AND duration_min > 0) AS total_hours,
            (SELECT COUNT(*) FROM user_history
             WHERE user_id = ? AND action = 'done'
               AND ts >= ?) AS this_year_done
        FROM (SELECT 1)
        """,
        (user_id, user_id, user_id, f"{year}-01-01"),
    ).fetchone()

    # 4. Settings (creates defaults if missing — side-effect kept)
    settings_row = conn.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
    if not settings_row:
        conn.execute("INSERT INTO user_settings (user_id) VALUES (?)", (user_id,))
        conn.commit()
        settings = {"user_id": user_id, "yearly_goal": 24, "playback_speed": 1.0}
    else:
        settings = dict(settings_row)

    # 5. Random quote
    quote_row = conn.execute(
        "SELECT * FROM user_quotes WHERE user_id = ? ORDER BY RANDOM() LIMIT 1",
        (user_id,),
    ).fetchone()

    return {
        "active": [dict(r) for r in active],
        "history": [dict(r) for r in history],
        "counts": dict(counts) if counts else {},
        "settings": settings,
        "quote": dict(quote_row) if quote_row else None,
    }


def get_session_stats(user_id: str, days: int = 7) -> dict:
    """Return {total_hours, today_min, week_hours, peak_hour}."""
    conn = _get_conn()
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


# ===========================================================================
# User Bookmarks
# ===========================================================================


def get_all_user_bookmarks_map(user_id: str) -> dict[int, list[dict]]:
    """Return {book_id: [bookmark, ...]} for all books with bookmarks."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM user_bookmarks WHERE user_id = ? ORDER BY book_id, created_at",
        (user_id,),
    ).fetchall()
    result: dict[int, list[dict]] = {}
    for r in rows:
        result.setdefault(r["book_id"], []).append(dict(r))
    return result


def get_user_bookmarks(user_id: str, book_id: int) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM user_bookmarks WHERE user_id = ? AND book_id = ? ORDER BY created_at",
        (user_id, book_id),
    ).fetchall()
    return [dict(r) for r in rows]


def add_user_bookmark(user_id: str, book_id: int, track_index: int, position: float, note: str = "") -> dict:
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO user_bookmarks (user_id, book_id, track_index, position, note) VALUES (?, ?, ?, ?, ?)",
        (user_id, book_id, track_index, position, note),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM user_bookmarks WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def remove_user_bookmark(user_id: str, bookmark_id: int) -> bool:
    conn = _get_conn()
    cur = conn.execute(
        "DELETE FROM user_bookmarks WHERE id = ? AND user_id = ?",
        (bookmark_id, user_id),
    )
    conn.commit()
    return cur.rowcount > 0


# ===========================================================================
# User Collections
# ===========================================================================


def get_user_collections(user_id: str) -> list[dict]:
    """Return collections with their book lists."""
    conn = _get_conn()
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


def create_user_collection(user_id: str, name: str, book_ids: list[int] | None = None, description: str = "") -> int:
    """Create a collection and return its id."""
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO user_collections (user_id, name, description) VALUES (?, ?, ?)",
        (user_id, name, description),
    )
    coll_id = cur.lastrowid
    # INSERT OR IGNORE silently skips invalid book_ids (FK constraint + PRAGMA foreign_keys=ON)
    for bid in book_ids or []:
        conn.execute(
            "INSERT OR IGNORE INTO collection_books (collection_id, book_id) VALUES (?, ?)",
            (coll_id, bid),
        )
    conn.commit()
    return coll_id


def update_user_collection(user_id: str, collection_id: int, name: str, book_ids: list[int], description: str):
    conn = _get_conn()
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


def delete_user_collection(user_id: str, collection_id: int) -> bool:
    conn = _get_conn()
    cur = conn.execute(
        "DELETE FROM user_collections WHERE id = ? AND user_id = ?",
        (collection_id, user_id),
    )
    conn.commit()
    return cur.rowcount > 0


# ===========================================================================
# Batch queries (for list views — avoid N+1)
# ===========================================================================


def get_all_user_notes_map(user_id: str) -> dict[int, str]:
    """Return {book_id: note} for all books with notes."""
    conn = _get_conn()
    rows = conn.execute("SELECT book_id, note FROM user_notes WHERE user_id = ?", (user_id,)).fetchall()
    return {r["book_id"]: r["note"] for r in rows}


def get_all_user_tags_map(user_id: str) -> dict[int, list[str]]:
    """Return {book_id: [tag1, tag2, ...]} for all books with tags."""
    conn = _get_conn()
    rows = conn.execute("SELECT book_id, tag FROM user_tags WHERE user_id = ? ORDER BY book_id", (user_id,)).fetchall()
    result: dict[int, list[str]] = {}
    for r in rows:
        result.setdefault(r["book_id"], []).append(r["tag"])
    return result


def get_user_history_for_book(user_id: str, book_id: int) -> list[dict]:
    """Return history entries for a specific book."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM user_history WHERE user_id = ? AND book_id = ? ORDER BY ts DESC",
        (user_id, book_id),
    ).fetchall()
    return [dict(r) for r in rows]


def get_user_rating(user_id: str, book_id: int) -> int:
    """Return the rating from the most recent 'rated' or 'done' history entry for a book."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT rating FROM user_history WHERE user_id = ? AND book_id = ? AND action IN ('rated', 'done') AND rating > 0 ORDER BY ts DESC LIMIT 1",
        (user_id, book_id),
    ).fetchone()
    return row["rating"] if row else 0


def set_user_rating(user_id: str, book_id: int, rating: int) -> None:
    """Set or update a standalone rating for a book (1-5, or 0 to remove)."""
    conn = _get_conn()
    if rating == 0:
        conn.execute(
            "DELETE FROM user_history WHERE user_id = ? AND book_id = ? AND action = 'rated'",
            (user_id, book_id),
        )
    else:
        existing = conn.execute(
            "SELECT id FROM user_history WHERE user_id = ? AND book_id = ? AND action = 'rated' LIMIT 1",
            (user_id, book_id),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE user_history SET rating = ?, ts = datetime('now') WHERE id = ?",
                (rating, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO user_history (user_id, book_id, action, rating, ts) VALUES (?, ?, 'rated', ?, datetime('now'))",
                (user_id, book_id, rating),
            )
    conn.commit()


def get_categories() -> list[str]:
    """Return distinct categories from the books table."""
    conn = _get_conn()
    rows = conn.execute("SELECT DISTINCT category FROM books WHERE category != '' ORDER BY category").fetchall()
    return [r["category"] for r in rows]


# ── Categories table helpers ──────────────────────────────────────────────


def _seed_categories(conn: sqlite3.Connection):
    """Insert default categories if the categories table is empty."""
    count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    if count > 0:
        return
    defaults = [
        ("Бизнес", "#d4940c", "linear-gradient(135deg, #92400e 0%, #d97706 100%)", 1),
        ("Отношения", "#c9366d", "linear-gradient(135deg, #9d174d 0%, #db2777 100%)", 2),
        ("Саморазвитие", "#E8923A", "linear-gradient(135deg, #9a5c16 0%, #E8923A 100%)", 3),
        ("Художественная", "#0e8a99", "linear-gradient(135deg, #155e75 0%, #0891b2 100%)", 4),
        ("Языки", "#0f8660", "linear-gradient(135deg, #064e3b 0%, #059669 100%)", 5),
    ]
    conn.executemany(
        "INSERT INTO categories (name, color, gradient, sort_order) VALUES (?, ?, ?, ?)",
        defaults,
    )
    conn.commit()
    logger.info("Seeded %d default categories", len(defaults))


def get_all_categories() -> list[dict]:
    """Return all categories ordered by sort_order."""
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM categories ORDER BY sort_order").fetchall()
    return [dict(r) for r in rows]


def get_category_by_name(name: str) -> dict | None:
    """Return a single category by name."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM categories WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def upsert_category(name: str, color: str, gradient: str, sort_order: int) -> dict:
    """Insert or update a category. Returns the category dict."""
    conn = _get_conn()
    conn.execute(
        """
        INSERT INTO categories (name, color, gradient, sort_order)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            color = excluded.color,
            gradient = excluded.gradient,
            sort_order = excluded.sort_order
        """,
        (name, color, gradient, sort_order),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM categories WHERE name = ?", (name,)).fetchone()
    return dict(row)


def update_category_by_id(cat_id: int, **fields) -> dict | None:
    """Update specific fields of a category by ID. Returns updated dict or None."""
    conn = _get_conn()
    existing = conn.execute("SELECT * FROM categories WHERE id = ?", (cat_id,)).fetchone()
    if not existing:
        return None
    allowed = {"name", "color", "gradient", "sort_order"}
    updates = {k: v for k, v in fields.items() if v is not None and k in allowed}
    if not updates:
        return dict(existing)
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [cat_id]
    conn.execute(f"UPDATE categories SET {set_clause} WHERE id = ?", values)
    conn.commit()
    row = conn.execute("SELECT * FROM categories WHERE id = ?", (cat_id,)).fetchone()
    return dict(row)


def create_category(name: str, color: str, gradient: str, sort_order: int) -> dict:
    """Create a new category. Returns the category dict."""
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO categories (name, color, gradient, sort_order) VALUES (?, ?, ?, ?)",
        (name, color, gradient, sort_order),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM categories WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def delete_category(cat_id: int) -> bool:
    """Delete a category by ID. Returns True if deleted."""
    conn = _get_conn()
    deleted = conn.execute("DELETE FROM categories WHERE id = ?", (cat_id,)).rowcount
    conn.commit()
    return deleted > 0


def update_book_language(book_id: int, language: str) -> bool:
    """Update a book's language. Returns True if updated."""
    conn = _get_conn()
    updated = conn.execute("UPDATE books SET language = ? WHERE id = ?", (language, book_id)).rowcount
    conn.commit()
    return updated > 0


def update_book_category(book_id: int, category: str) -> bool:
    """Update a book's category. Returns True if updated."""
    conn = _get_conn()
    updated = conn.execute("UPDATE books SET category = ? WHERE id = ?", (category, book_id)).rowcount
    conn.commit()
    return updated > 0


# ── Ingestion Jobs ─────────────────────────────────────────────────────────


def create_ingestion_job(source: str, input_data: dict, timeout_seconds: int = 600) -> int:
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO ingestion_jobs (source, input_data, timeout_seconds) VALUES (?, ?, ?)",
        (source, json.dumps(input_data, ensure_ascii=False), timeout_seconds),
    )
    conn.commit()
    return cur.lastrowid


def get_ingestion_job(job_id: int) -> dict | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM ingestion_jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def list_ingestion_jobs(status: str | None = None, limit: int = 100) -> list[dict]:
    conn = _get_conn()
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


def update_ingestion_job(job_id: int, status: str | None = None, result: dict | None = None) -> None:
    conn = _get_conn()
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


def heartbeat_ingestion_job(job_id: int) -> None:
    conn = _get_conn()
    conn.execute(
        "UPDATE ingestion_jobs SET heartbeat_at = datetime('now') WHERE id = ?",
        (job_id,),
    )
    conn.commit()


def recover_stalled_jobs() -> int:
    conn = _get_conn()
    cur = conn.execute("""
        UPDATE ingestion_jobs
        SET status = 'pending', retries = retries + 1, updated_at = datetime('now')
        WHERE status = 'processing'
          AND heartbeat_at IS NOT NULL
          AND (julianday('now') - julianday(heartbeat_at)) * 86400 > timeout_seconds
    """)
    conn.commit()
    return cur.rowcount


# ── Ingestion Pipeline helpers ────────────────────────────────────────────


def insert_book_for_ingest(
    *,
    slug,
    title,
    author,
    reader,
    category,
    language,
    source,
    fingerprint,
    mp3_count,
    duration_hours,
    size_mb,
    has_cover,
) -> int:
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO books
        (slug, title, author, reader, category, folder, s3_prefix,
         language, source, fingerprint, has_cover, mp3_count, duration_hours, size_mb)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            slug,
            title,
            author,
            reader,
            category,
            slug,
            f"books/{slug}",
            language,
            source,
            fingerprint,
            has_cover,
            mp3_count,
            duration_hours,
            size_mb,
        ),
    )
    conn.commit()
    return cur.lastrowid


def update_book_description(book_id: int, description: str) -> None:
    conn = _get_conn()
    conn.execute("UPDATE books SET description = ? WHERE id = ?", (description, book_id))
    conn.commit()


def get_books_without_description() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, title, author, category FROM books WHERE description IS NULL OR description = '' ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def insert_tracks_for_ingest(book_id: int, tracks: list[dict]) -> None:
    conn = _get_conn()
    for t in tracks:
        conn.execute(
            "INSERT INTO tracks (book_id, idx, filename, s3_key, duration) VALUES (?, ?, ?, ?, ?)",
            (
                book_id,
                t["track"],
                t["file"],
                f"books/{book_id}/audio/{t['file']}",
                t["duration"],
            ),
        )
    conn.commit()
