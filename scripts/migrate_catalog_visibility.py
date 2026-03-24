#!/usr/bin/env python3
"""
One-time migration: set owner_user_id on copyrighted catalog books.

Public domain books (source='librivox' or 'archive') remain public (owner_user_id=NULL).
All other catalog books become private to the specified user.

Usage:
    python scripts/migrate_catalog_visibility.py <user_id>

    # Dry run (no changes):
    python scripts/migrate_catalog_visibility.py <user_id> --dry-run
"""

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "leerio.db"
PUBLIC_SOURCES = ("librivox", "archive")


def main():
    parser = argparse.ArgumentParser(description="Migrate catalog visibility")
    parser.add_argument("user_id", help="Owner user_id for copyrighted books")
    parser.add_argument("--dry-run", action="store_true", help="Preview without changes")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="Path to database")
    args = parser.parse_args()

    db_path = args.db
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}")
        sys.exit(1)

    # Backup
    if not args.dry_run:
        backup = db_path.with_suffix(".db.bak")
        shutil.copy2(db_path, backup)
        print(f"Backup created: {backup}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Ensure column exists
    cols = [r[1] for r in conn.execute("PRAGMA table_info(books)").fetchall()]
    if "owner_user_id" not in cols:
        if args.dry_run:
            print("Would add column: owner_user_id TEXT DEFAULT NULL")
        else:
            conn.execute("ALTER TABLE books ADD COLUMN owner_user_id TEXT DEFAULT NULL")
            print("Added column: owner_user_id")

    # Count books by source
    all_books = conn.execute("SELECT id, title, author, source, category FROM books").fetchall()
    public = [b for b in all_books if b["source"] in PUBLIC_SOURCES]
    private = [b for b in all_books if b["source"] not in PUBLIC_SOURCES]

    print(f"\nTotal books: {len(all_books)}")
    print(f"Public domain (source in {PUBLIC_SOURCES}): {len(public)}")
    print(f"Copyrighted (will be private): {len(private)}")

    # Show source breakdown
    sources = {}
    for b in all_books:
        s = b["source"] or "manual"
        sources[s] = sources.get(s, 0) + 1
    print(f"\nSource breakdown:")
    for s, count in sorted(sources.items()):
        label = "PUBLIC" if s in PUBLIC_SOURCES else "PRIVATE"
        print(f"  {s}: {count} [{label}]")

    if args.dry_run:
        print(f"\n[DRY RUN] Would set owner_user_id='{args.user_id}' on {len(private)} books")
        print("\nSample private books:")
        for b in private[:10]:
            print(f"  #{b['id']} {b['title']} — {b['author']} (source={b['source']})")
        if len(private) > 10:
            print(f"  ... and {len(private) - 10} more")
        return

    # Apply migration
    private_ids = [b["id"] for b in private]
    if private_ids:
        placeholders = ",".join("?" * len(private_ids))
        conn.execute(
            f"UPDATE books SET owner_user_id = ? WHERE id IN ({placeholders})",
            [args.user_id, *private_ids],
        )
        conn.commit()

    # Verify
    pub_count = conn.execute("SELECT COUNT(*) FROM books WHERE owner_user_id IS NULL").fetchone()[0]
    priv_count = conn.execute("SELECT COUNT(*) FROM books WHERE owner_user_id IS NOT NULL").fetchone()[0]
    print(f"\nMigration complete:")
    print(f"  Public books: {pub_count}")
    print(f"  Private books (owner={args.user_id}): {priv_count}")
    print(f"\nRollback: cp {db_path.with_suffix('.db.bak')} {db_path}")

    conn.close()


if __name__ == "__main__":
    main()
