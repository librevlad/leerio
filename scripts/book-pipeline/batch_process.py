"""
Batch process multiple public domain books:
Download from Gutenberg -> split chapters -> translate -> edge-tts -> upload to S3.
"""

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Load .env
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

import boto3
import edge_tts
from botocore.config import Config
from deep_translator import GoogleTranslator

WORK_DIR = Path(__file__).parent / "work"
WORK_DIR.mkdir(exist_ok=True)

S3_BUCKET = os.environ.get("S3_BUCKET", "leerio-books")
VOICE = "ru-RU-DmitryNeural"

# ── Books to process ─────────────────────────────────────────────────
BOOKS = [
    {
        "url": "https://www.gutenberg.org/cache/epub/132/pg132.txt",
        "title_en": "The Art of War",
        "author_en": "Sun Tzu",
        "category": "Саморазвитие",
        "chapter_pattern": r"^(?:I{1,3}V?|VI{0,3}|IX|X[IVX]*)\.\s+(.+)$",
    },
    {
        "url": "https://www.gutenberg.org/cache/epub/2680/pg2680.txt",
        "title_en": "Meditations",
        "author_en": "Marcus Aurelius",
        "category": "Саморазвитие",
        "chapter_pattern": r"^THE (?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|ELEVENTH|TWELFTH) BOOK$",
    },
    {
        "url": "https://www.gutenberg.org/cache/epub/2251/pg2251.txt",
        "title_en": "The Science of Being Well",
        "author_en": "Wallace D. Wattles",
        "category": "Саморазвитие",
    },
    {
        "url": "https://www.gutenberg.org/cache/epub/706/pg706.txt",
        "title_en": "The Imitation of Christ",
        "author_en": "Thomas a Kempis",
        "category": "Саморазвитие",
    },
    {
        "url": "https://www.gutenberg.org/cache/epub/4300/pg4300.txt",
        "title_en": "The Science of Getting Rich",
        "author_en": "Wallace D. Wattles",
        "category": "Бизнес",
    },
]


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
        config=Config(signature_version="s3v4"),
    )


def download_text(url: str) -> str:
    """Download book text from Project Gutenberg."""
    import urllib.request

    print(f"  Downloading {url}...")
    data = urllib.request.urlopen(url).read()
    # Try UTF-8 first, fallback to latin-1
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    return text


def strip_gutenberg(text: str) -> str:
    """Remove Project Gutenberg header/footer."""
    # Find start marker
    start_markers = [
        "*** START OF THIS PROJECT GUTENBERG",
        "*** START OF THE PROJECT GUTENBERG",
        "***START OF THIS PROJECT GUTENBERG",
        "***START OF THE PROJECT GUTENBERG",
    ]
    for marker in start_markers:
        idx = text.find(marker)
        if idx != -1:
            # Skip to next line after marker
            nl = text.find("\n", idx)
            text = text[nl + 1 :] if nl != -1 else text[idx + len(marker) :]
            break

    # Find end marker
    end_markers = [
        "*** END OF THIS PROJECT GUTENBERG",
        "*** END OF THE PROJECT GUTENBERG",
        "***END OF THIS PROJECT GUTENBERG",
        "***END OF THE PROJECT GUTENBERG",
        "End of the Project Gutenberg",
        "End of Project Gutenberg",
    ]
    for marker in end_markers:
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx]
            break

    return text.strip()


def split_chapters_generic(text: str, pattern: str = None) -> list[dict]:
    """Split text into chapters using various heuristics."""
    chapters = []

    if pattern:
        parts = re.split(pattern, text, flags=re.MULTILINE)
        if len(parts) > 2:
            for i in range(1, len(parts), 2):
                title = parts[i].strip() if i < len(parts) else f"Chapter {len(chapters) + 1}"
                content = parts[i + 1].strip() if i + 1 < len(parts) else parts[i].strip()
                if len(content) > 200:
                    chapters.append({"title": title, "text": content})
            if chapters:
                return chapters

    # Try common chapter patterns
    patterns = [
        r"^CHAPTER\s+([IVXLCDM]+\.?\s*.*?)$",
        r"^Chapter\s+(\d+\.?\s*.*?)$",
        r"^CHAPTER\s+(\d+\.?\s*.*?)$",
        r"^BOOK\s+([IVXLCDM]+\.?\s*.*?)$",
        r"^THE\s+(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|ELEVENTH|TWELFTH)\s+BOOK$",
        r"^(PART\s+[IVXLCDM]+\.?\s*.*?)$",
    ]

    for pat in patterns:
        parts = re.split(pat, text, flags=re.MULTILINE)
        if len(parts) >= 3:
            for i in range(1, len(parts), 2):
                title = parts[i].strip()
                content = parts[i + 1].strip() if i + 1 < len(parts) else ""
                if len(content) > 200:
                    chapters.append({"title": title, "text": content})
            if len(chapters) >= 2:
                return chapters
            chapters = []

    # Fallback: split by double newlines into ~3000 char chunks
    paragraphs = re.split(r"\n\s*\n", text)
    current_text = ""
    chunk_idx = 0
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        current_text += "\n\n" + para
        if len(current_text) > 3000:
            chunk_idx += 1
            chapters.append({"title": f"Part {chunk_idx}", "text": current_text.strip()})
            current_text = ""
    if current_text.strip():
        chunk_idx += 1
        chapters.append({"title": f"Part {chunk_idx}", "text": current_text.strip()})

    return chapters


