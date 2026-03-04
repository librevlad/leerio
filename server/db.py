"""
server/db.py — SQLite user database for authentication.

Manages users table with Google OAuth and email/password identity.
"""

import hashlib
import logging
import os
import secrets
import sqlite3

from .core import DATA_DIR

logger = logging.getLogger("leerio.db")

DB_PATH = DATA_DIR / "leerio.db"

SEED_EMAIL = "librevlad@gmail.com"
SEED_ROLE = "admin"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create users table, allowed_emails table, and ensure seed user exists."""
    conn = _get_conn()
    try:
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
        conn.commit()
        _migrate_password_column(conn)
        _ensure_seed_user(conn)
        _seed_allowed_emails(conn)
    finally:
        conn.close()
    logger.info("Database initialized at %s", DB_PATH)


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
