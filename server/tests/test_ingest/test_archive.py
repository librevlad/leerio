"""Tests for Archive.org source."""

from server.ingest.sources.archive import parse_item


def test_parse_item_basic():
    raw = {
        "identifier": "war-and-peace-audio",
        "title": "War and Peace",
        "creator": "Leo Tolstoy",
        "description": "Classic novel",
    }
    result = parse_item(raw)
    assert result["title"] == "War and Peace"
    assert result["author"] == "Leo Tolstoy"
    assert result["external_id"] == "archive:war-and-peace-audio"
    assert result["source_url"] == "https://archive.org/details/war-and-peace-audio"
    assert result["archive_identifier"] == "war-and-peace-audio"


def test_parse_item_missing_fields():
    raw = {"identifier": "test-item"}
    result = parse_item(raw)
    assert result["title"] == "Unknown"
    assert result["author"] == "Unknown"
    assert result["external_id"] == "archive:test-item"
