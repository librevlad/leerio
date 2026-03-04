"""Smoke tests for API endpoints using TestClient."""


class TestConstants:
    def test_returns_categories(self, api_client):
        r = api_client.get("/api/config/constants")
        assert r.status_code == 200
        data = r.json()
        assert "categories" in data
        assert len(data["categories"]) == 5
        assert data["trello_connected"] is False


class TestDashboard:
    def test_returns_200(self, api_client, sample_books):
        r = api_client.get("/api/dashboard")
        assert r.status_code == 200
        data = r.json()
        assert "total_books" in data
        assert "total_done" in data
        assert "velocity" in data
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
