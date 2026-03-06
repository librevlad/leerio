"""Archive.org audiobook source."""

import logging
from urllib.parse import urlencode

import httpx

logger = logging.getLogger("leerio.ingest")

SEARCH_URL = "https://archive.org/advancedsearch.php"
METADATA_URL = "https://archive.org/metadata"
DOWNLOAD_URL = "https://archive.org/download"


def search_audiobooks(query: str = "audiobook russian", limit: int = 20) -> list[dict]:
    """Search Archive.org for audiobooks. Returns list of raw result dicts."""
    params = {
        "q": f"({query}) AND mediatype:audio AND format:VBR+MP3",
        "fl[]": "identifier,title,creator,description",
        "rows": limit,
        "output": "json",
    }
    url = f"{SEARCH_URL}?{urlencode(params, doseq=True)}"
    logger.info("Searching Archive.org: %s", url)

    resp = httpx.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("response", {}).get("docs", [])


def get_mp3_files(identifier: str) -> list[str]:
    """Get list of MP3 file URLs for an Archive.org item."""
    url = f"{METADATA_URL}/{identifier}/files"
    resp = httpx.get(url, timeout=30)
    resp.raise_for_status()
    files = resp.json().get("result", [])

    mp3_urls = []
    for f in files:
        name = f.get("name", "")
        if name.lower().endswith(".mp3"):
            mp3_urls.append(f"{DOWNLOAD_URL}/{identifier}/{name}")

    return sorted(mp3_urls)


def parse_item(raw: dict) -> dict:
    """Parse an Archive.org search result into ingestion input_data format."""
    identifier = raw.get("identifier", "")
    return {
        "title": raw.get("title", "Unknown"),
        "author": raw.get("creator", "Unknown"),
        "reader": "",
        "language": "",
        "category": "",
        "source_url": f"https://archive.org/details/{identifier}",
        "external_id": f"archive:{identifier}",
        "archive_identifier": identifier,
    }


def create_ingestion_jobs(query: str = "audiobook russian", limit: int = 20) -> list[int]:
    """Search Archive.org and create ingestion jobs for each result."""
    from ... import db

    results = search_audiobooks(query=query, limit=limit)
    job_ids = []
    for raw in results:
        parsed = parse_item(raw)
        identifier = parsed["archive_identifier"]

        # Fetch MP3 file list
        try:
            mp3_urls = get_mp3_files(identifier)
        except Exception:
            logger.warning("Failed to get files for %s", identifier)
            continue

        if not mp3_urls:
            logger.warning("No MP3s found for %s", identifier)
            continue

        parsed["mp3_urls"] = mp3_urls
        job_id = db.create_ingestion_job("archive", parsed)
        job_ids.append(job_id)
        logger.info("Created job #%d for: %s", job_id, parsed["title"])

    return job_ids
