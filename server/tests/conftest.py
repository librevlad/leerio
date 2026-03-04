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
    """Patch server.core paths to use a temporary directory."""
    import server.core as core

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

    return {"data": data_dir, "books": books_dir}


@pytest.fixture()
def api_client(tmp_data_dir, monkeypatch):
    """TestClient with isolated data directories and mocked auth."""
    from starlette.testclient import TestClient

    import server.api as api_mod
    import server.db as db_mod
    from server.auth import get_current_user
    from server.core import Library

    # Replace the Library instance so it uses patched BOOKS_DIR
    monkeypatch.setattr(api_mod, "lib", Library())

    # Patch DB path so init_db doesn't touch real DB
    monkeypatch.setattr(db_mod, "DB_PATH", tmp_data_dir["data"] / "leerio.db")

    # Override auth dependency to return test user
    def _mock_user():
        return TEST_USER

    api_mod.app.dependency_overrides[get_current_user] = _mock_user

    client = TestClient(api_mod.app)
    yield client

    # Clean up overrides
    api_mod.app.dependency_overrides.clear()


@pytest.fixture()
def sample_books(tmp_data_dir):
    """Create a few sample book directories."""
    books_dir = tmp_data_dir["books"]
    books = [
        ("Саморазвитие", "Автор Один - Книга Первая [Чтец]"),
        ("Бизнес", "Автор Два - Книга Вторая"),
        ("Художественная", "Толстой - Война и Мир [Козий]"),
    ]
    for cat, folder in books:
        (books_dir / cat / folder).mkdir()
    return books
