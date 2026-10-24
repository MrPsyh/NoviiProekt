"""Игра «Крокодил».

Ведущий получает слово в личку (с карточкой-картинкой) и объясняет его в чате,
не называя само слово. Остальные угадывают сообщениями. Кто угадал — новый ведущий.
Язык слов и интерфейса берётся из self.lang.
"""
from __future__ import annotations

import random
import re

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from ..cards import render_word_card
from ..data.crocodile_words import WORDS
from ..i18n import t
from .base import BaseGame, Phase, Player


class CrocodileGame(BaseGame):
    title = "🐊 Крокодил"
    slug = "crocodile"
    min_players = 2
    max_players = 35

    def __init__(self, chat_id: int, host: Player, lang: str = "ru",
                 difficulty: str = "medium"):
        super().__init__(chat_id, host, lang)
        self.word: str = ""
        self.difficulty: str = difficulty
        self.leader_id: int = host.user_id
        self.scores: dict[int, int] = {}
        self.used: set[str] = set()   # чтобы слова не повторялись

    def _words(self) -> dict:
        return WORDS.get(self.lang, WORDS["ru"])

    def _pick_word(self) -> None:
        pool = self._words().get(self.difficulty) or self._words()["medium"]
        available = [w for w in pool if w not in self.used]
        if not available:              # все слова прошли — начинаем круг заново
            self.used.clear()
            available = list(pool)
        self.word = random.choice(available)
        self.used.add(self.word)

    async def _send_word_to_leader(self, bot: Bot) -> bool:
        image = render_word_card(self.word, self.difficulty)
        try:
            await bot.send_photo(
                chat_id=self.leader_id, photo=image,
                caption=t(self.lang, "croc_pm_caption"),
            )
            return True
        except TelegramError:
            return False

    async def start(self, bot: Bot) -> None:
        self.phase = Phase.RUNNING
        self.leader_id = random.choice(list(self.players.keys()))
        await self._new_round(bot)

    async def _new_round(self, bot: Bot) -> None:
        self._pick_word()
        leader = self.players[self.leader_id]
        delivered = await self._send_word_to_leader(bot)
        text = t(self.lang, "croc_leader", m=leader.mention)
        if not delivered:
            text += "\n\n" + t(self.lang, "croc_no_pm", m=leader.mention)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(t(self.lang, "croc_replace_btn"), callback_data="cnew")
        ]])
        await bot.send_message(self.chat_id, text, parse_mode="HTML", reply_markup=kb)

    def check_guess(self, text: str) -> bool:
        target = self.word.strip().lower()
        if not target:
            return False
        tokens = re.findall(r"[\w']+", text.lower(), flags=re.UNICODE)
        # слово может состоять из нескольких слов ("traffic light")
        return target in tokens or target in text.strip().lower().split("  ") \
            or target == " ".join(tokens)

    async def handle_guess(self, bot: Bot, player: Player, text: str) -> bool:
        if self.phase != Phase.RUNNING or player.user_id == self.leader_id:
            return False
        if not self.check_guess(text):
            return False
        self.scores[player.user_id] = self.scores.get(player.user_id, 0) + 1
        await bot.send_message(
            self.chat_id,
            t(self.lang, "croc_guessed", m=player.mention, word=self.word,
              score=self.scores[player.user_id], name=player.name),
            parse_mode="HTML",
        )
        if player.user_id not in self.players:
            self.players[player.user_id] = player
        self.leader_id = player.user_id
        await self._new_round(bot)
        return True

    async def skip_word(self, bot: Bot, user_id: int) -> None:
        if user_id != self.leader_id:
            return
        await bot.send_message(
            self.chat_id, t(self.lang, "croc_skipped", word=self.word), parse_mode="HTML"
        )
        self._pick_word()
        await self._send_word_to_leader(bot)

    def scoreboard(self) -> str:
        if not self.scores:
            return t(self.lang, "score_empty")
        ranked = sorted(self.scores.items(), key=lambda kv: kv[1], reverse=True)
        lines = [
            f"• {self.players[uid].name if uid in self.players else uid}: {score}"
            for uid, score in ranked
        ]
        return t(self.lang, "score_title") + "\n" + "\n".join(lines)
