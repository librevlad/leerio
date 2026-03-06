"""Tests for chapter detection."""
from server.ingest.chapters import detect_chapters_fallback, parse_embedded_chapters


def test_fallback_splits_by_duration():
    # 3 tracks of 600s each = 1800s total; fallback at 600s = 3 chapters
    tracks = [
        {"track": 1, "file": "01.mp3", "duration": 600},
        {"track": 2, "file": "02.mp3", "duration": 600},
        {"track": 3, "file": "03.mp3", "duration": 600},
    ]
    chapters = detect_chapters_fallback(tracks, interval_seconds=600)
    assert len(chapters) == 3
    assert chapters[0] == {"title": "Часть 1", "start": 0, "track": 0}
    assert chapters[1] == {"title": "Часть 2", "start": 600, "track": 1}
    assert chapters[2] == {"title": "Часть 3", "start": 1200, "track": 2}


def test_fallback_single_track():
    tracks = [{"track": 1, "file": "01.mp3", "duration": 300}]
    chapters = detect_chapters_fallback(tracks, interval_seconds=600)
    assert len(chapters) == 1
    assert chapters[0]["title"] == "Часть 1"


def test_parse_embedded_chapters_empty():
    assert parse_embedded_chapters([]) == []
