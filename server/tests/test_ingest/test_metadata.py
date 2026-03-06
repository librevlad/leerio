"""Tests for metadata extraction."""

from pathlib import Path
from unittest.mock import patch

from server.ingest.extract_metadata import (
    build_metadata_json,
    build_tracks_json,
)


def test_build_tracks_json():
    files = [Path("/tmp/01.mp3"), Path("/tmp/02.mp3")]
    durations = {"01.mp3": 600.5, "02.mp3": 720.3}
    with patch("server.ingest.extract_metadata.extract_track_duration", side_effect=lambda p: durations[p.name]):
        result = build_tracks_json(files)
    assert len(result) == 2
    assert result[0] == {"track": 1, "file": "01.mp3", "duration": 600.5}
    assert result[1] == {"track": 2, "file": "02.mp3", "duration": 720.3}


def test_build_metadata_json():
    meta = build_metadata_json(
        title="Test Book",
        author="Author",
        reader="Reader",
        category="\u0411\u0438\u0437\u043d\u0435\u0441",
        language="ru",
        source="librivox",
        duration_hours=5.2,
    )
    assert meta["version"] == 1
    assert meta["title"] == "Test Book"
    assert meta["language"] == "ru"
    assert meta["duration_hours"] == 5.2
