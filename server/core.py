"""
server/core.py — Business logic for the audiobook library.

Extracted from _library.py (lines 1-1085). No TUI dependencies (rich, InquirerPy).
"""

import calendar
import csv
import json
import os
import re
import shutil
import time as _time
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

import requests

# ── Path config (env-var based) ──────────────────────────────────────────────

BASE = Path(os.environ.get("LEERIO_BASE", str(Path(__file__).resolve().parent.parent)))
DATA_DIR = Path(os.environ.get("LEERIO_DATA", str(BASE / "data")))
BOOKS_DIR = Path(os.environ.get("LEERIO_BOOKS", str(BASE / "books")))

CONFIG_PATH = DATA_DIR / "config.json"
TRACKER_PATH = DATA_DIR / "tracker.csv"
RECOMMENDATIONS_PATH = DATA_DIR / "recommendations.md"
HISTORY_PATH = DATA_DIR / "history.json"
CACHE_PATH = DATA_DIR / "trello_cache.json"
NOTES_PATH = DATA_DIR / "notes.json"
TAGS_PATH = DATA_DIR / "tags.json"
COLLECTIONS_PATH = DATA_DIR / "collections.json"
PROGRESS_PATH = DATA_DIR / "progress.json"
PLAYBACK_PATH = DATA_DIR / "playback.json"
QUOTES_PATH = DATA_DIR / "quotes.json"
SESSIONS_PATH = DATA_DIR / "sessions.json"
USERS_DIR = DATA_DIR / "users"
BACKUP_DIR = BASE / "_backups"

CATEGORIES = ["Бизнес", "Отношения", "Саморазвитие", "Художественная", "Языки"]

LIST_TO_STATUS = {
    "Прочесть": "Не начато",
    "В телефоне": "В телефоне",
    "В процессе": "Слушаю",
    "На Паузе": "На паузе",
    "Прочитано": "Прочитано",
    "Скачать": "Скачать",
    "Забраковано": "Забраковано",
}
STATUS_STYLE = {
    "Прочесть": "white",
    "В телефоне": "blue",
    "В процессе": "magenta",
    "На Паузе": "yellow",
    "Прочитано": "green",
    "Скачать": "dim",
    "Забраковано": "red",
}

LABEL_TO_FOLDER = {
    "саморазвитие": "Саморазвитие",
    "бизнес": "Бизнес",
    "отношения": "Отношения",
    "художественная": "Художественная",
    "иностранный язык": "Языки",
    "здоровье": "Саморазвитие",
    "хобби": "Саморазвитие",
}
FOLDER_TO_LABEL = {
    "Саморазвитие": "саморазвитие",
    "Бизнес": "бизнес",
    "Отношения": "отношения",
    "Художественная": "художественная",
    "Языки": "иностранный язык",
}

# Fuzzy match thresholds
MATCH_EXACT = 0.85
MATCH_STRONG = 0.6
MATCH_LIKELY = 0.5
MATCH_WEAK = 0.4

HISTORY_LIMIT = 500

ACTION_STYLES = {
    "inbox": "cyan",
    "listen": "magenta",
    "phone": "blue",
    "done": "green",
    "pause": "yellow",
    "reject": "red",
    "relisten": "cyan",
    "move": "white",
    "undo": "dim",
    "delete": "red",
    "download": "dim",
    "bulk": "white",
}
ACTION_LABELS = {
    "inbox": "Добавлено",
    "listen": "Слушаю",
    "phone": "На телефон",
    "done": "Прослушано",
    "pause": "На паузе",
    "reject": "Забраковано",
    "relisten": "Снова слушаю",
    "move": "Перемещено",
    "undo": "Отменено",
    "delete": "Удалено",
    "bulk": "Массовое",
}

TRELLO_BOARD_URL = "https://trello.com/b/62d4e115/библиотека"


# ── Utilities ────────────────────────────────────────────────────────────────


def _load_json(path: Path, default_factory=dict):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default_factory()


def _format_stars(rating: int, total: int = 5) -> str:
    return chr(9733) * rating + chr(9734) * (total - rating)


