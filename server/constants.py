"""Shared constants for the Leerio server."""

import os

# ── Upload limits ─────────────────────────────────────────────────────
MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500 MB (matches nginx client_max_body_size)
MAX_COVER_SIZE = 50 * 1024 * 1024  # 50 MB
FREE_BOOK_LIMIT = int(os.environ.get("FREE_BOOK_LIMIT", "10"))

# ── Cryptography ──────────────────────────────────────────────────────
PBKDF2_ITERATIONS = 100_000
PBKDF2_ALGORITHM = "sha256"

# ── API defaults ──────────────────────────────────────────────────────
DEFAULT_HISTORY_LIMIT = 100
DASHBOARD_HISTORY_LIMIT = 500

# ── Rate limits ───────────────────────────────────────────────────────
RATE_LIMIT_OAUTH = "10/minute"
RATE_LIMIT_LOGIN = "5/minute"

# ── Category fallback ─────────────────────────────────────────────────
DEFAULT_CATEGORY_GRADIENT = "linear-gradient(135deg, #334155 0%, #64748b 100%)"

# ── File validation ───────────────────────────────────────────────────
VALID_IMAGE_HEADERS = [b"\xff\xd8\xff", b"\x89PNG"]
VALID_MP3_HEADERS = [b"\xff\xfb", b"\xff\xfa", b"\xff\xf3", b"\xff\xf2", b"ID3"]
VALID_AUDIO_EXTENSIONS = {".mp3", ".m4a", ".m4b", ".ogg", ".opus", ".flac", ".wav"}
VALID_AUDIO_HEADERS = [
    b"\xff\xfb",
    b"\xff\xfa",
    b"\xff\xf3",
    b"\xff\xf2",
    b"ID3",  # MP3
    b"ftyp",  # M4A/M4B (offset 4, but first 4 bytes vary)
    b"OggS",  # OGG/Opus
    b"fLaC",  # FLAC
    b"RIFF",  # WAV
]
