"""Metadata extraction from audio files."""
import logging
from pathlib import Path

from mutagen.mp3 import MP3

logger = logging.getLogger("leerio.ingest")


def extract_track_duration(path: Path) -> float:
    """Get duration in seconds from an MP3 file."""
    try:
        audio = MP3(str(path))
        return audio.info.length
    except Exception:
        logger.warning("Cannot read duration: %s", path.name)
        return 0.0


def extract_cover_from_mp3(path: Path) -> bytes | None:
    """Extract embedded cover art from MP3 ID3 tags."""
    try:
        from mutagen.id3 import ID3
        tags = ID3(str(path))
        for key in tags:
            if key.startswith("APIC"):
                return tags[key].data
    except Exception:
        pass
    return None


def build_tracks_json(mp3_files: list[Path]) -> list[dict]:
    """Build tracks.json from ordered list of MP3 files."""
    result = []
    for i, f in enumerate(sorted(mp3_files), 1):
        duration = extract_track_duration(f)
        result.append({"track": i, "file": f.name, "duration": duration})
    return result


def build_metadata_json(
    *,
    title: str,
    author: str,
    reader: str = "",
    category: str = "",
    language: str = "ru",
    source: str = "manual",
    duration_hours: float = 0,
) -> dict:
    """Build metadata.json content."""
    return {
        "version": 1,
        "title": title,
        "author": author,
        "reader": reader,
        "category": category,
        "language": language,
        "source": source,
        "duration_hours": round(duration_hours, 2),
    }
