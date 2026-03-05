"""Tests for user book upload API."""

import io


class TestUserBooks:
    def test_list_empty(self, api_client):
        r = api_client.get("/api/user/books")
        assert r.status_code == 200
        assert r.json() == []

    def test_upload_book(self, api_client):
        mp3_content = b"\xff\xfb\x90\x00" + b"\x00" * 100  # Minimal MP3 header
        r = api_client.post(
            "/api/user/books",
            data={"title": "Тестовая книга", "author": "Автор Тест", "reader": "Чтец"},
            files=[
                ("files", ("track1.mp3", io.BytesIO(mp3_content), "audio/mpeg")),
                ("files", ("track2.mp3", io.BytesIO(mp3_content), "audio/mpeg")),
            ],
        )
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "Тестовая книга"
        assert data["author"] == "Автор Тест"
        assert data["is_personal"] is True
        assert data["source"] == "upload"
        assert data["slug"]
        assert data["id"].startswith("ub:")

    def test_list_after_upload(self, api_client):
        mp3_content = b"\xff\xfb\x90\x00" + b"\x00" * 100
        api_client.post(
            "/api/user/books",
            data={"title": "Книга Один", "author": "Автор"},
            files=[("files", ("01.mp3", io.BytesIO(mp3_content), "audio/mpeg"))],
        )
        r = api_client.get("/api/user/books")
        assert r.status_code == 200
        books = r.json()
        assert len(books) == 1
        assert books[0]["title"] == "Книга Один"
        assert books[0]["mp3_count"] == 1

    def test_get_user_book(self, api_client):
        mp3_content = b"\xff\xfb\x90\x00" + b"\x00" * 100
        r = api_client.post(
            "/api/user/books",
            data={"title": "Детали", "author": "Авт"},
            files=[("files", ("01.mp3", io.BytesIO(mp3_content), "audio/mpeg"))],
        )
        slug = r.json()["slug"]

        r = api_client.get(f"/api/user/books/{slug}")
        assert r.status_code == 200
        data = r.json()
        assert data["title"] == "Детали"
        assert data["mp3_count"] == 1

    def test_get_user_book_not_found(self, api_client):
        r = api_client.get("/api/user/books/nonexistent")
        assert r.status_code == 404

    def test_delete_user_book(self, api_client):
        mp3_content = b"\xff\xfb\x90\x00" + b"\x00" * 100
        r = api_client.post(
            "/api/user/books",
            data={"title": "Удалить", "author": ""},
            files=[("files", ("01.mp3", io.BytesIO(mp3_content), "audio/mpeg"))],
        )
        slug = r.json()["slug"]

        r = api_client.delete(f"/api/user/books/{slug}")
        assert r.status_code == 200
        assert r.json()["ok"] is True

        r = api_client.get("/api/user/books")
        assert r.json() == []

    def test_delete_not_found(self, api_client):
        r = api_client.delete("/api/user/books/nonexistent")
        assert r.status_code == 404

    def test_user_book_tracks(self, api_client):
        mp3_content = b"\xff\xfb\x90\x00" + b"\x00" * 100
        r = api_client.post(
            "/api/user/books",
            data={"title": "Треки", "author": ""},
            files=[
                ("files", ("track1.mp3", io.BytesIO(mp3_content), "audio/mpeg")),
                ("files", ("track2.mp3", io.BytesIO(mp3_content), "audio/mpeg")),
            ],
        )
        slug = r.json()["slug"]

        r = api_client.get(f"/api/user/books/{slug}/tracks")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 2
        assert len(data["tracks"]) == 2
        assert data["tracks"][0]["index"] == 0

    def test_upload_invalid_file_type(self, api_client):
        r = api_client.post(
            "/api/user/books",
            data={"title": "Bad", "author": ""},
            files=[("files", ("doc.pdf", io.BytesIO(b"fake"), "application/pdf"))],
        )
        assert r.status_code == 400

    def test_upload_with_cover(self, api_client):
        mp3_content = b"\xff\xfb\x90\x00" + b"\x00" * 100
        cover_content = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # Minimal JPEG header
        r = api_client.post(
            "/api/user/books",
            data={"title": "С обложкой", "author": ""},
            files=[
                ("files", ("01.mp3", io.BytesIO(mp3_content), "audio/mpeg")),
                ("cover", ("cover.jpg", io.BytesIO(cover_content), "image/jpeg")),
            ],
        )
        assert r.status_code == 200
        slug = r.json()["slug"]

        r = api_client.get(f"/api/user/books/{slug}/cover")
        assert r.status_code == 200

    def test_user_books_in_library_list(self, api_client):
        """User books should appear in the main /api/books list."""
        mp3_content = b"\xff\xfb\x90\x00" + b"\x00" * 100
        api_client.post(
            "/api/user/books",
            data={"title": "В общем списке", "author": ""},
            files=[("files", ("01.mp3", io.BytesIO(mp3_content), "audio/mpeg"))],
        )
        r = api_client.get("/api/books")
        assert r.status_code == 200
        personal = [b for b in r.json() if b.get("is_personal")]
        assert len(personal) == 1
        assert personal[0]["title"] == "В общем списке"
