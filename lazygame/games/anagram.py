"""Соло-игра «Анаграммы»: собери слово из перемешанных букв (в ЛС)."""
from __future__ import annotations

import random

from telegram import Bot

from ..data.crocodile_words import WORDS
from ..i18n import t
from .base import BaseGame, Phase, Player

ROUNDS = 7


class AnagramGame(BaseGame):
    title = "🔤 Анаграммы"
    slug = "anagram"
    min_players = 1
    max_players = 1

    def __init__(self, chat_id: int, host: Player, lang: str = "ru",
                 difficulty: str = "medium"):
        super().__init__(chat_id, host, lang)
        self.difficulty = difficulty
        self.words: list[str] = []
        self.index = 0
        self.score = 0

    def _scramble(self, word: str) -> str:
        letters = list(word)
        for _ in range(10):
            random.shuffle(letters)
            if "".join(letters) != word:
                break
        return " ".join(ch.upper() for ch in letters)

    async def start(self, bot: Bot) -> None:
        self.phase = Phase.RUNNING
        pool = WORDS.get(self.lang, WORDS["ru"]).get(self.difficulty) \
            or WORDS["ru"]["medium"]
        # только однословные, без пробелов
        pool = [w for w in pool if " " not in w]
        self.words = random.sample(pool, min(ROUNDS, len(pool)))
        self.index = 0
        self.score = 0
        await self._ask(bot)

    async def _ask(self, bot: Bot) -> None:
        word = self.words[self.index]
        await bot.send_message(
            self.chat_id,
            f"<b>Слово {self.index + 1}/{len(self.words)}</b>\n"
            f"Собери слово из букв:\n\n<code>{self._scramble(word)}</code>\n\n"
            f"Напиши ответ в чат. /skip — пропустить.",
            parse_mode="HTML",
        )

    async def handle_input(self, bot: Bot, player: Player, text: str) -> None:
        if self.phase != Phase.RUNNING:
            return
        guess = text.strip().lower().replace("ё", "е")
        if guess == self.words[self.index].replace("ё", "е"):
            self.score += 1
            await bot.send_message(self.chat_id, "✅ Верно!")
            await self._advance(bot)

    async def skip(self, bot: Bot) -> None:
        if self.phase != Phase.RUNNING:
            return
        await bot.send_message(
            self.chat_id, f"⏭ Это было «<b>{self.words[self.index]}</b>».",
            parse_mode="HTML")
        await self._advance(bot)

    async def _advance(self, bot: Bot) -> None:
        self.index += 1
        if self.index >= len(self.words):
            self.phase = Phase.FINISHED
            await bot.send_message(
                self.chat_id,
                f"🏁 Готово! Результат: <b>{self.score}/{len(self.words)}</b>\n"
                f"/play — сыграть ещё.",
                parse_mode="HTML")
        else:
            await self._ask(bot)
