"""Tests for URL/RSS/YouTube source."""

from unittest.mock import patch

from server.ingest.sources.url import download_direct, download_from_source


@patch("server.ingest.sources.url.download_file")
def test_download_direct(mock_dl, tmp_path):
    mock_dl.return_value = tmp_path / "audio.mp3"
    files = download_direct("https://example.com/book.mp3", tmp_path)
    assert len(files) == 1
    mock_dl.assert_called_once_with("https://example.com/book.mp3", tmp_path / "book.mp3")


@patch("server.ingest.sources.url.download_direct")
def test_download_from_source_direct(mock_direct, tmp_path):
    mock_direct.return_value = [tmp_path / "test.mp3"]
    result = download_from_source("https://example.com/test.mp3", "direct", tmp_path)
    assert len(result) == 1
    mock_direct.assert_called_once()


@patch("server.ingest.sources.url.download_rss")
def test_download_from_source_rss(mock_rss, tmp_path):
    mock_rss.return_value = [tmp_path / "001.mp3"]
    result = download_from_source("https://feed.example.com/rss", "rss", tmp_path)
    assert len(result) == 1
    mock_rss.assert_called_once()


@patch("server.ingest.sources.url.download_youtube")
def test_download_from_source_youtube(mock_yt, tmp_path):
    mock_yt.return_value = [tmp_path / "video.mp3"]
    result = download_from_source("https://youtube.com/watch?v=abc", "youtube", tmp_path)
    assert len(result) == 1
    mock_yt.assert_called_once()
