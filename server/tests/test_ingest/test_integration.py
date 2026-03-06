"""Integration test — full pipeline with mocked S3 and real SQLite."""

import json
from unittest.mock import MagicMock, patch

import pytest

from server import db
from server.ingest.pipeline import IngestPipeline


@pytest.fixture()
def setup_db(tmp_data_dir):
    db.init_db()


@pytest.fixture()
def fake_mp3(tmp_path):
    """Create a minimal fake MP3 file for testing."""
    mp3 = tmp_path / "01.mp3"
    # Write a minimal valid MP3 frame header (not playable but mutagen-parseable enough)
    # We'll mock extract_track_duration instead
    mp3.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 500)
    return mp3


def test_full_pipeline_with_mocked_s3(setup_db, tmp_path):
    """End-to-end: create pipeline → normalize → upload → register."""
    # Put fake audio files in work dir
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    for i in range(3):
        f = work_dir / f"{i + 1:02d}.mp3"
        f.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 500)

    uploaded_keys = []

    with (
        patch("server.ingest.pipeline.norm.normalize_file") as mock_norm,
        patch("server.ingest.pipeline.norm.is_mp3", return_value=True),
        patch("server.ingest.pipeline.build_tracks_json") as mock_tracks,
        patch("server.ingest.pipeline.extract_cover_from_mp3", return_value=None),
        patch("server.ingest.pipeline.detect_chapters_from_file", return_value=[]),
        patch("server.storage.upload_file_to_s3") as mock_upload_file,
        patch("server.storage.upload_json_to_s3") as mock_upload_json,
    ):
        # Mock normalize to just copy files
        def fake_normalize(src, out, *, fast=False, timeout=300):
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(src.read_bytes())

        mock_norm.side_effect = fake_normalize
        mock_tracks.return_value = [
            {"track": 1, "file": "01.mp3", "duration": 600},
            {"track": 2, "file": "02.mp3", "duration": 600},
            {"track": 3, "file": "03.mp3", "duration": 600},
        ]
        mock_upload_file.side_effect = lambda local, key: uploaded_keys.append(key)
        mock_upload_json.side_effect = lambda data, key: uploaded_keys.append(key)

        pipeline = IngestPipeline(
            work_dir=work_dir,
            title="Интеграционный Тест",
            author="Тестовый Автор",
            reader="Читатель",
            category="Бизнес",
            language="ru",
            source="url",
            fast=True,
        )

        result = pipeline.run()

    # Verify pipeline result
    assert result["status"] == "done"
    assert result["tracks_processed"] == 3
    book_id = result["book_id"]
    assert book_id > 0

    # Verify DB records
    book = db.get_book_by_id(book_id)
    assert book is not None
    assert book["title"] == "Интеграционный Тест"
    assert book["author"] == "Тестовый Автор"
    assert book["language"] == "ru"
    assert book["source"] == "url"
    assert book["fingerprint"] is not None

    tracks = db.get_book_tracks(book_id)
    assert len(tracks) == 3
    assert tracks[0]["s3_key"] == f"books/{book_id}/audio/01.mp3"

    # Verify S3 uploads happened
    assert f"books/{book_id}/audio/01.mp3" in uploaded_keys
    assert f"books/{book_id}/audio/02.mp3" in uploaded_keys
    assert f"books/{book_id}/audio/03.mp3" in uploaded_keys
    assert f"books/{book_id}/metadata.json" in uploaded_keys
    assert f"books/{book_id}/tracks.json" in uploaded_keys
    assert f"books/{book_id}/chapters.json" in uploaded_keys


def test_pipeline_dedup_skips_duplicate(setup_db, tmp_path):
    """Running the pipeline twice with same data returns skipped."""
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    (work_dir / "01.mp3").write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 500)

    with (
        patch("server.ingest.pipeline.norm.normalize_file") as mock_norm,
        patch("server.ingest.pipeline.norm.is_mp3", return_value=True),
        patch("server.ingest.pipeline.build_tracks_json") as mock_tracks,
        patch("server.ingest.pipeline.extract_cover_from_mp3", return_value=None),
        patch("server.ingest.pipeline.detect_chapters_from_file", return_value=[]),
        patch("server.storage.upload_file_to_s3"),
        patch("server.storage.upload_json_to_s3"),
    ):

        def fake_normalize(src, out, *, fast=False, timeout=300):
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(src.read_bytes())

        mock_norm.side_effect = fake_normalize
        mock_tracks.return_value = [{"track": 1, "file": "01.mp3", "duration": 600}]

        kwargs = dict(
            work_dir=work_dir,
            title="Дубликат",
            author="Автор",
            source="url",
            fast=True,
        )

        # First run should succeed
        p1 = IngestPipeline(**kwargs)
        r1 = p1.run()
        assert r1["status"] == "done"

        # Second run with same title/author/duration should be skipped
        p2 = IngestPipeline(**kwargs)
        r2 = p2.run()
        assert r2["status"] == "skipped"
        assert r2["reason"] == "duplicate"


def test_job_runner_integration(setup_db):
    """Create a job and run it through the runner."""
    import asyncio

    from server.ingest.jobs import run_job

    job_id = db.create_ingestion_job("url", {"title": "Test", "author": "Auth"})

    with patch("server.ingest.pipeline.IngestPipeline") as mock_cls:
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = {"status": "done", "book_id": 1, "tracks_processed": 5}
        mock_cls.return_value = mock_pipeline

        result = asyncio.run(run_job(job_id))

    assert result["status"] == "done"
    job = db.get_ingestion_job(job_id)
    assert job["status"] == "done"
    assert json.loads(job["result"])["book_id"] == 1
