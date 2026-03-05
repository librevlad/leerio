"""
server/tts_api.py — TTS API endpoints.

Handles document upload, TTS job creation, and progress polling.
"""

import asyncio
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from .auth import get_current_user
from .core import UserData, make_slug
from .tts import VOICES, run_tts_job

logger = logging.getLogger("leerio.tts")

router = APIRouter(prefix="/api/tts", tags=["tts"])

ALLOWED_EXTENSIONS = {".pdf", ".epub", ".txt", ".fb2"}


def _user_data(user: dict) -> UserData:
    return UserData(user["user_id"])


@router.get("/voices")
def list_voices():
    return VOICES


@router.post("/convert")
async def start_conversion(
    title: str = Form(...),
    author: str = Form(""),
    voice: str = Form("ru-RU-DmitryNeural"),
    rate: str = Form("+0%"),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    # Validate file extension
    if not file.filename:
        raise HTTPException(400, "No filename provided")
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported format: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # Validate voice
    valid_voices = {v["id"] for v in VOICES}
    if voice not in valid_voices:
        raise HTTPException(400, f"Unknown voice: {voice}")

    ud = _user_data(user)
    slug = make_slug(title, author)

    # Ensure unique slug
    existing = ud.books_dir / slug
    if existing.exists():
        counter = 2
        while (ud.books_dir / f"{slug}-{counter}").exists():
            counter += 1
        slug = f"{slug}-{counter}"

    # Save uploaded document to temp location
    temp_dir = ud.dir / "tmp"
    temp_dir.mkdir(exist_ok=True)
    source_path = temp_dir / f"{slug}{ext}"
    content = await file.read()
    source_path.write_bytes(content)

    # Create job
    job_id = str(uuid.uuid4())[:8]
    job = ud.tts_job_create(job_id, title, author, voice, slug)

    # Start background task
    asyncio.create_task(run_tts_job(ud, job_id, source_path, voice, slug, title, author, rate))

    logger.info("TTS conversion started: job=%s, slug=%s, voice=%s", job_id, slug, voice)
    return job


@router.get("/jobs")
def list_jobs(user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    return ud.tts_jobs_load()


@router.get("/jobs/{job_id}")
def get_job(job_id: str, user: dict = Depends(get_current_user)):
    ud = _user_data(user)
    job = ud.tts_job_get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job
