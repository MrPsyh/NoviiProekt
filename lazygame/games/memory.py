"""Соло-игра «Повтори»: запомни и повтори растущую последовательность (в ЛС)."""
from __future__ import annotations

import asyncio
import random

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from .base import BaseGame, Phase, Player

SYMBOLS = ["🔴", "🟢", "🔵", "🟡"]


class MemoryGame(BaseGame):
    title = "🧠 Повтори"
    slug = "memory"
    min_players = 1
    max_players = 1

    def __init__(self, chat_id: int, host: Player, lang: str = "ru"):
        super().__init__(chat_id, host, lang)
        self.seq: list[int] = []
        self.idx = 0

    def _kb(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton(SYMBOLS[i], callback_data=f"mem:{i}") for i in range(4)
        ]])

    async def start(self, bot: Bot) -> None:
        self.phase = Phase.RUNNING
        self.seq = []
        await bot.send_message(
            self.chat_id,
            "🧠 <b>Повтори</b>\nЗапоминай последовательность и повторяй её кнопками. "
            "С каждым уровнем — на один символ длиннее!",
            parse_mode="HTML")
        await asyncio.sleep(0.6)
        await self._next_round(bot)

    async def _next_round(self, bot: Bot) -> None:
        self.seq.append(random.randrange(4))
        self.idx = 0
        shown = " ".join(SYMBOLS[i] for i in self.seq)
        await bot.send_message(
            self.chat_id,
            f"Уровень <b>{len(self.seq)}</b>. Запомни:\n\n{shown}",
            parse_mode="HTML")
        await asyncio.sleep(min(1.0 + 0.4 * len(self.seq), 4.0))
        await bot.send_message(self.chat_id, "Повтори:", reply_markup=self._kb())

    async def tap(self, bot: Bot, idx: int) -> None:
        if self.phase != Phase.RUNNING or self.idx >= len(self.seq):
            return
        if idx == self.seq[self.idx]:
            self.idx += 1
            if self.idx >= len(self.seq):
                await bot.send_message(
                    self.chat_id, f"✅ Уровень {len(self.seq)} пройден!")
                await asyncio.sleep(0.6)
                await self._next_round(bot)
        else:
            self.phase = Phase.FINISHED
            self.record_scores({self.host.user_id: len(self.seq) - 1})
            await bot.send_message(
                self.chat_id,
                f"❌ Ошибка!\nТвой результат: <b>{len(self.seq) - 1}</b> уровней.\n"
                f"/play — сыграть ещё.",
                parse_mode="HTML")
