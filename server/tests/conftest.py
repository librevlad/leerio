"""Shared fixtures for server tests."""

import json

import pytest


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
    config = {"trello_api_key": "", "trello_token": "", "board_id": "test"}
    (data_dir / "config.json").write_text(json.dumps(config), encoding="utf-8")

    # Patch all path constants in core
    monkeypatch.setattr(core, "DATA_DIR", data_dir)
    monkeypatch.setattr(core, "BOOKS_DIR", books_dir)
    monkeypatch.setattr(core, "CONFIG_PATH", data_dir / "config.json")
    monkeypatch.setattr(core, "TRACKER_PATH", data_dir / "tracker.csv")
    monkeypatch.setattr(core, "HISTORY_PATH", data_dir / "history.json")
    monkeypatch.setattr(core, "CACHE_PATH", data_dir / "trello_cache.json")
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
    """TestClient with isolated data directories."""
    from starlette.testclient import TestClient

    import server.api as api_mod
    from server.core import Library

    # Replace the Library instance so it uses patched BOOKS_DIR
    monkeypatch.setattr(api_mod, "lib", Library())
    monkeypatch.setattr(api_mod, "trello", None)

    return TestClient(api_mod.app)


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
