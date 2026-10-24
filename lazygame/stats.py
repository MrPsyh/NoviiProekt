"""Простая статистика бота с сохранением в JSON-файл.

Запоминаем чаты, где был бот (для админ-панели: где бот админ + сколько людей),
и счётчики запущенных игр. Актуальное число участников и статус админа бот
узнаёт у Telegram в момент открытия панели.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone

_PATH = os.path.join(os.path.dirname(__file__), "data", "stats.json")
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Stats:
    def __init__(self) -> None:
        self.started_at = _now()
        self.chats: dict[str, dict] = {}       # chat_id -> {title, type, games, last}
        self.users: set[int] = set()
        self.games_started: dict[str, int] = {}
        self.games_total = 0
        self._load()

    # --- хранилище ----------------------------------------------------
    def _load(self) -> None:
        try:
            with open(_PATH, encoding="utf-8") as f:
                data = json.load(f)
            self.started_at = data.get("started_at", self.started_at)
            self.chats = data.get("chats", {})
            self.users = set(data.get("users", []))
            self.games_started = data.get("games_started", {})
            self.games_total = data.get("games_total", 0)
        except (FileNotFoundError, ValueError):
            pass

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(_PATH), exist_ok=True)
            tmp = _PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({
                    "started_at": self.started_at,
                    "chats": self.chats,
                    "users": sorted(self.users),
                    "games_started": self.games_started,
                    "games_total": self.games_total,
                }, f, ensure_ascii=False)
            os.replace(tmp, _PATH)
        except OSError:
            pass

    # --- запись -------------------------------------------------------
    def touch_chat(self, chat) -> None:
        """Отмечаем чат (группу), где появился бот."""
        if chat is None or chat.type not in ("group", "supergroup"):
            return
        with _lock:
            rec = self.chats.setdefault(str(chat.id), {"games": 0})
            rec["title"] = chat.title or rec.get("title", str(chat.id))
            rec["type"] = chat.type
            rec["last"] = _now()
            self._save()

    def remove_chat(self, chat_id: int) -> None:
        with _lock:
            if self.chats.pop(str(chat_id), None) is not None:
                self._save()

    def game_started(self, slug: str, chat_id: int, user_ids) -> None:
        with _lock:
            self.games_total += 1
            self.games_started[slug] = self.games_started.get(slug, 0) + 1
            self.users.update(int(u) for u in user_ids)
            rec = self.chats.get(str(chat_id))
            if rec is not None:
                rec["games"] = rec.get("games", 0) + 1
            self._save()

    # --- чтение -------------------------------------------------------
    def group_chat_ids(self) -> list[int]:
        return [int(cid) for cid in self.chats]

    def base_snapshot(self) -> dict:
        return {
            "started_at": self.started_at,
            "games_total": self.games_total,
            "by_game": dict(self.games_started),
            "users_total": len(self.users),
            "chats_known": len(self.chats),
        }


stats = Stats()
