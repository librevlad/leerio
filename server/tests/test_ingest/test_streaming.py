"""Tests verifying streaming compatibility with new S3 layout."""

import pytest

from server import db


@pytest.fixture()
def setup_db(tmp_data_dir):
    db.init_db()


def test_new_layout_book_tracks_resolve(setup_db):
    """Books with new s3_prefix format have correct track s3_keys."""
    book_id = db.insert_book_for_ingest(
        slug="test-book",
        title="Test Book",
        author="Author",
        reader="Reader",
        category="Бизнес",
        language="ru",
        source="url",
        fingerprint="abc123",
        mp3_count=2,
        duration_hours=1.0,
        size_mb=10.0,
        has_cover=True,
    )
    db.insert_tracks_for_ingest(
        book_id,
        [
            {"track": 1, "file": "01.mp3", "duration": 1800},
            {"track": 2, "file": "02.mp3", "duration": 1800},
        ],
    )

    tracks = db.get_book_tracks(book_id)
    assert len(tracks) == 2
    assert tracks[0]["s3_key"] == f"books/{book_id}/audio/01.mp3"
    assert tracks[1]["s3_key"] == f"books/{book_id}/audio/02.mp3"


def test_new_layout_book_cover_prefix(setup_db):
    """Books with new s3_prefix have cover at books/{id}/cover.jpg."""
    book_id = db.insert_book_for_ingest(
        slug="cover-test",
        title="Cover Test",
        author="Author",
        reader="",
        category="",
        language="ru",
        source="url",
        fingerprint="def456",
        mp3_count=1,
        duration_hours=0.5,
        size_mb=5.0,
        has_cover=True,
    )

    book = db.get_book_by_id(book_id)
    assert book["s3_prefix"] == "books/cover-test"
    assert book["has_cover"] == 1
