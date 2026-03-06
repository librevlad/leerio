"""Admin API endpoints for content ingestion."""

import json

from fastapi import APIRouter, Depends, HTTPException
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
