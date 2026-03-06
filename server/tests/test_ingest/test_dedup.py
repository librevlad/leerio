"""Tests for deduplication fingerprinting."""
from server.ingest.dedup import make_fingerprint, normalize_text


def test_normalize_text():
    assert normalize_text("  Hello, World!  ") == "hello world"
    assert normalize_text("Стивен Кинг") == "стивен кинг"
    assert normalize_text("Author's Name.") == "authors name"


def test_fingerprint_deterministic():
    fp1 = make_fingerprint("Зелёная миля", "Стивен Кинг", 12.3)
    fp2 = make_fingerprint("Зелёная миля", "Стивен Кинг", 12.3)
    assert fp1 == fp2


def test_fingerprint_includes_duration():
    fp1 = make_fingerprint("Same Title", "Same Author", 5.0)
    fp2 = make_fingerprint("Same Title", "Same Author", 10.0)
    assert fp1 != fp2


def test_fingerprint_case_insensitive():
    fp1 = make_fingerprint("THE BOOK", "AUTHOR", 5.0)
    fp2 = make_fingerprint("the book", "author", 5.0)
    assert fp1 == fp2


def test_fingerprint_ignores_punctuation():
    fp1 = make_fingerprint("Hello, World!", "Author's Name.", 3.0)
    fp2 = make_fingerprint("Hello World", "Authors Name", 3.0)
    assert fp1 == fp2
