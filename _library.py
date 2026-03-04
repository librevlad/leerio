#!/usr/bin/env python3
"""
_library.py — TUI for managing the audiobook library with Trello sync.

Business logic lives in server/core.py; this file is the local TUI wrapper.

Run:
  python _library.py              — interactive menu
  python _library.py sync         — sync and exit
  python _library.py status       — show status and exit
  python _library.py stats        — library stats

Dependencies: pip install rich InquirerPy requests
"""

import json
import os
import random
import re
import shutil
import subprocess
import sys
import webbrowser
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# Ensure server package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from server.core import (
    # Paths
    BASE, BOOKS_DIR, DATA_DIR,
    CONFIG_PATH, TRACKER_PATH, RECOMMENDATIONS_PATH,
    HISTORY_PATH, CACHE_PATH, NOTES_PATH, TAGS_PATH,
    COLLECTIONS_PATH, PROGRESS_PATH, PLAYBACK_PATH,
    QUOTES_PATH, SESSIONS_PATH, BACKUP_DIR,
    # Constants
    CATEGORIES, LIST_TO_STATUS, STATUS_STYLE,
    LABEL_TO_FOLDER, FOLDER_TO_LABEL,
    MATCH_EXACT, MATCH_STRONG, MATCH_LIKELY, MATCH_WEAK,
    HISTORY_LIMIT, ACTION_STYLES, ACTION_LABELS,
    TRELLO_BOARD_URL,
    SPARKLINE_CHARS,
    # Utilities
    _load_json, _format_stars, _progress_bar,
    parse_folder_name, normalize, fuzzy_match,
    best_card_match, find_book_on_disk,
    standardize_name, folder_size_mb, count_mp3,
    estimate_duration_hours, fmt_duration,
    _safe_json_write,
    # Data persistence
    history_load, history_add,
    cache_save, cache_load,
    notes_load, notes_save, note_get, note_set,
    tags_load, tags_save, tags_get, tags_set, tags_all,
    collections_load, collections_save,
    compute_achievements, reading_velocity,
    progress_load, progress_save, progress_get, progress_set,
    playback_load, playback_save, playback_get, playback_set,
    quotes_load, quotes_save, quotes_add,
    sessions_load, sessions_save, session_start, session_stop, session_stats,
    find_similar,
    sparkline, calendar_heatmap,
    # Classes
    CategoryInferrer, parse_recommendations,
    TrelloClient, Library,
    # Config
    load_config,
)

import requests
from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

# ── TUI-only constants ───────────────────────────────────────────────────────

METADATA_SCRIPT = BASE / "server" / "metadata.py"
DL_DIR = BASE / "dl"

console = Console()


# Add find_dl_books back for TUI compatibility (dl/ may or may not exist)
def _find_dl_books(self) -> list[dict]:
    if not DL_DIR.exists(): return []
    books = []
    for d in sorted(DL_DIR.iterdir()):
        if d.is_dir() and not d.name.startswith("."):
            a, t, r = parse_folder_name(d.name)
            books.append({"path": d, "folder": d.name,
                          "author": a, "title": t, "reader": r})
    return books

Library.find_dl_books = _find_dl_books


# ── TUI-only utilities ───────────────────────────────────────────────────────

