"""Групповая игра «Реакция»: кто первым нажмёт кнопку — получает очко."""
from __future__ import annotations

import asyncio
import random

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from .base import BaseGame, Phase, Player

ROUNDS = 5


class ReactionGame(BaseGame):
    title = "⚡ Реакция"
    slug = "reaction"
    min_players = 2
    max_players = 30

    def __init__(self, chat_id: int, host: Player, lang: str = "ru"):
        super().__init__(chat_id, host, lang)
        self.scores: dict[int, int] = {}
        self.open = False
        self._event: asyncio.Event | None = None
        self._winner_name: str | None = None
        self._task = None

    async def start(self, bot: Bot) -> None:
        self.phase = Phase.RUNNING
        await bot.send_message(
            self.chat_id,
            f"⚡ <b>Реакция!</b> {ROUNDS} раундов.\n"
            f"Как появится кнопка «ЖМИ» — жми первым! Побеждает самый быстрый.",
            parse_mode="HTML")
        self._task = asyncio.create_task(self._run(bot))

    async def _run(self, bot: Bot) -> None:
        for r in range(1, ROUNDS + 1):
            if self.phase != Phase.RUNNING:
                return
            await bot.send_message(self.chat_id, f"Раунд {r}/{ROUNDS}. Приготовьтесь…")
            await asyncio.sleep(random.uniform(2.5, 6.0))
            if self.phase != Phase.RUNNING:
                return
            self._event = asyncio.Event()
            self._winner_name = None
            self.open = True
            await bot.send_message(
                self.chat_id, "⚡⚡⚡ ЖМИ! ⚡⚡⚡",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🔴 ЖМИ!", callback_data="rx")]]))
            try:
                await asyncio.wait_for(self._event.wait(), timeout=8.0)
                await bot.send_message(
                    self.chat_id,
                    f"🏆 {self._winner_name} — быстрее всех! +1 очко")
            except asyncio.TimeoutError:
                self.open = False
                await bot.send_message(self.chat_id, "⏱ Никто не успел!")
            await asyncio.sleep(1.6)
        await self._finish(bot)

    def press(self, user_id: int, name: str) -> str:
        if not self.open:
            return "late"
        if user_id not in self.players:
            return "notin"
        self.open = False
        self.scores[user_id] = self.scores.get(user_id, 0) + 1
        self._winner_name = name
        if self._event:
            self._event.set()
        return "win"

    async def _finish(self, bot: Bot) -> None:
        self.phase = Phase.FINISHED
        self.record_scores(dict(self.scores))
        if self.scores:
            ranked = sorted(self.scores.items(), key=lambda kv: kv[1], reverse=True)
            board = "\n".join(f"• {self.players[u].name}: {s}" for u, s in ranked)
            winner = self.players[ranked[0][0]].name
            head = f"🏁 Победитель: <b>{winner}</b>!"
        else:
            board = "никто не нажал"
            head = "🏁 Игра окончена."
        await bot.send_message(
            self.chat_id, f"{head}\n\n🏆 <b>Итоги:</b>\n{board}\n\n/newgame — ещё.",
            parse_mode="HTML")
