"""
server/librivox.py — LibriVox API client and RSS parser.

Proxies calls to librivox.org (no CORS on their API) and parses RSS feeds
for chapter data. Audio streams come directly from archive.org (CORS-enabled).
"""

import logging
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger("leerio.librivox")

LIBRIVOX_API = "https://librivox.org/api/feed/audiobooks"
LIBRIVOX_RSS = "https://librivox.org/rss"
REQUEST_TIMEOUT = 15


def _parse_duration(s: str) -> int:
    """Parse duration string to total seconds. Handles HH:MM:SS, MM:SS, or raw seconds."""
    if not s:
        return 0
    s = s.strip()
    # Raw seconds
    if s.isdigit():
        return int(s)
    parts = s.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        pass
    return 0


def _normalize_book(raw: dict) -> dict:
    """Convert LibriVox API JSON to our normalized format."""
    authors = raw.get("authors") or []
    author_names = ", ".join(f"{a.get('first_name', '')} {a.get('last_name', '')}".strip() for a in authors)
    total_time = raw.get("totaltime", "")
    return {
        "librivox_id": str(raw.get("id", "")),
        "title": raw.get("title", "").strip(),
        "author": author_names or "Unknown",
        "description": raw.get("description", ""),
        "language": raw.get("language", ""),
        "copyright_year": str(raw.get("copyright_year", "")),
        "num_sections": int(raw.get("num_sections") or 0),
        "total_time": total_time,
        "total_time_secs": _parse_duration(total_time),
        "url_librivox": raw.get("url_librivox", ""),
    }


def search_books(
    title: str = "",
    author: str = "",
    language: str = "",
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Search LibriVox audiobooks. Returns {books, total}."""
    params: dict[str, str | int] = {"format": "json", "limit": limit, "offset": offset}
    if title:
        params["title"] = title
    if author:
        params["author"] = author
    if language:
        # LibriVox API uses full language names
        params["language"] = language

    try:
        resp = requests.get(LIBRIVOX_API, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.exception("LibriVox search failed")
        return {"books": [], "total": 0}

    raw_books = data.get("books") or []
    # LibriVox returns {"error": "..."} when no results
    if isinstance(raw_books, dict):
        return {"books": [], "total": 0}

    books = [_normalize_book(b) for b in raw_books]
    return {"books": books, "total": len(books)}


def get_book(librivox_id: str) -> dict | None:
    """Fetch a single book by LibriVox ID."""
    params = {"format": "json", "id": librivox_id}
    try:
        resp = requests.get(LIBRIVOX_API, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        logger.exception("LibriVox get_book failed for id=%s", librivox_id)
        return None

    raw_books = data.get("books") or []
    if isinstance(raw_books, dict) or not raw_books:
        return None
    return _normalize_book(raw_books[0])


def get_chapters(librivox_id: str) -> dict:
    """Parse RSS feed for chapter list. Returns {chapters, cover_url}."""
    url = f"{LIBRIVOX_RSS}/{librivox_id}"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception:
        logger.exception("LibriVox RSS fetch failed for id=%s", librivox_id)
        return {"chapters": [], "cover_url": None}

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError:
        logger.error("Failed to parse RSS XML for id=%s", librivox_id)
        return {"chapters": [], "cover_url": None}

    # Namespace handling for itunes tags
    ns = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}

    # Cover image from channel-level itunes:image
    cover_url = None
    channel = root.find("channel")
    if channel is not None:
        img_el = channel.find("itunes:image", ns)
        if img_el is not None:
            cover_url = img_el.get("href")

    chapters = []
    items = root.findall(".//item") if channel is None else channel.findall("item")
    for i, item in enumerate(items):
        title_el = item.find("title")
        title = title_el.text.strip() if title_el is not None and title_el.text else f"Chapter {i + 1}"

        enclosure = item.find("enclosure")
        mp3_url = enclosure.get("url", "") if enclosure is not None else ""
        size_str = enclosure.get("length", "0") if enclosure is not None else "0"

        dur_el = item.find("itunes:duration", ns)
        dur_text = dur_el.text if dur_el is not None and dur_el.text else "0"
        duration = _parse_duration(dur_text)

        # Clean up http -> https for archive.org
        if mp3_url.startswith("http://"):
            mp3_url = "https://" + mp3_url[7:]

        chapters.append(
            {
                "index": i,
                "title": title,
                "url": mp3_url,
                "duration": duration,
                "size_bytes": int(size_str) if size_str.isdigit() else 0,
            }
        )

    return {"chapters": chapters, "cover_url": cover_url}
