"""Tests for the async job runner."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from server import db
from server.ingest.jobs import heartbeat_loop, process_queue, run_job


@pytest.fixture()
def setup_db(tmp_data_dir):
    db.init_db()


def test_heartbeat_loop_updates(setup_db):
    """heartbeat_loop updates heartbeat_at until cancelled."""
    job_id = db.create_ingestion_job("test", {})
    db.update_ingestion_job(job_id, status="processing")

    async def _test():
        task = asyncio.create_task(heartbeat_loop(job_id, interval=0.05))
        await asyncio.sleep(0.15)
        task.cancel()
        await task
        job = db.get_ingestion_job(job_id)
        assert job["heartbeat_at"] is not None

    asyncio.run(_test())


def test_run_job_creates_and_finishes(setup_db):
    """Integration: run_job transitions job through processing -> done."""
    job_id = db.create_ingestion_job("url", {"title": "Test", "author": "Auth"})

    with patch("server.ingest.pipeline.IngestPipeline") as mock_cls:
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = {"status": "done", "book_id": 1}
        mock_cls.return_value = mock_pipeline

        async def _test():
            result = await run_job(job_id)
            assert result["status"] == "done"

        asyncio.run(_test())

    job = db.get_ingestion_job(job_id)
    assert job["status"] == "done"


def test_run_job_handles_failure(setup_db):
    """run_job sets status to failed on pipeline error."""
    job_id = db.create_ingestion_job("url", {"title": "Test", "author": "Auth"})

    with patch("server.ingest.pipeline.IngestPipeline") as mock_cls:
        mock_pipeline = MagicMock()
        mock_pipeline.run.side_effect = RuntimeError("No audio files")
        mock_cls.return_value = mock_pipeline

        async def _test():
            result = await run_job(job_id)
            assert result["status"] == "failed"

        asyncio.run(_test())

    job = db.get_ingestion_job(job_id)
    assert job["status"] == "failed"


def test_process_queue_runs_pending(setup_db):
    """process_queue picks up pending jobs and runs them."""
    db.create_ingestion_job("url", {"title": "T1", "author": "A1"})
    db.create_ingestion_job("url", {"title": "T2", "author": "A2"})

    with patch("server.ingest.pipeline.IngestPipeline") as mock_cls:
        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = {"status": "done", "book_id": 1}
        mock_cls.return_value = mock_pipeline

        async def _test():
            count = await process_queue()
            assert count == 2

        asyncio.run(_test())
