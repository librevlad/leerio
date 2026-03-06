"""Async job runner with heartbeat watchdog."""

import asyncio
import json
import logging
import os
import shutil
import tempfile
from pathlib import Path

from .. import db

logger = logging.getLogger("leerio.ingest")

# Concurrency: half of CPU cores, minimum 1
MAX_WORKERS = max(1, (os.cpu_count() or 2) // 2)
_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_WORKERS)
    return _semaphore


async def heartbeat_loop(job_id: int, interval: float = 10) -> None:
    """Update heartbeat_at every *interval* seconds until cancelled."""
    try:
        while True:
            await asyncio.sleep(interval)
            db.heartbeat_ingestion_job(job_id)
    except asyncio.CancelledError:
        pass


async def run_job(job_id: int) -> dict:
    """Execute a single ingestion job."""
    job = db.get_ingestion_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    input_data = json.loads(job["input_data"] or "{}")
    db.update_ingestion_job(job_id, status="processing")

    # Start heartbeat
    hb_task = asyncio.create_task(heartbeat_loop(job_id))
    work_dir: Path | None = None

    try:
        # Create temp work directory
        work_dir = Path(tempfile.mkdtemp(prefix=f"leerio-ingest-{job_id}-"))

        # Lazy import to avoid circular imports
        from .pipeline import IngestPipeline

        pipeline = IngestPipeline(
            work_dir=work_dir,
            title=input_data.get("title", "Unknown"),
            author=input_data.get("author", "Unknown"),
            reader=input_data.get("reader", ""),
            category=input_data.get("category", ""),
            language=input_data.get("language", "ru"),
            source=job["source"],
            fast=input_data.get("fast", False),
        )

        def on_progress(current: int, total: int, phase: str) -> None:
            logger.info("Job %d: %s %d/%d", job_id, phase, current, total)
            db.heartbeat_ingestion_job(job_id)

        result = pipeline.run(job_id=job_id, on_progress=on_progress)
        db.update_ingestion_job(job_id, status=result.get("status", "done"), result=result)
        return result

    except Exception as e:
        logger.error("Job %d failed: %s", job_id, e)
        db.update_ingestion_job(job_id, status="failed", result={"error": str(e)})
        return {"status": "failed", "error": str(e)}

    finally:
        hb_task.cancel()
        try:
            await hb_task
        except asyncio.CancelledError:
            pass
        # Cleanup temp dir
        if work_dir and work_dir.exists():
            shutil.rmtree(work_dir, ignore_errors=True)


async def process_queue() -> int:
    """Pull and execute all pending jobs. Returns count processed."""
    jobs = db.list_ingestion_jobs(status="pending")
    if not jobs:
        return 0

    sem = _get_semaphore()
    processed = 0

    async def _run_with_sem(jid: int) -> None:
        nonlocal processed
        async with sem:
            await run_job(jid)
            processed += 1

    tasks = [asyncio.create_task(_run_with_sem(j["id"])) for j in jobs]
    await asyncio.gather(*tasks, return_exceptions=True)
    return processed
