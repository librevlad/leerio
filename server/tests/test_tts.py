"""Tests for TTS engine and API endpoints."""

import io
from textwrap import dedent

from server.tts import (
    Chapter,
    _detect_chapters,
    _rate_to_speed,
    _safe_filename,
    clean_text,
    extract_text_fb2,
    extract_text_txt,
    get_voices,
    openai_available,
)

# ── Unit tests: text cleaning ─────────────────────────────────────────────────


class TestCleanText:
    def test_removes_urls(self):
        text = "Прочитайте на https://example.com/page?x=1 и www.site.ru подробнее"
        result = clean_text(text)
        assert "https://" not in result
        assert "www." not in result

    def test_removes_emails(self):
        text = "Пишите на user@example.com для связи"
        result = clean_text(text)
        assert "@" not in result

    def test_removes_page_numbers_standalone(self):
        text = "Конец абзаца.\n\n42\n\nНачало следующего."
        result = clean_text(text)
        assert "\n42\n" not in result

    def test_removes_page_numbers_dashed(self):
        text = "Текст.\n\n- 34 -\n\nПродолжение."
        result = clean_text(text)
        assert "34" not in result

    def test_removes_page_str(self):
        text = "Смотри стр. 245 подробнее."
        result = clean_text(text)
        assert "стр" not in result
        assert "245" not in result

    def test_fixes_broken_words(self):
        text = "Это про-\nдолжение текста."
        result = clean_text(text)
        assert "продолжение" in result

    def test_normalizes_whitespace(self):
        text = "Текст   с    пробелами.\n\n\n\n\nСлишком много переносов."
        result = clean_text(text)
        assert "   " not in result
        assert "\n\n\n" not in result

    def test_ensures_punctuation(self):
        text = "Это длинный абзац который не заканчивается знаком препинания и продолжается дальше"
        result = clean_text(text)
        assert result.endswith(".")

    def test_no_punctuation_for_short_lines(self):
        text = "Заголовок"
        result = clean_text(text)
        assert not result.endswith(".")

    def test_preserves_existing_punctuation(self):
        text = "Это предложение с восклицательным знаком!"
        result = clean_text(text)
        assert result.endswith("!")
        assert not result.endswith("!.")

    def test_removes_junk_characters(self):
        text = "Текст *** разделитель === ещё _____ и ─────── тоже"
        result = clean_text(text)
        assert "***" not in result
        assert "===" not in result
        assert "___" not in result


# ── Unit tests: chapter detection ─────────────────────────────────────────────


class TestDetectChapters:
    def test_russian_glava_headings(self):
        text = dedent("""\
            Вступление.

            Глава 1. Начало
            Текст первой главы. Много текста здесь и далее по тексту.

            Глава 2. Продолжение
            Текст второй главы. И тут тоже достаточно текста.

            Глава 3. Финал
            Текст третьей главы с завершением истории.
        """)
        chapters = _detect_chapters(text)
        assert len(chapters) == 3
        assert "Глава 1" in chapters[0].title
        assert "Глава 2" in chapters[1].title
        assert "Глава 3" in chapters[2].title
        assert isinstance(chapters[0], Chapter)

    def test_english_chapter_headings(self):
        text = dedent("""\
            Preface text.

            Chapter 1. The Beginning
            First chapter body text goes here with enough content.

            Chapter 2. The Middle
            Second chapter body text continues the story.
        """)
        chapters = _detect_chapters(text)
        assert len(chapters) == 2
        assert "Chapter 1" in chapters[0].title
        assert "Chapter 2" in chapters[1].title

    def test_chast_headings(self):
        text = dedent("""\
            Часть 1 Введение
            Содержание первой части с достаточным количеством текста.

            Часть 2 Развитие
            Содержание второй части с продолжением истории.
        """)
        chapters = _detect_chapters(text)
        assert len(chapters) == 2
        assert "Часть 1" in chapters[0].title

    def test_fallback_to_size_split(self):
        text = "Абзац один.\n\n" * 50 + "Абзац два.\n\n" * 50
        chapters = _detect_chapters(text)
        assert len(chapters) >= 1
        assert all(isinstance(ch, Chapter) for ch in chapters)
        # Fallback titles are "Часть N"
        assert chapters[0].title.startswith("Часть ")

    def test_single_match_falls_back(self):
        """A single heading match should not split — need 2+."""
        text = "Глава 1. Единственная\nТекст главы."
        chapters = _detect_chapters(text)
        # Only 1 match, so falls back to size split
        assert chapters[0].title.startswith("Часть ")


