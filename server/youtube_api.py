"""YouTube metadata resolution and audio streaming."""

import asyncio
import json
import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .auth import get_current_user

router = APIRouter(prefix="/api/youtube", tags=["youtube"])

_YT_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")

# ── YouTube auth for bot-detection bypass ─────────────────────────────────────
_BASE = Path(__file__).resolve().parent.parent
_DATA_DIR = Path(os.environ.get("LEERIO_DATA", str(_BASE / "data")))
_COOKIES_PATH = Path(os.environ.get("YT_COOKIES", str(_DATA_DIR / "youtube-cookies.txt")))
_CACHE_DIR = _DATA_DIR / "yt-dlp-cache"


def _yt_dlp_auth_args() -> list[str]:
    """Return yt-dlp auth args: cookies file or OAuth2 cached token."""
    args: list[str] = [
        "--cache-dir", str(_CACHE_DIR),
        "--remote-components", "ejs:github",
    ]
    if _COOKIES_PATH.is_file():
        args.extend(["--cookies", str(_COOKIES_PATH)])
    return args


_YT_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})"
)
_MAX_DURATION = 24 * 3600


class ResolveRequest(BaseModel):
    url: str


class Chapter(BaseModel):
    title: str
    start: float
    end: float


class ResolveResponse(BaseModel):
    video_id: str
    title: str
    author: str
    duration: float
    thumbnail: str
    chapters: list[Chapter]


def _parse_author(title: str) -> tuple[str, str]:
    """Try to extract author from 'Author — Title' pattern."""
    for sep in (" — ", " – ", " - "):
        if sep in title:
            parts = title.split(sep, 1)
            return parts[0].strip(), parts[1].strip()
    return "", title


def _extract_video_id(url: str) -> str | None:
    m = _YT_URL_RE.search(url)
    return m.group(1) if m else None


async def _yt_dlp_json(video_id: str) -> dict:
    if not _YT_ID_RE.match(video_id):
        raise HTTPException(400, "Invalid video ID")
    try:
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            *_yt_dlp_auth_args(),
            "--dump-json",
            "--no-download",
            "--no-warnings",
            f"https://www.youtube.com/watch?v={video_id}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise HTTPException(503, "yt-dlp is not installed on the server")
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(504, "YouTube metadata fetch timed out")
    if proc.returncode != 0:
        err = stderr.decode(errors="replace").strip()
        if "Private video" in err or "Video unavailable" in err:
            raise HTTPException(404, "Video not found or private")
        err_lower = err.lower()
        if "sign in" in err_lower or "cookie" in err_lower or "bot" in err_lower:
            raise HTTPException(
                403,
                "YouTube requires authentication — update cookies file on the server",
            )
        raise HTTPException(400, f"yt-dlp error: {err[:200]}")
    return json.loads(stdout)


@router.post("/resolve", response_model=ResolveResponse)
async def resolve(body: ResolveRequest, _user=Depends(get_current_user)):
    video_id = _extract_video_id(body.url)
    if not video_id:
        raise HTTPException(400, "Invalid YouTube URL")

    info = await _yt_dlp_json(video_id)

    duration = info.get("duration") or 0
    if duration <= 0:
        raise HTTPException(400, "Video has no duration (possibly a live stream)")
    if duration > _MAX_DURATION:
        raise HTTPException(413, f"Video too long ({duration}s > {_MAX_DURATION}s)")

    raw_title = info.get("title", "")
    author, title = _parse_author(raw_title)

    chapters: list[Chapter] = []
    for i, ch in enumerate(info.get("chapters") or []):
        start = ch.get("start_time", 0)
        end = ch.get("end_time", 0)
        if end > start:
            title = ch.get("title", "").strip() or f"Chapter {i + 1}"
            chapters.append(Chapter(title=title, start=start, end=end))

    thumbnail = info.get("thumbnail", "")

    return ResolveResponse(
        video_id=video_id,
        title=title,
        author=author,
        duration=duration,
        thumbnail=thumbnail,
        chapters=chapters,
    )


@router.get("/stream/{video_id}")
async def stream_audio(video_id: str, _user=Depends(get_current_user)):
    if not _YT_ID_RE.match(video_id):
        raise HTTPException(400, "Invalid video ID")

    try:
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            *_yt_dlp_auth_args(),
            "-f",
            "bestaudio",
            "-o",
            "-",
            f"https://www.youtube.com/watch?v={video_id}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise HTTPException(503, "yt-dlp is not installed on the server")

    async def generate():
        try:
            while True:
                chunk = await proc.stdout.read(64 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()

    return StreamingResponse(
        generate(),
        media_type="audio/webm",
        headers={"Cache-Control": "no-store"},
    )
