"""Smoke tests for pure functions in server.core."""

from server.core import (
    fmt_duration,
    fuzzy_match,
    normalize,
    parse_folder_name,
    sparkline,
    standardize_name,
)

# ── parse_folder_name ────────────────────────────────────────────────────────


class TestParseFolderName:
    def test_standard(self):
        author, title, reader = parse_folder_name("Автор - Название [Чтец]")
        assert author == "Автор"
        assert title == "Название"
        assert reader == "Чтец"

    def test_no_reader(self):
        author, title, reader = parse_folder_name("Автор - Название")
        assert author == "Автор"
        assert title == "Название"
        assert reader is None

    def test_title_only(self):
        author, title, reader = parse_folder_name("Просто Название")
        assert author == ""
        assert title == "Просто Название"
        assert reader is None

    def test_underscores(self):
        author, title, reader = parse_folder_name("Имя_Автора_-_Моя_Книга_[Чтец_Один]")
        assert "Автора" in author
        assert "Книга" in title
        assert "Чтец" in reader

    def test_parenthetical_reader(self):
        author, title, reader = parse_folder_name("Автор - Название (Чтец)")
        assert author == "Автор"
        assert title == "Название"
        assert reader == "Чтец"

    def test_strips_tech_suffix(self):
        author, title, reader = parse_folder_name("Автор - Название - 2015(64kbts)")
        assert author == "Автор"
        assert title == "Название"


# ── normalize ────────────────────────────────────────────────────────────────


class TestNormalize:
    def test_lowercasing(self):
        assert normalize("Hello World") == "hello world"

    def test_punctuation_removed(self):
        result = normalize('Привет, "мир"!')
        assert "," not in result
        assert '"' not in result
        assert "!" not in result
        assert "привет" in result
        assert "мир" in result

    def test_empty(self):
        assert normalize("") == ""

    def test_whitespace_collapsed(self):
        assert normalize("  hello   world  ") == "hello world"


# ── fuzzy_match ──────────────────────────────────────────────────────────────


class TestFuzzyMatch:
    def test_identical(self):
        assert fuzzy_match("hello", "hello") == 1.0

    def test_different(self):
        assert fuzzy_match("abc", "xyz") < 0.5

    def test_empty(self):
        assert fuzzy_match("", "hello") == 0.0
        assert fuzzy_match("hello", "") == 0.0

    def test_similar(self):
        score = fuzzy_match("Автор - Книга", "Автор - Книга [Чтец]")
        assert score > 0.6


# ── standardize_name ─────────────────────────────────────────────────────────


class TestStandardizeName:
    def test_full(self):
        assert standardize_name("Автор", "Книга", "Чтец") == "Автор - Книга [Чтец]"

    def test_no_reader(self):
        assert standardize_name("Автор", "Книга", None) == "Автор - Книга"

    def test_no_author(self):
        assert standardize_name("", "Книга", "Чтец") == "Книга [Чтец]"

    def test_title_only(self):
        assert standardize_name("", "Книга", None) == "Книга"


# ── fmt_duration ─────────────────────────────────────────────────────────────


class TestFmtDuration:
    def test_none(self):
        assert fmt_duration(None) == ""

    def test_minutes(self):
        assert fmt_duration(0.5) == "30 мин"

    def test_hours(self):
        assert fmt_duration(2.5) == "2.5 ч"

    def test_one_hour(self):
        assert fmt_duration(1.0) == "1.0 ч"


# ── sparkline ────────────────────────────────────────────────────────────────


class TestSparkline:
    def test_empty(self):
        assert sparkline([]) == ""

    def test_values(self):
        result = sparkline([0, 4, 8, 4, 0])
        assert len(result) == 5
        assert result[0] == " "  # zero value → space

    def test_uniform(self):
        result = sparkline([5, 5, 5])
        assert len(result) == 3