def clipboard_copy(text: str):
    try:
        subprocess.run("clip", input=text.encode("utf-16-le"), check=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception:
        pass


def open_in_explorer(path: Path):
    try:
        os.startfile(str(path))
    except Exception:
        pass


def connect_trello(config):
    """Connect to Trello with TUI output."""
    key, tok = config.get("trello_api_key", ""), config.get("trello_token", "")
    bid = config.get("board_id", "62d4e11502252b7a4dc11d7f")
    if not (key and tok):
        console.print(Panel(
            "[bold yellow]Trello не настроен[/bold yellow]\n\n"
            "1. Откройте https://trello.com/app-key\n"
            "2. Скопируйте [bold]API Key[/bold]\n"
            "3. Нажмите ссылку [bold]Token[/bold] -> авторизуйте -> скопируйте\n"
            "4. Вставьте в [cyan]data/config.json[/cyan]\n\n"
            "[dim]API Secret НЕ нужен, нужен именно Token[/dim]",
            title="Настройка", border_style="yellow"))
        return None
    t = TrelloClient(key, tok, bid)
    try:
        with console.status("[dim]Trello..."):
            t.get_lists(); t.get_cards(); t.get_labels()
        t.save_cache()
        console.print("[green]Trello: ok[/green]")
        return t
    except Exception as e:
        console.print(f"[red]Trello API: {e}[/red]")
        if t.load_from_cache():
            console.print("[yellow]Trello: из кеша (оффлайн)[/yellow]")
            return t
        console.print("[red]Нет кеша. Работаем без Trello.[/red]")
        return None


# ── TUI ───────────────────────────────────────────────────────────────────────

class TUI:
    def __init__(self, lib: Library, trello: TrelloClient | None):
        self.lib = lib
        self.trello = trello
        self._inf: CategoryInferrer | None = None
        self._books_cache: list[dict] | None = None
        self._history_cache: list[dict] | None = None

    @property
    def inf(self):
        if not self._inf: self._inf = CategoryInferrer(self.lib)
        return self._inf

    def _books(self, force=False) -> list[dict]:
        """Cached find_all_books — invalidated by inbox/move/rename/cleanup."""
        if self._books_cache is None or force:
            self._books_cache = self.lib.find_all_books()
        return self._books_cache

    def _invalidate(self):
        """Call after disk operations that change book locations."""
        self._books_cache = None
        self._inf = None

    def _history(self, force=False) -> list[dict]:
        if self._history_cache is None or force:
            self._history_cache = history_load()
        return self._history_cache

    def _history_add(self, action, book, detail="", rating=0):
        history_add(action, book, detail, rating)
        self._history_cache = None  # invalidate

    def _book_ratings(self) -> dict[str, int]:
        return {normalize(h["book"]): h["rating"]
                for h in self._history() if h["action"] == "done" and h.get("rating")}

    def _select_card(self, list_names, message, multiselect=False):
        if not self._ok():
            return [] if multiselect else None
        names = [list_names] if isinstance(list_names, str) else list(list_names)
        cards = self._cards_in(*names)
        if not cards:
            console.print("\n[dim]Нет книг.[/dim]")
            return [] if multiselect else None
        lm = self._lmap()
        choices = [Choice(c, name=f"[{lm.get(c['idList'],'')}] {c['name']}")
                   for c in sorted(cards, key=lambda c: c["name"])]
        return inquirer.fuzzy(message=message, max_height="70%",
                              multiselect=multiselect, choices=choices).execute()

    def _select_book(self, message, multiselect=False):
        books = self._books()
        choices = [Choice(b, name=f"{b['author']} - {b['title']}" if b["author"] else b["title"])
                   for b in books]
        if not choices:
            console.print("\n[dim]Нет книг.[/dim]")
            return [] if multiselect else None
        return inquirer.fuzzy(message=message, max_height="70%",
                              multiselect=multiselect, choices=choices).execute()

    def _move_with_history(self, card, target_list, action, detail="", rating=0, sync=True):
        self.trello.move_card(card["id"], target_list)
        self._history_add(action, card["name"], detail, rating)
        if sync:
            self._sync_csv()

    def _smart_insights(self) -> list[str]:
        """Generate smart notifications for _header and screen_status."""
        insights = []
        hist = self._history()
        if not hist:
            return insights
        now = datetime.now()
        # Days since last activity
        last_ts = max((datetime.fromisoformat(h["ts"]) for h in hist), default=now)
        days_idle = (now - last_ts).days
        if days_idle >= 7:
            insights.append(f"[yellow]Нет активности {days_idle} дней — послушай![/yellow]")
        # Streak check
        year = str(now.year)
        month = f"{now.year}-{now.month:02d}"
        done_this_month = sum(1 for h in hist if h["action"] == "done" and h["ts"].startswith(month))
        if done_this_month == 0:
            prev_month = f"{now.year}-{now.month - 1:02d}" if now.month > 1 else f"{now.year - 1}-12"
            done_prev = sum(1 for h in hist if h["action"] == "done" and h["ts"].startswith(prev_month))
            if done_prev > 0:
                insights.append("[yellow]Стрик под угрозой — ещё 0 книг в этом месяце[/yellow]")
        # Books on phone too long
        if self.trello:
            lm = self._lmap()
            for c in self.trello.get_cards():
                if lm.get(c["idList"]) == "В телефоне":
                    for h in reversed(hist):
                        if h["action"] == "phone" and fuzzy_match(h["book"], c["name"]) > MATCH_LIKELY:
                            days = (now - datetime.fromisoformat(h["ts"])).days
                            if days >= 10:
                                _, ct, _ = parse_folder_name(c["name"])
                                insights.append(f"[yellow]{ct[:30]} в телефоне уже {days} дней[/yellow]")
                            break
        # Yearly goal check
        config = load_config()
        yearly_goal = config.get("yearly_goal", 0)
        if yearly_goal:
            done_year = sum(1 for h in hist if h["action"] == "done" and h["ts"].startswith(year))
            expected = int(yearly_goal * now.timetuple().tm_yday / 365)
            if done_year < expected:
                insights.append(f"[yellow]Отставание от цели: {done_year}/{yearly_goal} (ожидалось ~{expected})[/yellow]")
        # Overdue deadlines
        plans = config.get("plans", [])
        for p in plans:
            days_left = (datetime.fromisoformat(p["deadline"]) - now).days
            if days_left < 0:
                insights.append(f"[red]Дедлайн просрочен: {p['book'][:35]}[/red]")
        return insights

    def _ok(self):
        if not self.trello:
            console.print("[red]Trello не настроен.[/red]"); return False
        return True

    def _cards_in(self, *names):
        if not self.trello:
            return []
        ids = {self.trello.list_id(n) for n in names}
        return [c for c in self.trello.get_cards() if c["idList"] in ids]

    def _lmap(self):
        if not self.trello:
            return {}
        return {l["id"]: l["name"] for l in self.trello.get_lists()}

    def _sync_csv(self):
        if not self.trello: return
        self.trello.reload()
        lm = self._lmap()
        rows = []
        for c in self.trello.get_cards():
            ln = lm.get(c["idList"], "?")
            a, t, r = parse_folder_name(c["name"])
            rows.append({"Автор": a, "Название": t, "Чтец": r or "",
                         "Категория": self.trello.category(c) or "", "Статус": LIST_TO_STATUS.get(ln, ln)})
        rows.sort(key=lambda r: (r["Категория"], r["Автор"].lower(), r["Название"].lower()))
        self.lib.save_tracker(rows)

    def _find_and_copy(self, card_name):
        book = find_book_on_disk(card_name, self.lib.find_all_books())
        if book:
            clipboard_copy(str(book["path"]))
            console.print(f"  [bold]Путь:[/bold] {book['path']}  [dim](скопировано)[/dim]")
            return book["path"]
        return None

    def _enrich_card(self, card_id, book_path: Path | None):
        """Add size, duration, path to card description."""
        if not book_path or not self.trello:
            return
        try:
            size = folder_size_mb(book_path)
            mp3 = count_mp3(book_path)
            dur = estimate_duration_hours(book_path)
            lines = [f"{size:.0f} МБ, {mp3} файлов"]
            if dur:
                lines.append(f"~{fmt_duration(dur)}")
            lines.append(str(book_path))
            self.trello.set_desc(card_id, "\n".join(lines))
        except Exception:
            pass

    def _header(self):
        """Compact status bar with greeting and stats at top of every screen."""
        hour = datetime.now().hour
        if hour < 6:
            greet = "Ночное чтение"
        elif hour < 12:
            greet = "Доброе утро"
        elif hour < 18:
            greet = "Добрый день"
        else:
            greet = "Добрый вечер"

        parts = []
        active_name = ""
        if self.trello:
            lm = self._lmap()
            sc = defaultdict(int)
            for c in self.trello.get_cards():
                ln = lm.get(c["idList"], "")
                sc[ln] += 1
                if ln == "В процессе" and not active_name:
                    _, t, _ = parse_folder_name(c["name"])
                    active_name = t[:30]
            if sc.get("В процессе"):
                parts.append(f"[magenta]>{sc['В процессе']}[/]")
            if sc.get("В телефоне"):
                parts.append(f"[blue]>{sc['В телефоне']}[/]")
            if sc.get("На Паузе"):
                parts.append(f"[yellow]||{sc['На Паузе']}[/]")
            pr = sc.get("Прочитано", 0)
            total = sum(sc.values())
            parts.append(f"[green]{pr}[/]/{total}")
        dl_n = len(self.lib.find_dl_books())
        if dl_n:
            parts.append(f"[yellow]dl:{dl_n}[/]")

        # Velocity hint
        vel = reading_velocity(self._history())
        if vel.get("recent_pace", 0) > 0:
            parts.append(f"[dim]{vel['recent_pace']:.1f}/мес[/dim]")

        bar = "  ".join(parts)
        now_str = f"  [dim magenta]{active_name}[/]" if active_name else ""
        console.print(Panel.fit(
            f"[bold cyan]{greet}[/bold cyan]   {bar}{now_str}",
            border_style="cyan"))
        # Smart insights
        for insight in self._smart_insights()[:2]:
            console.print(f"  {insight}")

    def run(self):
        last_action = "status"
        while True:
            console.clear()
            self._header()

            dl_n = len(self.lib.find_dl_books())
            inbox_lbl = f"Разобрать входящие [yellow][{dl_n}][/yellow]" if dl_n else "Разобрать входящие"

            # Smart default: if there are dl/ books, default to inbox; otherwise last action
            default = "inbox" if dl_n else last_action

            choices = [
                Choice("status", name="Статус библиотеки"),
                Choice("search", name="Поиск"),
                Choice("filter", name="Умный фильтр"),
                Separator("── Слушаю ──"),
                Choice("pick", name="Что послушать?"),
                Choice("listen", name="Начать слушать"),
                Choice("phone", name="На телефон"),
                Choice("pause", name="На паузу"),
                Choice("done", name="Прослушано"),
                Choice("relisten", name="Снова послушать"),
                Separator("── Управление ──"),
                Choice("inbox", name=inbox_lbl),
                Choice("sync", name="Синхронизация с Trello"),
                Choice("move", name="Переместить (категория)"),
                Choice("rename", name="Стандартизировать имена"),
                Choice("reject", name="Забраковать"),
                Choice("cleanup", name="Очистка диска"),
                Choice("bulk", name="Массовые операции"),
                Separator("── Коллекции ──"),
                Choice("collections", name="Коллекции"),
                Choice("tags", name="Теги"),
                Choice("quotes", name="Цитаты"),
                Separator("── Аналитика ──"),
                Choice("dashboard", name="Недельный дашборд"),
                Choice("stats", name="Статистика"),
                Choice("analytics", name="Глубокая аналитика"),
                Choice("achievements", name="Достижения"),
                Choice("session", name="Сессии прослушивания"),
                Choice("history", name="История"),
                Separator("── Обзор ──"),
                Choice("recommend", name="Что скачать"),
                Choice("discover", name="Поиск новых (Google)"),
                Choice("download", name="Список «Скачать»"),
                Choice("queue", name="Очередь чтения"),
                Choice("similar", name="Похожие книги"),
                Choice("compare", name="Сравнить книги"),
                Choice("author", name="По автору"),
                Choice("timeline", name="Хронология книги"),
                Separator("── Система ──"),
                Choice("progress", name="Прогресс чтения"),
                Choice("plans", name="Планы и дедлайны"),
                Choice("export", name="Экспорт каталога"),
                Choice("backup", name="Бэкап данных"),
                Choice("undo", name="Отменить действие"),
                Choice("config", name="Настройки"),
                Choice("help", name="Справка"),
                Choice("trello", name="Открыть Trello"),
                Choice("quit", name="Выход"),
            ]

            action = inquirer.select(message="", choices=choices, default=default).execute()
            if action == "quit":
                console.print("[dim]До встречи![/dim]"); break

            if action == "trello":
                webbrowser.open(TRELLO_BOARD_URL)
                continue

            last_action = action
            try:
                getattr(self, f"screen_{action}")()
            except requests.exceptions.RequestException as e:
                console.print(f"\n[red]Ошибка Trello: {e}[/red]")
            except KeyboardInterrupt:
                pass

            console.print()
            inquirer.text(message="Enter -- меню").execute()

    # ── Статус ────────────────────────────────────────────────────────────────

    def screen_status(self):
        console.print()
        counts = self.lib.count_by_category()
        total = sum(counts.values())

        t1 = Table(title="Категории", show_lines=False, min_width=28)
        t1.add_column("Категория", style="bold")
        t1.add_column("#", justify="right", style="cyan")
        for c, n in counts.items(): t1.add_row(c, str(n))
        t1.add_row("[bold]Всего[/bold]", f"[bold]{total}[/bold]")

        if self.trello:
            cards = self.trello.get_cards()
            lm = self._lmap()
            sc = defaultdict(int)
            active, paused = [], []
            for c in cards:
                ln = lm.get(c["idList"], "?")
                sc[ln] += 1
                if ln in ("В процессе", "В телефоне"):
                    active.append((ln, c))
                elif ln == "На Паузе":
                    paused.append(c)

            t2 = Table(title="Trello", show_lines=False, min_width=28)
            t2.add_column("Статус", style="bold")
            t2.add_column("#", justify="right", style="cyan")
            for lst in self.trello.get_lists():
                n, cnt = lst["name"], sc.get(lst["name"], 0)
                if cnt: t2.add_row(f"[{STATUS_STYLE.get(n,'white')}]{n}[/]", str(cnt))
            t2.add_row("[bold]Всего[/bold]", f"[bold]{len(cards)}[/bold]")

            console.print(Columns([t1, t2], padding=(0, 4)))

            # Active books with duration and progress
            if active:
                console.print("\n[bold]Сейчас:[/bold]")
                all_books = self.lib.find_all_books()
                for ln, card in active:
                    style = "magenta" if ln == "В процессе" else "blue"
                    _, ct, _ = parse_folder_name(card["name"])
                    pct = progress_get(ct)
                    book = find_book_on_disk(card["name"], all_books)
                    extra = ""
                    if book:
                        dur = estimate_duration_hours(book["path"])
                        size = folder_size_mb(book["path"])
                        extra = f"  [dim]{size:.0f} МБ"
                        if dur: extra += f", ~{fmt_duration(dur)}"
                        extra += "[/dim]"
                    pbar = ""
                    if pct > 0:
                        pbar = f"  [cyan]{_progress_bar(pct, 15)}[/cyan] {pct}%"
                    console.print(f"  [{style}]{ln}[/] {card['name']}{extra}{pbar}")

            # Stale detection: books "В процессе" started >14 days ago
            hist = self._history()
            now = datetime.now()
            for ln, card in active:
                if ln != "В процессе":
                    continue
                for h in reversed(hist):
                    if h["action"] == "listen" and fuzzy_match(h["book"], card["name"]) > MATCH_STRONG:
                        started = datetime.fromisoformat(h["ts"])
                        days = (now - started).days
                        if days > 14:
                            console.print(f"    [yellow]^ {days} дней — завершить или на паузу?[/yellow]")
                        break

            # Paused
            if paused:
                console.print("\n[yellow]На паузе:[/yellow]")
                for c in paused:
                    console.print(f"  [dim]{c['name']}[/dim]")

            # Read percentage
            read = sc.get("Прочитано", 0)
            if read and cards:
                pct = read / len(cards) * 100
                console.print(f"\n[dim]Прочитано {read} из {len(cards)} ({pct:.0f}%)[/dim]")

            # Recently finished (from history)
            hist = self._history()
            done_hist = [h for h in hist if h["action"] == "done"]
            if done_hist:
                console.print(f"\n[bold]Недавно прослушано:[/bold]")
                for h in done_hist[-3:]:
                    ts = h["ts"][:10]
                    rating_s = ""
                    if h.get("rating"):
                        rating_s = f"  [yellow]{_format_stars(h['rating'])}[/yellow]"
                    console.print(f"  [dim]{ts}[/dim]  [green]{h['book']}[/green]{rating_s}")

            # Plan deadlines
            config = load_config()
            plans = config.get("plans", [])
            now = datetime.now()
            urgent = [p for p in plans if (datetime.fromisoformat(p["deadline"]) - now).days <= 7]
            if urgent:
                console.print(f"\n[bold yellow]Дедлайны:[/bold yellow]")
                for p in urgent:
                    days = (datetime.fromisoformat(p["deadline"]) - now).days
                    if days < 0:
                        console.print(f"  [red]ПРОСРОЧЕНО ({-days}д):[/red] {p['book'][:45]}")
                    else:
                        console.print(f"  [yellow]{days} дней:[/yellow] {p['book'][:45]}")

            # Random quote of the day
            quotes = quotes_load()
            if quotes:
                q = quotes[hash(str(now.date())) % len(quotes)]
                console.print(f'\n  [dim italic]"{q["text"][:80]}"[/dim italic]')
                console.print(f"  [dim]— {q.get("author", "")} «{q["book"]}»[/dim]")
        else:
            console.print(t1)

        dl = self.lib.find_dl_books()
        if dl:
            console.print(f"\n[yellow]dl/ -- {len(dl)} ожидают сортировки[/yellow]")
            for b in dl[:8]:
                console.print(f"  [dim]{'  '.join(filter(None, [b['author'], b['title']]))}[/dim]")
            if len(dl) > 8:
                console.print(f"  [dim]...и ещё {len(dl) - 8}[/dim]")

        # Quick actions for active books
        if self.trello and (active or paused):
            console.print()
            qc = []
            for ln, card in active:
                qc.append(Choice(("done", card), name=f"Прослушано: {card['name'][:45]}"))
                qc.append(Choice(("pause", card), name=f"На паузу: {card['name'][:45]}"))
            for card in paused:
                qc.append(Choice(("resume", card), name=f"Продолжить: {card['name'][:45]}"))
            qc.append(Choice(("skip", None), name="Пропустить"))
            try:
                qa = inquirer.select(message="Быстрое действие:", choices=qc, default=None).execute()
            except Exception:
                return
            if qa[0] == "done":
                self._move_with_history(qa[1], "Прочитано", "done", "(quick)")
                console.print(f"  [green]{qa[1]['name']} -> Прочитано[/green]")
            elif qa[0] == "pause":
                self._move_with_history(qa[1], "На Паузе", "pause", "(quick)")
                console.print(f"  [yellow]{qa[1]['name']} -> На Паузе[/yellow]")
            elif qa[0] == "resume":
                self._move_with_history(qa[1], "В процессе", "listen", "(resume)")
                console.print(f"  [magenta]{qa[1]['name']} -> В процессе[/magenta]")
                p = self._find_and_copy(qa[1]["name"])
                if p: open_in_explorer(p)

    # ── Разобрать входящие ────────────────────────────────────────────────────

    def screen_inbox(self):
        dl_books = self.lib.find_dl_books()
        if not dl_books:
            console.print("\n[green]dl/ пуста.[/green]"); return

        cards = self.trello.get_cards() if self.trello else []
        inf = self.inf

        # Analyze
        plan = []
        for book in dl_books:
            a, t, r = book["author"], book["title"], book["reader"]
            mc, ms = best_card_match(a, t, cards) if cards else (None, 0)
            if ms < MATCH_WEAK: mc = None
            tc = self.trello.category(mc) if mc and self.trello else None
            cat = inf.infer(a, t, tc)
            sn = standardize_name(a, t, r)
            plan.append({**book, "card": mc, "score": ms, "cat": cat, "std": sn,
                         "auto": bool(cat)})

        auto = [p for p in plan if p["auto"]]
        ask = [p for p in plan if not p["auto"]]

        if auto:
            console.print(f"\n[bold green]Автоматически ({len(auto)}):[/bold green]")
            tbl = Table(show_lines=False, padding=(0, 1))
            tbl.add_column("#", style="dim", width=3)
            tbl.add_column("Книга", max_width=55)
            tbl.add_column("Категория", style="cyan", width=15)
            tbl.add_column("Trello", style="dim", width=5)
            for i, p in enumerate(auto, 1):
                tbl.add_row(str(i), p["std"], p["cat"], f"{p['score']:.0%}" if p["card"] else "new")
            console.print(tbl)

        if ask:
            console.print(f"\n[yellow]Требуют выбора ({len(ask)}):[/yellow]")
            for p in ask:
                console.print(f"  [dim]{p['std']}[/dim]")

        console.print()
        mode = inquirer.select(message="Как обработать?", choices=[
            Choice("batch", name=f"Авто ({len(auto)}) + вручную ({len(ask)})"),
            Choice("manual", name="Все вручную"),
            Choice("cancel", name="Отмена"),
        ], default="batch").execute()
        if mode == "cancel": return

        done_n, skip_n = 0, 0

        # Auto batch with progress bar
        if mode == "batch" and auto:
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                          BarColumn(), TaskProgressColumn(), console=console) as prog:
                task = prog.add_task("Обрабатываю", total=len(auto))
                for p in auto:
                    prog.update(task, description=f"[green]{p['std'][:40]}[/green]")
                    dest = self.lib.move_to_category(p["path"], p["cat"], p["std"])
                    if self.trello:
                        lbl = FOLDER_TO_LABEL.get(p["cat"])
                        if p["card"]:
                            self.trello.move_card(p["card"]["id"], "Прочесть")
                            if p["std"] != p["card"]["name"]:
                                self.trello.update_name(p["card"]["id"], p["std"])
                            self._enrich_card(p["card"]["id"], dest)
                        else:
                            c = self.trello.create_card(p["std"], "Прочесть", lbl)
                            self._enrich_card(c["id"], dest)
                    self._history_add("inbox", p["std"], f"-> {p['cat']}")
                    done_n += 1
                    prog.advance(task)
            console.print(f"[green]Авто: {done_n}[/green]\n")

        # Manual
        for p in (ask if mode == "batch" else plan):
            console.rule(f"[bold]{p['folder'][:70]}[/bold]")
            console.print(f"  {p['author'] or '—'} | {p['title']} | {p['reader'] or '—'}")
            if p["card"]:
                console.print(f"  [dim]Trello: {p['card']['name']} ({p['score']:.0%})[/dim]")

            cat = p["cat"]
            if not cat:
                cat = inquirer.select(message="Категория:", choices=CATEGORIES, default="Саморазвитие").execute()

            sn = p["std"]
            console.print(f"  [cyan]{cat}[/cyan] / [green]{sn}[/green]")

            act = inquirer.select(message="", choices=[
                Choice("ok", name="OK"), Choice("edit", name="Изменить"), Choice("skip", name="Пропустить"),
            ], default="ok").execute()

            if act == "skip": skip_n += 1; continue
            if act == "edit":
                sn = inquirer.text(message="Имя:", default=sn).execute()
                cat = inquirer.select(message="Категория:", choices=CATEGORIES, default=cat).execute()

            dest = self.lib.move_to_category(p["path"], cat, sn)
            done_n += 1
            console.print(f"  [green]-> {cat}/{sn}[/green]")
            self._history_add("inbox", sn, f"-> {cat}")
            if self.trello:
                lbl = FOLDER_TO_LABEL.get(cat)
                if p["card"]:
                    self.trello.move_card(p["card"]["id"], "Прочесть")
                    if sn != p["card"]["name"]: self.trello.update_name(p["card"]["id"], sn)
                    self._enrich_card(p["card"]["id"], dest)
                else:
                    c = self.trello.create_card(sn, "Прочесть", lbl)
                    self._enrich_card(c["id"], dest)

        console.print(f"\n[bold]Обработано: {done_n}, пропущено: {skip_n}[/bold]")
        if done_n and self.trello:
            with console.status("[dim]CSV..."): self._sync_csv()
            console.print("[dim]CSV обновлён[/dim]")
            self._invalidate()

        if done_n and METADATA_SCRIPT.exists():
            if inquirer.confirm(message="Запустить _metadata.py?", default=True).execute():
                subprocess.run([sys.executable, str(METADATA_SCRIPT)], cwd=str(BASE))

    # ── Синхронизация ─────────────────────────────────────────────────────────

    def screen_sync(self):
        if not self._ok(): return
        changes = []

        console.print("\n[bold]Синхронизация с Trello...[/bold]\n")
        self.trello.reload()
        cards = self.trello.get_cards()
        books = self.lib.find_all_books()

        # Disk -> Trello (with progress)
        new_cards = []
        for b in books:
            _, s = best_card_match(b["author"], b["title"], cards)
            if s < MATCH_LIKELY:
                new_cards.append(b)

        if new_cards:
            if len(new_cards) > 10:
                if not inquirer.confirm(
                    message=f"Создать {len(new_cards)} новых карточек на Trello?",
                    default=True,
                ).execute():
                    new_cards = []

            if new_cards:
                with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                              BarColumn(), TaskProgressColumn(), console=console) as prog:
                    task = prog.add_task("Создаю карточки", total=len(new_cards))
                    for b in new_cards:
                        self.trello.create_card(b["folder"], "Прочесть", FOLDER_TO_LABEL.get(b["category"]))
                        changes.append(f"[green]+[/green] {b['title']}")
                        prog.advance(task)

        # "Скачать" already on disk -> "Прочесть"
        for c in self._cards_in("Скачать"):
            if find_book_on_disk(c["name"], books):
                self.trello.move_card(c["id"], "Прочесть")
                changes.append(f"[cyan]->[/cyan] {c['name']}: Скачать -> Прочесть")

        # Detect duplicates (fuzzy)
        self.trello.reload()
        all_cards = self.trello.get_cards()
        seen: dict[str, dict] = {}
        for c in all_cards:
            key = normalize(c["name"])
            if key in seen:
                changes.append(f"[yellow]!![/yellow] Дубликат: {c['name']}")
            else:
                # Also check fuzzy duplicates
                for sk, sv in seen.items():
                    if fuzzy_match(key, sk) > MATCH_EXACT and sv["idList"] == c["idList"]:
                        changes.append(f"[yellow]~[/yellow] Похожи: {sv['name']}  /  {c['name']}")
                        break
            seen[key] = c

        with console.status("[dim]CSV..."):
            self._sync_csv()

        console.print(Panel("[bold]Синхронизация завершена[/bold]", border_style="green"))
        if changes:
            for ch in changes: console.print(f"  {ch}")
        else:
            console.print("  [dim]Без изменений[/dim]")
        console.print(f"\n  [dim]CSV: {len(self.lib.load_tracker())} записей[/dim]")

        # Offer batch enrich: add metadata to cards without descriptions
        self.trello.reload()
        empty_desc = [c for c in self.trello.get_cards() if not c.get("desc", "").strip()]
        if empty_desc and books:
            console.print(f"\n[dim]{len(empty_desc)} карточек без описания[/dim]")
            if inquirer.confirm(message=f"Обогатить карточки метаданными ({len(empty_desc)})?", default=False).execute():
                enriched = 0
                with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                              BarColumn(), TaskProgressColumn(), console=console) as prog:
                    task = prog.add_task("Обогащаю", total=len(empty_desc))
                    for c in empty_desc:
                        b = find_book_on_disk(c["name"], books)
                        if b:
                            self._enrich_card(c["id"], b["path"])
                            enriched += 1
                        prog.advance(task)
                console.print(f"[green]Обогащено: {enriched}[/green]")

    # ── На телефон (multi-select) ─────────────────────────────────────────────

    def screen_phone(self):
        selected = self._select_card("Прочесть", "На телефон:", multiselect=True)
        if not selected: return

        with console.status("[bold]Trello..."):
            for c in selected:
                self._move_with_history(c, "В телефоне", "phone", sync=False)

        console.print(f"\n[green]-> В телефоне: {len(selected)}[/green]\n")
        paths = []
        books = self.lib.find_all_books()
        for c in selected:
            b = find_book_on_disk(c["name"], books)
            if b:
                console.print(f"  {b['path']}")
                paths.append(str(b["path"]))
        if paths:
            clipboard_copy("\n".join(paths))
            console.print(f"\n[dim]{len(paths)} путей -> буфер[/dim]")
            if len(paths) == 1:
                open_in_explorer(Path(paths[0]))
        self._sync_csv()

    # ── Начать слушать ────────────────────────────────────────────────────────

    def screen_listen(self):
        sel = self._select_card(["Прочесть", "В телефоне"], "Начинаю слушать:")
        if not sel: return

        self._move_with_history(sel, "В процессе", "listen")
        console.print(f"\n[green]{sel['name']} -> В процессе[/green]")
        p = self._find_and_copy(sel["name"])
        if p:
            self._enrich_card(sel["id"], p)
            open_in_explorer(p)

    # ── На паузу ──────────────────────────────────────────────────────────────

    def screen_pause(self):
        sel = self._select_card(["В процессе", "В телефоне"], "На паузу:")
        if not sel: return
        self._move_with_history(sel, "На Паузе", "pause")
        console.print(f"\n[yellow]{sel['name']} -> На Паузе[/yellow]")

    # ── Прослушано (multi-select) ─────────────────────────────────────────────

    def screen_done(self):
        selected = self._select_card(["В процессе", "В телефоне", "На Паузе"], "Прослушано:", multiselect=True)
        if not selected: return

        with console.status("[bold]Обновляю..."):
            for c in selected:
                self.trello.move_card(c["id"], "Прочитано")
        for c in selected: console.print(f"  [green]{c['name']} -> Прочитано[/green]")

        # Ask for ratings
        for c in selected:
            rating_str = inquirer.select(
                message=f"Оценка «{c['name'][:40]}»:",
                choices=[
                    Choice(5, name="5 - Шедевр"),
                    Choice(4, name="4 - Отлично"),
                    Choice(3, name="3 - Хорошо"),
                    Choice(2, name="2 - Средне"),
                    Choice(1, name="1 - Плохо"),
                    Choice(0, name="Без оценки"),
                ],
                default=4,
            ).execute()
            self._history_add("done", c["name"], rating=rating_str)
            if rating_str:
                console.print(f"  [yellow]{_format_stars(rating_str)}[/yellow] {c['name'][:50]}")

        self._sync_csv()
        console.print(f"\n[bold]Завершено: {len(selected)}[/bold]")

        # Set progress to 100% for finished books (don't overwrite notes)
        for c in selected:
            _, ct, _ = parse_folder_name(c["name"])
            if progress_get(ct) < 100:
                progress_set(ct, 100, "Прослушано")

        # Offer to save a quote
        for c in selected:
            if inquirer.confirm(message=f"Сохранить цитату из «{c['name'][:35]}»?", default=False).execute():
                quote_text = inquirer.text(message="Цитата:").execute().strip()
                if quote_text:
                    ca, ct, _ = parse_folder_name(c["name"])
                    quotes_add(quote_text, ct, ca)
                    console.print(f"  [green]Цитата сохранена[/green]")

        # Suggest similar books
        all_books = self._books()
        hist = self._history()
        for c in selected:
            book = find_book_on_disk(c["name"], all_books)
            if not book:
                continue
            similar = find_similar(book, all_books, hist, top_n=3)
            if similar:
                console.print(f"\n[bold]Похожие на «{book['title'][:30]}»:[/bold]")
                for sb, score in similar:
                    console.print(f"  [dim]{sb['category']}[/dim]  {sb['author']} - {sb['title']}" if sb["author"]
                                  else f"  [dim]{sb['category']}[/dim]  {sb['title']}")

    # ── Переместить между категориями ─────────────────────────────────────────

    def screen_move(self):
        sel = self._select_book("Какую книгу переместить?")
        if not sel: return

        console.print(f"\n  Сейчас: [cyan]{sel['category']}[/cyan] / {sel['folder']}")
        new_cat = inquirer.select(
            message="Новая категория:",
            choices=[c for c in CATEGORIES if c != sel["category"]],
        ).execute()

        if not inquirer.confirm(message=f"{sel['title'][:40]}: {sel['category']} -> {new_cat}?", default=True).execute():
            return

        dest = self.lib.move_to_category(sel["path"], new_cat)
        console.print(f"  [green]-> {new_cat}/{dest.name}[/green]")
        self._history_add("move", sel["title"], f"{sel['category']} -> {new_cat}")

        # Update Trello label
        if self.trello:
            card, score = best_card_match(sel["author"], sel["title"], self.trello.get_cards())
            if card and score > MATCH_LIKELY:
                new_label = FOLDER_TO_LABEL.get(new_cat)
                if new_label:
                    self.trello.add_label(card["id"], new_label)
                    console.print(f"  [dim]Trello: метка {new_label}[/dim]")
            self._sync_csv()

    # ── Стандартизировать имена ────────────────────────────────────────────────

    def screen_rename(self):
        books = self.lib.find_all_books()
        renames = []
        for b in books:
            ideal = standardize_name(b["author"], b["title"], b["reader"])
            if ideal != b["folder"] and b["author"]:
                renames.append((b, ideal))

        if not renames:
            console.print("\n[green]Все имена стандартны.[/green]"); return

        console.print(f"\n[bold]Можно переименовать: {len(renames)}[/bold]\n")
        tbl = Table(show_lines=False, padding=(0, 1))
        tbl.add_column("#", style="dim", width=3)
        tbl.add_column("Сейчас", max_width=55, style="red")
        tbl.add_column("Новое", max_width=55, style="green")
        for i, (b, ideal) in enumerate(renames[:30], 1):
            tbl.add_row(str(i), b["folder"][:55], ideal[:55])
        console.print(tbl)
        if len(renames) > 30:
            console.print(f"  [dim]...и ещё {len(renames) - 30}[/dim]")

        act = inquirer.select(message="", choices=[
            Choice("all", name=f"Переименовать все {len(renames)}"),
            Choice("pick", name="Выбрать конкретные"),
            Choice("cancel", name="Отмена"),
        ], default="all").execute()

        if act == "cancel": return

        to_do = renames
        if act == "pick":
            selected = inquirer.fuzzy(
                message="Выберите:", multiselect=True, max_height="70%",
                choices=[Choice((b, ideal), name=f"{b['folder']} -> {ideal}") for b, ideal in renames],
            ).execute()
            to_do = selected if selected else []

        done_n = 0
        with console.status("[bold]Переименовываю..."):
            for b, ideal in to_do:
                new_path = self.lib.rename_book(b["path"], ideal)
                if new_path != b["path"]:
                    done_n += 1
                    # Update Trello card name
                    if self.trello:
                        card, score = best_card_match(b["author"], b["title"], self.trello.get_cards())
                        if card and score > MATCH_LIKELY and card["name"] != ideal:
                            self.trello.update_name(card["id"], ideal)

        console.print(f"\n[green]Переименовано: {done_n}[/green]")
        if done_n and self.trello:
            self._sync_csv()
            console.print("[dim]CSV обновлён[/dim]")

    # ── Что послушать (умный выбор с настроением) ──────────────────────────────

    def screen_pick(self):
        if not self._ok(): return
        cards = self._cards_in("Прочесть")
        if not cards:
            console.print("\n[dim]Нет книг «Прочесть».[/dim]"); return

        # Mood selection
        mood = inquirer.select(message="Настроение:", choices=[
            Choice(None, name="Любое (умный выбор)"),
            Choice("short", name="Что-то короткое (< 6ч)"),
            Choice("long", name="Длинный марафон (> 10ч)"),
            Choice("new_author", name="Новый автор"),
            Choice("favorite_cat", name="Любимая категория"),
            Choice("english", name="На английском"),
            Choice("random", name="Случайная книга"),
        ], default=None).execute()

        recs = parse_recommendations()
        rec_titles = {normalize(r["title"]): r.get("priority", "-") for r in recs}

        # Genre rotation: find last listened category to penalize
        last_cat = None
        hist = self._history()
        for h in reversed(hist):
            if h["action"] in ("listen", "done"):
                book_on_disk = find_book_on_disk(h["book"], self.lib.find_all_books())
                if book_on_disk:
                    last_cat = book_on_disk["category"]
                    break

        # Find favorite category from history
        cat_counts = Counter()
        done_entries = [h for h in hist if h["action"] == "done"]
        all_books = self.lib.find_all_books()
        for h in done_entries:
            b = find_book_on_disk(h["book"], all_books)
            if b:
                cat_counts[b["category"]] += 1
        fav_cat = cat_counts.most_common(1)[0][0] if cat_counts else "Саморазвитие"

        # Known authors (already listened)
        known_authors = set()
        for h in done_entries:
            b = find_book_on_disk(h["book"], all_books)
            if b and b["author"]:
                known_authors.add(b["author"].lower())

        # Score each card
        scored = []
        for card in cards:
            score = 0
            ca, ct, _ = parse_folder_name(card["name"])
            # Boost: priority from recommendations
            for rt, pri in rec_titles.items():
                if fuzzy_match(ct, rt) > MATCH_LIKELY:
                    score += {"1": 30, "2": 15, "-": 5}.get(pri, 0)
                    break
            # Boost: has category label (well-organized)
            card_cat = self.trello.category(card)
            if card_cat:
                score += 5
            # Boost: exists on disk (ready to listen)
            book = find_book_on_disk(card["name"], all_books)
            if book:
                score += 20
                dur = estimate_duration_hours(book["path"])
                # Genre rotation: penalize same category as last listened
                if last_cat and book["category"] == last_cat:
                    score -= 10

                # Mood-based scoring
                if mood == "short" and dur and dur < 6:
                    score += 40
                elif mood == "short" and dur and dur >= 6:
                    score -= 30
                elif mood == "long" and dur and dur > 10:
                    score += 40
                elif mood == "long" and dur and dur <= 10:
                    score -= 30
                elif mood == "new_author":
                    if ca.lower() not in known_authors and ca:
                        score += 40
                    else:
                        score -= 20
                elif mood == "favorite_cat":
                    if book["category"] == fav_cat:
                        score += 40
                elif mood == "english":
                    if book["category"] == "Языки":
                        score += 50
                    else:
                        score -= 40
                elif mood == "random":
                    score = random.randint(0, 100)
            elif mood in ("short", "long"):
                score -= 20  # Unknown duration, deprioritize

            # Add randomness (unless random mode)
            if mood != "random":
                score += random.randint(0, 15)
            scored.append((score, card, book))

        scored.sort(key=lambda x: -x[0])
        top = scored[:5]

        console.print("\n[bold]Рекомендации из «Прочесть»:[/bold]\n")
        tbl = Table(show_lines=False, padding=(0, 1))
        tbl.add_column("#", style="dim", width=2)
        tbl.add_column("Книга", max_width=50)
        tbl.add_column("Категория", style="dim", width=14)
        tbl.add_column("Длит.", style="dim", width=8)
        tbl.add_column("Диск", width=4)
        for i, (score, card, book) in enumerate(top, 1):
            dur = ""
            cat = self.trello.category(card) or ""
            if book:
                d = estimate_duration_hours(book["path"])
                dur = fmt_duration(d)
                cat = book["category"]
            on_disk = "[green]+[/green]" if book else "[red]-[/red]"
            tbl.add_row(str(i), card["name"], cat, dur, on_disk)
        console.print(tbl)

        # Let user pick which one
        pick_choices = [Choice(i, name=f"#{i+1}: {top[i][1]['name'][:45]}") for i in range(len(top))]
        pick_choices.append(Choice(-1, name="Выбрать из полного списка"))
        pick_choices.append(Choice(-2, name="Назад"))

        idx = inquirer.select(message="Какую?", choices=pick_choices, default=0).execute()
        if idx == -2: return
        if idx == -1:
            self.screen_listen(); return

        target_card = top[idx][1]

        act = inquirer.select(message="Действие:", choices=[
            Choice("listen", name="Начать слушать"),
            Choice("phone", name="На телефон"),
        ], default="listen").execute()

        target_list = "В процессе" if act == "listen" else "В телефоне"
        self._move_with_history(target_card, target_list, act)
        console.print(f"\n[green]{target_card['name']} -> {target_list}[/green]")
        p = self._find_and_copy(target_card["name"])
        if p:
            self._enrich_card(target_card["id"], p)
            if act == "listen":
                open_in_explorer(p)

    # ── Забраковать ───────────────────────────────────────────────────────────

    def screen_reject(self):
        if not self._ok(): return
        cards = self.trello.get_cards()
        lm = self._lmap()
        # Show all except already rejected/read
        exclude = {"Прочитано", "Забраковано"}
        choices = [
            Choice(c, name=f"[{lm.get(c['idList'],'')}] {c['name']}")
            for c in cards if lm.get(c["idList"], "") not in exclude
        ]
        if not choices:
            console.print("\n[dim]Нечего браковать.[/dim]"); return

        selected = inquirer.fuzzy(
            message="Забраковать:", max_height="70%", multiselect=True,
            choices=choices,
        ).execute()
        if not selected: return

        if not inquirer.confirm(message=f"Забраковать {len(selected)} книг?", default=False).execute():
            return

        with console.status("[bold red]Забраковываю..."):
            for c in selected:
                self._move_with_history(c, "Забраковано", "reject", sync=False)
            self._sync_csv()

        for c in selected:
            console.print(f"  [red]{c['name']} -> Забраковано[/red]")

        # Remove from disk if exists
        all_books = self.lib.find_all_books()
        for c in selected:
            book = find_book_on_disk(c["name"], all_books)
            if book:
                console.print(f"  [dim]На диске: {book['path']}[/dim]")
        console.print(f"\n[bold]Забраковано: {len(selected)}[/bold]")

    # ── Что скачать (рекомендации) ────────────────────────────────────────────

    def screen_recommend(self):
        recs = parse_recommendations()
        if not recs:
            console.print("\n[dim]Файл рекомендаций не найден.[/dim]"); return

        books = self.lib.find_all_books()
        dl = self.lib.find_dl_books()
        all_titles = books + dl

        # Check Trello "Скачать" list
        trello_download = set()
        if self.trello:
            for c in self._cards_in("Скачать"):
                trello_download.add(normalize(c["name"]))

        missing = []
        for rec in recs:
            # Check if already in library or dl
            found = False
            for b in all_titles:
                if fuzzy_match(rec["title"], b["title"]) > MATCH_STRONG:
                    found = True; break
                if rec["author"] and fuzzy_match(rec["author"], b["author"]) > MATCH_STRONG and fuzzy_match(rec["title"], b["title"]) > MATCH_WEAK:
                    found = True; break
            if not found:
                # Check if in Trello at all
                in_trello = False
                if self.trello:
                    _, s = best_card_match(rec["author"], rec["title"], self.trello.get_cards())
                    in_trello = s > MATCH_LIKELY
                missing.append({**rec, "in_trello": in_trello})

        if not missing:
            console.print("\n[green]Все рекомендованные книги уже в библиотеке![/green]"); return

        # Sort: priority 1 first, then 2, then -
        priority_order = {"1": 0, "2": 1, "-": 2}
        missing.sort(key=lambda r: (priority_order.get(r["priority"], 3), r["section"]))

        tbl = Table(title=f"Не скачано ({len(missing)} из {len(recs)})", show_lines=False, padding=(0, 1))
        tbl.add_column("P", width=2, style="bold")
        tbl.add_column("Автор", max_width=25)
        tbl.add_column("Название", max_width=40)
        tbl.add_column("Раздел", style="dim", max_width=20)
        tbl.add_column("Trello", width=6, style="dim")

        for r in missing:
            p_style = {"1": "[green]1[/green]", "2": "[yellow]2[/yellow]", "-": "[dim]-[/dim]"}
            tbl.add_row(
                p_style.get(r["priority"], r["priority"]),
                r["author"], r["title"], r["section"],
                "да" if r["in_trello"] else "[red]нет[/red]",
            )
        console.print(tbl)

        # Offer to add missing to Trello "Скачать"
        if self.trello:
            not_in_trello = [r for r in missing if not r["in_trello"]]
            if not_in_trello:
                if inquirer.confirm(
                    message=f"Добавить {len(not_in_trello)} книг в Trello «Скачать»?",
                    default=True
                ).execute():
                    with console.status("[bold]Добавляю..."):
                        for r in not_in_trello:
                            cat_label = self.inf.infer(r["author"], r["title"])
                            label = FOLDER_TO_LABEL.get(cat_label) if cat_label else None
                            self.trello.create_card(
                                f"{r['author']} - {r['title']}", "Скачать",
                                label=label,
                            )
                    console.print(f"[green]Добавлено: {len(not_in_trello)}[/green]")
                    self._sync_csv()

    # ── Статистика ─────────────────────────────────────────────────────────

    def screen_stats(self):
        books = self.lib.find_all_books()
        counts = self.lib.count_by_category()
        total = sum(counts.values())

        console.print()

        # -- Category breakdown with visual bars
        t1 = Table(title="По категориям", show_lines=False, min_width=40)
        t1.add_column("Категория", style="bold", min_width=15)
        t1.add_column("#", justify="right", style="cyan", width=4)
        t1.add_column("", min_width=20)
        max_n = max(counts.values()) if counts else 1
        for cat, n in sorted(counts.items(), key=lambda x: -x[1]):
            bar_len = int(n / max_n * 20)
            bar = "[cyan]" + "\u2588" * bar_len + "[/cyan]"
            t1.add_row(cat, str(n), bar)
        t1.add_row("[bold]Всего[/bold]", f"[bold]{total}[/bold]", "")

        # -- Top authors
        author_cnt = Counter()
        for b in books:
            a = b["author"].strip()
            if a:
                author_cnt[a] += 1
        top_authors = author_cnt.most_common(10)

        t2 = Table(title="Топ авторов", show_lines=False, min_width=35)
        t2.add_column("Автор", style="bold", min_width=22)
        t2.add_column("#", justify="right", style="cyan", width=4)
        for a, n in top_authors:
            t2.add_row(a, str(n))

        console.print(Columns([t1, t2], padding=(0, 4)))

        # -- Total library size and duration estimate (sample-based for speed)
        total_size = 0.0
        total_hours = 0.0
        sampled = 0
        for b in books:
            try:
                total_size += folder_size_mb(b["path"])
            except Exception:
                pass

        # Estimate duration from a sample of up to 20 books
        sample = random.sample(books, min(20, len(books))) if books else []
        sample_hours = 0.0
        sample_n = 0
        for b in sample:
            d = estimate_duration_hours(b["path"])
            if d:
                sample_hours += d
                sample_n += 1

        console.print()
        console.print(f"  [bold]Размер библиотеки:[/bold] {total_size / 1024:.1f} ГБ")
        if sample_n > 0:
            avg_hours = sample_hours / sample_n
            est_total = avg_hours * total
            console.print(f"  [bold]Длительность (оценка):[/bold] ~{est_total:.0f} ч ({est_total / 24:.0f} дней)")
            console.print(f"  [bold]Средняя книга:[/bold] ~{avg_hours:.1f} ч")

        # -- Trello stats
        hist = self._history()
        if self.trello:
            cards = self.trello.get_cards()
            lm = self._lmap()
            sc = defaultdict(int)
            for c in cards:
                sc[lm.get(c["idList"], "")] += 1

            read = sc.get("Прочитано", 0)
            active = sc.get("В процессе", 0) + sc.get("В телефоне", 0)
            backlog = sc.get("Прочесть", 0)
            console.print()
            console.print(f"  [bold]Прочитано:[/bold]  [green]{read}[/green] из {len(cards)} ({read * 100 // max(len(cards),1)}%)")
            console.print(f"  [bold]Активных:[/bold]   [magenta]{active}[/magenta]")
            console.print(f"  [bold]В очереди:[/bold]  {backlog}")

            # Yearly goal
            config = load_config()
            yearly_goal = config.get("yearly_goal", 0)
            if yearly_goal:
                year = str(datetime.now().year)
                done_this_year = sum(1 for h in hist
                                     if h["action"] == "done" and h["ts"].startswith(year))
                pct = min(done_this_year * 100 // yearly_goal, 100)
                console.print(f"\n  [bold]Цель {year}:[/bold] {done_this_year}/{yearly_goal} ({pct}%)")
                console.print(f"  [cyan]{_progress_bar(pct)}[/cyan]")

            # Reading velocity & predictions
            vel = reading_velocity(hist)
            if vel.get("avg_per_month", 0) > 0:
                console.print(f"\n  [bold]Темп чтения:[/bold]")
                console.print(f"    Средний:        [cyan]{vel['avg_per_month']:.1f}[/cyan] книг/мес")
                console.print(f"    Последние 90д:  [cyan]{vel['recent_pace']:.1f}[/cyan] книг/мес")
                console.print(f"    Лучший месяц:   [cyan]{vel['best_month_count']}[/cyan] ({vel['best_month']})")
                if backlog > 0 and vel["recent_pace"] > 0:
                    months_left = backlog / vel["recent_pace"]
                    console.print(f"    [dim]При текущем темпе очередь ({backlog}) займёт ~{months_left:.0f} мес[/dim]")

            # Recently finished (from history)
            done_hist = [h for h in hist if h["action"] == "done"]
            if done_hist:
                console.print(f"\n[bold]Недавно прослушано:[/bold]")
                for h in done_hist[-5:]:
                    ts = h["ts"][:10]
                    console.print(f"  [dim]{ts}[/dim]  [green]{h['book']}[/green]")

        # -- Reader stats
        reader_cnt = Counter()
        for b in books:
            r = (b.get("reader") or "").strip()
            if r and r != "EN":
                reader_cnt[r] += 1
        if reader_cnt:
            top_readers = reader_cnt.most_common(5)
            console.print(f"\n[bold]Топ чтецов:[/bold]")
            for r, n in top_readers:
                console.print(f"  {r}: {n}")

        # -- Monthly listening stats from history
        done_entries = [h for h in hist if h["action"] == "done"]
        if done_entries:
            monthly: dict[str, int] = Counter()
            ratings = []
            for h in done_entries:
                month = h["ts"][:7]  # YYYY-MM
                monthly[month] += 1
                if h.get("rating"):
                    ratings.append(h["rating"])

            if len(monthly) > 1:
                console.print(f"\n[bold]Прослушано по месяцам:[/bold]")
                for month in sorted(monthly.keys())[-6:]:
                    n = monthly[month]
                    bar = "\u2588" * min(n, 20)
                    console.print(f"  [dim]{month}[/dim]  [cyan]{bar}[/cyan] {n}")

                # Streak: consecutive months
                months_sorted = sorted(monthly.keys())
                streak = 1
                for i in range(len(months_sorted) - 1, 0, -1):
                    y1, m1 = map(int, months_sorted[i].split("-"))
                    y0, m0 = map(int, months_sorted[i - 1].split("-"))
                    if (y1 * 12 + m1) - (y0 * 12 + m0) == 1:
                        streak += 1
                    else:
                        break
                if streak > 1:
                    console.print(f"  [bold]Стрик:[/bold] {streak} месяцев подряд")

            # Rating summary
            if ratings:
                avg = sum(ratings) / len(ratings)
                console.print(f"\n[bold]Средняя оценка:[/bold] [yellow]{_format_stars(round(avg))}[/yellow] ({avg:.1f})")
                # Top rated books
                rated = [(h["book"], h["rating"]) for h in done_entries if h.get("rating", 0) >= 4]
                if rated:
                    console.print(f"[bold]Лучшие книги:[/bold]")
                    for book, r in rated[-5:]:
                        console.print(f"  [yellow]{_format_stars(r)}[/yellow] {book[:50]}")

    # ── История ──────────────────────────────────────────────────────────────

    def screen_history(self):
        hist = self._history()
        if not hist:
            console.print("\n[dim]История пуста.[/dim]"); return

        console.print()
        tbl = Table(title=f"История ({len(hist)} записей)", show_lines=False, padding=(0, 1))
        tbl.add_column("Дата", style="dim", width=11)
        tbl.add_column("Действие", width=10)
        tbl.add_column("Книга", max_width=55)
        tbl.add_column("", style="dim", max_width=20)

        # Show last 30
        for h in hist[-30:]:
            ts = h["ts"][:10]
            s = ACTION_STYLES.get(h["action"], "white")
            act = f"[{s}]{h['action']}[/{s}]"
            detail = h.get("detail", "")
            if h.get("rating"):
                detail = _format_stars(h["rating"])
            tbl.add_row(ts, act, h.get("book", "")[:55], detail)
        console.print(tbl)

        if len(hist) > 30:
            console.print(f"\n[dim]Показано последних 30 из {len(hist)}[/dim]")

        # Summary
        action_counts = Counter(h["action"] for h in hist)
        parts = []
        for a, n in action_counts.most_common():
            parts.append(f"{a}:{n}")
        console.print(f"\n[dim]Итого: {', '.join(parts)}[/dim]")

    # ── Снова послушать ──────────────────────────────────────────────────────

    def screen_relisten(self):
        sel = self._select_card("Прочитано", "Снова послушать:")
        if not sel: return

        target = inquirer.select(message="Куда?", choices=[
            Choice("Прочесть", name="В очередь (Прочесть)"),
            Choice("В процессе", name="Слушать сейчас (В процессе)"),
            Choice("В телефоне", name="На телефон"),
        ], default="Прочесть").execute()

        self._move_with_history(sel, target, "relisten", f"-> {target}")
        console.print(f"\n[green]{sel['name']} -> {target}[/green]")

        if target in ("В процессе", "В телефоне"):
            p = self._find_and_copy(sel["name"])
            if p and target == "В процессе":
                open_in_explorer(p)

    # ── Управление "Скачать" ────────────────────────────────────────────────

    def screen_download(self):
        if not self._ok(): return
        cards = self._cards_in("Скачать")
        if not cards:
            console.print("\n[dim]Список «Скачать» пуст.[/dim]"); return

        console.print(f"\n[bold]Скачать ({len(cards)}):[/bold]\n")
        tbl = Table(show_lines=False, padding=(0, 1))
        tbl.add_column("#", style="dim", width=3)
        tbl.add_column("Книга", max_width=55)
        tbl.add_column("Метки", style="dim", max_width=20)
        for i, c in enumerate(sorted(cards, key=lambda x: x["name"]), 1):
            labels = ", ".join(self.trello.label_names(c))
            tbl.add_row(str(i), c["name"], labels)
        console.print(tbl)

        act = inquirer.select(message="Действие:", choices=[
            Choice("downloaded", name="Уже скачал (-> Прочесть)"),
            Choice("remove", name="Удалить из списка"),
            Choice("reject", name="Забраковать"),
            Choice("back", name="Назад"),
        ], default="back").execute()
        if act == "back": return

        target = {"downloaded": "Прочесть", "remove": None, "reject": "Забраковано"}.get(act)

        selected = inquirer.fuzzy(
            message="Выберите:", multiselect=True, max_height="70%",
            choices=[Choice(c, name=c["name"]) for c in sorted(cards, key=lambda x: x["name"])],
        ).execute()
        if not selected: return

        for c in selected:
            if target:
                self.trello.move_card(c["id"], target)
                console.print(f"  [green]{c['name']} -> {target}[/green]")
                self._history_add("download", c["name"], f"-> {target}")
            else:
                self.trello.archive_card(c["id"])
                console.print(f"  [dim]{c['name']} -> архив[/dim]")
                self._history_add("download", c["name"], "archived")
        self._sync_csv()
        console.print(f"\n[bold]Обработано: {len(selected)}[/bold]")

    # ── Отменить последнее действие ──────────────────────────────────────────

    def screen_undo(self):
        if not self._ok(): return
        hist = self._history()
        # Filter to undoable actions (Trello state changes)
        undoable = [h for h in hist if h["action"] in ("listen", "phone", "done", "pause", "reject", "relisten")]
        if not undoable:
            console.print("\n[dim]Нечего отменять.[/dim]"); return

        recent = undoable[-10:]
        recent.reverse()

        sel = inquirer.select(
            message="Отменить:", max_height="70%",
            choices=[Choice(h, name=f"[{h['ts'][:16]}] {h['action']}: {h['book'][:50]}") for h in recent]
                  + [Choice(None, name="Отмена")],
        ).execute()
        if not sel: return

        # Determine the "before" state — reverse the action
        reverse_map = {
            "listen": "Прочесть", "phone": "Прочесть", "done": "В процессе",
            "pause": "В процессе", "reject": "Прочесть", "relisten": "Прочитано",
        }
        target_list = reverse_map.get(sel["action"])
        if not target_list:
            console.print("[red]Не удалось определить прежний статус.[/red]"); return

        # Find the card
        card, score = best_card_match("", sel["book"], self.trello.get_cards())
        if not card or score < MATCH_WEAK:
            console.print(f"[red]Карточка не найдена: {sel['book']}[/red]"); return

        current_list = self.trello.list_name(card["idList"])
        console.print(f"\n  {card['name']}")
        console.print(f"  Сейчас: [cyan]{current_list}[/cyan]")
        console.print(f"  Вернуть в: [green]{target_list}[/green]")

        if inquirer.confirm(message="Подтвердить?", default=True).execute():
            self.trello.move_card(card["id"], target_list)
            self._history_add("undo", card["name"], f"{current_list} -> {target_list}")
            console.print(f"\n[green]{card['name']} -> {target_list}[/green]")
            self._sync_csv()

    # ── Очистка диска ────────────────────────────────────────────────────────

    def screen_cleanup(self):
        books = self.lib.find_all_books()
        issues = []

        # 1. Books on disk that are "Забраковано" in Trello
        if self.trello:
            rejected = self._cards_in("Забраковано")
            for c in rejected:
                b = find_book_on_disk(c["name"], books)
                if b:
                    size = folder_size_mb(b["path"])
                    issues.append({"type": "rejected", "book": b, "card": c, "size": size})

        # 2. Empty folders (no mp3 files)
        for b in books:
            mp3 = count_mp3(b["path"])
            if mp3 == 0:
                size = folder_size_mb(b["path"])
                issues.append({"type": "empty", "book": b, "size": size})

        # 3. Duplicate-looking folders on disk
        seen_titles: dict[str, dict] = {}
        for b in books:
            key = normalize(b["title"])
            if key in seen_titles:
                prev = seen_titles[key]
                if prev["category"] != b["category"] or prev["folder"] != b["folder"]:
                    issues.append({"type": "dup", "book": b, "other": prev})
            else:
                seen_titles[key] = b

        if not issues:
            console.print("\n[green]Диск чист![/green]"); return

        console.print(f"\n[bold]Найдено проблем: {len(issues)}[/bold]\n")

        total_reclaimable = 0.0
        tbl = Table(show_lines=False, padding=(0, 1))
        tbl.add_column("Тип", width=12, style="bold")
        tbl.add_column("Книга", max_width=50)
        tbl.add_column("Категория", style="dim", width=15)
        tbl.add_column("МБ", justify="right", width=7, style="cyan")

        for iss in issues:
            if iss["type"] == "rejected":
                tbl.add_row("[red]Забраковано[/red]", iss["book"]["folder"][:50],
                            iss["book"]["category"], f"{iss['size']:.0f}")
                total_reclaimable += iss["size"]
            elif iss["type"] == "empty":
                tbl.add_row("[yellow]Пусто[/yellow]", iss["book"]["folder"][:50],
                            iss["book"]["category"], f"{iss['size']:.0f}")
            elif iss["type"] == "dup":
                tbl.add_row("[yellow]Дубликат?[/yellow]",
                            f"{iss['book']['folder'][:25]} / {iss['other']['folder'][:25]}",
                            iss["book"]["category"], "")
        console.print(tbl)

        if total_reclaimable > 0:
            console.print(f"\n[dim]Можно освободить: ~{total_reclaimable:.0f} МБ[/dim]")

        # Offer to delete rejected
        rejected_issues = [i for i in issues if i["type"] == "rejected"]
        if rejected_issues:
            console.print()
            if inquirer.confirm(
                message=f"Удалить забракованные с диска ({len(rejected_issues)})?",
                default=False,
            ).execute():
                deleted = 0
                for iss in rejected_issues:
                    try:
                        shutil.rmtree(iss["book"]["path"])
                        console.print(f"  [red]Удалено:[/red] {iss['book']['folder']}")
                        self._history_add("delete", iss["book"]["folder"], f"{iss['size']:.0f} МБ")
                        deleted += 1
                    except Exception as e:
                        console.print(f"  [red]Ошибка: {iss['book']['folder']}: {e}[/red]")
                console.print(f"\n[green]Удалено: {deleted}, освобождено ~{total_reclaimable:.0f} МБ[/green]")

        # Offer to delete empty
        empty_issues = [i for i in issues if i["type"] == "empty"]
        if empty_issues:
            console.print()
            if inquirer.confirm(
                message=f"Удалить пустые папки ({len(empty_issues)})?",
                default=False,
            ).execute():
                for iss in empty_issues:
                    try:
                        shutil.rmtree(iss["book"]["path"])
                        console.print(f"  [dim]Удалено:[/dim] {iss['book']['folder']}")
                    except Exception as e:
                        console.print(f"  [red]Ошибка: {e}[/red]")

    # ── Экспорт каталога ─────────────────────────────────────────────────────

    def screen_export(self):
        books = self.lib.find_all_books()
        out_path = BASE / "_каталог.md"
        _ratings = self._book_ratings()
        hist = self._history()
        all_notes = notes_load()
        all_tags_data = tags_load()
        colls = collections_load()
        quotes = quotes_load()
        prog_data = progress_load()

        lines = ["# Аудиокниготека", "",
                 f"Экспорт: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]

        # Table of contents
        lines.append("## Оглавление")
        lines.append("")
        for cat in CATEGORIES:
            lines.append(f"- [{cat}](#{cat.lower().replace(' ', '-')})")
        lines.append("- [Статус (Trello)](#статус-trello)")
        if colls:
            lines.append("- [Коллекции](#коллекции)")
        if quotes:
            lines.append("- [Цитаты](#цитаты)")
        lines.append("- [Достижения](#достижения)")
        lines.append("- [Статистика](#статистика)")
        lines.append("")

        # Group by category
        by_cat: dict[str, list] = defaultdict(list)
        for b in books:
            by_cat[b["category"]].append(b)

        total = 0
        for cat in CATEGORIES:
            cat_books = by_cat.get(cat, [])
            if not cat_books:
                continue
            lines.append(f"## {cat} ({len(cat_books)})")
            lines.append("")
            lines.append("| # | Автор | Название | Чтец | Теги | Оценка | Прогресс |")
            lines.append("|---|-------|----------|------|------|--------|----------|")
            for i, b in enumerate(sorted(cat_books, key=lambda x: (x["author"].lower(), x["title"].lower())), 1):
                a = b["author"] or ""
                t = b["title"]
                r = b.get("reader") or ""
                btags = ", ".join(all_tags_data.get(normalize(t), []))
                rt = _ratings.get(normalize(b["folder"]), 0)
                rt_str = _format_stars(rt) if rt else ""
                pct_entry = prog_data.get(normalize(t), {})
                pct_str = f"{pct_entry['pct']}%" if pct_entry.get("pct") else ""
                lines.append(f"| {i} | {a} | {t} | {r} | {btags} | {rt_str} | {pct_str} |")
                total += 1
                # Inline note
                note_key = normalize(t)
                note_val = all_notes.get(note_key, "")
                if note_val:
                    lines.append(f"| | | > _{note_val[:80]}_ | | | | |")
            lines.append("")

        # Trello stats
        if self.trello:
            lm = self._lmap()
            sc = defaultdict(int)
            for c in self.trello.get_cards():
                sc[lm.get(c["idList"], "")] += 1
            lines.append("## Статус (Trello)")
            lines.append("")
            for lst in self.trello.get_lists():
                n = lst["name"]
                cnt = sc.get(n, 0)
                if cnt:
                    lines.append(f"- **{n}**: {cnt}")
            lines.append("")

        # Collections
        if colls:
            lines.append("## Коллекции")
            lines.append("")
            for c in colls:
                lines.append(f"### {c['name']}")
                if c.get("desc"):
                    lines.append(f"_{c['desc']}_")
                lines.append("")
                for bkey in c.get("books", []):
                    lines.append(f"- {bkey}")
                lines.append("")

        # Quotes
        if quotes:
            lines.append("## Цитаты")
            lines.append("")
            for q in quotes:
                lines.append(f'> "{q["text"]}"')
                lines.append(f'> — {q.get("author", "")} «{q["book"]}»')
                lines.append("")

        # Achievements
        badges = compute_achievements(hist, books)
        if badges:
            lines.append("## Достижения")
            lines.append("")
            for b in badges:
                lines.append(f"- {b['icon']} **{b['name']}** — {b['desc']}")
            lines.append("")

        # Stats
        vel = reading_velocity(hist)
        lines.append("## Статистика")
        lines.append("")
        lines.append(f"- **Всего книг**: {total}")
        if vel.get("total"):
            lines.append(f"- **Прослушано**: {vel['total']}")
            lines.append(f"- **Темп**: {vel['avg_per_month']:.1f} книг/мес")
            lines.append(f"- **Лучший месяц**: {vel['best_month_count']} ({vel['best_month']})")
        rated = [h for h in hist if h["action"] == "done" and h.get("rating")]
        if rated:
            avg_r = sum(h["rating"] for h in rated) / len(rated)
            lines.append(f"- **Средняя оценка**: {avg_r:.1f}/5 ({len(rated)} оценок)")
        lines.append("")

        lines.append("---")
        lines.append(f"Всего книг: **{total}**")

        try:
            out_path.write_text("\n".join(lines), encoding="utf-8")
        except OSError as e:
            console.print(f"\n[red]Ошибка записи: {e}[/red]")
            return
        console.print(f"\n[green]Экспортировано: {out_path}[/green]")
        console.print(f"[dim]{total} книг, {len(CATEGORIES)} категорий, "
                      f"{len(colls)} коллекций, {len(quotes)} цитат[/dim]")
        clipboard_copy(str(out_path))

    # ── Автор ─────────────────────────────────────────────────────────────────

    def screen_author(self):
        books = self._books()
        author_cnt = Counter()
        for b in books:
            a = b["author"].strip()
            if a:
                author_cnt[a] += 1

        if not author_cnt:
            console.print("\n[dim]Нет авторов.[/dim]"); return

        # Let user pick an author
        choices = [Choice(a, name=f"{a} ({n})") for a, n in author_cnt.most_common()]
        author = inquirer.fuzzy(
            message="Автор:", max_height="70%",
            choices=choices,
        ).execute()

        # Show all books by this author
        author_books = [b for b in books if b["author"].strip() == author]
        console.print(f"\n[bold]{author}[/bold] — {len(author_books)} книг\n")

        tbl = Table(show_lines=False, padding=(0, 1))
        tbl.add_column("#", style="dim", width=3)
        tbl.add_column("Название", max_width=45)
        tbl.add_column("Категория", style="dim", width=14)
        tbl.add_column("Чтец", style="dim", max_width=20)
        tbl.add_column("Статус", width=12)

        for i, b in enumerate(sorted(author_books, key=lambda x: x["title"]), 1):
            status = ""
            if self.trello:
                card, score = best_card_match(b["author"], b["title"], self.trello.get_cards())
                if card and score > MATCH_LIKELY:
                    ln = self.trello.list_name(card["idList"])
                    style = STATUS_STYLE.get(ln, "white")
                    status = f"[{style}]{ln}[/]"
            tbl.add_row(str(i), b["title"], b["category"], b.get("reader") or "", status)
        console.print(tbl)

        # Also show Trello cards by this author that aren't on disk
        if self.trello:
            trello_only = []
            for c in self.trello.get_cards():
                ca, ct, _ = parse_folder_name(c["name"])
                if ca.strip().lower() == author.lower():
                    if not find_book_on_disk(c["name"], books):
                        ln = self.trello.list_name(c["idList"])
                        trello_only.append((c, ln))
            if trello_only:
                console.print(f"\n[dim]Только в Trello:[/dim]")
                for c, ln in trello_only:
                    style = STATUS_STYLE.get(ln, "white")
                    console.print(f"  [{style}]{ln}[/] {c['name']}")

    # ── Помощь ────────────────────────────────────────────────────────────────

    def screen_help(self):
        console.print()
        help_text = """[bold]Основные:[/bold]
  [cyan]status[/cyan]        — дашборд с прогрессом и быстрыми действиями
  [cyan]search[/cyan]        — поиск с тегами, заметками, хронологией
  [cyan]filter[/cyan]        — мульти-фильтр (5 критериев одновременно)
  [cyan]pick[/cyan]          — умная рекомендация с выбором настроения

[bold]Слушаю:[/bold]
  [cyan]listen[/cyan]        — начать слушать
  [cyan]phone[/cyan]         — на телефон
  [cyan]pause[/cyan]         — на паузу
  [cyan]done[/cyan]          — прослушано (оценка + цитата + похожие)
  [cyan]relisten[/cyan]      — вернуть из прочитанных
  [cyan]progress[/cyan]      — обновить % прогресса

[bold]Управление:[/bold]
  [cyan]inbox[/cyan]         — разобрать dl/ (автосортировка)
  [cyan]sync[/cyan]          — синхронизация Trello <-> диск <-> CSV
  [cyan]move[/cyan] [cyan]rename[/cyan] [cyan]reject[/cyan] [cyan]cleanup[/cyan] [cyan]bulk[/cyan]

[bold]Организация:[/bold]
  [cyan]collections[/cyan]   — тематические подборки
  [cyan]tags[/cyan]          — пользовательские теги
  [cyan]quotes[/cyan]        — коллекция цитат
  [cyan]plans[/cyan]         — планы чтения с дедлайнами
  [cyan]queue[/cyan]         — приоритизация очереди

[bold]Аналитика:[/bold]
  [cyan]dashboard[/cyan]     — недельный дашборд
  [cyan]stats[/cyan]         — статистика, темп, прогнозы
  [cyan]analytics[/cyan]     — хитмап, тренды, распределения
  [cyan]achievements[/cyan]  — 15+ достижений и бейджей
  [cyan]session[/cyan]       — сессии прослушивания (таймер)

[bold]Обзор:[/bold]
  [cyan]similar[/cyan]       — движок похожих книг
  [cyan]compare[/cyan]       — сравнение двух книг бок о бок
  [cyan]discover[/cyan]      — поиск новых книг (Google Books)
  [cyan]author[/cyan]        — все книги одного автора
  [cyan]timeline[/cyan]      — полная хронология книги

[bold]Система:[/bold]
  [cyan]backup[/cyan]        — бэкап / восстановление данных
  [cyan]export[/cyan]        — каталог в markdown (с тегами и оценками)
  [cyan]config[/cyan]        — настройки, цели, планы

[bold]Данные:[/bold] 10 файлов (_config, _трекер, _history, _tags,
  _collections, _notes, _progress, _quotes, _trello_cache, _каталог)

[bold]Рабочий процесс:[/bold]
  Скачай -> [cyan]dl/[/cyan] -> [cyan]inbox[/cyan] -> Trello + категория
  -> [cyan]pick[/cyan]/[cyan]listen[/cyan] -> [cyan]progress[/cyan] -> [cyan]done[/cyan] (оценка + цитата)
  -> [cyan]similar[/cyan] -> следующая книга -> [cyan]achievements[/cyan]"""

        console.print(Panel(help_text, title="Справка — 40 команд", border_style="cyan"))

    # ── Настройки ─────────────────────────────────────────────────────────────

    def screen_config(self):
        config = load_config()
        console.print(f"\n[bold]Текущие настройки:[/bold]")
        console.print(f"  API Key: [cyan]{config.get('trello_api_key', '')[:8]}...[/cyan]" if config.get("trello_api_key") else "  API Key: [red]не задан[/red]")
        console.print(f"  Token:   [cyan]{config.get('trello_token', '')[:8]}...[/cyan]" if config.get("trello_token") else "  Token:   [red]не задан[/red]")
        console.print(f"  Board:   [dim]{config.get('board_id', '')}[/dim]")
        console.print(f"  Цель:    [cyan]{config.get('yearly_goal', 0)}[/cyan] книг/год" if config.get("yearly_goal") else "  Цель:    [dim]не задана[/dim]")

        act = inquirer.select(message="", choices=[
            Choice("key", name="Изменить API Key"),
            Choice("token", name="Изменить Token"),
            Choice("goal", name="Установить цель (книг/год)"),
            Choice("open", name="Открыть _config.json"),
            Choice("back", name="Назад"),
        ], default="back").execute()

        if act == "back": return
        if act == "open":
            open_in_explorer(CONFIG_PATH); return
        if act == "key":
            val = inquirer.text(message="API Key:", default=config.get("trello_api_key", "")).execute()
            config["trello_api_key"] = val.strip()
        elif act == "token":
            val = inquirer.text(message="Token:", default=config.get("trello_token", "")).execute()
            config["trello_token"] = val.strip()
        elif act == "goal":
            val = inquirer.text(message="Книг в год:", default=str(config.get("yearly_goal", 12))).execute()
            try:
                config["yearly_goal"] = int(val)
            except ValueError:
                console.print("[red]Введите число[/red]"); return

        _safe_json_write(CONFIG_PATH, config, indent=2)
        console.print("[green]Сохранено[/green]")

    # ── Поиск ─────────────────────────────────────────────────────────────────

    def screen_search(self):
        books = self.lib.find_all_books()
        choices = [Choice(("disk", b), name=f"{b['author']} - {b['title']}" if b["author"] else b["title"])
                   for b in books]
        # Add Trello-only cards
        if self.trello:
            for c in self.trello.get_cards():
                if not find_book_on_disk(c["name"], books):
                    ln = self.trello.list_name(c["idList"])
                    choices.append(Choice(("trello", c), name=f"[Trello:{ln}] {c['name']}"))

        result = inquirer.fuzzy(
            message="Поиск:", max_height="70%",
            choices=choices,
        ).execute()

        if result[0] == "trello":
            # Trello-only card view
            card = result[1]
            ln = self.trello.list_name(card["idList"])
            style = STATUS_STYLE.get(ln, "white")
            labels = ", ".join(self.trello.label_names(card))
            console.print(f"\n  [bold]Карточка:[/bold]  {card['name']}")
            console.print(f"  [bold]Статус:[/bold]    [{style}]{ln}[/]")
            if labels:
                console.print(f"  [bold]Метки:[/bold]     [dim]{labels}[/dim]")
            if card.get("desc"):
                console.print(f"  [bold]Описание:[/bold]  [dim]{card['desc'][:100]}[/dim]")
            console.print(f"\n  [yellow]Нет на диске[/yellow]")
            return

        sel = result[1]

        console.print()
        console.print(f"  [bold]Автор:[/bold]     {sel['author'] or '—'}")
        console.print(f"  [bold]Название:[/bold]  {sel['title']}")
        console.print(f"  [bold]Чтец:[/bold]      {sel['reader'] or '—'}")
        console.print(f"  [bold]Категория:[/bold] {sel['category']}")

        trello_card = None
        if self.trello:
            card, score = best_card_match(sel["author"], sel["title"], self.trello.get_cards())
            if card and score > MATCH_LIKELY:
                trello_card = card
                ln = self.trello.list_name(card["idList"])
                style = STATUS_STYLE.get(ln, "white")
                labels = ", ".join(self.trello.label_names(card))
                console.print(f"  [bold]Trello:[/bold]    [{style}]{ln}[/]  [dim]{labels}[/dim]")

        p = str(sel["path"])
        size = folder_size_mb(sel["path"])
        mp3 = count_mp3(sel["path"])
        dur = estimate_duration_hours(sel["path"])
        console.print(f"  [bold]Путь:[/bold]      {p}")
        dur_str = f", ~{fmt_duration(dur)}" if dur else ""
        console.print(f"  [bold]Размер:[/bold]    {size:.0f} МБ, {mp3} файлов{dur_str}")

        # Show note if exists
        existing_note = note_get(sel["title"])
        if existing_note:
            console.print(f"  [bold]Заметка:[/bold]   [italic]{existing_note}[/italic]")

        # Show tags
        book_tags = tags_get(sel["title"])
        if book_tags:
            console.print(f"  [bold]Теги:[/bold]      [cyan]{', '.join(book_tags)}[/cyan]")

        # Show rating from history
        hist = self._history()
        for h in reversed(hist):
            if h["action"] == "done" and h.get("rating") and fuzzy_match(h["book"], sel["folder"]) > MATCH_STRONG:
                console.print(f"  [bold]Оценка:[/bold]    [yellow]{_format_stars(h['rating'])}[/yellow]")
                break

        # Book timeline (history for this book)
        book_hist = [h for h in hist if fuzzy_match(h.get("book", ""), sel["folder"]) > MATCH_STRONG]
        if book_hist:
            console.print(f"  [bold]Хронология:[/bold]")
            for h in book_hist[-5:]:
                console.print(f"    [dim]{h['ts'][:16]}[/dim]  {h['action']}  {h.get('detail','')}")

        clipboard_copy(p)
        console.print("  [dim](путь -> буфер)[/dim]")

        # Context-aware actions (deduplicated via dict, first wins)
        actions_set = []
        if trello_card and self.trello:
            ln = self.trello.list_name(trello_card["idList"])
            if ln in ("Прочесть", "В телефоне"):
                actions_set.append(("phone", "На телефон"))
                actions_set.append(("listen", "Начать слушать"))
            if ln in ("В процессе", "В телефоне"):
                actions_set.append(("done", "Прослушано"))
                actions_set.append(("pause", "На паузу"))
            if ln == "На Паузе":
                actions_set.append(("listen", "Продолжить"))
                actions_set.append(("done", "Прослушано"))
        seen = {}
        for val, name in actions_set:
            if val not in seen:
                seen[val] = name
        unique_choices = [Choice("open", name="Открыть папку")]
        unique_choices += [Choice(v, name=n) for v, n in seen.items()]
        unique_choices.append(Choice("move", name="Переместить (категория)"))
        unique_choices.append(Choice("note", name="Заметка"))
        unique_choices.append(Choice("tag", name="Теги"))
        unique_choices.append(Choice("files", name="Список файлов"))
        unique_choices.append(Choice("delete", name="Удалить с диска"))
        unique_choices.append(Choice("back", name="Назад"))

        act = inquirer.select(message="", choices=unique_choices, default="back").execute()

        if act == "open":
            open_in_explorer(sel["path"])
        elif act == "move":
            new_cat = inquirer.select(message="Категория:",
                choices=[c for c in CATEGORIES if c != sel["category"]]).execute()
            self.lib.move_to_category(sel["path"], new_cat)
            console.print(f"  [green]-> {new_cat}[/green]")
            if self.trello and trello_card:
                lbl = FOLDER_TO_LABEL.get(new_cat)
                if lbl: self.trello.add_label(trello_card["id"], lbl)
                self._sync_csv()
        elif act == "note":
            current = note_get(sel["title"])
            new_note = inquirer.text(message="Заметка:", default=current).execute()
            note_set(sel["title"], new_note)
            if new_note:
                console.print(f"  [green]Заметка сохранена[/green]")
            else:
                console.print(f"  [dim]Заметка удалена[/dim]")
        elif act == "tag":
            current = tags_get(sel["title"])
            all_t = tags_all()
            if all_t:
                console.print(f"  [dim]Существующие теги: {', '.join(all_t)}[/dim]")
            new_tags = inquirer.text(
                message="Теги (через запятую):",
                default=", ".join(current),
            ).execute()
            tags_set(sel["title"], [t.strip() for t in new_tags.split(",") if t.strip()])
            console.print(f"  [green]Теги обновлены[/green]")
        elif act == "files":
            mp3s = sorted(sel["path"].rglob("*.mp3"))
            if not mp3s:
                console.print("  [dim]Нет MP3 файлов[/dim]")
            else:
                tbl = Table(show_lines=False, padding=(0, 1))
                tbl.add_column("#", style="dim", width=3)
                tbl.add_column("Файл", max_width=55)
                tbl.add_column("МБ", justify="right", style="cyan", width=6)
                for i, f in enumerate(mp3s, 1):
                    tbl.add_row(str(i), f.name[:55], f"{f.stat().st_size / 1024 / 1024:.1f}")
                console.print(tbl)
                console.print(f"  [dim]{len(mp3s)} файлов[/dim]")
        elif act == "delete":
            size = folder_size_mb(sel["path"])
            if inquirer.confirm(message=f"Удалить {sel['folder']} ({size:.0f} МБ)?", default=False).execute():
                shutil.rmtree(sel["path"])
                console.print(f"  [red]Удалено: {sel['folder']}[/red]")
                self._history_add("delete", sel["folder"], f"{size:.0f} МБ")
                self._invalidate()
        elif act in ("phone", "listen", "done", "pause") and trello_card and self.trello:
            target = {"phone": "В телефоне", "listen": "В процессе", "done": "Прочитано", "pause": "На Паузе"}[act]
            self._move_with_history(trello_card, target, act, detail="(search)")
            console.print(f"  [green]-> {target}[/green]")
            if act == "listen": open_in_explorer(sel["path"])


    # ── Умный фильтр ────────────────────────────────────────────────────────

    def screen_filter(self):
        books = self._books()
        console.print("\n[bold]Умный фильтр[/bold]\n")

        # Category
        cat_choices = [Choice(None, name="Все")] + [Choice(c, name=c) for c in CATEGORIES]
        category = inquirer.select(message="Категория:", choices=cat_choices, default=None).execute()

        # Status (if Trello)
        status_filter = None
        if self.trello:
            status_choices = [Choice(None, name="Все")]
            for lst in self.trello.get_lists():
                status_choices.append(Choice(lst["name"], name=lst["name"]))
            status_filter = inquirer.select(message="Статус:", choices=status_choices, default=None).execute()

        # Rating
        rating_filter = inquirer.select(message="Оценка:", choices=[
            Choice(None, name="Все"),
            Choice("rated", name="С оценкой"),
            Choice("unrated", name="Без оценки"),
            Choice("5", name="5 звёзд"),
            Choice("4+", name="4+ звезды"),
        ], default=None).execute()

        # Tags
        all_t = tags_all()
        tag_filter = None
        if all_t:
            tag_choices = [Choice(None, name="Все")] + [Choice(t, name=t) for t in all_t]
            tag_filter = inquirer.select(message="Тег:", choices=tag_choices, default=None).execute()

        # Duration
        dur_filter = inquirer.select(message="Длительность:", choices=[
            Choice(None, name="Все"),
            Choice("short", name="< 5 часов"),
            Choice("medium", name="5-15 часов"),
            Choice("long", name="> 15 часов"),
        ], default=None).execute()

        # Apply category filter
        result = list(books)
        if category:
            result = [b for b in result if b["category"] == category]

        book_ratings = self._book_ratings()

        # Apply rating filter
        if rating_filter:
            filtered = []
            for b in result:
                key = normalize(b["folder"])
                r = book_ratings.get(key, 0)
                if rating_filter == "rated" and r > 0:
                    filtered.append(b)
                elif rating_filter == "unrated" and r == 0:
                    filtered.append(b)
                elif rating_filter == "5" and r == 5:
                    filtered.append(b)
                elif rating_filter == "4+" and r >= 4:
                    filtered.append(b)
            result = filtered

        # Apply tag filter
        if tag_filter:
            result = [b for b in result if tag_filter in tags_get(b["title"])]

        # Apply duration filter
        if dur_filter:
            filtered = []
            for b in result:
                d = estimate_duration_hours(b["path"])
                if d is None:
                    continue
                if dur_filter == "short" and d < 5:
                    filtered.append(b)
                elif dur_filter == "medium" and 5 <= d <= 15:
                    filtered.append(b)
                elif dur_filter == "long" and d > 15:
                    filtered.append(b)
            result = filtered

        # Apply status filter
        if status_filter and self.trello:
            cards = self.trello.get_cards()
            lid = self.trello.list_id(status_filter)
            filtered = []
            for b in result:
                card, score = best_card_match(b["author"], b["title"], cards)
                if card and score > MATCH_LIKELY and card["idList"] == lid:
                    filtered.append(b)
            result = filtered

        if not result:
            console.print("\n[dim]Ничего не найдено.[/dim]")
            return

        tbl = Table(title=f"Результат ({len(result)})", show_lines=False, padding=(0, 1))
        tbl.add_column("#", style="dim", width=3)
        tbl.add_column("Автор", max_width=22)
        tbl.add_column("Название", max_width=32)
        tbl.add_column("Кат.", style="dim", width=14)
        tbl.add_column("Статус", width=12)
        tbl.add_column("", width=5)
        tbl.add_column("Теги", style="dim", max_width=15)

        for i, b in enumerate(sorted(result, key=lambda x: (x["category"], x["author"].lower())), 1):
            status = ""
            if self.trello:
                card, score = best_card_match(b["author"], b["title"], self.trello.get_cards())
                if card and score > MATCH_LIKELY:
                    ln = self.trello.list_name(card["idList"])
                    style = STATUS_STYLE.get(ln, "white")
                    status = f"[{style}]{ln}[/]"
            rating = book_ratings.get(normalize(b["folder"]), 0)
            stars_str = f"[yellow]{_format_stars(rating)}[/]" if rating else ""
            btags = tags_get(b["title"])
            tbl.add_row(str(i), b["author"][:22], b["title"][:32], b["category"],
                         status, stars_str, ", ".join(btags)[:15])
        console.print(tbl)

    # ── Теги ──────────────────────────────────────────────────────────────────

    def screen_tags(self):
        books = self._books()
        all_t = tags_all()

        console.print()
        if all_t:
            console.print(f"[bold]Существующие теги:[/bold] {', '.join(all_t)}\n")
            # Show tag cloud with counts
            tag_counts = Counter()
            data = tags_load()
            for ts in data.values():
                for t in ts:
                    tag_counts[t] += 1
            for t, n in tag_counts.most_common():
                console.print(f"  [cyan]{t}[/cyan] ({n})")
        else:
            console.print("[dim]Тегов пока нет.[/dim]\n")

        act = inquirer.select(message="", choices=[
            Choice("add", name="Добавить теги к книге"),
            Choice("browse", name="Показать книги по тегу"),
            Choice("bulk", name="Массовое тегирование"),
            Choice("back", name="Назад"),
        ], default="add" if not all_t else "browse").execute()

        if act == "back":
            return
        elif act == "add":
            sel = inquirer.fuzzy(
                message="Книга:", max_height="70%",
                choices=[Choice(b, name=f"{b['author']} - {b['title']}" if b["author"] else b["title"])
                         for b in books],
            ).execute()
            current = tags_get(sel["title"])
            if all_t:
                console.print(f"  [dim]Все теги: {', '.join(all_t)}[/dim]")
            console.print(f"  [dim]Текущие: {', '.join(current) if current else 'нет'}[/dim]")
            new_tags = inquirer.text(
                message="Теги (через запятую):",
                default=", ".join(current),
            ).execute()
            tags_set(sel["title"], [t.strip() for t in new_tags.split(",") if t.strip()])
            console.print(f"  [green]Теги обновлены[/green]")

        elif act == "browse":
            if not all_t:
                console.print("[dim]Нет тегов.[/dim]")
                return
            tag = inquirer.select(
                message="Тег:", choices=[Choice(t, name=t) for t in all_t],
            ).execute()
            # Find all books with this tag
            data = tags_load()
            tagged_books = []
            for b in books:
                key = normalize(b["title"])
                if key in data and tag in data[key]:
                    tagged_books.append(b)
            if not tagged_books:
                console.print(f"[dim]Нет книг с тегом «{tag}».[/dim]")
                return
            console.print(f"\n[bold]Книги с тегом «{tag}» ({len(tagged_books)}):[/bold]\n")
            for i, b in enumerate(tagged_books, 1):
                console.print(f"  {i}. {b['author']} - {b['title']}" if b['author'] else f"  {i}. {b['title']}")

        elif act == "bulk":
            tag_name = inquirer.text(message="Тег для добавления:").execute().strip()
            if not tag_name:
                return
            selected = inquirer.fuzzy(
                message="Выберите книги:", max_height="70%", multiselect=True,
                choices=[Choice(b, name=f"[{b['category']}] {b['author']} - {b['title']}" if b["author"] else f"[{b['category']}] {b['title']}")
                         for b in books],
            ).execute()
            if not selected:
                return
            for b in selected:
                current = tags_get(b["title"])
                if tag_name not in current:
                    current.append(tag_name)
                    tags_set(b["title"], current)
            console.print(f"[green]Тег «{tag_name}» добавлен к {len(selected)} книгам[/green]")

    # ── Коллекции ─────────────────────────────────────────────────────────────

    def screen_collections(self):
        colls = collections_load()
        books = self._books()

        console.print()
        if colls:
            tbl = Table(title="Коллекции", show_lines=False, padding=(0, 1))
            tbl.add_column("#", style="dim", width=3)
            tbl.add_column("Название", style="bold", max_width=30)
            tbl.add_column("Книг", justify="right", style="cyan", width=5)
            tbl.add_column("Описание", style="dim", max_width=40)
            for i, c in enumerate(colls, 1):
                tbl.add_row(str(i), c["name"], str(len(c.get("books", []))), c.get("desc", ""))
            console.print(tbl)
        else:
            console.print("[dim]Коллекций пока нет.[/dim]")

        act = inquirer.select(message="", choices=[
            Choice("create", name="Создать коллекцию"),
            Choice("view", name="Открыть коллекцию") if colls else Choice("_none", name="[dim]Нет коллекций[/dim]"),
            Choice("edit", name="Редактировать") if colls else Choice("_none2", name="[dim]—[/dim]"),
            Choice("delete", name="Удалить коллекцию") if colls else Choice("_none3", name="[dim]—[/dim]"),
            Choice("back", name="Назад"),
        ], default="create" if not colls else "view").execute()

        if act == "back" or act.startswith("_"):
            return

        elif act == "create":
            name = inquirer.text(message="Название:").execute().strip()
            if not name:
                return
            desc = inquirer.text(message="Описание (необязательно):", default="").execute().strip()
            selected = inquirer.fuzzy(
                message="Книги:", max_height="70%", multiselect=True,
                choices=[Choice(normalize(b["title"]),
                                name=f"{b['author']} - {b['title']}" if b["author"] else b["title"])
                         for b in books],
            ).execute()
            colls.append({"name": name, "desc": desc, "books": selected or [], "created": datetime.now().isoformat(timespec="seconds")})
            collections_save(colls)
            console.print(f"[green]Коллекция «{name}» создана ({len(selected or [])} книг)[/green]")

        elif act == "view":
            sel = inquirer.select(
                message="Коллекция:",
                choices=[Choice(i, name=c["name"]) for i, c in enumerate(colls)],
            ).execute()
            coll = colls[sel]
            console.print(f"\n[bold]{coll['name']}[/bold]")
            if coll.get("desc"):
                console.print(f"[dim]{coll['desc']}[/dim]")
            console.print()
            if not coll.get("books"):
                console.print("[dim]Пусто[/dim]")
                return
            found = 0
            for bkey in coll["books"]:
                for b in books:
                    if normalize(b["title"]) == bkey:
                        status = ""
                        if self.trello:
                            card, score = best_card_match(b["author"], b["title"], self.trello.get_cards())
                            if card and score > MATCH_LIKELY:
                                ln = self.trello.list_name(card["idList"])
                                style = STATUS_STYLE.get(ln, "white")
                                status = f" [{style}]{ln}[/]"
                        console.print(f"  {b['author']} - {b['title']}{status}" if b["author"] else f"  {b['title']}{status}")
                        found += 1
                        break
            if found < len(coll["books"]):
                console.print(f"\n[dim]{len(coll['books']) - found} книг не найдено на диске[/dim]")

        elif act == "edit":
            sel = inquirer.select(
                message="Редактировать:",
                choices=[Choice(i, name=c["name"]) for i, c in enumerate(colls)],
            ).execute()
            coll = colls[sel]
            edit_act = inquirer.select(message="", choices=[
                Choice("add", name="Добавить книги"),
                Choice("remove", name="Убрать книги"),
                Choice("rename", name="Переименовать"),
            ], default="add").execute()
            if edit_act == "add":
                existing = set(coll.get("books", []))
                available = [b for b in books if normalize(b["title"]) not in existing]
                if not available:
                    console.print("[dim]Все книги уже в коллекции.[/dim]")
                    return
                selected = inquirer.fuzzy(
                    message="Добавить:", max_height="70%", multiselect=True,
                    choices=[Choice(normalize(b["title"]),
                                    name=f"{b['author']} - {b['title']}" if b["author"] else b["title"])
                             for b in available],
                ).execute()
                if selected:
                    coll["books"].extend(selected)
                    collections_save(colls)
                    console.print(f"[green]+{len(selected)} книг[/green]")
            elif edit_act == "remove":
                if not coll.get("books"):
                    console.print("[dim]Пусто[/dim]")
                    return
                to_remove = inquirer.fuzzy(
                    message="Убрать:", max_height="70%", multiselect=True,
                    choices=[Choice(bk, name=bk) for bk in coll["books"]],
                ).execute()
                if to_remove:
                    coll["books"] = [bk for bk in coll["books"] if bk not in to_remove]
                    collections_save(colls)
                    console.print(f"[green]Убрано: {len(to_remove)}[/green]")
            elif edit_act == "rename":
                new_name = inquirer.text(message="Новое название:", default=coll["name"]).execute().strip()
                if new_name:
                    coll["name"] = new_name
                    collections_save(colls)
                    console.print("[green]Переименовано[/green]")

        elif act == "delete":
            sel = inquirer.select(
                message="Удалить:",
                choices=[Choice(i, name=c["name"]) for i, c in enumerate(colls)],
            ).execute()
            name = colls[sel]["name"]
            if inquirer.confirm(message=f"Удалить коллекцию «{name}»?", default=False).execute():
                colls.pop(sel)
                collections_save(colls)
                console.print(f"[red]Коллекция «{name}» удалена[/red]")

    # ── Достижения ────────────────────────────────────────────────────────────

    def screen_achievements(self):
        hist = self._history()
        books = self._books()
        badges = compute_achievements(hist, books)

        console.print()
        if not badges:
            console.print("[dim]Пока нет достижений. Начни слушать книги![/dim]")
            return

        console.print(f"[bold]Достижения ({len(badges)}):[/bold]\n")
        tbl = Table(show_lines=False, padding=(0, 1), show_header=False)
        tbl.add_column("", width=3)
        tbl.add_column("", style="bold", max_width=25)
        tbl.add_column("", style="dim", max_width=50)
        for b in badges:
            tbl.add_row(b["icon"], b["name"], b["desc"])
        console.print(tbl)

        # Upcoming badges
        done_count = sum(1 for h in hist if h["action"] == "done")
        upcoming = []
        milestones = [5, 10, 25, 50, 100]
        for m in milestones:
            if done_count < m:
                upcoming.append(f"Ещё {m - done_count} до {m} книг")
                break
        # O(n) category check
        book_by_norm = {}
        for b in books:
            book_by_norm[normalize(b["folder"])] = b
            book_by_norm[normalize(b["title"])] = b
        cats_done = set()
        for h in hist:
            if h["action"] == "done":
                b = book_by_norm.get(normalize(h["book"]))
                if b:
                    cats_done.add(b["category"])
        if len(cats_done) < len(CATEGORIES):
            missing = [c for c in CATEGORIES if c not in cats_done]
            upcoming.append(f"Осталось: {', '.join(missing)}")

        if upcoming:
            console.print(f"\n[bold]На горизонте:[/bold]")
            for u in upcoming:
                console.print(f"  [dim]{u}[/dim]")

    # ── Массовые операции ─────────────────────────────────────────────────────

    def screen_bulk(self):
        if not self._ok():
            return
        books = self._books()

        act = inquirer.select(message="Массовая операция:", choices=[
            Choice("status", name="Изменить статус"),
            Choice("category", name="Переместить категорию"),
            Choice("tag", name="Добавить тег"),
            Choice("enrich", name="Обогатить карточки"),
            Choice("back", name="Назад"),
        ], default="status").execute()

        if act == "back":
            return

        elif act == "status":
            cards = self.trello.get_cards()
            lm = self._lmap()
            selected = inquirer.fuzzy(
                message="Выберите книги:", max_height="70%", multiselect=True,
                choices=[Choice(c, name=f"[{lm.get(c['idList'],'')}] {c['name']}") for c in cards],
            ).execute()
            if not selected:
                return
            target = inquirer.select(message="Новый статус:", choices=[
                Choice(lst["name"], name=lst["name"]) for lst in self.trello.get_lists()
            ]).execute()
            if not inquirer.confirm(message=f"{len(selected)} книг -> {target}?", default=True).execute():
                return
            with console.status(f"[bold]Перемещаю {len(selected)} карточек..."):
                for c in selected:
                    self.trello.move_card(c["id"], target)
                    self._history_add("bulk", c["name"], f"-> {target}")
            console.print(f"[green]{len(selected)} книг -> {target}[/green]")
            self._sync_csv()

        elif act == "category":
            selected = inquirer.fuzzy(
                message="Выберите книги:", max_height="70%", multiselect=True,
                choices=[Choice(b, name=f"[{b['category']}] {b['author']} - {b['title']}" if b["author"]
                         else f"[{b['category']}] {b['title']}") for b in books],
            ).execute()
            if not selected:
                return
            new_cat = inquirer.select(message="Новая категория:", choices=CATEGORIES).execute()
            moved = 0
            for b in selected:
                if b["category"] != new_cat:
                    self.lib.move_to_category(b["path"], new_cat)
                    moved += 1
            console.print(f"[green]Перемещено: {moved}[/green]")
            if moved:
                self._invalidate()
                if self.trello:
                    self._sync_csv()

        elif act == "tag":
            tag_name = inquirer.text(message="Тег:").execute().strip()
            if not tag_name:
                return
            selected = inquirer.fuzzy(
                message="Книги:", max_height="70%", multiselect=True,
                choices=[Choice(b, name=f"{b['author']} - {b['title']}" if b["author"] else b["title"])
                         for b in books],
            ).execute()
            if not selected:
                return
            for b in selected:
                current = tags_get(b["title"])
                if tag_name not in current:
                    current.append(tag_name)
                    tags_set(b["title"], current)
            console.print(f"[green]Тег «{tag_name}» -> {len(selected)} книг[/green]")

        elif act == "enrich":
            cards = self.trello.get_cards()
            empty = [c for c in cards if not c.get("desc", "").strip()]
            if not empty:
                console.print("[dim]Все карточки обогащены.[/dim]")
                return
            console.print(f"[dim]{len(empty)} карточек без описания[/dim]")
            if not inquirer.confirm(message=f"Обогатить {len(empty)} карточек?", default=True).execute():
                return
            enriched = 0
            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                          BarColumn(), TaskProgressColumn(), console=console) as prog:
                task = prog.add_task("Обогащаю", total=len(empty))
                for c in empty:
                    b = find_book_on_disk(c["name"], books)
                    if b:
                        self._enrich_card(c["id"], b["path"])
                        enriched += 1
                    prog.advance(task)
            console.print(f"[green]Обогащено: {enriched}[/green]")

    # ── Хронология книги ──────────────────────────────────────────────────────

    def screen_timeline(self):
        """Show full timeline for a specific book across all history."""
        sel = self._select_book("Книга:")
        if not sel: return

        hist = self._history()
        book_hist = [h for h in hist if fuzzy_match(h.get("book", ""), sel["folder"]) > MATCH_LIKELY
                     or fuzzy_match(h.get("book", ""), sel["title"]) > MATCH_LIKELY]

        console.print(f"\n[bold]{sel['author']} - {sel['title']}[/bold]" if sel['author'] else f"\n[bold]{sel['title']}[/bold]")
        console.print(f"[dim]{sel['category']} | {sel['path']}[/dim]\n")

        if not book_hist:
            console.print("[dim]Нет истории для этой книги.[/dim]")
        else:
            # Journey visualization
            for h in book_hist:
                label = ACTION_LABELS.get(h["action"], h["action"])
                style = ACTION_STYLES.get(h["action"], "white")
                detail = f"  {h.get('detail', '')}" if h.get("detail") else ""
                rating = ""
                if h.get("rating"):
                    rating = f"  [yellow]{_format_stars(h['rating'])}[/yellow]"
                console.print(f"  [dim]{h['ts'][:10]}[/dim]  [{style}]{chr(9679)} {label}[/]{detail}{rating}")
            # Duration summary
            if len(book_hist) >= 2:
                try:
                    d0 = datetime.fromisoformat(book_hist[0]["ts"])
                    d1 = datetime.fromisoformat(book_hist[-1]["ts"])
                    span = (d1 - d0).days
                    console.print(f"  [dim]{'─' * 12} {span} дней {'─' * 12}[/dim]"  )
                except Exception:
                    pass

        # Additional info
        note = note_get(sel["title"])
        if note:
            console.print(f"\n[bold]Заметка:[/bold] [italic]{note}[/italic]")
        btags = tags_get(sel["title"])
        if btags:
            console.print(f"[bold]Теги:[/bold] [cyan]{', '.join(btags)}[/cyan]")

        # Size and duration
        size = folder_size_mb(sel["path"])
        mp3 = count_mp3(sel["path"])
        dur = estimate_duration_hours(sel["path"])
        console.print(f"\n[dim]{size:.0f} МБ, {mp3} файлов{f', ~{fmt_duration(dur)}' if dur else ''}[/dim]")

    # ── Прогресс чтения ──────────────────────────────────────────────────────

    def screen_progress(self):
        """Update reading progress for active books."""
        if not self._ok():
            return
        cards = self._cards_in("В процессе", "В телефоне")
        if not cards:
            console.print("\n[dim]Нет активных книг.[/dim]")
            return

        console.print("\n[bold]Прогресс чтения:[/bold]\n")
        for c in cards:
            _, ct, _ = parse_folder_name(c["name"])
            pct = progress_get(ct)
            console.print(f"  [cyan]{_progress_bar(pct)}[/cyan] {pct:3d}%  {c['name'][:50]}")

        sel = inquirer.fuzzy(
            message="Обновить прогресс:", max_height="70%",
            choices=[Choice(c, name=c["name"]) for c in cards]
                    + [Choice(None, name="Назад")],
        ).execute()
        if not sel:
            return

        _, ct, _ = parse_folder_name(sel["name"])
        current = progress_get(ct)
        new_pct = inquirer.text(
            message=f"Прогресс (0-100):",
            default=str(current),
        ).execute()
        try:
            pct = int(new_pct)
        except ValueError:
            console.print("[red]Введите число 0-100[/red]")
            return
        note = inquirer.text(message="Заметка (необязательно):", default="").execute().strip()
        progress_set(ct, pct, note)
        console.print(f"\n  [cyan]{_progress_bar(pct)}[/cyan] {pct}%")

        if pct >= 100:
            if inquirer.confirm(message="Отметить как прослушанную?", default=True).execute():
                self.trello.move_card(sel["id"], "Прочитано")
                rating = inquirer.select(
                    message="Оценка:",
                    choices=[Choice(5, name="5"), Choice(4, name="4"), Choice(3, name="3"),
                             Choice(2, name="2"), Choice(1, name="1"), Choice(0, name="Без")],
                    default=4,
                ).execute()
                self._history_add("done", sel["name"], rating=rating)
                console.print(f"[green]{sel['name']} -> Прочитано[/green]")
                self._sync_csv()

    # ── Цитаты ────────────────────────────────────────────────────────────────

    def screen_quotes(self):
        quotes = quotes_load()
        console.print()

        if quotes:
            console.print(f"[bold]Цитаты ({len(quotes)}):[/bold]\n")
            for i, q in enumerate(quotes[-15:], 1):
                console.print(f'  [italic]"{q["text"]}"[/italic]')
                console.print(f"    [dim]— {q.get('author', '')} «{q['book']}»  {q['ts'][:10]}[/dim]\n")
            if len(quotes) > 15:
                console.print(f"  [dim]...и ещё {len(quotes) - 15}[/dim]")
        else:
            console.print("[dim]Цитат пока нет.[/dim]\n")

        act = inquirer.select(message="", choices=[
            Choice("add", name="Добавить цитату"),
            Choice("random", name="Случайная цитата") if quotes else Choice("_n", name="[dim]—[/dim]"),
            Choice("export", name="Экспорт цитат") if quotes else Choice("_n2", name="[dim]—[/dim]"),
            Choice("delete", name="Удалить цитату") if quotes else Choice("_n3", name="[dim]—[/dim]"),
            Choice("back", name="Назад"),
        ], default="add" if not quotes else "random").execute()

        if act == "back" or act.startswith("_"):
            return
        elif act == "add":
            books = self._books()
            sel = inquirer.fuzzy(
                message="Книга:", max_height="70%",
                choices=[Choice(b, name=f"{b['author']} - {b['title']}" if b["author"] else b["title"])
                         for b in books],
            ).execute()
            text = inquirer.text(message="Цитата:").execute().strip()
            if text:
                quotes_add(text, sel["title"], sel["author"])
                console.print("[green]Сохранено[/green]")
        elif act == "random":
            q = random.choice(quotes)
            console.print(f'\n  [bold italic]"{q["text"]}"[/bold italic]')
            console.print(f"  [dim]— {q.get('author', '')} «{q['book']}»[/dim]")
        elif act == "export":
            out = BASE / "_цитаты.md"
            lines = ["# Цитаты из аудиокниг\n"]
            for q in quotes:
                lines.append(f'> "{q["text"]}"')
                lines.append(f'> — {q.get("author", "")} «{q["book"]}»\n')
            out.write_text("\n".join(lines), encoding="utf-8")
            console.print(f"[green]Экспортировано: {out}[/green]")
        elif act == "delete":
            sel = inquirer.select(
                message="Удалить:",
                choices=[Choice(i, name=f'"{q["text"][:50]}" — {q["book"]}') for i, q in enumerate(quotes)]
                        + [Choice(-1, name="Отмена")],
            ).execute()
            if sel >= 0:
                quotes.pop(sel)
                quotes_save(quotes)
                console.print("[green]Удалено[/green]")

    # ── Похожие книги ─────────────────────────────────────────────────────────

    def screen_similar(self):
        sel = self._select_book("Найти похожие на:")
        if not sel: return

        hist = self._history()
        similar = find_similar(sel, self._books(), hist, top_n=8)

        console.print(f"\n[bold]Похожие на «{sel['title']}»:[/bold]\n")
        if not similar:
            console.print("[dim]Не найдено похожих книг.[/dim]")
            return

        tbl = Table(show_lines=False, padding=(0, 1))
        tbl.add_column("#", style="dim", width=3)
        tbl.add_column("Автор", max_width=22)
        tbl.add_column("Название", max_width=35)
        tbl.add_column("Категория", style="dim", width=14)
        tbl.add_column("Совпад.", justify="right", style="cyan", width=7)
        for i, (b, score) in enumerate(similar, 1):
            tbl.add_row(str(i), b["author"][:22], b["title"][:35], b["category"], f"{score:.0f}")
        console.print(tbl)

        # Why similar?
        for b, score in similar[:3]:
            reasons = []
            if b["category"] == sel["category"]:
                reasons.append("категория")
            if b["author"].lower() == sel["author"].lower() and sel["author"]:
                reasons.append("автор")
            shared = set(tags_get(b["title"])) & set(tags_get(sel["title"]))
            if shared:
                reasons.append(f"теги: {', '.join(shared)}")
            if reasons:
                console.print(f"  [dim]{b['title'][:30]}: {', '.join(reasons)}[/dim]")

    # ── Очередь (приоритизация) ───────────────────────────────────────────────

    def screen_queue(self):
        """Manage and reorder the reading queue (Прочесть)."""
        if not self._ok():
            return
        cards = self._cards_in("Прочесть")
        if not cards:
            console.print("\n[dim]Очередь пуста.[/dim]")
            return

        all_books = self._books()

        # Build enriched list
        enriched = []
        for c in cards:
            ca, ct, _ = parse_folder_name(c["name"])
            book = find_book_on_disk(c["name"], all_books)
            cat = self.trello.category(c) or (book["category"] if book else "?")
            dur = estimate_duration_hours(book["path"]) if book else None
            on_disk = bool(book)
            enriched.append({"card": c, "title": ct, "author": ca, "cat": cat,
                             "dur": dur, "on_disk": on_disk})

        console.print(f"\n[bold]Очередь «Прочесть» ({len(enriched)}):[/bold]\n")

        tbl = Table(show_lines=False, padding=(0, 1))
        tbl.add_column("#", style="dim", width=3)
        tbl.add_column("Книга", max_width=45)
        tbl.add_column("Категория", style="dim", width=14)
        tbl.add_column("Длит.", style="dim", width=8)
        tbl.add_column("Диск", width=4)
        for i, e in enumerate(enriched, 1):
            disk = "[green]+[/green]" if e["on_disk"] else "[red]-[/red]"
            dur_s = fmt_duration(e["dur"]) if e["dur"] else ""
            tbl.add_row(str(i), e["card"]["name"][:45], e["cat"], dur_s, disk)
        console.print(tbl)

        act = inquirer.select(message="", choices=[
            Choice("top", name="Поднять в начало очереди"),
            Choice("listen", name="Начать слушать"),
            Choice("phone", name="На телефон"),
            Choice("reject", name="Забраковать"),
            Choice("back", name="Назад"),
        ], default="back").execute()

        if act == "back":
            return
        elif act == "top":
            sel = inquirer.fuzzy(
                message="Какую поднять:", max_height="70%",
                choices=[Choice(e["card"], name=e["card"]["name"]) for e in enriched],
            ).execute()
            # Move to top by setting pos to "top"
            try:
                self.trello._put(f"/cards/{sel['id']}", {"pos": "top"})
                console.print(f"[green]{sel['name']} -> начало очереди[/green]")
            except Exception as ex:
                console.print(f"[red]Ошибка: {ex}[/red]")
        elif act in ("listen", "phone"):
            sel = inquirer.fuzzy(
                message="Книга:", max_height="70%",
                choices=[Choice(e["card"], name=e["card"]["name"]) for e in enriched],
            ).execute()
            target = "В процессе" if act == "listen" else "В телефоне"
            self._move_with_history(sel, target, act)
            console.print(f"[green]{sel['name']} -> {target}[/green]")
            self._find_and_copy(sel["name"])
        elif act == "reject":
            selected = inquirer.fuzzy(
                message="Забраковать:", max_height="70%", multiselect=True,
                choices=[Choice(e["card"], name=e["card"]["name"]) for e in enriched],
            ).execute()
            if selected and inquirer.confirm(message=f"Забраковать {len(selected)} книг?", default=False).execute():
                for c in selected:
                    self._move_with_history(c, "Забраковано", "reject", sync=False)
                self._sync_csv()
                console.print(f"[red]Забраковано: {len(selected)}[/red]")

    # ── Аналитика (глубокая) ──────────────────────────────────────────────────

    def screen_analytics(self):
        hist = self._history()
        books = self._books()
        done = [h for h in hist if h["action"] == "done"]

        console.print("\n[bold]Глубокая аналитика[/bold]\n")

        if not done:
            console.print("[dim]Недостаточно данных. Прослушайте хотя бы одну книгу.[/dim]")
            return

        # Pre-build O(1) lookup: normalized name -> book
        book_by_norm: dict[str, dict] = {}
        for b in books:
            book_by_norm[normalize(b["folder"])] = b
            book_by_norm[normalize(b["title"])] = b

        # ── 1. Activity heatmap
        console.print("[bold]Активность (полгода):[/bold]")
        for line in calendar_heatmap(done, months=6, all_hist=hist):
            console.print(line)
        console.print(f"  [dim]{chr(9617)}=1  {chr(9618)}=2  {chr(9619)}=3  {chr(9608)}=4+[/dim]")

        # ── 2. Category radar (text-based, O(n))
        console.print(f"\n[bold]Категории прослушанного:[/bold]")
        cat_done = Counter()
        for h in done:
            b = book_by_norm.get(normalize(h["book"]))
            if b:
                cat_done[b["category"]] += 1
        total_done = sum(cat_done.values()) or 1
        max_cat = max(cat_done.values()) if cat_done else 1
        for cat in CATEGORIES:
            n = cat_done.get(cat, 0)
            pct = n * 100 // total_done
            bar_len = n * 25 // max_cat if max_cat else 0
            bar = chr(9608) * bar_len
            console.print(f"  {cat:<15} [cyan]{bar}[/cyan] {n} ({pct}%)")

        # ── 3. Monthly sparkline
        monthly = Counter()
        for h in done:
            monthly[h["ts"][:7]] += 1
        if len(monthly) > 1:
            months_sorted = sorted(monthly.keys())
            vals = [monthly[m] for m in months_sorted[-12:]]
            spark = sparkline(vals, width=len(vals))
            console.print(f"\n[bold]Тренд (по месяцам):[/bold]  [cyan]{spark}[/cyan]  {'/'.join(str(v) for v in vals[-6:])}")

        # ── 4. Day-of-week analysis
        dow_counts = Counter()
        dow_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        for h in hist:
            if h["action"] in ("listen", "done", "phone"):
                dt = datetime.fromisoformat(h["ts"])
                dow_counts[dt.weekday()] += 1
        if dow_counts:
            console.print(f"\n[bold]Активность по дням недели:[/bold]")
            max_dow = max(dow_counts.values()) or 1
            for i in range(7):
                n = dow_counts.get(i, 0)
                bar_len = n * 15 // max_dow if max_dow else 0
                console.print(f"  {dow_names[i]}  [cyan]{chr(9608) * bar_len}[/cyan] {n}")

        # ── 5. Velocity trends
        vel = reading_velocity(hist)
        if vel.get("avg_per_month", 0) > 0:
            console.print(f"\n[bold]Скорость чтения:[/bold]")
            console.print(f"  Всего прослушано:   [cyan]{vel['total']}[/cyan] книг за {vel['span_days']} дней")
            console.print(f"  Средний темп:       [cyan]{vel['avg_per_month']:.1f}[/cyan] книг/мес")
            console.print(f"  Последние 90 дней:  [cyan]{vel['recent_pace']:.1f}[/cyan] книг/мес")
            console.print(f"  Лучший месяц:       [cyan]{vel['best_month_count']}[/cyan] книг ({vel['best_month']})")
            console.print(f"  В этом году:        [cyan]{vel['this_year']}[/cyan]")

        # ── 6. Rating distribution
        ratings = [h["rating"] for h in done if h.get("rating")]
        if ratings:
            console.print(f"\n[bold]Распределение оценок:[/bold]")
            rc = Counter(ratings)
            for r in range(5, 0, -1):
                n = rc.get(r, 0)
                bar = chr(9608) * (n * 2)
                console.print(f"  {_format_stars(r)}  [yellow]{bar}[/yellow] {n}")
            avg = sum(ratings) / len(ratings)
            console.print(f"  [dim]Средняя: {avg:.1f} ({len(ratings)} оценок)[/dim]")

        # ── 7. Longest / shortest books listened
        if len(done) >= 3:
            dur_data = []
            for h in done:
                b = book_by_norm.get(normalize(h["book"]))
                if b:
                    d = estimate_duration_hours(b["path"])
                    if d:
                        dur_data.append((b["title"][:30], d))
            if dur_data:
                dur_data.sort(key=lambda x: x[1])
                console.print(f"\n[bold]Самые длинные прослушанные:[/bold]")
                for title, d in dur_data[-3:]:
                    console.print(f"  {fmt_duration(d):>8}  {title}")
                console.print(f"[bold]Самые короткие:[/bold]")
                for title, d in dur_data[:3]:
                    console.print(f"  {fmt_duration(d):>8}  {title}")

    # ── Бэкап / Восстановление ────────────────────────────────────────────────

    def screen_backup(self):
        data_files = [
            HISTORY_PATH, NOTES_PATH, TAGS_PATH, COLLECTIONS_PATH,
            PROGRESS_PATH, QUOTES_PATH, CONFIG_PATH, TRACKER_PATH, CACHE_PATH,
        ]
        existing = [f for f in data_files if f.exists()]

        console.print(f"\n[bold]Данные библиотеки:[/bold]")
        total_size = 0
        for f in existing:
            sz = f.stat().st_size
            total_size += sz
            console.print(f"  {f.name:<25} {sz / 1024:.1f} КБ")
        console.print(f"  [bold]{'Итого':<25} {total_size / 1024:.1f} КБ[/bold]")

        # List existing backups
        if BACKUP_DIR.exists():
            backups = sorted(BACKUP_DIR.glob("backup_*.zip"), reverse=True)
            if backups:
                console.print(f"\n[bold]Бэкапы ({len(backups)}):[/bold]")
                for bk in backups[:5]:
                    sz = bk.stat().st_size / 1024
                    console.print(f"  [dim]{bk.name}[/dim]  {sz:.0f} КБ")

        act = inquirer.select(message="", choices=[
            Choice("create", name="Создать бэкап"),
            Choice("restore", name="Восстановить из бэкапа"),
            Choice("back", name="Назад"),
        ], default="create").execute()

        if act == "back":
            return
        elif act == "create":
            import zipfile
            BACKUP_DIR.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_path = BACKUP_DIR / f"backup_{ts}.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in existing:
                    zf.write(f, f.name)
            sz = zip_path.stat().st_size / 1024
            console.print(f"\n[green]Бэкап создан: {zip_path.name} ({sz:.0f} КБ)[/green]")
            console.print(f"[dim]{len(existing)} файлов[/dim]")

            # Cleanup old backups (keep last 10)
            backups = sorted(BACKUP_DIR.glob("backup_*.zip"), reverse=True)
            for old in backups[10:]:
                old.unlink()
                console.print(f"  [dim]Удалён старый: {old.name}[/dim]")

        elif act == "restore":
            if not BACKUP_DIR.exists():
                console.print("[dim]Нет бэкапов.[/dim]")
                return
            backups = sorted(BACKUP_DIR.glob("backup_*.zip"), reverse=True)
            if not backups:
                console.print("[dim]Нет бэкапов.[/dim]")
                return
            sel = inquirer.select(
                message="Восстановить:",
                choices=[Choice(bk, name=f"{bk.name} ({bk.stat().st_size / 1024:.0f} КБ)")
                         for bk in backups],
            ).execute()
            if not inquirer.confirm(message=f"Восстановить из {sel.name}? Текущие данные будут перезаписаны.", default=False).execute():
                return
            import zipfile
            with zipfile.ZipFile(sel, "r") as zf:
                zf.extractall(BASE)
            console.print(f"[green]Восстановлено из {sel.name}[/green]")

    # ── Сравнение книг ────────────────────────────────────────────────────────

    def screen_compare(self):
        book1 = self._select_book("Первая книга:")
        if not book1: return
        book2 = self._select_book("Вторая книга:")
        if not book2: return

        book_ratings = self._book_ratings()

        console.print()
        tbl = Table(title="Сравнение", show_lines=True, padding=(0, 2))
        tbl.add_column("", style="bold", width=14)
        tbl.add_column(book1["title"][:30], max_width=35)
        tbl.add_column(book2["title"][:30], max_width=35)

        tbl.add_row("Автор", book1["author"] or "—", book2["author"] or "—")
        tbl.add_row("Категория", book1["category"], book2["category"])
        tbl.add_row("Чтец", book1.get("reader") or "—", book2.get("reader") or "—")

        s1, s2 = folder_size_mb(book1["path"]), folder_size_mb(book2["path"])
        tbl.add_row("Размер", f"{s1:.0f} МБ", f"{s2:.0f} МБ")

        m1, m2 = count_mp3(book1["path"]), count_mp3(book2["path"])
        tbl.add_row("Файлов", str(m1), str(m2))

        d1, d2 = estimate_duration_hours(book1["path"]), estimate_duration_hours(book2["path"])
        tbl.add_row("Длительность", fmt_duration(d1) or "?", fmt_duration(d2) or "?")

        r1 = book_ratings.get(normalize(book1["folder"]), 0)
        r2 = book_ratings.get(normalize(book2["folder"]), 0)
        tbl.add_row("Оценка",
                     f"[yellow]{_format_stars(r1)}[/]" if r1 else "—",
                     f"[yellow]{_format_stars(r2)}[/]" if r2 else "—")

        t1 = tags_get(book1["title"])
        t2 = tags_get(book2["title"])
        tbl.add_row("Теги", ", ".join(t1) or "—", ", ".join(t2) or "—")

        n1, n2 = note_get(book1["title"]), note_get(book2["title"])
        tbl.add_row("Заметка", (n1[:30] + "..." if len(n1) > 30 else n1) or "—",
                     (n2[:30] + "..." if len(n2) > 30 else n2) or "—")

        console.print(tbl)

    # ── Поиск новых книг (Google Books) ───────────────────────────────────────

    def screen_discover(self):
        """Search for new audiobooks via Google Books API."""
        query = inquirer.text(message="Поиск книг (автор, название, тема):").execute().strip()
        if not query:
            return

        console.print()
        with console.status("[dim]Поиск в Google Books..."):
            try:
                resp = requests.get(
                    "https://www.googleapis.com/books/v1/volumes",
                    params={"q": query, "maxResults": 10, "langRestrict": "ru"},
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                console.print(f"[red]Ошибка: {e}[/red]")
                return

        items = data.get("items", [])
        if not items:
            console.print("[dim]Ничего не найдено.[/dim]")
            return

        tbl = Table(title=f"Google Books: «{query}»", show_lines=False, padding=(0, 1))
        tbl.add_column("#", style="dim", width=3)
        tbl.add_column("Автор", max_width=25)
        tbl.add_column("Название", max_width=40)
        tbl.add_column("Год", style="dim", width=5)
        tbl.add_column("Стр.", style="dim", width=5)

        results = []
        for i, item in enumerate(items, 1):
            info = item.get("volumeInfo", {})
            authors = ", ".join(info.get("authors", ["?"]))[:25]
            title = info.get("title", "?")[:40]
            year = info.get("publishedDate", "")[:4]
            pages = str(info.get("pageCount", ""))
            tbl.add_row(str(i), authors, title, year, pages)
            results.append({"author": authors, "title": title})
        console.print(tbl)

        # Check which are already in library
        all_books = self._books()
        for r in results:
            for b in all_books:
                if fuzzy_match(r["title"], b["title"]) > MATCH_STRONG:
                    console.print(f"  [green]В библиотеке:[/green] {r['title']}")
                    break

        # Offer to add to Trello "Скачать"
        if self.trello:
            add_choices = [Choice(r, name=f"{r['author']} - {r['title']}") for r in results]
            selected = inquirer.fuzzy(
                message="Добавить в «Скачать»:", max_height="70%", multiselect=True,
                choices=add_choices + [Choice(None, name="Пропустить")],
            ).execute()
            if selected and selected != [None]:
                for r in selected:
                    if r is None:
                        continue
                    name = f"{r['author']} - {r['title']}"
                    self.trello.create_card(name, "Скачать")
                    console.print(f"  [green]+ {name}[/green]")
                self._sync_csv()

    # ── Планы чтения ──────────────────────────────────────────────────────────

    def screen_plans(self):
        """Set and track reading plans with deadlines."""
        config = load_config()
        plans = config.get("plans", [])

        console.print("\n[bold]Планы чтения:[/bold]\n")

        now = datetime.now()
        if plans:
            tbl = Table(show_lines=False, padding=(0, 1))
            tbl.add_column("#", style="dim", width=3)
            tbl.add_column("Книга", max_width=40)
            tbl.add_column("Дедлайн", width=12)
            tbl.add_column("Осталось", width=12)
            tbl.add_column("Прогресс", width=22)
            for i, p in enumerate(plans, 1):
                deadline = datetime.fromisoformat(p["deadline"])
                days_left = (deadline - now).days
                _, ct, _ = parse_folder_name(p["book"])
                pct = progress_get(ct)
                bar = _progress_bar(pct, 15)
                if days_left < 0:
                    days_str = f"[red]просрочен {-days_left}д[/red]"
                elif days_left <= 3:
                    days_str = f"[yellow]{days_left} дней[/yellow]"
                else:
                    days_str = f"{days_left} дней"
                tbl.add_row(str(i), p["book"][:40], p["deadline"][:10], days_str,
                            f"[cyan]{bar}[/cyan] {pct}%")
            console.print(tbl)
        else:
            console.print("[dim]Нет активных планов.[/dim]")

        act = inquirer.select(message="", choices=[
            Choice("add", name="Добавить план"),
            Choice("remove", name="Удалить план") if plans else Choice("_n", name="[dim]—[/dim]"),
            Choice("back", name="Назад"),
        ], default="add").execute()

        if act == "back" or act.startswith("_"):
            return
        elif act == "add":
            if not self._ok():
                return
            cards = self._cards_in("В процессе", "В телефоне", "Прочесть")
            if not cards:
                console.print("[dim]Нет книг для планирования.[/dim]")
                return
            sel = inquirer.fuzzy(
                message="Книга:", max_height="70%",
                choices=[Choice(c["name"], name=c["name"]) for c in cards],
            ).execute()
            if now.month < 12:
                next_m = now.replace(month=now.month + 1, day=1)
            else:
                next_m = now.replace(year=now.year + 1, month=1, day=1)
            deadline = inquirer.text(
                message="Дедлайн (ГГГГ-ММ-ДД):",
                default=next_m.strftime("%Y-%m-%d"),
            ).execute().strip()
            try:
                datetime.fromisoformat(deadline)
            except ValueError:
                console.print("[red]Неверный формат даты[/red]")
                return
            plans.append({"book": sel, "deadline": deadline})
            config["plans"] = plans
            _safe_json_write(CONFIG_PATH, config, indent=2)
            console.print(f"[green]План добавлен: {sel} до {deadline}[/green]")
        elif act == "remove":
            sel = inquirer.select(
                message="Удалить:",
                choices=[Choice(i, name=f"{p['book'][:40]} — {p['deadline'][:10]}") for i, p in enumerate(plans)],
            ).execute()
            plans.pop(sel)
            config["plans"] = plans
            _safe_json_write(CONFIG_PATH, config, indent=2)
            console.print("[green]Удалено[/green]")

    # ── Сессии прослушивания ─────────────────────────────────────────────────

    def screen_session(self):
        """Start/stop listening timer, view session stats."""
        sessions = sessions_load()
        stats = session_stats()

        console.print("\n[bold]Сессии прослушивания[/bold]\n")

        # Show current active session
        active = [s for s in sessions if s.get("end") is None]
        if active:
            s = active[-1]
            start = datetime.fromisoformat(s["start"])
            elapsed = int((datetime.now() - start).total_seconds() / 60)
            _, ct, _ = parse_folder_name(s["book"])
            console.print(f"  [magenta]Активная сессия:[/magenta] {ct[:40]}")
            console.print(f"  [dim]Начало: {s['start'][:16]}, прошло: {elapsed} мин[/dim]\n")

        # Stats
        if stats["total_hours"] > 0:
            console.print(f"  [bold]Всего:[/bold]      {stats['total_hours']:.1f} ч")
            console.print(f"  [bold]Сегодня:[/bold]    {stats['today_min']} мин")
            console.print(f"  [bold]За неделю:[/bold]  {stats['week_hours']:.1f} ч")
            if stats["peak_hour"] is not None:
                console.print(f"  [bold]Пиковый час:[/bold] {stats['peak_hour']}:00")
            console.print()

        # Recent sessions
        completed = [s for s in sessions if s.get("end")][-5:]
        if completed:
            console.print("[bold]Последние сессии:[/bold]")
            for s in reversed(completed):
                _, ct, _ = parse_folder_name(s["book"])
                console.print(f"  [dim]{s['start'][:16]}[/dim]  {s['minutes']} мин  {ct[:35]}")
            console.print()

        act = inquirer.select(message="", choices=[
            Choice("start", name="Начать сессию") if not active else Choice("stop", name="Остановить сессию"),
            Choice("back", name="Назад"),
        ], default="start" if not active else "stop").execute()

        if act == "back":
            return
        elif act == "start":
            if not self._ok():
                return
            cards = self._cards_in("В процессе", "В телефоне")
            if not cards:
                console.print("[dim]Нет активных книг.[/dim]")
                return
            sel = inquirer.fuzzy(
                message="Книга:", max_height="70%",
                choices=[Choice(c["name"], name=c["name"]) for c in cards],
            ).execute()
            session_start(sel)
            console.print(f"\n[green]Сессия начата: {sel[:45]}[/green]")
            console.print("[dim]Не забудь остановить, когда закончишь![/dim]")
        elif act == "stop":
            if not active:
                console.print("[dim]Нет активной сессии.[/dim]")
                return
            mins = session_stop(active[-1]["book"])
            console.print(f"\n[green]Сессия завершена: {mins} мин[/green]")

    # ── Недельный дашборд ────────────────────────────────────────────────────

    def screen_dashboard(self):
        """Weekly dashboard: what happened this week."""
        hist = self._history()
        books = self._books()
        now = datetime.now()
        week_ago = now.replace(hour=0, minute=0, second=0, microsecond=0)

        console.print("\n[bold]Недельный дашборд[/bold]\n")

        # This week's activity
        week_done = [h for h in hist if h["action"] == "done"
                     and (now - datetime.fromisoformat(h["ts"])).days < 7]
        week_started = [h for h in hist if h["action"] == "listen"
                        and (now - datetime.fromisoformat(h["ts"])).days < 7]
        week_added = [h for h in hist if h["action"] == "inbox"
                      and (now - datetime.fromisoformat(h["ts"])).days < 7]

        console.print(f"  [green]Завершено:[/green]  {len(week_done)}")
        console.print(f"  [magenta]Начато:[/magenta]     {len(week_started)}")
        console.print(f"  [cyan]Добавлено:[/cyan]  {len(week_added)}")

        # Streak and yearly goal
        year = str(now.year)
        done_all = [h for h in hist if h["action"] == "done"]
        done_year = sum(1 for h in done_all if h["ts"].startswith(year))
        config = load_config()
        yearly_goal = config.get("yearly_goal", 0)
        if yearly_goal:
            pct = min(done_year * 100 // yearly_goal, 100)
            console.print(f"\n  [bold]Цель {year}:[/bold] {done_year}/{yearly_goal} ({pct}%)")
            console.print(f"  [cyan]{_progress_bar(pct)}[/cyan]")

        # Books needing attention
        attention = []
        if self.trello:
            lm = self._lmap()
            for c in self.trello.get_cards():
                ln = lm.get(c["idList"], "")
                if ln in ("В процессе", "В телефоне"):
                    for h in reversed(hist):
                        if h["action"] in ("listen", "phone") and fuzzy_match(h["book"], c["name"]) > MATCH_LIKELY:
                            days = (now - datetime.fromisoformat(h["ts"])).days
                            if days >= 14:
                                _, ct, _ = parse_folder_name(c["name"])
                                attention.append(f"  [yellow]{ct[:35]}[/yellow] — {days} дней ({ln})")
                            break
        if attention:
            console.print(f"\n[bold]Требуют внимания:[/bold]")
            for a in attention:
                console.print(a)

        # Recommendation of the day
        if self.trello:
            to_read = self._cards_in("Прочесть")
            if to_read:
                pick = to_read[hash(str(now.date())) % len(to_read)]
                _, ct, _ = parse_folder_name(pick["name"])
                console.print(f"\n  [bold]Рекомендация дня:[/bold] [cyan]{ct}[/cyan]")

        # Quote of the day
        quotes = quotes_load()
        if quotes:
            q = quotes[hash(str(now.date())) % len(quotes)]
            console.print(f'\n  [dim italic]"{q["text"][:80]}"[/dim italic]')
            console.print(f"  [dim]— {q.get('author', '')} «{q['book']}»[/dim]")

        # Session stats
        stats = session_stats()
        if stats["total_hours"] > 0:
            console.print(f"\n  [bold]Прослушано за неделю:[/bold] {stats['week_hours']:.1f} ч")
            console.print(f"  [bold]Сегодня:[/bold] {stats['today_min']} мин")


# ── Main ──────────────────────────────────────────────────────────────────────

def load_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps({
            "trello_api_key": "", "trello_token": "",
            "board_id": "62d4e11502252b7a4dc11d7f",
        }, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def connect_trello(config):
    key, tok = config.get("trello_api_key", ""), config.get("trello_token", "")
    bid = config.get("board_id", "62d4e11502252b7a4dc11d7f")
    if not (key and tok):
        console.print(Panel(
            "[bold yellow]Trello не настроен[/bold yellow]\n\n"
            "1. Откройте https://trello.com/app-key\n"
            "2. Скопируйте [bold]API Key[/bold]\n"
            "3. Нажмите ссылку [bold]Token[/bold] -> авторизуйте -> скопируйте\n"
            "4. Вставьте в [cyan]_config.json[/cyan]\n\n"
            "[dim]API Secret НЕ нужен, нужен именно Token[/dim]",
            title="Настройка", border_style="yellow"))
        return None
    t = TrelloClient(key, tok, bid)
    try:
        with console.status("[dim]Trello..."):
            t.get_lists(); t.get_cards(); t.get_labels()
        t.save_cache()
        console.print("[green]Trello: ok[/green]")
        return t
    except Exception as e:
        console.print(f"[red]Trello API: {e}[/red]")
        # Try cache fallback
        if t.load_from_cache():
            console.print("[yellow]Trello: из кеша (оффлайн)[/yellow]")
            return t
        console.print("[red]Нет кеша. Работаем без Trello.[/red]")
        return None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    os.system("")  # ANSI on Windows

    config = load_config()
    lib = Library()
    trello = connect_trello(config)
    tui = TUI(lib, trello)

    # CLI mode
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        handler = {
            "sync": tui.screen_sync, "inbox": tui.screen_inbox,
            "status": tui.screen_status, "rename": tui.screen_rename,
            "recommend": tui.screen_recommend, "search": tui.screen_search,
            "pick": tui.screen_pick, "reject": tui.screen_reject,
            "phone": tui.screen_phone, "listen": tui.screen_listen,
            "done": tui.screen_done, "stats": tui.screen_stats,
            "history": tui.screen_history, "relisten": tui.screen_relisten,
            "cleanup": tui.screen_cleanup, "export": tui.screen_export,
            "undo": tui.screen_undo, "download": tui.screen_download,
            "help": tui.screen_help, "pause": tui.screen_pause,
            "move": tui.screen_move, "author": tui.screen_author,
            "config": tui.screen_config,
            "filter": tui.screen_filter, "tags": tui.screen_tags,
            "collections": tui.screen_collections,
            "achievements": tui.screen_achievements,
            "bulk": tui.screen_bulk, "timeline": tui.screen_timeline,
            "progress": tui.screen_progress, "quotes": tui.screen_quotes,
            "similar": tui.screen_similar, "queue": tui.screen_queue,
            "analytics": tui.screen_analytics, "backup": tui.screen_backup,
            "compare": tui.screen_compare, "discover": tui.screen_discover,
            "plans": tui.screen_plans,
            "session": tui.screen_session, "dashboard": tui.screen_dashboard,
        }.get(cmd)
        if handler:
            try:
                handler()
            except requests.exceptions.RequestException as e:
                console.print(f"[red]Trello: {e}[/red]")
            return
        console.print(f"[red]Неизвестная команда: {cmd}[/red]")
        console.print("[dim]sync inbox status stats search pick listen phone pause done relisten reject rename cleanup recommend download export history undo help[/dim]")
        return

    # Auto-sync CSV on startup (silent)
    if trello:
        try:
            lm = {l["id"]: l["name"] for l in trello.get_lists()}
            rows = []
            for c in trello.get_cards():
                ln = lm.get(c["idList"], "?")
                a, t, r = parse_folder_name(c["name"])
                rows.append({"Автор": a, "Название": t, "Чтец": r or "",
                             "Категория": trello.category(c) or "",
                             "Статус": LIST_TO_STATUS.get(ln, ln)})
            rows.sort(key=lambda r: (r["Категория"], r["Автор"].lower(), r["Название"].lower()))
            lib.save_tracker(rows)
        except Exception:
            pass

    # Auto-suggest inbox if dl/ not empty
    dl = lib.find_dl_books()
    if dl:
        console.print(f"\n[yellow]В dl/ {len(dl)} книг.[/yellow]")
        if inquirer.confirm(message="Разобрать сейчас?", default=True).execute():
            tui.screen_inbox()
            console.print()
            inquirer.text(message="Enter — меню").execute()

    tui.run()


if __name__ == "__main__":
    main()
