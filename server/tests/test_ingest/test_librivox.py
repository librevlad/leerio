"""Tests for LibriVox source."""

from server.ingest.sources.librivox import parse_book


def test_parse_book_basic():
    raw = {
        "id": "123",
        "title": "War and Peace",
        "authors": [{"first_name": "Leo", "last_name": "Tolstoy"}],
        "language": "Russian",
        "totaltime": "61:30:00",
        "url_librivox": "https://librivox.org/war-and-peace",
        "sections": [
            {"listen_url": "https://example.com/01.mp3"},
            {"listen_url": "https://example.com/02.mp3"},
        ],
    }
    result = parse_book(raw)
    assert result["title"] == "War and Peace"
    assert result["author"] == "Leo Tolstoy"
    assert result["external_id"] == "librivox:123"
    assert len(result["mp3_urls"]) == 2
    assert result["duration_hours"] == 61.5


def test_parse_book_no_sections():
    raw = {
        "id": "456",
        "title": "Empty Book",
        "authors": [],
        "language": "English",
        "totaltime": "0:00:00",
        "sections": [],
    }
    result = parse_book(raw)
    assert result["title"] == "Empty Book"
    assert result["author"] == "Unknown"
    assert result["mp3_urls"] == []


def test_parse_book_multiple_authors():
    raw = {
        "id": "789",
        "title": "Anthology",
        "authors": [
            {"first_name": "Author", "last_name": "One"},
            {"first_name": "Author", "last_name": "Two"},
        ],
        "language": "English",
        "totaltime": "2:30:00",
        "sections": [{"listen_url": "https://example.com/01.mp3"}],
    }
    result = parse_book(raw)
    assert result["author"] == "Author One, Author Two"