def translate_chunk(text: str, chunk_size: int = 4500) -> str:
    """Translate English text to Russian in chunks."""
    translator = GoogleTranslator(source="en", target="ru")

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) + 1 > chunk_size:
            if current:
                chunks.append(current)
            current = sent
        else:
            current = f"{current} {sent}".strip() if current else sent
    if current:
        chunks.append(current)

    translated = []
    for i, chunk in enumerate(chunks):
        try:
            result = translator.translate(chunk)
            translated.append(result)
            if i < len(chunks) - 1:
                time.sleep(0.3)
        except Exception as e:
            print(f"    Translation error chunk {i + 1}: {e}")
            translated.append(chunk)

    return " ".join(translated)


def translate_short(text: str) -> str:
    """Translate a short string."""
    try:
        return GoogleTranslator(source="en", target="ru").translate(text)
    except Exception:
        return text


async def generate_tts(text: str, output_path: Path, voice: str = VOICE) -> bool:
    """Generate TTS audio using edge-tts."""
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(str(output_path))
        return True
    except Exception as e:
        print(f"    TTS error: {e}")
        return False


def upload_to_s3(client, local_path: Path, s3_key: str):
    """Upload a file to S3."""
    client.upload_file(
        str(local_path),
        S3_BUCKET,
        s3_key,
        ExtraArgs={"ContentType": "audio/mpeg"},
    )


async def process_one_book(book_config: dict, s3_client) -> bool:
    """Process a single book end-to-end."""
    title_en = book_config["title_en"]
    author_en = book_config["author_en"]
    category = book_config["category"]

    print(f"\n{'='*60}")
    print(f"  {author_en} - {title_en}")
    print(f"{'='*60}")

    # 1. Download
    print("\n  [1/5] Downloading...")
    raw_text = download_text(book_config["url"])
    text = strip_gutenberg(raw_text)
    print(f"    Text length: {len(text)} chars")

    # 2. Split chapters
    print("\n  [2/5] Splitting chapters...")
    chapters = split_chapters_generic(text, book_config.get("chapter_pattern"))
    print(f"    Found {len(chapters)} chapters")
    if not chapters:
        print("    ERROR: No chapters found, skipping book")
        return False

    # 3. Translate
    print("\n  [3/5] Translating...")
    title_ru = translate_short(title_en)
    author_ru = translate_short(author_en)
    print(f"    Title: {title_ru}")
    print(f"    Author: {author_ru}")

    for i, ch in enumerate(chapters):
        ch["title_ru"] = translate_short(ch["title"])
        ch["text_ru"] = translate_chunk(ch["text"])
        print(f"    Chapter {i + 1}/{len(chapters)}: {ch['title']} -> {ch['title_ru']} ({len(ch['text_ru'])} chars)")
        time.sleep(0.5)

    # 4. Generate TTS
    print("\n  [4/5] Generating TTS...")
    folder_name = f"{author_ru} - {title_ru} [TTS]"
    audio_dir = WORK_DIR / folder_name
    audio_dir.mkdir(parents=True, exist_ok=True)

    mp3_files = []
    for i, ch in enumerate(chapters):
        mp3_name = f"Глава {i + 1:02d} - {ch['title_ru']}.mp3"
        # Sanitize filename
        mp3_name = re.sub(r'[<>:"/\\|?*]', "", mp3_name)
        mp3_path = audio_dir / mp3_name
        if mp3_path.exists() and mp3_path.stat().st_size > 1000:
            print(f"    Chapter {i + 1}: exists, skipping")
            mp3_files.append(mp3_path)
            continue

        print(f"    Chapter {i + 1}/{len(chapters)}: {ch['title_ru']}...")
        ok = await generate_tts(ch["text_ru"], mp3_path)
        if ok:
            size_kb = mp3_path.stat().st_size / 1024
            print(f"      OK ({size_kb:.0f} KB)")
            mp3_files.append(mp3_path)
        else:
            print(f"      FAILED")

    if not mp3_files:
        print("    No audio files generated!")
        return False

    # 5. Upload to S3
    print(f"\n  [5/5] Uploading {len(mp3_files)} files to S3...")
    s3_prefix = f"{category}/{folder_name}"
    for mp3 in sorted(mp3_files):
        s3_key = f"{s3_prefix}/{mp3.name}"
        upload_to_s3(s3_client, mp3, s3_key)
        print(f"    Uploaded: {mp3.name}")

    # Save metadata
    meta = {
        "title": title_ru,
        "author": author_ru,
        "reader": "TTS",
        "category": category,
        "chapters": len(mp3_files),
        "s3_prefix": s3_prefix,
    }
    (audio_dir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n  DONE: {author_ru} -- {title_ru} ({len(mp3_files)} chapters)")
    return True


async def main():
    s3_client = get_s3_client()
    results = []

    for book in BOOKS:
        try:
            ok = await process_one_book(book, s3_client)
            results.append((book["title_en"], ok))
        except Exception as e:
            print(f"\n  ERROR processing {book['title_en']}: {e}")
            results.append((book["title_en"], False))

    print(f"\n\n{'='*60}")
    print("  RESULTS")
    print(f"{'='*60}")
    for title, ok in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {title}")
    print(f"\n  Total: {sum(1 for _, ok in results if ok)}/{len(results)} successful")


if __name__ == "__main__":
    asyncio.run(main())
