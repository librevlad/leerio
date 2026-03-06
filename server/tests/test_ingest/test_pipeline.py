"""Tests for the main ingestion pipeline."""

from unittest.mock import patch

import pytest

from server.ingest.pipeline import IngestPipeline


@pytest.fixture
def pipeline(tmp_path):
    return IngestPipeline(
        work_dir=tmp_path,
        title="Test Book",
        author="Test Author",
        reader="Test Reader",
        category="Бизнес",
        language="ru",
        source="url",
        fast=False,
    )


def test_pipeline_init(pipeline, tmp_path):
    assert pipeline.work_dir == tmp_path
    assert pipeline.title == "Test Book"
    assert pipeline.fast is False


def test_pipeline_normalize_creates_output(pipeline, tmp_path):
    src = tmp_path / "input.m4a"
    src.write_bytes(b"fake audio")
    out = tmp_path / "output.mp3"

    with patch("server.ingest.pipeline.norm.normalize_file") as mock_norm:
        pipeline._normalize_single(src, out)
        mock_norm.assert_called_once_with(src, out, fast=False, timeout=300)


def test_pipeline_build_s3_key():
    key = IngestPipeline.s3_audio_key(42, "01.mp3")
    assert key == "books/42/audio/01.mp3"

    key = IngestPipeline.s3_metadata_key(42)
    assert key == "books/42/metadata.json"
