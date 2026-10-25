"""Соло-игра «Угадай число» (в ЛС). Бот загадывает 1..100, игрок угадывает."""
from __future__ import annotations

import random

from telegram import Bot

from ..i18n import t
from .base import BaseGame, Phase, Player

MAX_TRIES = 7


class GuessNumberGame(BaseGame):
    title = "🔢 Угадай число"
    slug = "guessnum"
    min_players = 1
    max_players = 1

    def __init__(self, chat_id: int, host: Player, lang: str = "ru"):
        super().__init__(chat_id, host, lang)
        self.secret = 0
        self.tries = 0

    async def start(self, bot: Bot) -> None:
        self.phase = Phase.RUNNING
        self.secret = random.randint(1, 100)
        self.tries = MAX_TRIES
        await bot.send_message(self.chat_id, t(self.lang, "num_start", n=MAX_TRIES))

    async def handle_input(self, bot: Bot, player: Player, text: str) -> None:
        if self.phase != Phase.RUNNING:
            return
        raw = text.strip()
        if not raw.lstrip("-").isdigit():
            return
        guess = int(raw)
        if not 1 <= guess <= 100:
            return
        self.tries -= 1
        if guess == self.secret:
            self.phase = Phase.FINISHED
            self.record_scores({self.host.user_id: self.tries + 1})  # меньше попыток — больше очков
            await bot.send_message(
                self.chat_id,
                t(self.lang, "num_win", n=self.secret, tries=MAX_TRIES - self.tries),
            )
            return
        if self.tries <= 0:
            self.phase = Phase.FINISHED
            await bot.send_message(self.chat_id, t(self.lang, "num_lose", n=self.secret))
            return
        hint = t(self.lang, "num_higher" if guess < self.secret else "num_lower")
        left = t(self.lang, "num_tries_left", n=self.tries)
        await bot.send_message(self.chat_id, f"{hint}\n{left}")
