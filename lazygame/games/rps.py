"""Соло-игра «Камень-ножницы-бумага» (в ЛС) против бота. До 3 побед."""
from __future__ import annotations

import random

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from ..i18n import t
from .base import BaseGame, Phase, Player

WIN_TARGET = 3
MOVES = ("rock", "paper", "scissors")
BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}


class RPSGame(BaseGame):
    title = "✊ Камень-ножницы-бумага"
    slug = "rps"
    min_players = 1
    max_players = 1

    def __init__(self, chat_id: int, host: Player, lang: str = "ru"):
        super().__init__(chat_id, host, lang)
        self.player_score = 0
        self.bot_score = 0

    def _kb(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton(t(self.lang, "rps_rock"), callback_data="rps:rock"),
            InlineKeyboardButton(t(self.lang, "rps_paper"), callback_data="rps:paper"),
            InlineKeyboardButton(t(self.lang, "rps_scissors"), callback_data="rps:scissors"),
        ]])

    async def start(self, bot: Bot) -> None:
        self.phase = Phase.RUNNING
        self.player_score = self.bot_score = 0
        await bot.send_message(
            self.chat_id, t(self.lang, "rps_start", n=WIN_TARGET), reply_markup=self._kb()
        )

    async def play(self, bot: Bot, user_id: int, move: str) -> None:
        if self.phase != Phase.RUNNING or move not in MOVES:
            return
        bot_move = random.choice(MOVES)
        if move == bot_move:
            res = t(self.lang, "rps_draw")
        elif BEATS[move] == bot_move:
            self.player_score += 1
            res = t(self.lang, "rps_you_win")
        else:
            self.bot_score += 1
            res = t(self.lang, "rps_you_lose")

        line = t(self.lang, "rps_round",
                 you=t(self.lang, f"rps_{move}"), me=t(self.lang, f"rps_{bot_move}"),
                 res=res, ps=self.player_score, bs=self.bot_score)

        if self.player_score >= WIN_TARGET or self.bot_score >= WIN_TARGET:
            self.phase = Phase.FINISHED
            if self.player_score > self.bot_score:
                self.record_scores({self.host.user_id: 1})
            final_key = "rps_final_win" if self.player_score > self.bot_score else "rps_final_lose"
            final = t(self.lang, final_key, ps=self.player_score, bs=self.bot_score)
            await bot.send_message(self.chat_id, f"{line}\n\n{final}")
        else:
            await bot.send_message(self.chat_id, line, reply_markup=self._kb())
