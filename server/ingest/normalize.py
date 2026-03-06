"""Audio normalization via ffmpeg."""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("leerio.ingest")

AUDIO_EXTENSIONS = {".mp3", ".m4b", ".m4a", ".opus", ".ogg", ".flac", ".wav", ".wma"}


def is_mp3(path: Path) -> bool:
    return path.suffix.lower() == ".mp3"


def build_ffmpeg_cmd(input_path: Path, output_path: Path, *, fast: bool = False, timeout: int = 300) -> list[str]:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ar",
        "44100",
        "-ac",
        "1",
        "-b:a",
        "128k",
    ]
    if not fast:
        cmd.extend(["-af", "loudnorm"])
    cmd.append(str(output_path))
    return cmd


def normalize_file(input_path: Path, output_path: Path, *, fast: bool = False, timeout: int = 300) -> None:
    cmd = build_ffmpeg_cmd(input_path, output_path, fast=fast)
    logger.info("ffmpeg: %s -> %s (fast=%s)", input_path.name, output_path.name, fast)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({result.returncode}): {result.stderr[:500]}")
