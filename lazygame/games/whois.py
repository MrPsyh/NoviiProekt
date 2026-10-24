"""Групповая пати-игра «Кто из нас?»: голосуем за игрока на забавный вопрос."""
from __future__ import annotations

import random

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from ..data.party import WHOIS_PROMPTS
from ..i18n import t
from .base import BaseGame, Phase, Player

ROUNDS = 5


class WhoisGame(BaseGame):
    title = "🗳 Кто из нас?"
    slug = "whois"
    min_players = 3
    max_players = 30

    def __init__(self, chat_id: int, host: Player, lang: str = "ru"):
        super().__init__(chat_id, host, lang)
        self.prompts: list[str] = []
        self.index = 0
        self.votes: dict[int, int] = {}
        self.voted: set[int] = set()

    async def start(self, bot: Bot) -> None:
        self.phase = Phase.RUNNING
        self.prompts = random.sample(WHOIS_PROMPTS, min(ROUNDS, len(WHOIS_PROMPTS)))
        self.index = 0
        await self._ask(bot)

    async def _ask(self, bot: Bot) -> None:
        self.votes = {}
        self.voted = set()
        buttons = [[InlineKeyboardButton(p.name, callback_data=f"wv:{p.user_id}")]
                   for p in self.players.values()]
        buttons.append([InlineKeyboardButton("📊 Показать результат", callback_data="wresult")])
        await bot.send_message(
            self.chat_id,
            f"<b>Вопрос {self.index + 1}/{len(self.prompts)}</b>\n\n"
            f"🗳 Кто из нас, скорее всего, <b>{self.prompts[self.index]}</b>",
            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))

    def register_vote(self, voter_id: int, target_id: int) -> bool:
        if self.phase != Phase.RUNNING or target_id not in self.players:
            return False
        if voter_id in self.voted:
            return False
        self.votes[voter_id] = target_id
        self.voted.add(voter_id)
        return True

    async def reveal(self, bot: Bot) -> None:
        if self.phase != Phase.RUNNING:
            return
        counts: dict[int, int] = {}
        for tgt in self.votes.values():
            counts[tgt] = counts.get(tgt, 0) + 1
        if counts:
            top = max(counts.values())
            leaders = [self.players[u].name for u, c in counts.items() if c == top]
            res = f"🏆 {', '.join(leaders)} — {top} голос(ов)!"
        else:
            res = "Никто не проголосовал 🤷"
        await bot.send_message(self.chat_id, res, parse_mode="HTML")
        self.index += 1
        if self.index >= len(self.prompts):
            self.phase = Phase.FINISHED
            await bot.send_message(self.chat_id, "🏁 Вопросы кончились! /newgame — ещё.")
        else:
            await self._ask(bot)
