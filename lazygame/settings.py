"""Настройки на уровне группового чата (лимиты игроков и язык).

Данные хранятся в SQLite (см. storage.py), поэтому переживают перезапуск бота.
Публичный API не изменился.
"""
from __future__ import annotations

from . import storage

# пресеты максимума игроков, по которым «пролистывается» настройка
MAX_PRESETS = [8, 10, 12, 15, 20, 25, 30, 35]


class GroupSettings:
    def get_max(self, chat_id: int, slug: str, default: int) -> int:
        return storage.get_maxes(chat_id).get(slug, default)

    def set_max(self, chat_id: int, slug: str, value: int) -> None:
        storage.set_max(chat_id, slug, value)

    def get_lang(self, chat_id: int, default: str = "ru") -> str:
        return storage.get_lang(chat_id) or default

    def set_lang(self, chat_id: int, lang: str) -> None:
        storage.set_lang(chat_id, lang)

    def cycle_max(self, chat_id: int, slug: str, current: int,
                  hard_cap: int, floor: int) -> int:
        """Переключает максимум на следующий пресет (с учётом границ игры)."""
        allowed = [p for p in MAX_PRESETS if floor <= p <= hard_cap]
        if not allowed:
            allowed = [hard_cap]
        try:
            nxt = allowed[(allowed.index(current) + 1) % len(allowed)]
        except ValueError:
            nxt = allowed[0]
        self.set_max(chat_id, slug, nxt)
        return nxt


settings = GroupSettings()
