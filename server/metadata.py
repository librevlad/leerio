"""
server/metadata.py — Cover art and ID3 tags for the audiobook library.

For each book:
  1. Standardizes existing covers -> cover.jpg
  2. Downloads cover via Google Books API (if missing)
  3. Writes ID3 tags (author, title, reader, genre, cover)
"""

import csv
import logging
import re
import sys
import time
from io import BytesIO
from pathlib import Path

import requests
from mutagen.id3 import APIC, ID3, TALB, TCON, TPE1, TPE2, ID3NoHeaderError
from PIL import Image

from .core import BOOKS_DIR, CATEGORIES, TRACKER_PATH

# ── Settings ──────────────────────────────────────────────────────────────────

logger = logging.getLogger("leerio.metadata")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}
API_DELAY = 0.5


# ── Utilities ────────────────────────────────────────────────────────────────


def parse_folder(name: str):
    """'Автор - Название [Чтец]' -> (author, title, reader)"""
    reader = None
    m = re.match(r"^(.+?)\s*\[(.+?)\]$", name)
    if m:
        rest, reader = m.group(1).strip(), m.group(2).strip()
    else:
        rest = name.strip()

    if " - " in rest:
        author, title = rest.split(" - ", 1)
    else:
        author, title = "", rest

    return author.strip(), title.strip(), reader


def load_tracker():
    """CSV -> dict by book title"""
    data = {}
    if not TRACKER_PATH.exists():
        return data
    with open(TRACKER_PATH, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            title = row["Название"].strip()
            if title:
                data[title] = row
    return data


def find_books():
    """All book folders from categories"""
    folders = []
    for cat in CATEGORIES:
        cat_path = BOOKS_DIR / cat
        if not cat_path.exists():
            continue
        for d in sorted(cat_path.iterdir()):
            if d.is_dir() and not d.name.startswith("_"):
                folders.append(d)
    return folders


def has_cyrillic(text: str) -> bool:
    return bool(re.search("[а-яёА-ЯЁ]", text))


# ── Covers ────────────────────────────────────────────────────────────────────


def standardize_cover(book_dir: Path):
    """Find/rename existing cover -> cover.jpg. Returns Path or None."""
    cover = book_dir / "cover.jpg"
    if cover.exists():
        return cover

    images = []
    for f in book_dir.iterdir():
        if not f.is_file():
            continue
        if f.suffix.lower() not in IMAGE_EXTS:
            continue
        if "_spectrogram" in f.name.lower():
            continue
        images.append(f)

    if not images:
        return None

    best = max(images, key=lambda p: p.stat().st_size)

    if best.suffix.lower() in (".jpg", ".jpeg"):
        best.rename(cover)
    else:
        img = Image.open(best)
        img.convert("RGB").save(cover, "JPEG", quality=95)
        best.unlink()

    return cover


def download_cover(author: str, title: str, book_dir: Path, is_english: bool = False):
    """Download cover via Google Books API. Returns Path or None."""
    cover = book_dir / "cover.jpg"
    if cover.exists():
        return cover

    query = f"{author} {title}".strip() if author else title

    try:
        resp = requests.get(
            "https://www.googleapis.com/books/v1/volumes",
            params={"q": query, "maxResults": 5},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("totalItems"):
            return None

        for item in data.get("items", []):
            links = item.get("volumeInfo", {}).get("imageLinks", {})
            url = links.get("thumbnail") or links.get("smallThumbnail")
            if not url:
                continue

            url = url.replace("zoom=1", "zoom=0").replace("&edge=curl", "")

            img_resp = requests.get(url, timeout=10)
            img_resp.raise_for_status()
            content = img_resp.content

            if len(content) < 1000:
                continue

            if content[:2] == b"\xff\xd8":
                cover.write_bytes(content)
            else:
                img = Image.open(BytesIO(content))
                img.convert("RGB").save(cover, "JPEG", quality=95)

            return cover

        return None
    except Exception as e:
        logger.warning("Cover API error for %s: %s", title, e)
        return None


# ── ID3 tags ───────────────────────────────────────────────────────────────────


def set_tags(mp3: Path, author: str, title: str, reader: str, cover_data: bytes):
    """Write ID3 tags. Existing TIT2/TRCK are preserved."""
    try:
        tags = ID3(mp3)
    except ID3NoHeaderError:
        tags = ID3()

    tags["TPE1"] = TPE1(encoding=3, text=author or title)
    tags["TALB"] = TALB(encoding=3, text=title)
    if reader:
        tags["TPE2"] = TPE2(encoding=3, text=reader)
    tags["TCON"] = TCON(encoding=3, text="Audiobook")

    if cover_data:
        tags.delall("APIC")
        tags["APIC:"] = APIC(encoding=0, mime="image/jpeg", type=3, desc="", data=cover_data)

    tags.save(mp3, v2_version=3)


# ── Process one book ──────────────────────────────────────────────────────────


def process_book(book_dir: Path, tracker: dict):
    """Process one book. Returns (cover_status, mp3_count)."""
    name = book_dir.name
    author, title, reader = parse_folder(name)

    csv_row = tracker.get(title)
    if csv_row:
        if not reader and csv_row.get("Чтец"):
            r = csv_row["Чтец"].strip()
            if r and r != "EN":
                reader = r
        if not author and csv_row.get("Автор"):
            author = csv_row["Автор"].strip()

    is_english = reader == "EN" or (book_dir.parent.name == "Языки" and not has_cyrillic(title))
    if reader == "EN":
        reader = None

    logger.info("Processing: %s", name)
    logger.info("  Author: %s  |  Reader: %s", author or "—", reader or "—")

    cover_status = "not found"
    cover = standardize_cover(book_dir)
    if cover:
        cover_status = "exists"
    else:
        time.sleep(API_DELAY)
        cover = download_cover(author, title, book_dir, is_english)
        cover_status = "downloaded" if cover else "not found"

    logger.info("  Cover: %s", cover_status)

    cover_data = cover.read_bytes() if cover and cover.exists() else None

    mp3s = sorted(book_dir.rglob("*.mp3"))
    errors = 0
    for mp3 in mp3s:
        try:
            set_tags(mp3, author, title, reader, cover_data)
        except Exception as e:
            errors += 1
            if errors <= 2:
                logger.warning("  Tag error %s: %s", mp3.name, e)

    count_str = f"{len(mp3s)} files"
    if errors:
        count_str += f" ({errors} errors)"
    logger.info("  Tags: %s", count_str)

    return cover_status, len(mp3s)


# ── main ───────────────────────────────────────────────────────────────────────


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    sys.stdout.reconfigure(encoding="utf-8")
    logger.info("=" * 60)
    logger.info("  Covers and metadata for audiobook library")
    logger.info("=" * 60)

    tracker = load_tracker()
    books = find_books()

    logger.info("Books: %d  |  CSV rows: %d", len(books), len(tracker))

    stats = {"exists": 0, "downloaded": 0, "not found": 0, "mp3s": 0}

    for i, book in enumerate(books, 1):
        logger.info("[%d/%d]", i, len(books))
        cover_status, mp3_count = process_book(book, tracker)
        stats[cover_status] = stats.get(cover_status, 0) + 1
        stats["mp3s"] += mp3_count

    logger.info("=" * 60)
    logger.info("  Summary:")
    logger.info("    Covers existed:     %d", stats.get("exists", 0))
    logger.info("    Covers downloaded:  %d", stats.get("downloaded", 0))
    logger.info("    No covers:          %d", stats.get("not found", 0))
    logger.info("    MP3s processed:     %d", stats["mp3s"])
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
