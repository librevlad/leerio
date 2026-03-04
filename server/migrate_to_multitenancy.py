"""
One-time migration: copy global data/*.json to data/users/{admin-id}/.

Run once after deploying the auth system to migrate existing data to the
admin user's per-user directory.

Usage:
    python -m server.migrate_to_multitenancy
"""

import hashlib
import shutil

from .core import DATA_DIR, USERS_DIR

ADMIN_EMAIL = "librevlad@gmail.com"
ADMIN_USER_ID = hashlib.sha256(ADMIN_EMAIL.encode()).hexdigest()[:16]

# Files that become per-user
USER_FILES = [
    "history.json",
    "notes.json",
    "tags.json",
    "collections.json",
    "progress.json",
    "playback.json",
    "quotes.json",
    "sessions.json",
]


def migrate():
    user_dir = USERS_DIR / ADMIN_USER_ID
    user_dir.mkdir(parents=True, exist_ok=True)

    migrated = []
    skipped = []

    for filename in USER_FILES:
        src = DATA_DIR / filename
        dst = user_dir / filename

        if not src.exists():
            skipped.append(f"  {filename} — source not found, skipping")
            continue

        if dst.exists():
            skipped.append(f"  {filename} — already exists in user dir, skipping")
            continue

        shutil.copy2(str(src), str(dst))
        migrated.append(f"  {filename} — copied")

    print(f"Migration to user {ADMIN_USER_ID} ({ADMIN_EMAIL}):")
    print(f"  Target: {user_dir}")
    print()
    if migrated:
        print("Migrated:")
        for m in migrated:
            print(m)
    if skipped:
        print("Skipped:")
        for s in skipped:
            print(s)
    print()
    print("Done. Original files left in place (safe to remove after verification).")


if __name__ == "__main__":
    migrate()
