"""
server/tts.py — Text-to-Speech engine using edge-tts.

Extracts text from PDF/EPUB/TXT/FB2 documents and converts to MP3 audiobooks
using Microsoft's free neural voices via edge-tts.
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger("leerio.tts")

# ── Voices ────────────────────────────────────────────────────────────────────

VOICES = [
    {"id": "ru-RU-DmitryNeural", "name": "Дмитрий", "lang": "ru", "gender": "male"},
    {"id": "ru-RU-SvetlanaNeural", "name": "Светлана", "lang": "ru", "gender": "female"},
    {"id": "en-US-GuyNeural", "name": "Guy", "lang": "en", "gender": "male"},
    {"id": "en-US-JennyNeural", "name": "Jenny", "lang": "en", "gender": "female"},
    {"id": "en-GB-RyanNeural", "name": "Ryan", "lang": "en", "gender": "male"},
    {"id": "de-DE-ConradNeural", "name": "Conrad", "lang": "de", "gender": "male"},
    {"id": "fr-FR-HenriNeural", "name": "Henri", "lang": "fr", "gender": "male"},
    {"id": "es-ES-AlvaroNeural", "name": "Alvaro", "lang": "es", "gender": "male"},
]

CHAPTER_SIZE = 5000  # ~5000 chars per chapter


# ── Text extraction ──────────────────────────────────────────────────────────


def _split_into_chapters(text: str, size: int = CHAPTER_SIZE) -> list[str]:
    """Split text into chapters of approximately `size` characters, breaking at paragraph boundaries."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    chapters = []
    current = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current_len + len(para) > size and current:
            chapters.append("\n\n".join(current))
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para)

    if current:
        chapters.append("\n\n".join(current))

    return chapters if chapters else [text.strip()]


def extract_text_pdf(path: Path) -> list[str]:
    """Extract text from PDF and split into chapters."""
    import pdfplumber

    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    full_text = "\n\n".join(text_parts)
    if not full_text.strip():
        raise ValueError("PDF contains no extractable text")
    return _split_into_chapters(full_text)


def extract_text_epub(path: Path) -> list[str]:
    """Extract text from EPUB and split into chapters."""
    import ebooklib
    from bs4 import BeautifulSoup
    from ebooklib import epub

    book = epub.read_epub(str(path))
    chapters = []

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "lxml")
        text = soup.get_text(separator="\n")
        text = text.strip()
        if len(text) > 100:  # Skip very short items (TOC, copyright, etc.)
            chapters.append(text)

    if not chapters:
        raise ValueError("EPUB contains no extractable text")

    # If chapters are too large, re-split
    result = []
    for ch in chapters:
        if len(ch) > CHAPTER_SIZE * 2:
            result.extend(_split_into_chapters(ch))
        else:
            result.append(ch)

    return result


def extract_text_txt(path: Path) -> list[str]:
    """Extract text from TXT file and split into chapters."""
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("TXT file is empty")
    return _split_into_chapters(text)


def extract_text_fb2(path: Path) -> list[str]:
    """Extract text from FB2 (XML) and split into chapters."""
    from lxml import etree

    tree = etree.parse(str(path))
    root = tree.getroot()

    # FB2 namespace
    ns = {"fb": "http://www.gribuser.ru/xml/fictionbook/2.0"}

    # Try with namespace first, then without
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
        return _split_into_chapters(text)

    chapters = []
    for section in sections:
        paragraphs = section.findall(".//{http://www.gribuser.ru/xml/fictionbook/2.0}p")
        if not paragraphs:
            paragraphs = section.findall(".//p")
        text = "\n\n".join("".join(p.itertext()).strip() for p in paragraphs if "".join(p.itertext()).strip())
        if text:
            chapters.append(text)

    if not chapters:
        raise ValueError("FB2 contains no extractable text")

    # Re-split if needed
    result = []
    for ch in chapters:
        if len(ch) > CHAPTER_SIZE * 2:
            result.extend(_split_into_chapters(ch))
        else:
            result.append(ch)

    return result


EXTRACTORS = {
    ".pdf": extract_text_pdf,
    ".epub": extract_text_epub,
    ".txt": extract_text_txt,
    ".fb2": extract_text_fb2,
}


def extract_text(path: Path) -> list[str]:
    """Extract text from a document file. Returns list of chapter texts."""
    ext = path.suffix.lower()
    extractor = EXTRACTORS.get(ext)
    if not extractor:
        raise ValueError(f"Unsupported format: {ext}")
    return extractor(path)


# ── TTS conversion ───────────────────────────────────────────────────────────


async def convert_chapter(text: str, voice: str, output: Path, rate: str = "+0%"):
    """Convert a chapter of text to MP3 using edge-tts."""
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(str(output))


async def run_tts_job(
    user_data,
    job_id: str,
    source_path: Path,
    voice: str,
    slug: str,
    title: str,
    author: str,
    rate: str = "+0%",
):
    """Full TTS pipeline: extract text → convert chapters → create book."""
    try:
        # Extract text
        logger.info("TTS job %s: extracting text from %s", job_id, source_path.name)
        chapters = extract_text(source_path)
        total = len(chapters)

        user_data.tts_job_update(job_id, total_chapters=total, status="processing")
        logger.info("TTS job %s: %d chapters to convert", job_id, total)

        # Create book directory
        book_dir = user_data.user_book_create(slug, title, author, reader=voice, source="tts")

        # Convert each chapter
        for i, chapter_text in enumerate(chapters, 1):
            output = book_dir / f"{i:02d}. Глава {i}.mp3"
            logger.info("TTS job %s: converting chapter %d/%d", job_id, i, total)

            await convert_chapter(chapter_text, voice, output, rate)

            user_data.tts_job_update(
                job_id,
                done_chapters=i,
                progress=int(i / total * 100),
            )

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