def _progress_bar(pct: int, width: int = 20) -> str:
    filled = max(0, min(width, pct * width // 100))
    return chr(9608) * filled + chr(9617) * (width - filled)


def parse_folder_name(name: str):
    """Parse 'Автор - Название [Чтец]' and messy variations."""
    reader = None
    rest = name.strip()

    if rest.count("_") > 2:
        rest = rest.replace("_", " ")

    # Strip trailing tech: "- 2015(64kbts)", "(64kbps)", "_128"
    rest = re.sub(r"\s*[-–]\s*\d{4}\s*(\(\d+k\w*\))?\s*$", "", rest).strip()
    rest = re.sub(r"\s*\(\d+k\w*\)\s*$", "", rest).strip()
    rest = re.sub(r"_\d+$", "", rest).strip()

    # [Чтец]
    m = re.match(r"^(.+?)\s*\[(.+?)\]$", rest)
    if m:
        rest, reader = m.group(1).strip(), m.group(2).strip()
    else:
        # (Чтец) — only if looks like a name
        m = re.match(r"^(.+?)\s*\(([^()]+)\)$", rest)
        if m:
            candidate = m.group(2).strip()
            if re.search(r"[a-zA-Zа-яА-ЯёЁ]{2}", candidate):
                rest, reader = m.group(1).strip(), candidate
            else:
                rest = m.group(1).strip()

    # Clean reader metadata
    if reader:
        reader = re.split(r",\s*\d{4}", reader)[0].strip()
        reader = re.split(r",\s*\d+\s*k", reader, flags=re.IGNORECASE)[0].strip()
        reader = re.sub(r"\s*\d+kbt?s\b", "", reader, flags=re.IGNORECASE).strip()
        reader = re.sub(r"^ИИ\s+", "", reader).strip()
        reader = re.sub(r"^чит\.\s*", "", reader).strip()
        reader = reader.replace("_", " ").strip()

    # «Название» / "Название"
    m = re.match(r'^(.+?)\s*[«"](.+?)[»"]\s*$', rest)
    if m:
        return m.group(1).strip(), m.group(2).strip(), reader

    if " - " in rest:
        author, title = rest.split(" - ", 1)
    else:
        author, title = "", rest

    author = author.replace("_", " ").strip()
    title = title.replace("_", " ").strip()

    # (Reader) inside title
    if not reader:
        m = re.match(r"^(.+?)\s*\(([^()]+)\)$", title)
        if m and re.search(r"[a-zA-Zа-яА-ЯёЁ]{2}", m.group(2)):
            title, reader = m.group(1).strip(), m.group(2).strip()

    return author, title, reader


def normalize(text: str) -> str:
    if not text:
        return ""
    t = text.lower().strip()
    t = re.sub(r'[«»"\'()[\]{}.,!?:;–—\-_]', " ", t)
    return re.sub(r"\s+", " ", t).strip()


def fuzzy_match(a: str, b: str) -> float:
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def best_card_match(author: str, title: str, cards: list) -> tuple:
    best_score, best_card = 0.0, None
    full = f"{author} {title}".strip() if author else title
    for card in cards:
        cn = card["name"]
        s = max(fuzzy_match(full, cn), fuzzy_match(title, cn))
        if " - " in cn:
            ct = re.sub(r"\s*[\[(].*$", "", cn.split(" - ", 1)[1]).strip()
            s = max(s, fuzzy_match(title, ct))
        if s > best_score:
            best_score, best_card = s, card
    return best_card, best_score


def find_book_on_disk(card_name: str, all_books: list) -> dict | None:
    best, bs = None, 0.0
    ca, ct, _ = parse_folder_name(card_name)
    for b in all_books:
        s = max(
            fuzzy_match(card_name, b["folder"]),
            fuzzy_match(card_name, f"{b['author']} - {b['title']}"),
            fuzzy_match(ct, b["title"]) * 0.95 if ct else 0,
        )
        if s > bs:
            bs, best = s, b
    return best if bs >= MATCH_WEAK else None


def standardize_name(author: str, title: str, reader: str | None) -> str:
    parts = []
    if author:
        parts.append(f"{author} - ")
    parts.append(title)
    if reader:
        parts.append(f" [{reader}]")
    return "".join(parts)


def folder_size_mb(path: Path) -> float:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return total / (1024 * 1024)


def count_mp3(path: Path) -> int:
    return sum(1 for f in path.rglob("*.mp3"))


def estimate_duration_hours(path: Path) -> float | None:
    """Estimate audiobook duration in hours using mutagen (fast: reads headers only)."""
    try:
        from mutagen.mp3 import MP3
    except ImportError:
        return None
    total = 0.0
    for f in path.rglob("*.mp3"):
        try:
            total += MP3(str(f)).info.length
        except Exception:
            pass
    return total / 3600 if total > 0 else None


def fmt_duration(hours: float | None) -> str:
    if hours is None:
        return ""
    if hours < 1:
        return f"{hours * 60:.0f} мин"
    return f"{hours:.1f} ч"


# ── Atomic JSON write ────────────────────────────────────────────────────────


def _safe_json_write(path: Path, data, indent=1):
    import tempfile

    content = json.dumps(data, ensure_ascii=False, indent=indent)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ── History log ──────────────────────────────────────────────────────────────


def history_load() -> list[dict]:
    return _load_json(HISTORY_PATH, list)


def history_add(action: str, book: str, detail: str = "", rating: int = 0):
    log = history_load()
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "action": action,
        "book": book,
        "detail": detail,
    }
    if rating:
        entry["rating"] = rating
    log.append(entry)
    if len(log) > HISTORY_LIMIT:
        log = log[-HISTORY_LIMIT:]
    _safe_json_write(HISTORY_PATH, log)


# ── Trello cache ─────────────────────────────────────────────────────────────


def cache_save(lists: list, cards: list, labels: list):
    data = {"ts": datetime.now().isoformat(timespec="seconds"), "lists": lists, "cards": cards, "labels": labels}
    _safe_json_write(CACHE_PATH, data, indent=None)


def cache_load() -> dict | None:
    if not CACHE_PATH.exists():
        return None
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        # Cache valid for 24 hours
        ts = datetime.fromisoformat(data["ts"])
        if (datetime.now() - ts).total_seconds() < 86400:
            return data
    except Exception:
        pass
    return None


# ── Notes ────────────────────────────────────────────────────────────────────


def notes_load() -> dict[str, str]:
    return _load_json(NOTES_PATH, dict)


def notes_save(data: dict[str, str]):
    _safe_json_write(NOTES_PATH, data)


def note_get(title: str) -> str:
    data = notes_load()
    key = normalize(title)
    return data.get(key, "")


def note_set(title: str, text: str):
    data = notes_load()
    key = normalize(title)
    if text.strip():
        data[key] = text.strip()
    elif key in data:
        del data[key]
    notes_save(data)


# ── Tags ────────────────────────────────────────────────────────────────────


def tags_load() -> dict[str, list[str]]:
    return _load_json(TAGS_PATH, dict)


def tags_save(data: dict[str, list[str]]):
    _safe_json_write(TAGS_PATH, data)


def tags_get(title: str) -> list[str]:
    data = tags_load()
    return data.get(normalize(title), [])


def tags_set(title: str, tags: list[str]):
    data = tags_load()
    key = normalize(title)
    if tags:
        data[key] = [t.strip() for t in tags if t.strip()]
    elif key in data:
        del data[key]
    tags_save(data)


def tags_all() -> list[str]:
    """All unique tags across all books."""
    data = tags_load()
    s = set()
    for ts in data.values():
        s.update(ts)
    return sorted(s)


# ── Collections ─────────────────────────────────────────────────────────────


def collections_load() -> list[dict]:
    return _load_json(COLLECTIONS_PATH, list)


def collections_save(data: list[dict]):
    _safe_json_write(COLLECTIONS_PATH, data)


# ── Achievements ────────────────────────────────────────────────────────────


def compute_achievements(hist: list[dict], books: list[dict], notes_data: dict | None = None) -> list[dict]:
    """Calculate earned achievements/badges from history and library state."""
    badges = []
    done = [h for h in hist if h["action"] == "done"]

    # Pre-build O(1) lookup: normalized name -> book
    book_by_norm: dict[str, dict] = {}
    for b in books:
        book_by_norm[normalize(b["folder"])] = b
        book_by_norm[normalize(b["title"])] = b

    # Quantity milestones
    milestones = [
        (1, "Первая книга", "Прослушал первую аудиокнигу"),
        (5, "Разогрев", "5 книг прослушано"),
        (10, "Читатель", "10 книг прослушано"),
        (25, "Книжный червь", "25 книг прослушано"),
        (50, "Библиофил", "50 книг прослушано"),
        (100, "Легенда", "100 книг прослушано"),
    ]
    for threshold, name, desc in milestones:
        if len(done) >= threshold:
            badges.append({"icon": chr(127942), "name": name, "desc": desc})

    # Category diversity
    cats_done = set()
    for h in done:
        b = book_by_norm.get(normalize(h["book"]))
        if b:
            cats_done.add(b["category"])
    if len(cats_done) >= len(CATEGORIES):
        badges.append({"icon": chr(127752), "name": "Всесторонний", "desc": "Книги во всех 5 категориях"})

    # Rating badges
    rated = [h for h in done if h.get("rating")]
    fives = [h for h in rated if h["rating"] == 5]
    if rated:
        badges.append({"icon": chr(11088), "name": "Критик", "desc": f"Оценил {len(rated)} книг"})
    if len(fives) >= 3:
        badges.append({"icon": chr(128142), "name": "Знаток шедевров", "desc": f"{len(fives)} книг на 5 звёзд"})

    # Streak calculation
    months = set()
    for h in done:
        months.add(h["ts"][:7])
    sorted_months = sorted(months)
    streak, max_streak = 1, 1
    for i in range(1, len(sorted_months)):
        y1, m1 = map(int, sorted_months[i].split("-"))
        y0, m0 = map(int, sorted_months[i - 1].split("-"))
        if (y1 * 12 + m1) - (y0 * 12 + m0) == 1:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 1
    if max_streak >= 3:
        badges.append({"icon": chr(128293), "name": "Стрик 3+", "desc": f"Рекорд: {max_streak} мес. подряд"})
    if max_streak >= 6:
        badges.append({"icon": chr(128293), "name": "Полугодие", "desc": "6+ месяцев подряд"})
    if max_streak >= 12:
        badges.append({"icon": chr(128081), "name": "Год без пауз", "desc": "12 месяцев подряд"})

    # Speed: best month
    if len(done) >= 3:
        monthly = Counter()
        for h in done:
            monthly[h["ts"][:7]] += 1
        best_month = monthly.most_common(1)[0]
        if best_month[1] >= 3:
            badges.append(
                {
                    "icon": chr(9889),
                    "name": "Марафонец",
                    "desc": f"Лучший месяц: {best_month[1]} книг ({best_month[0]})",
                }
            )

    # Library size
    if len(books) >= 100:
        badges.append({"icon": chr(128218), "name": "Коллекционер", "desc": f"{len(books)} книг в библиотеке"})
    if len(books) >= 200:
        badges.append({"icon": chr(127963), "name": "Библиотекарь", "desc": f"{len(books)}+ книг"})

    # Inbox speed
    inbox = [h for h in hist if h["action"] == "inbox"]
    if len(inbox) >= 10:
        badges.append({"icon": chr(128230), "name": "Сортировщик", "desc": f"Разобрал {len(inbox)} книг из dl/"})

    # Notes
    _notes = notes_data if notes_data is not None else notes_load()
    notes_count = len([v for v in _notes.values() if v.strip()])
    if notes_count >= 5:
        badges.append({"icon": chr(128221), "name": "Летописец", "desc": f"{notes_count} заметок"})

    return badges


def reading_velocity(hist: list[dict]) -> dict:
    """Calculate reading pace and predictions."""
    done = [h for h in hist if h["action"] == "done"]
    if not done:
        return {"total": 0}

    dates = sorted(datetime.fromisoformat(h["ts"]) for h in done)
    first, last = dates[0], dates[-1]
    span_days = max((last - first).days, 1)
    span_months = max(span_days / 30.44, 1)

    # Per-month breakdown
    monthly = Counter()
    for h in done:
        monthly[h["ts"][:7]] += 1

    avg_per_month = len(done) / span_months
    best_month_key = monthly.most_common(1)[0][0] if monthly else ""
    best_month_val = monthly.most_common(1)[0][1] if monthly else 0

    # Current year
    year = str(datetime.now().year)
    this_year = sum(1 for h in done if h["ts"].startswith(year))

    # Last 90 days
    cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    recent = sum(1 for d in dates if (cutoff - d).days <= 90)
    recent_pace = recent / 3

    return {
        "total": len(done),
        "span_days": span_days,
        "avg_per_month": avg_per_month,
        "best_month": best_month_key,
        "best_month_count": best_month_val,
        "this_year": this_year,
        "recent_90d": recent,
        "recent_pace": recent_pace,
    }


# ── Progress tracking ──────────────────────────────────────────────────────


def progress_load() -> dict[str, dict]:
    return _load_json(PROGRESS_PATH, dict)


def progress_save(data: dict[str, dict]):
    _safe_json_write(PROGRESS_PATH, data)


def progress_get(title: str) -> int:
    data = progress_load()
    entry = data.get(normalize(title), {})
    return entry.get("pct", 0)


def progress_set(title: str, pct: int, note: str = ""):
    data = progress_load()
    key = normalize(title)
    data[key] = {
        "pct": max(0, min(100, pct)),
        "updated": datetime.now().isoformat(timespec="seconds"),
        "note": note,
    }
    progress_save(data)


# ── Playback position ─────────────────────────────────────────────────────


def playback_load() -> dict:
    return _load_json(PLAYBACK_PATH, dict)


def playback_save(data: dict):
    _safe_json_write(PLAYBACK_PATH, data)


def playback_get(book_id: str) -> dict | None:
    data = playback_load()
    return data.get(book_id)


def playback_set(book_id: str, track_index: int, position: float, filename: str = ""):
    data = playback_load()
    data[book_id] = {
        "track_index": track_index,
        "position": position,
        "filename": filename,
        "updated": datetime.now().isoformat(timespec="seconds"),
    }
    playback_save(data)


# ── Quotes ──────────────────────────────────────────────────────────────────


def quotes_load() -> list[dict]:
    return _load_json(QUOTES_PATH, list)


def quotes_save(data: list[dict]):
    _safe_json_write(QUOTES_PATH, data)


def quotes_add(text: str, book: str, author: str = ""):
    data = quotes_load()
    data.append(
        {
            "text": text.strip(),
            "book": book,
            "author": author,
            "ts": datetime.now().isoformat(timespec="seconds"),
        }
    )
    quotes_save(data)


# ── Sessions ───────────────────────────────────────────────────────────────


def sessions_load() -> list[dict]:
    return _load_json(SESSIONS_PATH, list)


def sessions_save(data: list[dict]):
    _safe_json_write(SESSIONS_PATH, data)


def session_start(book: str) -> dict:
    data = sessions_load()
    entry = {
        "book": book,
        "start": datetime.now().isoformat(timespec="seconds"),
        "end": None,
        "minutes": 0,
    }
    data.append(entry)
    sessions_save(data)
    return entry


def session_stop(book: str) -> int:
    data = sessions_load()
    for s in reversed(data):
        if s["book"] == book and s["end"] is None:
            s["end"] = datetime.now().isoformat(timespec="seconds")
            start = datetime.fromisoformat(s["start"])
            s["minutes"] = int((datetime.now() - start).total_seconds() / 60)
            sessions_save(data)
            return s["minutes"]
    return 0


def session_stats(days: int = 7) -> dict:
    data = sessions_load()
    cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total_min = 0
    today_min = 0
    week_min = 0
    by_hour = Counter()
    for s in data:
        if not s.get("end"):
            continue
        mins = s.get("minutes", 0)
        total_min += mins
        start = datetime.fromisoformat(s["start"])
        if (cutoff - start).days == 0:
            today_min += mins
        if (cutoff - start).days < days:
            week_min += mins
        by_hour[start.hour] += mins
    peak_hour = by_hour.most_common(1)[0][0] if by_hour else None
    return {
        "total_hours": total_min / 60,
        "today_min": today_min,
        "week_hours": week_min / 60,
        "peak_hour": peak_hour,
    }


# ── Similar books engine ────────────────────────────────────────────────────


def find_similar(
    target_book: dict, all_books: list[dict], hist: list[dict], top_n: int = 5
) -> list[tuple[dict, float]]:
    """Find books similar to target based on category, author, tags, and ratings."""
    scored = []
    book_ratings = {}
    for h in hist:
        if h["action"] == "done" and h.get("rating"):
            book_ratings[normalize(h["book"])] = h["rating"]

    done_books = {normalize(h["book"]) for h in hist if h["action"] == "done"}

    target_cat = target_book.get("category", "")
    target_author = target_book.get("author", "").lower()
    target_tags = set(tags_get(target_book.get("title", "")))
    target_rating = book_ratings.get(normalize(target_book.get("folder", "")), 0)

    for b in all_books:
        if b["path"] == target_book.get("path"):
            continue
        score = 0.0
        if b["category"] == target_cat:
            score += 25
        ba = b["author"].lower()
        if ba and target_author and (ba == target_author or fuzzy_match(ba, target_author) > MATCH_STRONG):
            score += 40
        btags = set(tags_get(b["title"]))
        shared = target_tags & btags
        if shared:
            score += len(shared) * 15
        br = book_ratings.get(normalize(b["folder"]), 0)
        if br and target_rating and br >= 4 and target_rating >= 4:
            score += 15
        if normalize(b["folder"]) in done_books:
            score -= 30
        if score > 0:
            scored.append((b, score))

    scored.sort(key=lambda x: -x[1])
    return scored[:top_n]


# ── Heatmap / sparkline helpers ─────────────────────────────────────────────

SPARKLINE_CHARS = " " + chr(9601) + chr(9602) + chr(9603) + chr(9604) + chr(9605) + chr(9606) + chr(9607) + chr(9608)


def sparkline(values: list[int], width: int = 12) -> str:
    if not values:
        return ""
    mx = max(values) or 1
    return "".join(SPARKLINE_CHARS[min(int(v / mx * 8), 8)] for v in values[-width:])


def calendar_heatmap(done_entries: list[dict], months: int = 6, all_hist: list[dict] | None = None) -> list[str]:
    """Generate a text-based calendar heatmap of listening activity."""
    now = datetime.now()
    lines = []
    day_counts: dict[str, int] = Counter()
    for h in done_entries:
        day_counts[h["ts"][:10]] += 1

    hist = all_hist if all_hist is not None else history_load()
    for h in hist:
        if h["action"] in ("listen", "phone", "done"):
            day_counts[h["ts"][:10]] = day_counts.get(h["ts"][:10], 0) + 1

    intensity = [" ", chr(9617), chr(9618), chr(9619), chr(9608)]

    for m_offset in range(months - 1, -1, -1):
        month = now.month - m_offset
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        label = f"{year}-{month:02d}"
        days_in_month = calendar.monthrange(year, month)[1]
        cells = []
        for d in range(1, days_in_month + 1):
            key = f"{year}-{month:02d}-{d:02d}"
            n = day_counts.get(key, 0)
            idx = min(n, 4) if n > 0 else 0
            cells.append(intensity[idx])
        lines.append(f"  [dim]{label}[/dim] [cyan]{''.join(cells)}[/cyan]")

    return lines


# ── Category inference ────────────────────────────────────────────────────────


class CategoryInferrer:
    def __init__(self, library: "Library"):
        self._author_map: dict[str, str] = {}
        for book in library.find_all_books():
            a = book["author"].strip().lower()
            if a:
                self._author_map[a] = book["category"]
                parts = a.split()
                if len(parts) >= 2:
                    self._author_map[parts[-1]] = book["category"]
        self._rec_map: list[tuple[str, str, str]] = []
        self._parse_recommendations()

    def _parse_recommendations(self):
        if not RECOMMENDATIONS_PATH.exists():
            return
        text = RECOMMENDATIONS_PATH.read_text(encoding="utf-8")
        section_map = {
            "Привычки и продуктивность": "Саморазвитие",
            "Мышление и психология": "Саморазвитие",
            "Мотивация и дисциплина": "Саморазвитие",
            "Коммуникация и влияние": "Саморазвитие",
            "Здоровье": "Саморазвитие",
            "Деньги и финансы": "Бизнес",
            "Стоицизм и философия": "Саморазвитие",
            "Психология и отношения": "Саморазвитие",
            "Биографии и истории": "Бизнес",
            "Смысл": "Саморазвитие",
        }
        current_cat = None
        for line in text.split("\n"):
            if line.startswith("## "):
                for key, cat in section_map.items():
                    if key.lower() in line.lower():
                        current_cat = cat
                        break
            if current_cat and "|" in line:
                cols = [c.strip() for c in line.split("|")]
                if len(cols) >= 4:
                    author = re.sub(r"^[\d\-\s]+", "", cols[2]).strip()
                    title = cols[3].strip()
                    if author and title and not author.startswith("---"):
                        self._rec_map.append((author.lower(), title.lower(), current_cat))

    def infer(self, author: str, title: str, trello_category: str | None = None) -> str | None:
        if trello_category:
            return trello_category
        a_low = author.strip().lower()
        t_low = title.strip().lower()
        if a_low in self._author_map:
            return self._author_map[a_low]
        parts = a_low.split()
        if parts and parts[-1] in self._author_map:
            return self._author_map[parts[-1]]
        for ra, rt, cat in self._rec_map:
            if t_low and rt and (fuzzy_match(t_low, rt) > MATCH_STRONG or (a_low and ra in a_low)):
                return cat
        if title and not re.search(r"[а-яёА-ЯЁ]", title):
            return "Языки"
        return None


# ── Recommendations parser ────────────────────────────────────────────────────


def parse_recommendations() -> list[dict]:
    """Parse recommendations.md into structured list with priorities."""
    if not RECOMMENDATIONS_PATH.exists():
        return []
    text = RECOMMENDATIONS_PATH.read_text(encoding="utf-8")
    recs = []
    section = ""
    for line in text.split("\n"):
        if line.startswith("## "):
            section = re.sub(r"^##\s*\d+\.\s*", "", line).strip()
        if "|" not in line or line.startswith("|---") or line.startswith("| #"):
            continue
        cols = [c.strip() for c in line.split("|")]
        if len(cols) < 5:
            continue
        author_raw = cols[2].strip()
        m = re.match(r"^([12\-])\s*(.+)$", author_raw)
        if m:
            priority, author = m.group(1), m.group(2).strip()
        else:
            priority, author = "-", author_raw
        title = cols[3].strip()
        if not author or not title or author.startswith("---") or author == "Автор":
            continue
        recs.append(
            {
                "author": author,
                "title": title,
                "priority": priority,
                "section": section,
            }
        )
    return recs


# ── TrelloClient ──────────────────────────────────────────────────────────────


class TrelloClient:
    API = "https://api.trello.com/1"

    def __init__(self, api_key: str, token: str, board_id: str):
        self.api_key, self.token, self.board_id = api_key, token, board_id
        self._lists = self._labels = self._cards = None

    def _p(self, extra=None):
        p = {"key": self.api_key, "token": self.token}
        if extra:
            p.update(extra)
        return p

    def _get(self, path, params=None):
        r = requests.get(f"{self.API}{path}", params=self._p(params), timeout=15)
        r.raise_for_status()
        return r.json()

    def _post(self, path, params=None):
        r = requests.post(f"{self.API}{path}", params=self._p(params), timeout=15)
        r.raise_for_status()
        return r.json()

    def _put(self, path, params=None):
        r = requests.put(f"{self.API}{path}", params=self._p(params), timeout=15)
        r.raise_for_status()
        return r.json()

    def _delete(self, path, params=None):
        r = requests.delete(f"{self.API}{path}", params=self._p(params), timeout=15)
        r.raise_for_status()

    def get_lists(self, force=False):
        if self._lists is None or force:
            self._lists = self._get(f"/boards/{self.board_id}/lists")
        return self._lists

    def get_labels(self, force=False):
        if self._labels is None or force:
            self._labels = self._get(f"/boards/{self.board_id}/labels")
        return self._labels

    def get_cards(self, force=False):
        if self._cards is None or force:
            self._cards = self._get(
                f"/boards/{self.board_id}/cards", {"fields": "name,idList,idLabels,desc,closed", "filter": "open"}
            )
        return self._cards

    def save_cache(self):
        try:
            cache_save(self.get_lists(), self.get_cards(), self.get_labels())
        except Exception:
            pass

    def load_from_cache(self) -> bool:
        data = cache_load()
        if data:
            self._lists = data["lists"]
            self._cards = data["cards"]
            self._labels = data["labels"]
            return True
        return False

    def list_id(self, name):
        return next((l["id"] for l in self.get_lists() if l["name"] == name), None)

    def list_name(self, lid):
        return next((l["name"] for l in self.get_lists() if l["id"] == lid), "?")

    def label_id(self, name):
        return next((l["id"] for l in self.get_labels() if l.get("name", "").lower() == name.lower()), None)

    def label_names(self, card):
        m = {l["id"]: l.get("name", "") for l in self.get_labels()}
        return [m.get(i, "") for i in card.get("idLabels", [])]

    def category(self, card):
        for n in self.label_names(card):
            f = LABEL_TO_FOLDER.get(n.lower())
            if f:
                return f
        return None

    def move_card(self, cid, list_name):
        lid = self.list_id(list_name)
        if lid:
            self._put(f"/cards/{cid}/idList", {"value": lid})
            if self._cards:
                for c in self._cards:
                    if c["id"] == cid:
                        c["idList"] = lid
                        break

    def create_card(self, name, list_name, label=None, desc=""):
        p = {"name": name, "idList": self.list_id(list_name), "pos": "bottom"}
        if desc:
            p["desc"] = desc
        c = self._post("/cards", p)
        if label:
            lid = self.label_id(label)
            if lid:
                self._post(f"/cards/{c['id']}/idLabels", {"value": lid})
        return c

    def update_name(self, cid, name):
        self._put(f"/cards/{cid}", {"name": name})

    def add_label(self, cid, label):
        lid = self.label_id(label)
        if lid:
            self._post(f"/cards/{cid}/idLabels", {"value": lid})

    def set_desc(self, cid, desc):
        self._put(f"/cards/{cid}", {"desc": desc})

    def archive_card(self, cid):
        self._put(f"/cards/{cid}", {"closed": "true"})

    def reload(self):
        self._lists = self._labels = self._cards = None


# ── Library ───────────────────────────────────────────────────────────────────


class Library:
    def __init__(self):
        self.base = BOOKS_DIR
        self._books_cache: list[dict] | None = None
        self._cache_ts: float = 0

    def find_all_books(self) -> list[dict]:
        now = _time.time()
        if self._books_cache is not None and now - self._cache_ts < 5:
            return self._books_cache
        books = []
        for cat in CATEGORIES:
            p = self.base / cat
            if not p.exists():
                continue
            for d in sorted(p.iterdir()):
                if d.is_dir() and not d.name.startswith("_"):
                    a, t, r = parse_folder_name(d.name)
                    books.append({"path": d, "folder": d.name, "category": cat, "author": a, "title": t, "reader": r})
        self._books_cache = books
        self._cache_ts = now
        return books

    def invalidate_cache(self):
        self._books_cache = None

    def count_by_category(self):
        return {
            cat: sum(1 for d in (self.base / cat).iterdir() if d.is_dir() and not d.name.startswith("_"))
            if (self.base / cat).exists()
            else 0
            for cat in CATEGORIES
        }

    def move_to_category(self, src, category, new_name=None):
        dest_dir = self.base / category
        dest_dir.mkdir(exist_ok=True)
        dest = dest_dir / (new_name or src.name)
        if dest.exists():
            return dest
        shutil.move(str(src), str(dest))
        self.invalidate_cache()
        return dest

    def rename_book(self, old_path: Path, new_name: str) -> Path:
        new_path = old_path.parent / new_name
        if new_path == old_path or new_path.exists():
            return old_path
        old_path.rename(new_path)
        self.invalidate_cache()
        return new_path

    def load_tracker(self):
        if not TRACKER_PATH.exists():
            return []
        with open(TRACKER_PATH, encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    def save_tracker(self, rows):
        if not rows:
            return
        if TRACKER_PATH.exists():
            bak = TRACKER_PATH.with_suffix(".csv.bak")
            try:
                shutil.copy2(TRACKER_PATH, bak)
            except Exception:
                pass
        fields = ["Автор", "Название", "Чтец", "Категория", "Статус"]
        with open(TRACKER_PATH, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in fields})


# ── Per-user data ─────────────────────────────────────────────────────────────

BOOK_STATUSES = ["want_to_read", "reading", "paused", "done", "rejected"]


class UserData:
    """Per-user data access — reads/writes from data/users/{user_id}/."""

    _FILE_NAMES = [
        "history",
        "notes",
        "tags",
        "collections",
        "progress",
        "playback",
        "quotes",
        "sessions",
        "book_status",
    ]

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.dir = USERS_DIR / user_id
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self.dir / f"{name}.json"

    def _load(self, name: str, default_factory=dict):
        return _load_json(self._path(name), default_factory)

    def _save(self, name: str, data):
        _safe_json_write(self._path(name), data)

    # ── History ──
    def history_load(self) -> list[dict]:
        return self._load("history", list)

    def history_add(self, action: str, book: str, detail: str = "", rating: int = 0):
        log = self.history_load()
        entry = {"ts": datetime.now().isoformat(timespec="seconds"), "action": action, "book": book, "detail": detail}
        if rating:
            entry["rating"] = rating
        log.append(entry)
        if len(log) > HISTORY_LIMIT:
            log = log[-HISTORY_LIMIT:]
        self._save("history", log)

    # ── Notes ──
    def notes_load(self) -> dict[str, str]:
        return self._load("notes", dict)

    def note_get(self, title: str) -> str:
        return self.notes_load().get(normalize(title), "")

    def note_set(self, title: str, text: str):
        data = self.notes_load()
        key = normalize(title)
        if text.strip():
            data[key] = text.strip()
        elif key in data:
            del data[key]
        self._save("notes", data)

    # ── Tags ──
    def tags_load(self) -> dict[str, list[str]]:
        return self._load("tags", dict)

    def tags_get(self, title: str) -> list[str]:
        return self.tags_load().get(normalize(title), [])

    def tags_set(self, title: str, tags: list[str]):
        data = self.tags_load()
        key = normalize(title)
        if tags:
            data[key] = [t.strip() for t in tags if t.strip()]
        elif key in data:
            del data[key]
        self._save("tags", data)

    def tags_all(self) -> list[str]:
        data = self.tags_load()
        s = set()
        for ts in data.values():
            s.update(ts)
        return sorted(s)

    # ── Collections ──
    def collections_load(self) -> list[dict]:
        return self._load("collections", list)

    def collections_save(self, data: list[dict]):
        self._save("collections", data)

    # ── Progress ──
    def progress_load(self) -> dict[str, dict]:
        return self._load("progress", dict)

    def progress_get(self, title: str) -> int:
        entry = self.progress_load().get(normalize(title), {})
        return entry.get("pct", 0)

    def progress_set(self, title: str, pct: int, note: str = ""):
        data = self.progress_load()
        data[normalize(title)] = {
            "pct": max(0, min(100, pct)),
            "updated": datetime.now().isoformat(timespec="seconds"),
            "note": note,
        }
        self._save("progress", data)

    # ── Playback ──
    def playback_get(self, book_id: str) -> dict | None:
        return self._load("playback", dict).get(book_id)

    def playback_set(self, book_id: str, track_index: int, position: float, filename: str = ""):
        data = self._load("playback", dict)
        data[book_id] = {
            "track_index": track_index,
            "position": position,
            "filename": filename,
            "updated": datetime.now().isoformat(timespec="seconds"),
        }
        self._save("playback", data)

    # ── Quotes ──
    def quotes_load(self) -> list[dict]:
        return self._load("quotes", list)

    def quotes_save(self, data: list[dict]):
        self._save("quotes", data)

    def quotes_add(self, text: str, book: str, author: str = ""):
        data = self.quotes_load()
        data.append(
            {"text": text.strip(), "book": book, "author": author, "ts": datetime.now().isoformat(timespec="seconds")}
        )
        self.quotes_save(data)

    # ── Sessions ──
    def sessions_load(self) -> list[dict]:
        return self._load("sessions", list)

    def session_start(self, book: str) -> dict:
        data = self.sessions_load()
        entry = {"book": book, "start": datetime.now().isoformat(timespec="seconds"), "end": None, "minutes": 0}
        data.append(entry)
        self._save("sessions", data)
        return entry

    def session_stop(self, book: str) -> int:
        data = self.sessions_load()
        for s in reversed(data):
            if s["book"] == book and s["end"] is None:
                s["end"] = datetime.now().isoformat(timespec="seconds")
                start = datetime.fromisoformat(s["start"])
                s["minutes"] = int((datetime.now() - start).total_seconds() / 60)
                self._save("sessions", data)
                return s["minutes"]
        return 0

    def session_stats(self, days: int = 7) -> dict:
        data = self.sessions_load()
        cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        total_min = today_min = week_min = 0
        by_hour: dict[int, int] = {}
        for s in data:
            if not s.get("end"):
                continue
            mins = s.get("minutes", 0)
            total_min += mins
            start = datetime.fromisoformat(s["start"])
            if (cutoff - start).days == 0:
                today_min += mins
            if (cutoff - start).days < days:
                week_min += mins
            by_hour[start.hour] = by_hour.get(start.hour, 0) + mins
        peak_hour = max(by_hour, key=by_hour.get, default=None) if by_hour else None
        return {
            "total_hours": total_min / 60,
            "today_min": today_min,
            "week_hours": week_min / 60,
            "peak_hour": peak_hour,
        }

    # ── Book Status ──
    def book_status_load(self) -> dict[str, dict]:
        return self._load("book_status", dict)

    def book_status_get(self, book_id: str) -> dict | None:
        return self.book_status_load().get(book_id)

    def book_status_set(self, book_id: str, status: str):
        if status not in BOOK_STATUSES:
            return
        data = self.book_status_load()
        data[book_id] = {"status": status, "updated": datetime.now().isoformat(timespec="seconds")}
        self._save("book_status", data)

    def book_status_remove(self, book_id: str):
        data = self.book_status_load()
        if book_id in data:
            del data[book_id]
            self._save("book_status", data)


# ── Config ───────────────────────────────────────────────────────────────────


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(
                {
                    "trello_api_key": "",
                    "trello_token": "",
                    "board_id": "62d4e11502252b7a4dc11d7f",
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def connect_trello(config) -> TrelloClient | None:
    """Connect to Trello (headless, no TUI output)."""
    key, tok = config.get("trello_api_key", ""), config.get("trello_token", "")
    bid = config.get("board_id", "62d4e11502252b7a4dc11d7f")
    if not (key and tok):
        return None
    t = TrelloClient(key, tok, bid)
    try:
        t.get_lists()
        t.get_cards()
        t.get_labels()
        t.save_cache()
        return t
    except Exception:
        if t.load_from_cache():
            return t
        return None
