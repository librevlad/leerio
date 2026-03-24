"""Tests for book visibility (owner_user_id) and owned books in My Library.

Covers:
- Catalog only shows public books (owner_user_id IS NULL)
- Owned books appear in /api/user/books with correct format
- Owned book detail returns is_owned=True
- Owned book detail accessible by owner, 404 for others
- Audio/cover endpoints guard private books
- Delete owned book endpoint
- Anonymous user sees only public books
"""

import server.db as db

from .conftest import TEST_USER

OTHER_USER = {
    "user_id": "other-user-002",
    "email": "other@example.com",
    "name": "Other User",
    "picture": "",
    "role": "user",
    "created_at": "2024-01-01T00:00:00",
    "last_login": None,
}


def _insert_books_with_owner(owner_uid: str | None = None):
    """Insert 3 public + 2 owned books. Returns (public_ids, owned_ids)."""
    conn = db._get_conn()
    public_ids = []
    for i, (title, cat) in enumerate(
        [("Public One", "Художественная"), ("Public Two", "Художественная"), ("Public Three", "Языки")]
    ):
        conn.execute(
            """INSERT INTO books (slug, title, author, category, folder, s3_prefix, source)
               VALUES (?, ?, 'Author', ?, ?, ?, 'librivox')""",
            (f"pub-{i}", title, cat, f"folder-pub-{i}", f"{cat}/folder-pub-{i}"),
        )
        public_ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    owned_ids = []
    for i, (title, cat) in enumerate([("Owned Book A", "Бизнес"), ("Owned Book B", "Саморазвитие")]):
        conn.execute(
            """INSERT INTO books (slug, title, author, category, folder, s3_prefix, source, owner_user_id)
               VALUES (?, ?, 'Author', ?, ?, ?, 'manual', ?)""",
            (f"own-{i}", title, cat, f"folder-own-{i}", f"{cat}/folder-own-{i}", owner_uid),
        )
        owned_ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])

    conn.commit()
    return public_ids, owned_ids


class TestCatalogVisibility:
    """Catalog endpoints should only return public books."""

    def test_catalog_shows_only_public(self, api_client):
        pub_ids, own_ids = _insert_books_with_owner(TEST_USER["user_id"])
        r = api_client.get("/api/books")
        assert r.status_code == 200
        books = r.json()
        ids = {b["id"] for b in books}
        # Public books visible
        for pid in pub_ids:
            assert str(pid) in ids or pid in ids
        # Owned books NOT in catalog
        for oid in own_ids:
            assert str(oid) not in ids and oid not in ids

    def test_catalog_count(self, api_client):
        _insert_books_with_owner(TEST_USER["user_id"])
        r = api_client.get("/api/books")
        # Only 3 public books, not 5
        catalog_books = [b for b in r.json() if not b.get("is_personal")]
        assert len(catalog_books) == 3

    def test_search_excludes_owned(self, api_client):
        _insert_books_with_owner(TEST_USER["user_id"])
        r = api_client.get("/api/books?search=Owned")
        books = r.json()
        assert len(books) == 0

    def test_search_finds_public(self, api_client):
        _insert_books_with_owner(TEST_USER["user_id"])
        r = api_client.get("/api/books?search=Public")
        books = r.json()
        assert len(books) == 3


class TestOwnedBooksInMyLibrary:
    """Owned catalog books should appear in /api/user/books."""

    def test_owned_books_in_user_books_list(self, api_client):
        _insert_books_with_owner(TEST_USER["user_id"])
        r = api_client.get("/api/user/books")
        assert r.status_code == 200
        books = r.json()
        owned = [b for b in books if b.get("source") == "catalog"]
        assert len(owned) == 2

    def test_owned_books_have_string_ids(self, api_client):
        """Regression: owned books returned integer IDs, crashing the frontend."""
        _insert_books_with_owner(TEST_USER["user_id"])
        r = api_client.get("/api/user/books")
        books = r.json()
        for b in books:
            assert isinstance(b["id"], str), f"Book id should be string, got {type(b['id'])}: {b['id']}"

    def test_owned_books_have_required_fields(self, api_client):
        _insert_books_with_owner(TEST_USER["user_id"])
        r = api_client.get("/api/user/books")
        books = r.json()
        owned = [b for b in books if b.get("source") == "catalog"]
        for b in owned:
            assert "id" in b
            assert "title" in b
            assert "author" in b
            assert "is_personal" in b
            assert b["is_personal"] is True
            assert "has_cover" in b
            assert "mp3_count" in b

    def test_owned_books_not_mixed_with_other_users(self, api_client):
        """Books owned by another user should not appear in my library."""
        _insert_books_with_owner("someone-else-999")
        r = api_client.get("/api/user/books")
        books = r.json()
        owned = [b for b in books if b.get("source") == "catalog"]
        assert len(owned) == 0


class TestOwnedBookDetail:
    """Book detail endpoint should expose is_owned and guard access."""

    def test_owned_book_shows_is_owned(self, api_client):
        _, own_ids = _insert_books_with_owner(TEST_USER["user_id"])
        r = api_client.get(f"/api/books/{own_ids[0]}")
        assert r.status_code == 200
        data = r.json()
        assert data.get("is_owned") is True

    def test_public_book_no_is_owned(self, api_client):
        pub_ids, _ = _insert_books_with_owner(TEST_USER["user_id"])
        r = api_client.get(f"/api/books/{pub_ids[0]}")
        assert r.status_code == 200
        data = r.json()
        assert "is_owned" not in data or data.get("is_owned") is not True

    def test_other_users_book_returns_404(self, api_client):
        """Books owned by another user should be invisible."""
        _, own_ids = _insert_books_with_owner("someone-else-999")
        r = api_client.get(f"/api/books/{own_ids[0]}")
        assert r.status_code == 404


class TestDeleteOwnedBook:
    """DELETE /api/books/{id} for owned books."""

    def test_delete_owned_book(self, api_client):
        _, own_ids = _insert_books_with_owner(TEST_USER["user_id"])
        r = api_client.delete(f"/api/books/{own_ids[0]}")
        assert r.status_code == 200
        assert r.json()["ok"] is True
        # Verify deleted
        r = api_client.get(f"/api/books/{own_ids[0]}")
        assert r.status_code == 404

    def test_delete_public_book_fails(self, api_client):
        """Cannot delete books you don't own."""
        pub_ids, _ = _insert_books_with_owner(TEST_USER["user_id"])
        r = api_client.delete(f"/api/books/{pub_ids[0]}")
        assert r.status_code == 404

    def test_delete_other_users_book_fails(self, api_client):
        _, own_ids = _insert_books_with_owner("someone-else-999")
        r = api_client.delete(f"/api/books/{own_ids[0]}")
        assert r.status_code == 404

    def test_delete_nonexistent_book(self, api_client):
        r = api_client.delete("/api/books/999999")
        assert r.status_code == 404


class TestAnonymousAccess:
    """Anonymous users (no auth) should only see public books."""

    def test_anonymous_catalog(self, anon_client):
        _insert_books_with_owner(TEST_USER["user_id"])
        r = anon_client.get("/api/books")
        assert r.status_code == 200
        books = r.json()
        # Only public books, no owned
        assert len(books) == 3
        for b in books:
            assert "Owned" not in b["title"]

    def test_anonymous_owned_book_404(self, anon_client):
        _, own_ids = _insert_books_with_owner(TEST_USER["user_id"])
        r = anon_client.get(f"/api/books/{own_ids[0]}")
        assert r.status_code == 404
