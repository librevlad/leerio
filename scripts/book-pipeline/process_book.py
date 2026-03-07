"""
Book pipeline: translate, split chapters, TTS, upload to S3.
Usage: python process_book.py
"""

import json
import os
import re
import sys
import time
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────
WORK_DIR = Path(__file__).parent / "work"
S3_CATEGORY = "Саморазвитие"

# ── Step 1: Split text into chapters ────────────────────────────────

def split_chapters(text: str) -> list[dict]:
    """Split markdown-style text into chapters."""
    chapters = []
    parts = re.split(r"^## (.+)$", text, flags=re.MULTILINE)

    # parts[0] is before first ##, then alternating title/content
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if content:
            chapters.append({"title": title, "text": content})

    return chapters


# ── Step 2: Translate to Russian ────────────────────────────────────

def translate_text(text: str, chunk_size: int = 4500) -> str:
    """Translate English text to Russian using Google Translate (free)."""
    from deep_translator import GoogleTranslator

    translator = GoogleTranslator(source="en", target="ru")

    # Split into chunks respecting sentence boundaries
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

    translated_parts = []
    for i, chunk in enumerate(chunks):
        try:
            result = translator.translate(chunk)
            translated_parts.append(result)
            if i < len(chunks) - 1:
                time.sleep(0.5)  # Rate limit
        except Exception as e:
            print(f"  Translation error on chunk {i + 1}: {e}")
            translated_parts.append(chunk)  # fallback to original

    return " ".join(translated_parts)


def translate_title(title: str) -> str:
    """Translate a short title."""
    from deep_translator import GoogleTranslator
    try:
        return GoogleTranslator(source="en", target="ru").translate(title)
    except Exception:
        return title


# ── Step 3: Generate TTS audio ──────────────────────────────────────

def text_to_speech(text: str, output_path: Path, voice: str = "nova") -> bool:
    """Generate speech using OpenAI-compatible TTS API.

    Uses the Leerio openedai-speech service or OpenAI API.
    """
    import requests

    # Try local openedai-speech first, then OpenAI API
    base_url = os.environ.get("TTS_OPENAI_BASE_URL", "https://api.openai.com/v1")
    api_key = os.environ.get("TTS_OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
    model = os.environ.get("TTS_OPENAI_MODEL", "tts-1")

    if not api_key:
        print("  ERROR: No TTS API key found (TTS_OPENAI_API_KEY or OPENAI_API_KEY)")
        return False

    # Split long text into segments (TTS APIs have limits ~4096 chars)
    max_chars = 4000
    segments = []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    current = ""
    for sent in sentences:
        if len(current) + len(sent) + 1 > max_chars:
            if current:
                segments.append(current)
            current = sent
        else:
            current = f"{current} {sent}".strip() if current else sent
    if current:
        segments.append(current)

    # Generate audio for each segment
    audio_parts = []
    for i, segment in enumerate(segments):
        try:
            resp = requests.post(
                f"{base_url}/audio/speech",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "input": segment,
                    "voice": voice,
                    "response_format": "mp3",
                },
                timeout=300,
            )
            resp.raise_for_status()
            audio_parts.append(resp.content)
            if i < len(segments) - 1:
                time.sleep(0.5)
        except Exception as e:
            print(f"  TTS error on segment {i + 1}/{len(segments)}: {e}")
            return False

    # Concatenate MP3 segments
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        for part in audio_parts:
            f.write(part)

    return True


# ── Step 4: Upload to S3 ────────────────────────────────────────────

def upload_to_s3(local_path: Path, s3_key: str):
    """Upload file to S3 bucket."""
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
        config=Config(signature_version="s3v4"),
    )
    bucket = os.environ.get("S3_BUCKET", "leerio-books")

    content_type = "audio/mpeg" if str(local_path).endswith(".mp3") else "application/octet-stream"
    client.upload_file(
        str(local_path), bucket, s3_key,
        ExtraArgs={"ContentType": content_type},
    )
    print(f"  Uploaded: s3://{bucket}/{s3_key}")


# ── Main pipeline ───────────────────────────────────────────────────

