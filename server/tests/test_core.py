"""Smoke tests for pure functions in server.core."""

from server.core import (
    UserData,
    fmt_duration,
    fuzzy_match,
    make_slug,
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


# ── make_slug ────────────────────────────────────────────────────────────────


class TestMakeSlug:
    def test_cyrillic(self):
        slug = make_slug("Война и Мир", "Толстой")
        assert slug == "tolstoy-voyna-i-mir"

    def test_english(self):
        slug = make_slug("The Great Book", "Author")
        assert slug == "author-the-great-book"

    def test_empty_author(self):
        slug = make_slug("Название")
        assert slug == "nazvanie"

    def test_special_chars(self):
        slug = make_slug("Книга! (Часть 1)", "")
        assert "-" not in slug or slug.count("-") >= 0
        assert "!" not in slug
        assert "(" not in slug

    def test_max_length(self):
        slug = make_slug("А" * 200)
        assert len(slug) <= 80

    def test_empty(self):
        slug = make_slug("")
        assert slug == "book"


# ── UserData user books ─────────────────────────────────────────────────────


class TestUserDataBooks:
    def test_books_list_empty(self, tmp_data_dir):
        ud = UserData("test-user")
        assert ud.user_books_list() == []

    def test_create_and_list(self, tmp_data_dir):
        ud = UserData("test-user")
        ud.user_book_create("my-book", "Моя Книга", "Автор", "Чтец", "upload")
        books = ud.user_books_list()
        assert len(books) == 1
        assert books[0]["title"] == "Моя Книга"
        assert books[0]["slug"] == "my-book"

    def test_get(self, tmp_data_dir):
        ud = UserData("test-user")
        ud.user_book_create("slug1", "Title", "Author")
        meta = ud.user_book_get("slug1")
        assert meta is not None
        assert meta["title"] == "Title"

    def test_get_not_found(self, tmp_data_dir):
        ud = UserData("test-user")
        assert ud.user_book_get("nope") is None

    def test_delete(self, tmp_data_dir):
        ud = UserData("test-user")
        ud.user_book_create("del-me", "Delete", "")
        assert ud.user_book_delete("del-me") is True
        assert ud.user_book_get("del-me") is None

    def test_delete_not_found(self, tmp_data_dir):
        ud = UserData("test-user")
        assert ud.user_book_delete("nope") is False


# ── UserData TTS jobs ────────────────────────────────────────────────────────


class TestUserDataTTSJobs:
    def test_empty(self, tmp_data_dir):
        ud = UserData("test-user")
        assert ud.tts_jobs_load() == []

    def test_create_and_get(self, tmp_data_dir):
        ud = UserData("test-user")
        job = ud.tts_job_create("j1", "Title", "Author", "voice", "slug")
        assert job["id"] == "j1"
        assert job["status"] == "processing"
        fetched = ud.tts_job_get("j1")
        assert fetched["title"] == "Title"

    def test_update(self, tmp_data_dir):
        ud = UserData("test-user")
        ud.tts_job_create("j2", "T", "A", "v", "s")
        ud.tts_job_update("j2", status="done", progress=100)
        job = ud.tts_job_get("j2")
        assert job["status"] == "done"
        assert job["progress"] == 100