# ── Unit tests: safe filename ─────────────────────────────────────────────────


class TestSafeFilename:
    def test_basic(self):
        assert _safe_filename("Глава 1. Начало") == "Глава 1. Начало"

    def test_removes_illegal_chars(self):
        result = _safe_filename('Глава 1: "Начало" <пути>')
        assert ":" not in result
        assert '"' not in result
        assert "<" not in result
        assert ">" not in result

    def test_length_limit(self):
        long_title = "А" * 100
        result = _safe_filename(long_title)
        assert len(result) <= 60

    def test_empty_becomes_chapter(self):
        assert _safe_filename("") == "chapter"

    def test_whitespace_collapsed(self):
        assert _safe_filename("Глава  1   Начало") == "Глава 1 Начало"


# ── Unit tests: FB2 extractor ─────────────────────────────────────────────────


class TestExtractFB2:
    def test_extracts_titles_from_sections(self, tmp_path):
        fb2_content = """\
<?xml version="1.0" encoding="utf-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">
  <body>
    <section>
      <title><p>Первая глава</p></title>
      <p>Текст первой главы. Достаточно длинный текст чтобы пройти фильтр по длине и быть включённым в результат.</p>
      <p>Ещё один абзац первой главы с дополнительным содержанием для объёма текста в секции.</p>
    </section>
    <section>
      <title><p>Вторая глава</p></title>
      <p>Текст второй главы. Тоже достаточно длинный текст чтобы пройти все проверки и фильтры по размеру.</p>
      <p>Дополнительный абзац второй главы для набора необходимого количества символов в тексте.</p>
    </section>
  </body>
</FictionBook>"""
        fb2_file = tmp_path / "test.fb2"
        fb2_file.write_text(fb2_content, encoding="utf-8")

        chapters = extract_text_fb2(fb2_file)
        assert len(chapters) == 2
        assert chapters[0].title == "Первая глава"
        assert chapters[1].title == "Вторая глава"
        # Title text should NOT appear in body
        assert "Первая глава" not in chapters[0].text
        assert "Вторая глава" not in chapters[1].text

    def test_fallback_without_titles(self, tmp_path):
        fb2_content = """\
<?xml version="1.0" encoding="utf-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">
  <body>
    <section>
      <p>Текст без заголовка. Просто текст секции без элемента title внутри для тестирования.</p>
      <p>Ещё абзац текста для увеличения общего объёма и проверки корректной обработки.</p>
    </section>
  </body>
</FictionBook>"""
        fb2_file = tmp_path / "test.fb2"
        fb2_file.write_text(fb2_content, encoding="utf-8")

        chapters = extract_text_fb2(fb2_file)
        assert len(chapters) >= 1
        assert chapters[0].title == "Часть 1"


# ── Unit tests: TXT extractor ────────────────────────────────────────────────


class TestExtractTXT:
    def test_detects_chapters_in_txt(self, tmp_path):
        content = dedent("""\
            Вступительный текст книги.

            Глава 1. Утро
            Солнце встало рано. Герой проснулся и начал свой день.

            Глава 2. День
            Весь день был полон событий и приключений.

            Глава 3. Вечер
            К вечеру всё успокоилось и герой вернулся домой.
        """)
        txt_file = tmp_path / "book.txt"
        txt_file.write_text(content, encoding="utf-8")

        chapters = extract_text_txt(txt_file)
        assert len(chapters) == 3
        assert "Глава 1" in chapters[0].title
        assert "Глава 3" in chapters[2].title

    def test_plain_text_size_split(self, tmp_path):
        content = "Текст без глав. " * 500
        txt_file = tmp_path / "plain.txt"
        txt_file.write_text(content, encoding="utf-8")

        chapters = extract_text_txt(txt_file)
        assert len(chapters) >= 1
        assert chapters[0].title.startswith("Часть ")