def process_book(
    title_en: str,
    author_en: str,
    text: str,
    reader: str = "TTS",
    voice: str = "nova",
):
    """Full pipeline: split -> translate -> TTS -> upload."""
    print(f"\n{'='*60}")
    print(f"Processing: {author_en} - {title_en}")
    print(f"{'='*60}")

    # 1. Split into chapters
    print("\n[1/5] Splitting into chapters...")
    chapters = split_chapters(text)
    print(f"  Found {len(chapters)} chapters")

    # 2. Translate title and author
    print("\n[2/5] Translating metadata...")
    title_ru = translate_title(title_en)
    author_ru = translate_title(author_en)
    print(f"  Title: {title_ru}")
    print(f"  Author: {author_ru}")

    # 3. Translate chapters
    print("\n[3/5] Translating chapters...")
    for i, ch in enumerate(chapters):
        ch_title_ru = translate_title(ch["title"])
        print(f"  Chapter {i + 1}/{len(chapters)}: {ch['title']} -> {ch_title_ru}")
        ch["title_ru"] = ch_title_ru
        ch["text_ru"] = translate_text(ch["text"])
        print(f"    Translated {len(ch['text'])} -> {len(ch['text_ru'])} chars")
        time.sleep(1)

    # Save translated text
    book_dir = WORK_DIR / f"{author_ru} - {title_ru}"
    book_dir.mkdir(parents=True, exist_ok=True)

    for i, ch in enumerate(chapters):
        txt_path = book_dir / f"Глава {i + 1:02d} - {ch['title_ru']}.txt"
        txt_path.write_text(ch["text_ru"], encoding="utf-8")

    # Save metadata
    meta = {
        "title": title_ru,
        "title_en": title_en,
        "author": author_ru,
        "author_en": author_en,
        "reader": reader,
        "category": S3_CATEGORY,
        "license": "Public Domain",
        "chapters": [
            {"number": i + 1, "title": ch["title_ru"], "title_en": ch["title"]}
            for i, ch in enumerate(chapters)
        ],
    }
    (book_dir / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  Saved text to {book_dir}")

    # 4. Generate TTS
    print("\n[4/5] Generating TTS audio...")
    folder_name = f"{author_ru} - {title_ru} [{reader}]"
    audio_dir = book_dir / "audio"

    for i, ch in enumerate(chapters):
        mp3_name = f"{i + 1:03d} - {ch['title_ru']}.mp3"
        mp3_path = audio_dir / mp3_name
        if mp3_path.exists():
            print(f"  Chapter {i + 1}: already exists, skipping")
            continue
        print(f"  Chapter {i + 1}/{len(chapters)}: {ch['title_ru']} ({len(ch['text_ru'])} chars)...")
        ok = text_to_speech(ch["text_ru"], mp3_path, voice=voice)
        if ok:
            size_kb = mp3_path.stat().st_size / 1024
            print(f"    OK ({size_kb:.0f} KB)")
        else:
            print(f"    FAILED")

    # 5. Upload to S3
    print("\n[5/5] Uploading to S3...")
    s3_prefix = f"{S3_CATEGORY}/{folder_name}"

    mp3_files = sorted(audio_dir.glob("*.mp3")) if audio_dir.exists() else []
    if not mp3_files:
        print("  No audio files to upload!")
        return meta

    for mp3 in mp3_files:
        s3_key = f"{s3_prefix}/{mp3.name}"
        upload_to_s3(mp3, s3_key)

    print(f"\n  Done! Uploaded {len(mp3_files)} tracks to s3://{os.environ.get('S3_BUCKET')}/{s3_prefix}/")
    print(f"  Run sync_books() on server to add to catalog.")

    meta["s3_prefix"] = s3_prefix
    meta["track_count"] = len(mp3_files)
    return meta


if __name__ == "__main__":
    # Load .env from project root
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    # Test with "As a Man Thinketh"
    text_path = WORK_DIR / "as_a_man_thinketh.md"
    if not text_path.exists():
        print(f"Place the book text at {text_path}")
        sys.exit(1)

    text = text_path.read_text(encoding="utf-8")
    meta = process_book(
        title_en="As a Man Thinketh",
        author_en="James Allen",
        text=text,
        reader="TTS",
        voice="nova",
    )
    print("\nMetadata:")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
