"""Статистика бота на SQLite (см. storage.py).

Запоминаем чаты, где был бот (для админ-панели: где бот админ + сколько людей),
и счётчики запущенных игр. Актуальное число участников и статус админа бот
узнаёт у Telegram в момент открытия панели. Публичный API не изменился.
"""
from __future__ import annotations

from . import storage


class Stats:
    def touch_chat(self, chat) -> None:
        if chat is None or chat.type not in ("group", "supergroup"):
            return
        storage.touch_chat(chat.id, chat.title or str(chat.id), chat.type)

    def remove_chat(self, chat_id: int) -> None:
        storage.remove_chat(chat_id)

    def game_started(self, slug: str, chat_id: int, user_ids) -> None:
        storage.add_game(slug, chat_id, user_ids)

    def group_chat_ids(self) -> list[int]:
        return storage.chat_ids()

    @property
    def chats(self) -> dict[str, dict]:
        return storage.chats_dict()

    def base_snapshot(self) -> dict:
        return storage.snapshot()


stats = Stats()
