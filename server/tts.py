"""
server/tts.py — Text-to-Speech engine using edge-tts.

Extracts text from PDF/EPUB/TXT/FB2 documents, cleans it for TTS,
detects chapter boundaries, and converts to MP3 audiobooks using
Microsoft's free neural voices via edge-tts.
"""

import asyncio
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger("leerio.tts")

# ── OpenAI-compatible TTS config ─────────────────────────────────────────────

TTS_OPENAI_BASE_URL = os.environ.get("TTS_OPENAI_BASE_URL", "")
TTS_OPENAI_API_KEY = os.environ.get("TTS_OPENAI_API_KEY", "")
TTS_OPENAI_MODEL = os.environ.get("TTS_OPENAI_MODEL", "tts-1")

# ── Voices ────────────────────────────────────────────────────────────────────

VOICES = [
    {"id": "ru-RU-DmitryNeural", "name": "Дмитрий", "lang": "ru", "gender": "male", "engine": "edge"},
    {"id": "ru-RU-SvetlanaNeural", "name": "Светлана", "lang": "ru", "gender": "female", "engine": "edge"},
    {"id": "en-US-GuyNeural", "name": "Guy", "lang": "en", "gender": "male", "engine": "edge"},
    {"id": "en-US-JennyNeural", "name": "Jenny", "lang": "en", "gender": "female", "engine": "edge"},
    {"id": "en-GB-RyanNeural", "name": "Ryan", "lang": "en", "gender": "male", "engine": "edge"},
    {"id": "de-DE-ConradNeural", "name": "Conrad", "lang": "de", "gender": "male", "engine": "edge"},
    {"id": "fr-FR-HenriNeural", "name": "Henri", "lang": "fr", "gender": "male", "engine": "edge"},
    {"id": "es-ES-AlvaroNeural", "name": "Alvaro", "lang": "es", "gender": "male", "engine": "edge"},
]

OPENAI_VOICES = [
    {"id": "alloy", "name": "Alloy", "lang": "multi", "gender": "neutral", "engine": "openai"},
    {"id": "echo", "name": "Echo", "lang": "multi", "gender": "male", "engine": "openai"},
    {"id": "fable", "name": "Fable", "lang": "multi", "gender": "neutral", "engine": "openai"},
    {"id": "onyx", "name": "Onyx", "lang": "multi", "gender": "male", "engine": "openai"},
    {"id": "nova", "name": "Nova", "lang": "multi", "gender": "female", "engine": "openai"},
    {"id": "shimmer", "name": "Shimmer", "lang": "multi", "gender": "female", "engine": "openai"},
]

CHAPTER_SIZE = 5000  # ~5000 chars per chapter
MAX_CHAPTER_SIZE = 15000  # sub-split threshold
TTS_CONCURRENCY = 3


# ── Types ─────────────────────────────────────────────────────────────────────


class Chapter(NamedTuple):
    title: str  # real chapter name or "Часть N"
    text: str  # cleaned text


# ── Text cleaning pipeline ────────────────────────────────────────────────────


def _remove_urls_emails(text: str) -> str:
    """Strip URLs and email addresses."""
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"www\.\S+", "", text)
    text = re.sub(r"\S+@\S+\.\S+", "", text)
    return text


def _remove_junk_characters(text: str) -> str:
    """Remove decorative/junk characters: ***, ===, control chars."""
    text = re.sub(r"[*]{3,}", "", text)
    text = re.sub(r"[=]{3,}", "", text)
    text = re.sub(r"[─━—–]{3,}", "", text)
    text = re.sub(r"[_]{3,}", "", text)
    # Remove control characters (keep newlines, tabs)
    text = "".join(ch for ch in text if ch in "\n\t\r" or not unicodedata.category(ch).startswith("C"))
    return text


