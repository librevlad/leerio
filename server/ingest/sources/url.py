"""URL/RSS/YouTube audiobook source — direct download, RSS feed, or yt-dlp."""

import logging
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("leerio.ingest")


def download_file(url: str, dest: Path, timeout: int = 60) -> Path:
    """Download a file from URL to dest path."""
    logger.info("Downloading: %s -> %s", url, dest.name)
    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=8192):
                f.write(chunk)
    return dest


def download_direct(url: str, work_dir: Path) -> list[Path]:
    """Download a single audio file from a direct URL."""
    parsed = urlparse(url)
    filename = Path(parsed.path).name or "audio.mp3"
    dest = work_dir / filename
    download_file(url, dest)
    return [dest]


def download_rss(feed_url: str, work_dir: Path) -> list[Path]:
    """Parse RSS feed and download all audio enclosures."""
    import feedparser

    logger.info("Parsing RSS feed: %s", feed_url)
    feed = feedparser.parse(feed_url)
    files = []

    for i, entry in enumerate(feed.entries, 1):
        for enclosure in entry.get("enclosures", []):
            url = enclosure.get("href", "")
            if not url:
                continue
            ext = Path(urlparse(url).path).suffix or ".mp3"
            dest = work_dir / f"{i:03d}{ext}"
            try:
                download_file(url, dest)
                files.append(dest)
            except Exception:
                logger.warning("Failed to download: %s", url)

    return files


def download_youtube(url: str, work_dir: Path) -> list[Path]:
    """Extract audio from YouTube via yt-dlp. Private import only."""
    logger.info("Extracting audio from YouTube: %s", url)
    output_template = str(work_dir / "%(title)s.%(ext)s")

    result = subprocess.run(
        [
            "yt-dlp",
            "--extract-audio",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "128K",
            "-o",
            output_template,
            url,
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )

    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr[:500]}")

    # Find downloaded MP3 files
    files = sorted(work_dir.glob("*.mp3"))
    if not files:
        raise RuntimeError("yt-dlp produced no MP3 files")
    return files


def download_from_source(url: str, source_type: str, work_dir: Path) -> list[Path]:
    """Download audio files based on source type."""
    if source_type == "rss":
        return download_rss(url, work_dir)
    elif source_type == "youtube":
        return download_youtube(url, work_dir)
    else:
        return download_direct(url, work_dir)
