"""Deduplication via content fingerprinting."""

import hashlib
import re
import unicodedata


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text.lower().strip())
    text = re.sub(r"[^\w\s]", "", text)  # remove punctuation
    text = re.sub(r"\s+", " ", text).strip()
    return text


def make_fingerprint(title: str, author: str, duration_hours: float) -> str:
    key = normalize_text(title) + "|" + normalize_text(author) + "|" + str(round(duration_hours))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()
