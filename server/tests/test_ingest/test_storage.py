"""Tests for S3 upload functions."""
from unittest.mock import patch, MagicMock
from server.storage import upload_file_to_s3, upload_json_to_s3


@patch("server.storage._get_client")
def test_upload_file_to_s3(mock_client_fn):
    mock_client = MagicMock()
    mock_client_fn.return_value = mock_client
    upload_file_to_s3("/tmp/test.mp3", "books/1/audio/01.mp3")
    mock_client.upload_file.assert_called_once_with(
        "/tmp/test.mp3", "leerio-books", "books/1/audio/01.mp3"
    )


@patch("server.storage._get_client")
def test_upload_json_to_s3(mock_client_fn):
    mock_client = MagicMock()
    mock_client_fn.return_value = mock_client
    upload_json_to_s3({"title": "Test"}, "books/1/metadata.json")
    mock_client.put_object.assert_called_once()
    call_kwargs = mock_client.put_object.call_args[1]
    assert call_kwargs["Key"] == "books/1/metadata.json"
    assert call_kwargs["ContentType"] == "application/json"
