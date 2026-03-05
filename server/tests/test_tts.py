"""Tests for TTS API endpoints."""

import io


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