# ── API tests ─────────────────────────────────────────────────────────────────


class TestTTSApi:
    def test_list_voices(self, api_client):
        r = api_client.get("/api/tts/voices")
        assert r.status_code == 200
        voices = r.json()
        assert len(voices) > 0
        assert voices[0]["id"]
        assert voices[0]["name"]
        assert voices[0]["lang"]

    def test_list_jobs_empty(self, api_client):
        r = api_client.get("/api/tts/jobs")
        assert r.status_code == 200
        assert r.json() == []

    def test_get_job_not_found(self, api_client):
        r = api_client.get("/api/tts/jobs/nonexistent")
        assert r.status_code == 404

    def test_convert_invalid_format(self, api_client):
        r = api_client.post(
            "/api/tts/convert",
            data={"title": "Test", "author": "", "voice": "ru-RU-DmitryNeural"},
            files=[("file", ("doc.docx", io.BytesIO(b"fake"), "application/octet-stream"))],
        )
        assert r.status_code == 400
        assert "Unsupported format" in r.json()["detail"]

    def test_convert_invalid_voice(self, api_client):
        r = api_client.post(
            "/api/tts/convert",
            data={"title": "Test", "author": "", "voice": "invalid-voice"},
            files=[("file", ("doc.txt", io.BytesIO(b"Hello world"), "text/plain"))],
        )
        assert r.status_code == 400
        assert "Unknown voice" in r.json()["detail"]

    def test_list_engines(self, api_client):
        r = api_client.get("/api/tts/engines")
        assert r.status_code == 200
        engines = r.json()
        assert len(engines) == 2
        assert engines[0]["id"] == "edge"
        assert engines[0]["available"] is True
        assert engines[1]["id"] == "openai"

    def test_list_voices_with_engine(self, api_client):
        r = api_client.get("/api/tts/voices?engine=edge")
        assert r.status_code == 200
        voices = r.json()
        assert all(v["engine"] == "edge" for v in voices)

    def test_list_voices_openai(self, api_client):
        r = api_client.get("/api/tts/voices?engine=openai")
        assert r.status_code == 200
        voices = r.json()
        assert all(v["engine"] == "openai" for v in voices)
        assert len(voices) == 6

    def test_convert_invalid_engine(self, api_client):
        r = api_client.post(
            "/api/tts/convert",
            data={"title": "Test", "author": "", "voice": "alloy", "engine": "bad"},
            files=[("file", ("doc.txt", io.BytesIO(b"Hello world"), "text/plain"))],
        )
        assert r.status_code == 400
        assert "Unknown engine" in r.json()["detail"]


# ── Unit tests: engine helpers ───────────────────────────────────────────────


class TestRateToSpeed:
    def test_default(self):
        assert _rate_to_speed("+0%") == 1.0

    def test_positive(self):
        assert _rate_to_speed("+25%") == 1.25

    def test_negative(self):
        assert _rate_to_speed("-25%") == 0.75

    def test_large_positive(self):
        assert _rate_to_speed("+50%") == 1.5

    def test_empty(self):
        assert _rate_to_speed("") == 1.0

    def test_invalid(self):
        assert _rate_to_speed("abc") == 1.0


class TestGetVoices:
    def test_edge_voices(self):
        voices = get_voices("edge")
        assert len(voices) == 8
        assert all(v["engine"] == "edge" for v in voices)

    def test_openai_voices(self):
        voices = get_voices("openai")
        assert len(voices) == 6
        assert all(v["engine"] == "openai" for v in voices)

    def test_default_is_edge(self):
        voices = get_voices()
        assert all(v["engine"] == "edge" for v in voices)


class TestOpenaiAvailable:
    def test_not_configured(self, monkeypatch):
        monkeypatch.setattr("server.tts.TTS_OPENAI_BASE_URL", "")
        assert openai_available() is False

    def test_configured(self, monkeypatch):
        monkeypatch.setattr("server.tts.TTS_OPENAI_BASE_URL", "http://localhost:8000/v1")
        assert openai_available() is True
