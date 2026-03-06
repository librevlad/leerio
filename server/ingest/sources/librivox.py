"""LibriVox audiobook source — fetches from librivox.org API."""

import logging
from urllib.parse import urlencode

import httpx

logger = logging.getLogger("leerio.ingest")

API_BASE = "https://librivox.org/api/feed/audiobooks"


def fetch_catalog(lang: str = "ru", limit: int = 50, offset: int = 0) -> list[dict]:
    """Fetch audiobooks from LibriVox API.

    Returns list of raw book dicts from the API response.
    """
    params = {
        "format": "json",
        "limit": limit,
        "offset": offset,
    }
    if lang:
        params["language"] = lang

    url = f"{API_BASE}?{urlencode(params)}"
    logger.info("Fetching LibriVox catalog: %s", url)

    resp = httpx.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("books", [])


def parse_book(raw: dict) -> dict:
    """Parse a raw LibriVox API book into ingestion input_data format."""
    sections = raw.get("sections", [])
    mp3_urls = []
    for section in sections:
        url = section.get("listen_url", "")
        if url:
            mp3_urls.append(url)

    total_time = raw.get("totaltime", "0:00:00")
    # Parse "HH:MM:SS" to hours
    parts = total_time.split(":")
    try:
        hours = int(parts[0]) + int(parts[1]) / 60 + int(parts[2]) / 3600
    except (ValueError, IndexError):
        hours = 0

    return {
        "title": raw.get("title", "Unknown"),
        "author": ", ".join(
            f"{a.get('first_name', '')} {a.get('last_name', '')}".strip() for a in raw.get("authors", [])
        )
        or "Unknown",
        "reader": "",
        "language": raw.get("language", ""),
        "category": "",
        "source_url": raw.get("url_librivox", ""),
        "external_id": f"librivox:{raw.get('id', '')}",
        "mp3_urls": mp3_urls,
        "duration_hours": round(hours, 2),
    }


def create_ingestion_jobs(lang: str = "ru", limit: int = 50) -> list[int]:
    """Fetch LibriVox catalog and create ingestion jobs for each book."""
    from ... import db

    books = fetch_catalog(lang=lang, limit=limit)
    job_ids = []
    for raw in books:
        parsed = parse_book(raw)
        if not parsed["mp3_urls"]:
            logger.warning("Skipping %s — no MP3 URLs", parsed["title"])
            continue
        job_id = db.create_ingestion_job("librivox", parsed)
        job_ids.append(job_id)
        logger.info("Created job #%d for: %s", job_id, parsed["title"])

    return job_ids