def _remove_page_numbers(text: str) -> str:
    """Remove standalone page numbers and page markers."""
    # "стр. 245", "стр 34", "страница 12"
    text = re.sub(r"(?i)\bстр(?:аница)?\.?\s*\d+\b", "", text)
    # "- 34 -" or "— 34 —" (centered page numbers)
    text = re.sub(r"^[\s]*[—–-]\s*\d+\s*[—–-][\s]*$", "", text, flags=re.MULTILINE)
    # Standalone numbers on their own line (page numbers)
    text = re.sub(r"^\s*\d{1,4}\s*$", "", text, flags=re.MULTILINE)
    return text


def _fix_broken_words(text: str) -> str:
    """Rejoin hyphenated line breaks: 'про-\\nдолжение' → 'продолжение'."""
    return re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)


def _normalize_whitespace(text: str) -> str:
    """Collapse spaces, cap consecutive newlines at 2, strip lines."""
    # Collapse multiple spaces (not newlines) into one
    text = re.sub(r"[^\S\n]+", " ", text)
    # Strip trailing/leading whitespace per line
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[ \t]+", "", text, flags=re.MULTILINE)
    # Cap consecutive newlines at 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _ensure_punctuation(text: str) -> str:
    """Add period to paragraphs not ending with sentence-ending punctuation."""
    # Split into paragraphs, add period if needed
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.rstrip()
        if stripped and not re.search(r"[.!?…»\"'\)\]—–]$", stripped):
            # Only add period to substantial text lines (not headings, not short fragments)
            if len(stripped) > 30:
                stripped += "."
        result.append(stripped)
    return "\n".join(result)


def clean_text(text: str) -> str:
    """Full text cleaning pipeline for TTS."""
    for fn in (
        _remove_urls_emails,
        _remove_junk_characters,
        _remove_page_numbers,
        _fix_broken_words,
        _normalize_whitespace,
        _ensure_punctuation,
    ):
        text = fn(text)
    return text


# ── Chapter detection ─────────────────────────────────────────────────────────

# Patterns for chapter headings (ordered by specificity)
_CHAPTER_PATTERNS = [
    # "Глава 1", "ГЛАВА 1. Название", "Глава первая"
    re.compile(
        r"^[ \t]*(?:Глава|ГЛАВА)\s+[\dIVXLCDMivxlcdm]+[.:]?\s*.*$",
        re.MULTILINE,
    ),
    # "Часть 1", "ЧАСТЬ II"
    re.compile(
        r"^[ \t]*(?:Часть|ЧАСТЬ)\s+[\dIVXLCDMivxlcdm]+[.:]?\s*.*$",
        re.MULTILINE,
    ),
    # "Chapter 1", "CHAPTER 1. Title"
    re.compile(
        r"^[ \t]*(?:Chapter|CHAPTER)\s+[\dIVXLCDMivxlcdm]+[.:]?\s*.*$",
        re.MULTILINE,
    ),
    # "Part 1", "PART II"
    re.compile(
        r"^[ \t]*(?:Part|PART)\s+[\dIVXLCDMivxlcdm]+[.:]?\s*.*$",
        re.MULTILINE,
    ),
    # Numbered headings: "1. Title", "12. Something"
    re.compile(
        r"^[ \t]*\d{1,3}\.\s+[A-ZА-ЯЁ].+$",
        re.MULTILINE,
    ),
]


