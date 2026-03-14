"""Shared fixtures for server tests."""

import json

import pytest

TEST_USER = {
    "user_id": "test-user-001",
    "email": "test@example.com",
    "name": "Test User",
    "picture": "",
    "role": "admin",
    "created_at": "2024-01-01T00:00:00",
    "last_login": None,
}


@pytest.fixture()
def tmp_data_dir(tmp_path, monkeypatch):
    """Patch server.core paths and server.db to use a temporary directory."""
    import server.core as core
    import server.db as db_mod

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    books_dir = tmp_path / "books"
    for cat in core.CATEGORIES:
        (books_dir / cat).mkdir(parents=True)

    # Write minimal config so lifespan doesn't fail
    (data_dir / "config.json").write_text(json.dumps({}), encoding="utf-8")

    # Create users dir for per-user data
    users_dir = data_dir / "users"
    users_dir.mkdir()

    # Patch all path constants in core
    monkeypatch.setattr(core, "DATA_DIR", data_dir)
    monkeypatch.setattr(core, "BOOKS_DIR", books_dir)
    monkeypatch.setattr(core, "USERS_DIR", users_dir)
    monkeypatch.setattr(core, "CONFIG_PATH", data_dir / "config.json")
    monkeypatch.setattr(core, "TRACKER_PATH", data_dir / "tracker.csv")
    monkeypatch.setattr(core, "HISTORY_PATH", data_dir / "history.json")
    monkeypatch.setattr(core, "NOTES_PATH", data_dir / "notes.json")
    monkeypatch.setattr(core, "TAGS_PATH", data_dir / "tags.json")
    monkeypatch.setattr(core, "COLLECTIONS_PATH", data_dir / "collections.json")
    monkeypatch.setattr(core, "PROGRESS_PATH", data_dir / "progress.json")
    monkeypatch.setattr(core, "PLAYBACK_PATH", data_dir / "playback.json")
    monkeypatch.setattr(core, "QUOTES_PATH", data_dir / "quotes.json")
    monkeypatch.setattr(core, "SESSIONS_PATH", data_dir / "sessions.json")
    monkeypatch.setattr(core, "RECOMMENDATIONS_PATH", data_dir / "recommendations.md")

    # Patch DB path
    monkeypatch.setattr(db_mod, "DB_PATH", data_dir / "leerio.db")

    return {"data": data_dir, "books": books_dir}


@pytest.fixture()
def api_client(tmp_data_dir, monkeypatch):
    """TestClient with isolated data directories and mocked auth."""
    from starlette.testclient import TestClient

    import server.api as api_mod
    import server.db as db_mod
    from server.auth import get_current_user, get_optional_user

    # Ensure tables exist
    db_mod.init_db()

    # Override auth dependency to return test user
    def _mock_user():
        return TEST_USER

    api_mod.app.dependency_overrides[get_current_user] = _mock_user
    api_mod.app.dependency_overrides[get_optional_user] = _mock_user

    client = TestClient(api_mod.app)
    yield client

    # Clean up overrides
    api_mod.app.dependency_overrides.clear()


@pytest.fixture()
def sample_books(tmp_data_dir):
    """Create sample books in the database and filesystem."""
    import server.db as db_mod

    # Ensure tables exist
    db_mod.init_db()

    books_dir = tmp_data_dir["books"]

    # Create filesystem directories (for covers/audio)
    book_data = [
        ("Саморазвитие", "Автор Один - Книга Первая [Чтец]", "Автор Один", "Книга Первая", "Чтец"),
        ("Бизнес", "Автор Два - Книга Вторая", "Автор Два", "Книга Вторая", ""),
        ("Художественная", "Толстой - Война и Мир [Козий]", "Толстой", "Война и Мир", "Козий"),
    ]

    conn = db_mod._get_conn()
    book_ids = []
    for cat, folder, author, title, reader in book_data:
        (books_dir / cat / folder).mkdir(parents=True, exist_ok=True)
        slug = f"{author}-{title}".lower().replace(" ", "-")
        conn.execute(
            """INSERT INTO books (slug, title, author, reader, category, folder, s3_prefix, has_cover, mp3_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)""",
            (slug, title, author, reader, cat, folder, f"{cat}/{folder}"),
        )
        book_ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    conn.commit()
    return book_ids
