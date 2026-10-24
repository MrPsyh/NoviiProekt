"""Игра «Правда или Действие».

Бот выбирает случайного игрока, тот жмёт «Правда» или «Действие» и получает
случайное задание. Кнопкой «Следующий» ход передаётся другому игроку.
"""
from __future__ import annotations

import random

from telegram import Bot

from ..data.truth_or_dare import DARES, TRUTHS
from .base import BaseGame, Phase, Player


class TruthOrDareGame(BaseGame):
    title = "🎭 Правда или Действие"
    slug = "truthdare"
    min_players = 2
    max_players = 30

    def __init__(self, chat_id: int, host: Player):
        super().__init__(chat_id, host)
        self.current_id: int | None = None

    def _pick_player(self, exclude: int | None = None) -> Player:
        pool = [p for p in self.players.values() if p.user_id != exclude]
        if not pool:
            pool = list(self.players.values())
        return random.choice(pool)

    async def start(self, bot: Bot) -> None:
        self.phase = Phase.RUNNING
        await self.next_turn(bot)

    async def next_turn(self, bot: Bot) -> None:
        if self.phase != Phase.RUNNING:
            return
        chosen = self._pick_player(exclude=self.current_id)
        self.current_id = chosen.user_id
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🟢 Правда", callback_data="td:truth"),
            InlineKeyboardButton("🔴 Действие", callback_data="td:dare"),
        ]])
        await bot.send_message(
            self.chat_id,
            f"🎲 Ход игрока {chosen.mention}!\nВыбирай:",
            parse_mode="HTML",
            reply_markup=kb,
        )

    async def choose(self, bot: Bot, user_id: int, kind: str) -> bool:
        """kind = 'truth' | 'dare'. Возвращает False, если жмёт не тот игрок."""
        if self.phase != Phase.RUNNING or user_id != self.current_id:
            return False
        pool = TRUTHS if kind == "truth" else DARES
        label = "🟢 ПРАВДА" if kind == "truth" else "🔴 ДЕЙСТВИЕ"
        task = random.choice(pool)
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("➡️ Следующий игрок", callback_data="td:next")
        ]])
        await bot.send_message(
            self.chat_id,
            f"{label} для {self.players[user_id].mention}:\n\n<b>{task}</b>",
            parse_mode="HTML",
            reply_markup=kb,
        )
        return True
