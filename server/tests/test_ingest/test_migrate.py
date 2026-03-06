"""Tests for S3 migration tool."""

from unittest.mock import patch

import pytest

from server import db


@pytest.fixture()
def setup_db(tmp_data_dir):
    db.init_db()


def test_migrate_book_not_found(setup_db):
    from server.ingest.migrate import migrate_book

    result = migrate_book(99999)
    assert result["status"] == "error"
    assert "not found" in result["reason"]


def test_migrate_book_already_migrated(setup_db):
    from server.ingest.migrate import migrate_book

    # Insert a book with new-style prefix
    conn = db._get_conn()
    conn.execute(
        "INSERT INTO books (slug, title, author, folder, s3_prefix) VALUES (?, ?, ?, ?, ?)",
        ("test", "Test", "Author", "test", "books/1"),
    )
    conn.commit()
    book_id = conn.execute("SELECT id FROM books WHERE slug = 'test'").fetchone()[0]
    conn.close()

    result = migrate_book(book_id)
    assert result["status"] == "skipped"


def test_migrate_book_dry_run(setup_db):
    from server.ingest.migrate import migrate_book

    # Insert a book with old-style prefix
    conn = db._get_conn()
    conn.execute(
        "INSERT INTO books (slug, title, author, folder, s3_prefix) VALUES (?, ?, ?, ?, ?)",
        ("old-book", "Old Book", "Author", "old-book", "Бизнес/Author - Old Book"),
    )
    conn.commit()
    book_id = conn.execute("SELECT id FROM books WHERE slug = 'old-book'").fetchone()[0]
    conn.close()

    with patch("server.ingest.migrate.get_old_s3_files") as mock_list:
        mock_list.return_value = [
            {"key": "Бизнес/Author - Old Book/01.mp3", "size": 1000, "name": "01.mp3"},
            {"key": "Бизнес/Author - Old Book/02.mp3", "size": 2000, "name": "02.mp3"},
        ]
        result = migrate_book(book_id, dry_run=True)

    assert result["status"] == "dry_run"
    assert result["track_count"] == 2


def test_migrate_book_no_mp3s(setup_db):
    from server.ingest.migrate import migrate_book

    conn = db._get_conn()
    conn.execute(
        "INSERT INTO books (slug, title, author, folder, s3_prefix) VALUES (?, ?, ?, ?, ?)",
        ("no-audio", "No Audio", "Author", "no-audio", "Бизнес/Author - No Audio"),
    )
    conn.commit()
    book_id = conn.execute("SELECT id FROM books WHERE slug = 'no-audio'").fetchone()[0]
    conn.close()

    with patch("server.ingest.migrate.get_old_s3_files") as mock_list:
        mock_list.return_value = [
            {"key": "Бизнес/Author - No Audio/cover.jpg", "size": 500, "name": "cover.jpg"},
        ]
        result = migrate_book(book_id)

    assert result["status"] == "error"
    assert "No MP3" in result["reason"]


def test_migrate_all_filters_already_migrated(setup_db):
    from server.ingest.migrate import migrate_all

    conn = db._get_conn()
    # Already migrated book
    conn.execute(
        "INSERT INTO books (slug, title, author, folder, s3_prefix) VALUES (?, ?, ?, ?, ?)",
        ("migrated", "Migrated", "Author", "migrated", "books/1"),
    )
    # Old-style book
    conn.execute(
        "INSERT INTO books (slug, title, author, folder, s3_prefix) VALUES (?, ?, ?, ?, ?)",
        ("old", "Old", "Author", "old", "Бизнес/Author - Old"),
    )
    conn.commit()
    conn.close()

    with patch("server.ingest.migrate.get_old_s3_files") as mock_list:
        mock_list.return_value = [
            {"key": "Бизнес/Author - Old/01.mp3", "size": 1000, "name": "01.mp3"},
        ]
        results = migrate_all(dry_run=True)

    # Only the old-style book should be in results
    assert len(results) == 1
    assert results[0]["status"] == "dry_run"
