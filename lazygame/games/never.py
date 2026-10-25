"""Групповая пати-игра «Я никогда не…»: отмечаем «было / не было»."""
from __future__ import annotations

import random

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from ..data.party import NEVER_PROMPTS
from .base import BaseGame, Phase, Player

ROUNDS = 7


class NeverGame(BaseGame):
    title = "🙈 Я никогда не…"
    slug = "never"
    min_players = 2
    max_players = 30

    def __init__(self, chat_id: int, host: Player, lang: str = "ru"):
        super().__init__(chat_id, host, lang)
        self.prompts: list[str] = []
        self.index = 0
        self.yes: set[int] = set()
        self.no: set[int] = set()

    async def start(self, bot: Bot) -> None:
        self.phase = Phase.RUNNING
        self.prompts = random.sample(NEVER_PROMPTS, min(ROUNDS, len(NEVER_PROMPTS)))
        self.index = 0
        await self._ask(bot)

    async def _ask(self, bot: Bot) -> None:
        self.yes = set()
        self.no = set()
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🙋 Было", callback_data="nv:yes"),
             InlineKeyboardButton("🙅 Не было", callback_data="nv:no")],
            [InlineKeyboardButton("📊 Показать и дальше", callback_data="nnext")],
        ])
        await bot.send_message(
            self.chat_id,
            f"<b>{self.index + 1}/{len(self.prompts)}</b>\n\n"
            f"🙈 Я никогда не {self.prompts[self.index]}",
            parse_mode="HTML", reply_markup=kb)

    def react(self, user_id: int, kind: str) -> bool:
        if self.phase != Phase.RUNNING:
            return False
        if kind == "yes":
            self.no.discard(user_id)
            self.yes.add(user_id)
        else:
            self.yes.discard(user_id)
            self.no.add(user_id)
        return True

    async def reveal_next(self, bot: Bot) -> None:
        if self.phase != Phase.RUNNING:
            return
        await bot.send_message(
            self.chat_id,
            f"🙋 Было: <b>{len(self.yes)}</b>   ·   🙅 Не было: <b>{len(self.no)}</b>",
            parse_mode="HTML")
        self.index += 1
        if self.index >= len(self.prompts):
            self.phase = Phase.FINISHED
            await bot.send_message(self.chat_id, "🏁 Всё! /newgame — сыграть ещё.")
        else:
            await self._ask(bot)
