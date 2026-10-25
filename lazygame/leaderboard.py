"""Рекорды: запись очков игр и выборка топов (по чату и по миру)."""
from __future__ import annotations

from . import storage

# какие игры участвуют в рейтинге и как называются в UI
RANKED_GAMES = {
    "crocodile": "🐊 Крокодил",
    "hangman": "🪢 Весельница",
    "reaction": "⚡ Реакция",
    "mafia": "🔪 Мафия",
    "bunker": "🏚 Бункер",
    "spy": "🕵️ Шпион",
    "quiz": "🧠 Викторина",
    "anagram": "🔤 Анаграммы",
    "memory": "🧠 Повтори",
    "guessnum": "🔢 Угадай число",
    "rps": "✊ КНБ",
}


def record(slug: str, chat_id: int, entries) -> None:
    """entries: список (user_id, name, points) — накапливаем очки игрока."""
    if slug in RANKED_GAMES:
        storage.add_scores(slug, chat_id, [e for e in entries if e[2]])


def chat_top(slug: str, chat_id: int, limit: int = 10) -> list[dict]:
    return storage.chat_top(slug, chat_id, limit)


def world_top(slug: str, limit: int = 10) -> list[dict]:
    return storage.world_top(slug, limit)


def top_chats(limit: int = 10) -> list[dict]:
    return storage.top_chats(limit)


def games_with_scores() -> list[str]:
    return storage.games_with_scores()


def build_snapshot(chat_id: int | None, limit: int = 10) -> dict:
    """Готовит данные для страницы рекордов (мир + конкретный чат по всем играм)."""
    world = {slug: world_top(slug, limit) for slug in RANKED_GAMES}
    chat = {}
    if chat_id is not None:
        chat = {slug: chat_top(slug, chat_id, limit) for slug in RANKED_GAMES}
    return {
        "games": RANKED_GAMES,
        "world": world,
        "chat": chat,
        "top_chats": top_chats(limit),
        "has_chat": chat_id is not None,
    }
