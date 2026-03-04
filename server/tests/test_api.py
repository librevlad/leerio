"""Smoke tests for API endpoints using TestClient."""


class TestAuth:
    def test_me_unauthenticated(self, tmp_data_dir, monkeypatch):
        """GET /api/auth/me without auth returns 401."""
        from starlette.testclient import TestClient

        import server.api as api_mod
        import server.db as db_mod
        from server.core import Library

        monkeypatch.setattr(api_mod, "lib", Library())
        monkeypatch.setattr(db_mod, "DB_PATH", tmp_data_dir["data"] / "leerio.db")

        # No dependency override — real auth check
        client = TestClient(api_mod.app, raise_server_exceptions=False)
        r = client.get("/api/auth/me")
        assert r.status_code == 401

    def test_me_authenticated(self, api_client):
        """GET /api/auth/me with mocked auth returns user."""
        r = api_client.get("/api/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == "test@example.com"
        assert data["role"] == "admin"

    def test_logout(self, api_client):
        r = api_client.post("/api/auth/logout")
        assert r.status_code == 200
        assert r.json()["ok"] is True


class TestAccessControl:
    def test_unapproved_email_rejected(self, tmp_data_dir, monkeypatch):
        """Unapproved email gets 403 on /api/auth/google."""
        from starlette.testclient import TestClient

        import server.api as api_mod
        import server.db as db_mod
        from server.core import Library

        monkeypatch.setattr(api_mod, "lib", Library())
        monkeypatch.setattr(db_mod, "DB_PATH", tmp_data_dir["data"] / "leerio.db")

        # Initialize DB with allowlist containing only admin
        monkeypatch.setenv("ALLOWED_EMAILS", "admin@example.com")
        db_mod.init_db()

        # Mock verify_google_token to return an unapproved email
        def mock_verify(token):
            return {"email": "stranger@example.com", "name": "Stranger", "picture": ""}

        monkeypatch.setattr(api_mod, "verify_google_token", mock_verify)

        client = TestClient(api_mod.app, raise_server_exceptions=False)
        r = client.post("/api/auth/google", json={"id_token": "fake"})
        assert r.status_code == 403


class TestConstants:
    def test_returns_categories(self, api_client):
        r = api_client.get("/api/config/constants")
        assert r.status_code == 200
        data = r.json()
        assert "categories" in data
        assert len(data["categories"]) == 5
        assert "book_statuses" in data


class TestDashboard:
    def test_returns_200(self, api_client, sample_books):
        r = api_client.get("/api/dashboard")
        assert r.status_code == 200
        data = r.json()
        assert "total_books" in data
        assert "total_done" in data
        assert "recent" in data

    def test_counts_books(self, api_client, sample_books):
        r = api_client.get("/api/dashboard")
        assert r.json()["total_books"] == 3


class TestBooks:
    def test_list_returns_200(self, api_client, sample_books):
        r = api_client.get("/api/books")
        assert r.status_code == 200
        books = r.json()
        assert isinstance(books, list)
        assert len(books) == 3

    def test_filter_by_category(self, api_client, sample_books):
        r = api_client.get("/api/books?category=Бизнес")
        assert r.status_code == 200
        books = r.json()
        assert len(books) == 1
        assert books[0]["category"] == "Бизнес"

    def test_search(self, api_client, sample_books):
        r = api_client.get("/api/books?search=Толстой")
        assert r.status_code == 200
        books = r.json()
        assert len(books) == 1
        assert "Толстой" in books[0]["author"]

    def test_get_book_not_found(self, api_client):
        import base64

        fake_id = base64.urlsafe_b64encode(b"/nonexistent/path").decode()
        r = api_client.get(f"/api/books/{fake_id}")
        assert r.status_code == 404

    def test_empty_library(self, api_client):
        r = api_client.get("/api/books")
        assert r.status_code == 200
        assert r.json() == []


class TestHistory:
    def test_empty_history(self, api_client):
        r = api_client.get("/api/history")
        assert r.status_code == 200
        assert r.json() == []


class TestQuotes:
    def test_empty_quotes(self, api_client):
        r = api_client.get("/api/quotes")
        assert r.status_code == 200
        assert r.json() == []

    def test_add_and_list(self, api_client):
        r = api_client.post("/api/quotes", json={"text": "Цитата", "book": "Книга"})
        assert r.status_code == 200
        r = api_client.get("/api/quotes")
        assert len(r.json()) == 1
        assert r.json()[0]["text"] == "Цитата"


class TestCollections:
    def test_empty_collections(self, api_client):
        r = api_client.get("/api/collections")
        assert r.status_code == 200
        assert r.json() == []

    def test_create_collection(self, api_client):
        r = api_client.post("/api/collections", json={"name": "Лучшие"})
        assert r.status_code == 200
        r = api_client.get("/api/collections")
        assert len(r.json()) == 1


class TestProgress:
    def test_empty_progress(self, api_client):
        r = api_client.get("/api/progress")
        assert r.status_code == 200
        assert r.json() == {}

    def test_set_progress(self, api_client):
        r = api_client.put("/api/progress/Книга", json={"pct": 50})
        assert r.status_code == 200
        r = api_client.get("/api/progress")
        data = r.json()
        assert len(data) == 1