def _split_by_size(text: str, size: int = CHAPTER_SIZE) -> list[Chapter]:
    """Split text into chapters of approximately `size` characters at paragraph boundaries."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    chapters: list[Chapter] = []
    current: list[str] = []
    current_len = 0
    part_num = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current_len + len(para) > size and current:
            part_num += 1
            chapters.append(Chapter(f"Часть {part_num}", "\n\n".join(current)))
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para)

    if current:
        part_num += 1
        chapters.append(Chapter(f"Часть {part_num}", "\n\n".join(current)))

    return chapters if chapters else [Chapter("Часть 1", text.strip())]


def _sub_split_chapter(chapter: Chapter) -> list[Chapter]:
    """Sub-split a chapter that exceeds MAX_CHAPTER_SIZE."""
    if len(chapter.text) <= MAX_CHAPTER_SIZE:
        return [chapter]
    parts = _split_by_size(chapter.text, CHAPTER_SIZE)
    if len(parts) == 1:
        return [chapter]
    return [Chapter(f"{chapter.title} (ч. {i})", p.text) for i, p in enumerate(parts, 1)]


def _detect_chapters(text: str) -> list[Chapter]:
    """Detect chapter boundaries using heading patterns, with size-based fallback."""
    for pattern in _CHAPTER_PATTERNS:
        matches = list(pattern.finditer(text))
        if len(matches) >= 2:
            # Split at heading positions
            chapters: list[Chapter] = []
            for i, match in enumerate(matches):
                title = match.group().strip()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                # Chapter text is everything after the heading line until next heading
                body = text[match.end() : end].strip()
                if body:
                    chapters.append(Chapter(title, body))

            if chapters:
                # Sub-split very long chapters
                result: list[Chapter] = []
                for ch in chapters:
                    result.extend(_sub_split_chapter(ch))
                return result

    # No chapter pattern matched — fall back to size-based split
    return _split_by_size(text)


# ── Safe filename ─────────────────────────────────────────────────────────────


def _safe_filename(title: str, max_len: int = 60) -> str:
    """Convert a chapter title to a safe filename fragment."""
    # Remove characters illegal in filenames
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title)
    # Collapse whitespace
    safe = re.sub(r"\s+", " ", safe).strip()
    # Truncate
    if len(safe) > max_len:
        safe = safe[:max_len].rstrip()
    return safe or "chapter"


# ── Text extraction ──────────────────────────────────────────────────────────


def extract_text_pdf(path: Path) -> list[Chapter]:
    """Extract text from PDF, remove headers/footers, detect chapters."""
    import pdfplumber

    pages_text: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                pages_text.append(page_text)

    if not pages_text:
        raise ValueError("PDF contains no extractable text")

    # Detect repeating headers/footers (appear on >30% of pages)
    if len(pages_text) >= 5:
        pages_text = _remove_pdf_headers_footers(pages_text)

    full_text = "\n\n".join(pages_text)
    full_text = clean_text(full_text)

    if not full_text.strip():
        raise ValueError("PDF contains no extractable text")

    return _detect_chapters(full_text)


def _remove_pdf_headers_footers(pages: list[str], threshold: float = 0.3) -> list[str]:
    """Remove lines that repeat on >threshold fraction of pages (headers/footers)."""
    from collections import Counter

    first_lines: Counter[str] = Counter()
    last_lines: Counter[str] = Counter()
    n = len(pages)

    for page in pages:
        lines = page.strip().splitlines()
        if lines:
            first_lines[lines[0].strip()] += 1
            last_lines[lines[-1].strip()] += 1

    junk_first = {line for line, count in first_lines.items() if count / n > threshold and line}
    junk_last = {line for line, count in last_lines.items() if count / n > threshold and line}

    result = []
    for page in pages:
        lines = page.strip().splitlines()
        if lines and lines[0].strip() in junk_first:
            lines = lines[1:]
        if lines and lines[-1].strip() in junk_last:
            lines = lines[:-1]
        result.append("\n".join(lines))

    return result


def extract_text_epub(path: Path) -> list[Chapter]:
    """Extract text from EPUB with chapter titles from TOC."""
    import ebooklib
    from bs4 import BeautifulSoup
    from ebooklib import epub

    book = epub.read_epub(str(path))

    # Build href → title map from TOC
    toc_titles: dict[str, str] = {}
    for item in book.toc:
        if hasattr(item, "href") and hasattr(item, "title") and item.title:
            # Normalize href (strip fragment)
            href = item.href.split("#")[0]
            toc_titles[href] = item.title

    chapters: list[Chapter] = []
    chapter_num = 0

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "lxml")
        text = soup.get_text(separator="\n")
        text = text.strip()
        if len(text) < 100:
            continue

        text = clean_text(text)
        if not text.strip():
            continue

        chapter_num += 1

        # Try TOC title first
        item_href = getattr(item, "file_name", "") or ""
        title = toc_titles.get(item_href, "")

        # Fallback: first heading in content
        if not title:
            heading = soup.find(["h1", "h2", "h3", "h4"])
            if heading:
                title = heading.get_text(strip=True)

        # Final fallback
        if not title:
            title = f"Часть {chapter_num}"

        chapters.append(Chapter(title, text))

    if not chapters:
        raise ValueError("EPUB contains no extractable text")

    # Sub-split large chapters
    result: list[Chapter] = []
    for ch in chapters:
        result.extend(_sub_split_chapter(ch))

    return result


def extract_text_txt(path: Path) -> list[Chapter]:
    """Extract text from TXT file, detect chapters."""
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("TXT file is empty")
    text = clean_text(text)
    return _detect_chapters(text)


def extract_text_fb2(path: Path) -> list[Chapter]:
    """Extract text from FB2 (XML) with section titles."""
    from lxml import etree

    tree = etree.parse(str(path))
    root = tree.getroot()

    ns = {"fb": "http://www.gribuser.ru/xml/fictionbook/2.0"}

    sections = root.findall(".//fb:body/fb:section", ns)
    if not sections:
        sections = root.findall(".//{http://www.gribuser.ru/xml/fictionbook/2.0}section")

    if not sections:
        # Fallback: get all <p> tags
        paragraphs = root.findall(".//{http://www.gribuser.ru/xml/fictionbook/2.0}p")
        if not paragraphs:
            paragraphs = root.findall(".//p")
        text = "\n\n".join("".join(p.itertext()).strip() for p in paragraphs if "".join(p.itertext()).strip())
        if not text:
            raise ValueError("FB2 contains no extractable text")
        text = clean_text(text)
        return _detect_chapters(text)

    chapters: list[Chapter] = []
    chapter_num = 0

    for section in sections:
        # Extract title from <title> element
        title_el = section.find("{http://www.gribuser.ru/xml/fictionbook/2.0}title")
        if title_el is None:
            title_el = section.find("title")

        title = ""
        if title_el is not None:
            title = " ".join("".join(p.itertext()).strip() for p in title_el).strip()

        # Extract body paragraphs (skip title paragraphs)
        paragraphs = section.findall(".//{http://www.gribuser.ru/xml/fictionbook/2.0}p")
        if not paragraphs:
            paragraphs = section.findall(".//p")

        # Filter out paragraphs that are inside <title>
        title_paras = set()
        if title_el is not None:
            for tp in title_el.findall(".//{http://www.gribuser.ru/xml/fictionbook/2.0}p"):
                title_paras.add(id(tp))
            for tp in title_el.findall(".//p"):
                title_paras.add(id(tp))

        text = "\n\n".join(
            "".join(p.itertext()).strip()
            for p in paragraphs
            if id(p) not in title_paras and "".join(p.itertext()).strip()
        )

        if not text:
            continue

        text = clean_text(text)
        if not text.strip():
            continue

        chapter_num += 1
        if not title:
            title = f"Часть {chapter_num}"

        chapters.append(Chapter(title, text))

    if not chapters:
        raise ValueError("FB2 contains no extractable text")

    # Sub-split large chapters
    result: list[Chapter] = []
    for ch in chapters:
        result.extend(_sub_split_chapter(ch))

    return result


EXTRACTORS = {
    ".pdf": extract_text_pdf,
    ".epub": extract_text_epub,
    ".txt": extract_text_txt,
    ".fb2": extract_text_fb2,
}


def extract_text(path: Path) -> list[Chapter]:
    """Extract text from a document file. Returns list of Chapter(title, text)."""
    ext = path.suffix.lower()
    extractor = EXTRACTORS.get(ext)
    if not extractor:
        raise ValueError(f"Unsupported format: {ext}")
    return extractor(path)


# ── Engine helpers ────────────────────────────────────────────────────────────


def openai_available() -> bool:
    """Check if OpenAI-compatible TTS is configured."""
    return bool(TTS_OPENAI_BASE_URL)


def get_voices(engine: str = "edge") -> list[dict]:
    """Return voices for the given engine."""
    if engine == "openai":
        return OPENAI_VOICES
    return VOICES


def _rate_to_speed(rate: str) -> float:
    """Convert edge-tts rate format ('+25%') to OpenAI speed multiplier (1.25)."""
    rate = rate.strip()
    if not rate or rate == "+0%":
        return 1.0
    try:
        # Strip '%' and parse
        pct = int(rate.replace("%", "").replace("+", ""))
        return round(1.0 + pct / 100.0, 2)
    except ValueError:
        return 1.0


# ── TTS conversion ───────────────────────────────────────────────────────────


async def convert_chapter(text: str, voice: str, output: Path, rate: str = "+0%"):
    """Convert a chapter of text to MP3 using edge-tts."""
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(str(output))


async def convert_chapter_openai(text: str, voice: str, output: Path, rate: str = "+0%"):
    """Convert chapter via OpenAI-compatible API (openedai-speech, OpenAI, etc.)."""
    import httpx

    speed = _rate_to_speed(rate)
    url = f"{TTS_OPENAI_BASE_URL.rstrip('/')}/audio/speech"
    headers = {}
    if TTS_OPENAI_API_KEY:
        headers["Authorization"] = f"Bearer {TTS_OPENAI_API_KEY}"

    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(
            url,
            headers=headers,
            json={
                "model": TTS_OPENAI_MODEL,
                "input": text,
                "voice": voice,
                "response_format": "mp3",
                "speed": speed,
            },
        )
        r.raise_for_status()
        output.write_bytes(r.content)


async def run_tts_job(
    user_data,
    job_id: str,
    source_path: Path,
    voice: str,
    slug: str,
    title: str,
    author: str,
    rate: str = "+0%",
    engine: str = "edge",
):
    """Full TTS pipeline: extract text → clean → detect chapters → convert concurrently."""
    try:
        # Extract text
        logger.info("TTS job %s: extracting text from %s", job_id, source_path.name)
        chapters = extract_text(source_path)
        total = len(chapters)

        user_data.tts_job_update(job_id, total_chapters=total, status="processing")
        logger.info("TTS job %s: %d chapters to convert", job_id, total)

        # Create book directory
        book_dir = user_data.user_book_create(slug, title, author, reader=voice, source="tts")

        # Convert chapters concurrently with semaphore
        sem = asyncio.Semaphore(TTS_CONCURRENCY)
        done_count = 0
        lock = asyncio.Lock()

        async def convert_one(i: int, chapter: Chapter):
            nonlocal done_count
            fname = _safe_filename(chapter.title)
            output = book_dir / f"{i:02d}. {fname}.mp3"
            logger.info("TTS job %s: converting chapter %d/%d — %s", job_id, i, total, chapter.title)

            async with sem:
                if engine == "openai":
                    await convert_chapter_openai(chapter.text, voice, output, rate)
                else:
                    await convert_chapter(chapter.text, voice, output, rate)

            async with lock:
                done_count += 1
                user_data.tts_job_update(
                    job_id,
                    done_chapters=done_count,
                    progress=int(done_count / total * 100),
                )

        await asyncio.gather(*(convert_one(i, ch) for i, ch in enumerate(chapters, 1)))

        # Done
        user_data.tts_job_update(job_id, status="done", progress=100)
        logger.info("TTS job %s: completed successfully", job_id)

        # Clean up source file
        try:
            source_path.unlink()
        except Exception:
            pass

    except Exception as e:
        logger.error("TTS job %s failed: %s", job_id, e, exc_info=True)
        user_data.tts_job_update(job_id, status="error", error=str(e))
