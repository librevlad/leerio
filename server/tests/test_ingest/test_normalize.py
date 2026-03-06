"""Tests for audio normalization via ffmpeg."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from server.ingest.normalize import build_ffmpeg_cmd, is_mp3, normalize_file


def test_build_ffmpeg_cmd_default():
    cmd = build_ffmpeg_cmd(Path("/tmp/input.mp3"), Path("/tmp/output.mp3"))
    assert "ffmpeg" in cmd[0]
    assert "-ar" in cmd
    assert "44100" in cmd
    assert "-ac" in cmd
    assert "1" in cmd
    assert "-b:a" in cmd
    assert "128k" in cmd
    assert "loudnorm" in cmd[cmd.index("-af") + 1]


def test_build_ffmpeg_cmd_fast_mode():
    cmd = build_ffmpeg_cmd(Path("/tmp/in.m4b"), Path("/tmp/out.mp3"), fast=True)
    assert "-af" not in cmd  # no loudnorm in fast mode
    assert "128k" in cmd


def test_is_mp3():
    assert is_mp3(Path("book.mp3")) is True
    assert is_mp3(Path("book.m4b")) is False
    assert is_mp3(Path("book.M4A")) is False
    assert is_mp3(Path("book.opus")) is False


@patch("subprocess.run")
def test_normalize_file_calls_ffmpeg(mock_run):
    mock_run.return_value = MagicMock(returncode=0)
    src = Path("/tmp/test.m4a")
    out = Path("/tmp/test_out.mp3")
    normalize_file(src, out, fast=False)
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert call_args[0] == "ffmpeg"
    assert str(src) in call_args
    assert str(out) in call_args


@patch("subprocess.run")
def test_normalize_file_raises_on_failure(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stderr="codec error")
    import pytest

    with pytest.raises(RuntimeError, match="ffmpeg"):
        normalize_file(Path("/tmp/in.mp3"), Path("/tmp/out.mp3"))
