"""Admin API endpoints for content ingestion."""

import asyncio
import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from . import db
from .auth import get_current_user

router = APIRouter(prefix="/api/admin/ingest", tags=["ingest"])


def require_admin(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


class CreateJobRequest(BaseModel):
    source: str
    input_data: dict = {}
    timeout_seconds: int = 600


@router.post("")
def create_ingest_job(req: CreateJobRequest, user: dict = Depends(require_admin)):
    job_id = db.create_ingestion_job(req.source, req.input_data, req.timeout_seconds)
    return {"id": job_id, "status": "pending"}


@router.get("/jobs")
def list_ingest_jobs(
    status: str | None = None,
    limit: int = 50,
    user: dict = Depends(require_admin),
):
    jobs = db.list_ingestion_jobs(status=status, limit=limit)
    return {"jobs": jobs, "total": len(jobs)}


@router.get("/jobs/{job_id}")
def get_ingest_job(job_id: int, user: dict = Depends(require_admin)):
    job = db.get_ingestion_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # Parse JSON fields for display
    result = dict(job)
    if result.get("input_data"):
        result["input_data"] = json.loads(result["input_data"])
    if result.get("result"):
        result["result"] = json.loads(result["result"])
    return result


@router.post("/retry/{job_id}")
def retry_ingest_job(job_id: int, user: dict = Depends(require_admin)):
    job = db.get_ingestion_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] not in ("failed", "partial"):
        raise HTTPException(status_code=400, detail=f"Job is {job['status']}, not retryable")
    db.update_ingestion_job(job_id, status="pending")
    return {"id": job_id, "status": "pending"}


@router.post("/migrate")
def run_migration(user: dict = Depends(require_admin)):
    """Force-run DB migration for ingestion columns."""
    conn = db._get_conn()
    results = []
    try:
        for col in [
            "language TEXT DEFAULT 'ru'",
            "source TEXT DEFAULT 'manual'",
            "external_id TEXT",
            "fingerprint TEXT",
        ]:
            try:
                conn.execute(f"ALTER TABLE books ADD COLUMN {col}")
                results.append(f"Added: {col}")
            except Exception as e:
                results.append(f"Skipped: {col} ({e})")
        conn.commit()

        # Verify
        cols = [r[1] for r in conn.execute("PRAGMA table_info(books)").fetchall()]
        return {"results": results, "columns": cols}
    finally:
        conn.close()


@router.get("/stats")
def ingest_stats(user: dict = Depends(require_admin)):
    conn = db._get_conn()
    try:
        stats = conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped
            FROM ingestion_jobs
        """).fetchone()
        return dict(stats)
    finally:
        conn.close()


class LibriVoxImportRequest(BaseModel):
    lang: str = "Russian"
    scan_all: bool = True


# Track background import status
_import_status: dict = {"running": False, "jobs_created": 0, "error": None}


def _run_librivox_import(lang: str, scan_all: bool):
    """Background task to scan LibriVox and create jobs."""
    from .ingest.sources.librivox import create_ingestion_jobs

    _import_status["running"] = True
    _import_status["error"] = None
    try:
        job_ids = create_ingestion_jobs(lang=lang, scan_all=scan_all)
        _import_status["jobs_created"] = len(job_ids)
    except Exception as e:
        _import_status["error"] = str(e)
    finally:
        _import_status["running"] = False


@router.post("/librivox")
def import_librivox(
    req: LibriVoxImportRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_admin),
):
    """Scan LibriVox catalog and create ingestion jobs (runs in background)."""
    if _import_status["running"]:
        return {"message": "Import already running", "status": _import_status}
    background_tasks.add_task(_run_librivox_import, req.lang, req.scan_all)
    return {"message": "LibriVox scan started in background", "status": "started"}


@router.get("/librivox/status")
def librivox_status(user: dict = Depends(require_admin)):
    """Check status of background LibriVox import."""
    return _import_status


def _run_queue_sync():
    """Run the job queue in a new event loop (for background tasks)."""
    from .ingest.jobs import process_queue

    loop = asyncio.new_event_loop()
    try:
        processed = loop.run_until_complete(process_queue())
        return processed
    finally:
        loop.close()


@router.post("/process")
def process_queue_endpoint(background_tasks: BackgroundTasks, user: dict = Depends(require_admin)):
    """Start processing all pending ingestion jobs in the background."""
    pending = db.list_ingestion_jobs(status="pending")
    if not pending:
        return {"message": "No pending jobs", "pending": 0}

    background_tasks.add_task(_run_queue_sync)
    return {"message": f"Processing {len(pending)} jobs in background", "pending": len(pending)}
