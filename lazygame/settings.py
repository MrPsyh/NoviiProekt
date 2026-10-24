"""Настройки на уровне группового чата (лимиты игроков и т.п.).

Хранятся в памяти процесса — как и игровые комнаты. Для продакшена можно
заменить на БД, интерфейс (get_max/set_max) при этом не изменится.
"""
from __future__ import annotations

# пресеты максимума игроков, по которым «пролистывается» настройка
MAX_PRESETS = [8, 10, 12, 15, 20, 25, 30, 35]


class GroupSettings:
    def __init__(self) -> None:
        # chat_id -> {slug: max_players}
        self._max: dict[int, dict[str, int]] = {}
        # chat_id -> код языка ("ru" / "en" / "uk")
        self._lang: dict[int, str] = {}

    def get_max(self, chat_id: int, slug: str, default: int) -> int:
        return self._max.get(chat_id, {}).get(slug, default)

    def set_max(self, chat_id: int, slug: str, value: int) -> None:
        self._max.setdefault(chat_id, {})[slug] = value

    def get_lang(self, chat_id: int, default: str = "ru") -> str:
        return self._lang.get(chat_id, default)

    def set_lang(self, chat_id: int, lang: str) -> None:
        self._lang[chat_id] = lang

    def cycle_max(self, chat_id: int, slug: str, current: int,
                  hard_cap: int, floor: int) -> int:
        """Переключает максимум на следующий пресет (с учётом границ игры)."""
        allowed = [p for p in MAX_PRESETS if floor <= p <= hard_cap]
        if not allowed:
            allowed = [hard_cap]
        try:
            idx = allowed.index(current)
            nxt = allowed[(idx + 1) % len(allowed)]
        except ValueError:
            nxt = allowed[0]
        self.set_max(chat_id, slug, nxt)
        return nxt


settings = GroupSettings()
