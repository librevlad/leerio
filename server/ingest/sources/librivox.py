"""LibriVox audiobook source — fetches from librivox.org API."""

import logging
from urllib.parse import urlencode

import httpx

logger = logging.getLogger("leerio.ingest")

API_BASE = "https://librivox.org/api/feed/audiobooks"

# LibriVox API uses full language names
LANG_MAP = {"ru": "Russian", "en": "English", "de": "German", "fr": "French", "es": "Spanish"}


def fetch_catalog(lang: str = "Russian", limit: int = 50, offset: int = 0) -> list[dict]:
    """Fetch audiobooks from LibriVox API with section details.

    Returns list of raw book dicts from the API response.
    The `lang` param should be full name ("Russian") or ISO code ("ru").
    """
    lang_full = LANG_MAP.get(lang, lang)

    params = {
        "format": "json",
        "extended": 1,
        "limit": limit,
        "offset": offset,
    }

    url = f"{API_BASE}?{urlencode(params)}"
    logger.info("Fetching LibriVox catalog: %s", url)

    resp = httpx.get(url, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    all_books = data.get("books", [])

    # Filter by language client-side (API language filter is unreliable)
    if lang_full:
        all_books = [b for b in all_books if b.get("language", "").lower() == lang_full.lower()]

    return all_books


def fetch_all_by_language(lang: str = "Russian", batch_size: int = 1000) -> list[dict]:
    """Scan entire LibriVox catalog and return all books in given language."""
    lang_full = LANG_MAP.get(lang, lang)
    results = []
    offset = 0
    while True:
        params = {"format": "json", "extended": 1, "limit": batch_size, "offset": offset}
        url = f"{API_BASE}?{urlencode(params)}"
        logger.info("Scanning LibriVox offset=%d ...", offset)
        try:
            resp = httpx.get(url, timeout=60)
            resp.raise_for_status()
            books = resp.json().get("books", [])
        except Exception as e:
            logger.warning("LibriVox fetch failed at offset %d: %s", offset, e)
            break
        if not books:
            break
        matched = [b for b in books if b.get("language", "").lower() == lang_full.lower()]
        results.extend(matched)
        logger.info("  found %d/%d %s books (total so far: %d)", len(matched), len(books), lang_full, len(results))
        offset += batch_size
    return results


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


def create_ingestion_jobs(lang: str = "Russian", limit: int | None = None, scan_all: bool = False) -> list[int]:
    """Fetch LibriVox catalog and create ingestion jobs for each book.

    If scan_all=True, scans the entire catalog (slow, ~20 API calls).
    Otherwise fetches up to `limit` books from offset 0.
    """
    from ... import db

    if scan_all:
        books = fetch_all_by_language(lang=lang)
    else:
        books = fetch_catalog(lang=lang, limit=limit or 50)

    if limit:
        books = books[:limit]

    job_ids = []
    for raw in books:
        parsed = parse_book(raw)
        if not parsed["mp3_urls"]:
            logger.warning("Skipping %s — no MP3 URLs", parsed["title"])
            continue
        # Large books with many sections need more time (1 hour)
        job_id = db.create_ingestion_job("librivox", parsed, timeout_seconds=3600)
        job_ids.append(job_id)
        logger.info("Created job #%d for: %s", job_id, parsed["title"])

    return job_ids
