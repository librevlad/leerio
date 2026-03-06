"""Admin API endpoints for content ingestion."""

import asyncio
import json
import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from . import db
from .auth import get_current_user

logger = logging.getLogger("leerio.ingest_api")

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
            "description TEXT DEFAULT ''",
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


@router.post("/recover")
def recover_stalled(user: dict = Depends(require_admin)):
    """Reset stalled processing jobs back to pending."""
    conn = db._get_conn()
    try:
        cur = conn.execute("""
            UPDATE ingestion_jobs
            SET status = 'pending', retries = retries + 1, updated_at = datetime('now')
            WHERE status = 'processing'
        """)
        conn.commit()
        return {"recovered": cur.rowcount}
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


# --- Book description generation ---

_desc_status: dict = {"running": False, "total": 0, "done": 0, "error": None}


def _generate_descriptions_task():
    """Background task: generate short descriptions for all books missing one."""
    import httpx

    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key:
        _desc_status["error"] = "OPENAI_API_KEY not set"
        _desc_status["running"] = False
        return

    books = db.get_books_without_description()
    _desc_status["total"] = len(books)
    _desc_status["done"] = 0
    _desc_status["running"] = True
    _desc_status["error"] = None

    # Process in batches of 10 for efficiency
    batch_size = 10
    for i in range(0, len(books), batch_size):
        batch = books[i : i + batch_size]
        books_text = "\n".join(f"ID:{b['id']} | {b['title']} | {b['author']} | {b['category']}" for b in batch)
        prompt = (
            "Для каждой книги напиши краткое описание на русском языке (2-3 предложения, до 200 символов). "
            "Описание должно передать суть книги и заинтересовать читателя. "
            'Формат ответа — JSON массив: [{"id": <id>, "description": "<текст>"}]\n\n'
            f"Книги:\n{books_text}"
        )

        try:
            resp = httpx.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "response_format": {"type": "json_object"},
                },
                timeout=60,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            # Parse JSON from response
            data = json.loads(content)
            # Handle both {"descriptions": [...]} and [...] formats
            if isinstance(data, dict):
                items = data.get("descriptions", data.get("books", list(data.values())[0] if data else []))
            else:
                items = data

            for item in items:
                if isinstance(item, dict) and "id" in item and "description" in item:
                    db.update_book_description(int(item["id"]), item["description"])
                    _desc_status["done"] += 1
        except Exception as e:
            logger.error("Description generation batch failed: %s", e)
            _desc_status["error"] = str(e)

    _desc_status["running"] = False


@router.post("/descriptions/generate")
def generate_descriptions(
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_admin),
):
    """Generate short descriptions for all books that don't have one."""
    if _desc_status["running"]:
        return {"message": "Already running", "status": _desc_status}

    books = db.get_books_without_description()
    if not books:
        return {"message": "All books have descriptions", "total": 0}

    background_tasks.add_task(_generate_descriptions_task)
    return {"message": f"Generating descriptions for {len(books)} books", "total": len(books)}


@router.get("/descriptions/status")
def descriptions_status(user: dict = Depends(require_admin)):
    """Check status of description generation."""
    return _desc_status


class UpdateDescriptionRequest(BaseModel):
    description: str


@router.put("/books/{book_id}/description")
def update_description(
    book_id: int,
    req: UpdateDescriptionRequest,
    user: dict = Depends(require_admin),
):
    """Manually set a book's description."""
    book = db.get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    db.update_book_description(book_id, req.description)
    return {"id": book_id, "description": req.description}
