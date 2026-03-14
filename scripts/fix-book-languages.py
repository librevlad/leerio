"""
One-time migration: fix book languages in the database.

Run on VPS: python -m scripts.fix-book-languages
Or directly: python scripts/fix-book-languages.py
"""

import sqlite3
import os
import sys

# Books that should be EN (currently wrongly detected)
FORCE_EN = {
    188: "1984",
    183: "250 Job Interview Questions",
    184: "Brian Tracy",
    186: "David Horovitch",
    187: "Dune",
    189: "Harry Potter. Complete 7 Books",
    185: "How to Win Friends and Influence People",
    190: "Leadership",
    192: "Rich Dad Poor Dad",
    191: "The Tipping Point",
}

# Books wrongly classified as EN that should be RU
FORCE_RU_FROM_EN = {
    38: "Bullet Journal метод",
    123: "Mind Hacking",
    30: "Rework. Бизнес без предрассудков",
    1: "The War of Art",
    59: "Все успешные CEO делают это",
    45: "Дао Toyota",
    81: "Целеустремленность. Драйв BMW",
    82: "Цели. OKR",
}

# Books wrongly classified as UK that should be RU
FORCE_RU_FROM_UK = {
    29: "Как человек мыслит",
    145: "Шесть столпов самоуважения",
}

# All "Другое" (LibriVox) books are in Russian
# They'll be caught by the category-based update below


def main():
    db_path = os.environ.get("LEERIO_DATA", os.path.join(os.path.dirname(__file__), "..", "data"))
    db_file = os.path.join(db_path, "leerio.db")

    if not os.path.exists(db_file):
        print(f"Database not found: {db_file}")
        sys.exit(1)

    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row

    # 1. Fix wrongly-classified EN books → RU
    for book_id, title in FORCE_RU_FROM_EN.items():
        conn.execute("UPDATE books SET language = 'ru' WHERE id = ? AND language = 'en'", (book_id,))
        print(f"  EN→RU: [{book_id}] {title}")

    # 2. Fix wrongly-classified UK books → RU
    for book_id, title in FORCE_RU_FROM_UK.items():
        conn.execute("UPDATE books SET language = 'uk' WHERE id = ?", (book_id,))
        # Actually these ARE Russian books, not Ukrainian
        conn.execute("UPDATE books SET language = 'ru' WHERE id = ?", (book_id,))
        print(f"  UK→RU: [{book_id}] {title}")

    # 3. All "Другое" category books → RU (LibriVox Russian classics)
    result = conn.execute(
        "UPDATE books SET language = 'ru' WHERE category = 'Другое' AND (language IS NULL OR language = '' OR language != 'ru')"
    )
    print(f"  Другое→RU: {result.rowcount} books updated")

    # 4. Verify EN books are correct
    for book_id in FORCE_EN:
        conn.execute("UPDATE books SET language = 'en' WHERE id = ?", (book_id,))
    print(f"  Verified EN: {len(FORCE_EN)} books")

    # 5. Spanish language books
    conn.execute("UPDATE books SET language = 'es' WHERE title LIKE '%испанск%' OR title LIKE '%Испанск%'")
    es_count = conn.execute("SELECT COUNT(*) FROM books WHERE language = 'es'").fetchone()[0]
    if es_count:
        print(f"  Detected ES: {es_count} books")

    conn.commit()

    # Summary
    for lang in ['ru', 'en', 'uk', 'es']:
        count = conn.execute("SELECT COUNT(*) FROM books WHERE language = ?", (lang,)).fetchone()[0]
        print(f"  Total {lang}: {count}")

    null_count = conn.execute("SELECT COUNT(*) FROM books WHERE language IS NULL OR language = ''").fetchone()[0]
    if null_count:
        print(f"  WARNING: {null_count} books with no language!")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
