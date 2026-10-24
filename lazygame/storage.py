"""Персистентное хранилище на SQLite: настройки чатов, язык и статистика.

Активные игровые комнаты намеренно хранятся только в памяти (они временные),
а всё, что должно пережить перезапуск, лежит здесь.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

_DB = os.getenv("LAZYGAME_DB") or os.path.join(os.path.dirname(__file__), "data", "lazygame.db")
_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _c() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(_DB), exist_ok=True)
        _conn = sqlite3.connect(_DB, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings(
                chat_id INTEGER PRIMARY KEY, lang TEXT, maxes TEXT);
            CREATE TABLE IF NOT EXISTS stat_chats(
                chat_id INTEGER PRIMARY KEY, title TEXT, type TEXT,
                games INTEGER DEFAULT 0, last TEXT);
            CREATE TABLE IF NOT EXISTS stat_games(slug TEXT PRIMARY KEY, cnt INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS stat_users(user_id INTEGER PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS stat_meta(k TEXT PRIMARY KEY, v TEXT);
            """
        )
        _conn.commit()
        cur = _conn.execute("SELECT v FROM stat_meta WHERE k='started_at'")
        if cur.fetchone() is None:
            _conn.execute("INSERT INTO stat_meta(k, v) VALUES('started_at', ?)", (_now(),))
            _conn.commit()
    return _conn


# --- настройки -------------------------------------------------------
def get_lang(chat_id: int) -> str | None:
    with _lock:
        row = _c().execute("SELECT lang FROM settings WHERE chat_id=?", (chat_id,)).fetchone()
        return row["lang"] if row and row["lang"] else None


def set_lang(chat_id: int, lang: str) -> None:
    with _lock:
        _c().execute(
            "INSERT INTO settings(chat_id, lang) VALUES(?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET lang=excluded.lang",
            (chat_id, lang))
        _c().commit()


def get_maxes(chat_id: int) -> dict[str, int]:
    with _lock:
        row = _c().execute("SELECT maxes FROM settings WHERE chat_id=?", (chat_id,)).fetchone()
        if row and row["maxes"]:
            try:
                return json.loads(row["maxes"])
            except ValueError:
                return {}
        return {}


def set_max(chat_id: int, slug: str, value: int) -> None:
    with _lock:
        maxes = get_maxes(chat_id)
        maxes[slug] = value
        _c().execute(
            "INSERT INTO settings(chat_id, maxes) VALUES(?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET maxes=excluded.maxes",
            (chat_id, json.dumps(maxes)))
        _c().commit()


# --- статистика ------------------------------------------------------
def touch_chat(chat_id: int, title: str, ctype: str) -> None:
    with _lock:
        _c().execute(
            "INSERT INTO stat_chats(chat_id, title, type, games, last) VALUES(?,?,?,0,?) "
            "ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title, "
            "type=excluded.type, last=excluded.last",
            (chat_id, title, ctype, _now()))
        _c().commit()


def remove_chat(chat_id: int) -> None:
    with _lock:
        _c().execute("DELETE FROM stat_chats WHERE chat_id=?", (chat_id,))
        _c().commit()


def add_game(slug: str, chat_id: int, user_ids) -> None:
    with _lock:
        c = _c()
        c.execute(
            "INSERT INTO stat_games(slug, cnt) VALUES(?,1) "
            "ON CONFLICT(slug) DO UPDATE SET cnt=cnt+1", (slug,))
        c.execute("UPDATE stat_chats SET games=games+1 WHERE chat_id=?", (chat_id,))
        _meta_inc("games_total", 1)
        for uid in user_ids:
            c.execute("INSERT OR IGNORE INTO stat_users(user_id) VALUES(?)", (int(uid),))
        c.commit()


def _meta_inc(key: str, by: int) -> None:
    c = _c()
    row = c.execute("SELECT v FROM stat_meta WHERE k=?", (key,)).fetchone()
    cur = int(row["v"]) if row and row["v"] and row["v"].isdigit() else 0
    c.execute("INSERT INTO stat_meta(k, v) VALUES(?, ?) "
              "ON CONFLICT(k) DO UPDATE SET v=excluded.v", (key, str(cur + by)))


def chat_ids() -> list[int]:
    with _lock:
        return [r["chat_id"] for r in _c().execute("SELECT chat_id FROM stat_chats")]


def chats_dict() -> dict[str, dict]:
    with _lock:
        out: dict[str, dict] = {}
        for r in _c().execute("SELECT chat_id, title, type, games, last FROM stat_chats"):
            out[str(r["chat_id"])] = {
                "title": r["title"], "type": r["type"],
                "games": r["games"], "last": r["last"],
            }
        return out


def snapshot() -> dict:
    with _lock:
        c = _c()
        started = c.execute("SELECT v FROM stat_meta WHERE k='started_at'").fetchone()
        total = c.execute("SELECT v FROM stat_meta WHERE k='games_total'").fetchone()
        by_game = {r["slug"]: r["cnt"] for r in c.execute("SELECT slug, cnt FROM stat_games")}
        users = c.execute("SELECT COUNT(*) AS n FROM stat_users").fetchone()["n"]
        chats_known = c.execute("SELECT COUNT(*) AS n FROM stat_chats").fetchone()["n"]
        return {
            "started_at": started["v"] if started else _now(),
            "games_total": int(total["v"]) if total and total["v"].isdigit() else 0,
            "by_game": by_game,
            "users_total": users,
            "chats_known": chats_known,
        }
