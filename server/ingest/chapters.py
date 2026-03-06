"""Chapter detection for audiobooks."""

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("leerio.ingest")

DEFAULT_INTERVAL = 600  # 10 minutes


def detect_chapters_fallback(tracks: list[dict], interval_seconds: int = DEFAULT_INTERVAL) -> list[dict]:
    """Split tracks into chapters by cumulative duration."""
    chapters = []
    cumulative = 0
    next_split = 0
    for i, t in enumerate(tracks):
        if cumulative >= next_split:
            chapters.append(
                {
                    "title": f"Часть {len(chapters) + 1}",
                    "start": int(cumulative),
                    "track": i,
                }
            )
            next_split = cumulative + interval_seconds
        cumulative += t["duration"]
    if not chapters and tracks:
        chapters.append({"title": "Часть 1", "start": 0, "track": 0})
    return chapters


def parse_embedded_chapters(raw_chapters: list) -> list[dict]:
    """Parse ffprobe chapter output into standard format."""
    result = []
    for ch in raw_chapters:
        title = ch.get("tags", {}).get("title", f"Chapter {len(result) + 1}")
        start = float(ch.get("start_time", 0))
        result.append({"title": title, "start": int(start), "track": 0})
    return result


def detect_chapters_from_file(file_path: Path) -> list[dict]:
    """Try to extract embedded chapters from m4b/mp3 via ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_chapters",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            chapters = data.get("chapters", [])
            if chapters:
                return parse_embedded_chapters(chapters)
    except Exception:
        logger.warning("Failed to extract chapters from %s", file_path.name)
    return []
