"""Игра «Крокодил».

Ведущий получает слово в личку (с карточкой-картинкой) и объясняет его
в чате словами/эмодзи, не называя само слово. Остальные угадывают сообщениями
в чате. Кто угадал — становится новым ведущим.
"""
from __future__ import annotations

import random
import re

from telegram import Bot
from telegram.error import TelegramError

from ..cards import render_word_card
from ..data.crocodile_words import WORDS
from .base import BaseGame, Phase, Player


class CrocodileGame(BaseGame):
    title = "🐊 Крокодил"
    slug = "crocodile"
    min_players = 2
    max_players = 35

    def __init__(self, chat_id: int, host: Player):
        super().__init__(chat_id, host)
        self.word: str = ""
        self.difficulty: str = "medium"
        self.leader_id: int = host.user_id
        self.scores: dict[int, int] = {}

    def _pick_word(self) -> None:
        self.difficulty = random.choice(list(WORDS.keys()))
        self.word = random.choice(WORDS[self.difficulty])

    async def _send_word_to_leader(self, bot: Bot) -> bool:
        """Отправляет слово ведущему в ЛС. False, если ЛС недоступна."""
        image = render_word_card(self.word, self.difficulty)
        try:
            await bot.send_photo(
                chat_id=self.leader_id,
                photo=image,
                caption=(
                    f"Объясняй слово в чате, не называя его и однокоренные!\n"
                    f"/skip — пропустить слово."
                ),
            )
            return True
        except TelegramError:
            return False

    async def start(self, bot: Bot) -> None:
        self.phase = Phase.RUNNING
        self.leader_id = random.choice(list(self.players.keys()))
        await self._new_round(bot, announce=True)

    async def _new_round(self, bot: Bot, announce: bool) -> None:
        self._pick_word()
        leader = self.players[self.leader_id]
        delivered = await self._send_word_to_leader(bot)

        text = f"Ведущий: {leader.mention}\nОбъясняет слово — угадывайте в чате!"
        if not delivered:
            text += (
                f"\n\n⚠️ {leader.mention}, я не смог написать тебе в ЛС. "
                f"Напиши мне /start в личку и нажми «Новое слово»."
            )
        await bot.send_message(self.chat_id, text, parse_mode="HTML")

    def check_guess(self, text: str) -> bool:
        target = self.word.strip().lower()
        if not target:
            return False
        # разбиваем фразу на слова, отбрасывая пунктуацию ("это осьминог!" -> осьминог)
        tokens = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
        return target in tokens

    async def handle_guess(self, bot: Bot, player: Player, text: str) -> bool:
        """Проверяет сообщение-угадайку. True — если раунд завершён."""
        if self.phase != Phase.RUNNING:
            return False
        if player.user_id == self.leader_id:
            return False  # ведущий не угадывает
        if not self.check_guess(text):
            return False

        self.scores[player.user_id] = self.scores.get(player.user_id, 0) + 1
        await bot.send_message(
            self.chat_id,
            f"🎉 {player.mention} угадал слово «<b>{self.word}</b>»!\n"
            f"Счёт: {self.scores[player.user_id]} очк.\n\n"
            f"Теперь {player.name} — новый ведущий.",
            parse_mode="HTML",
        )
        # победитель становится ведущим
        if player.user_id not in self.players:
            self.players[player.user_id] = player
        self.leader_id = player.user_id
        await self._new_round(bot, announce=False)
        return True

    async def skip_word(self, bot: Bot, user_id: int) -> None:
        if user_id != self.leader_id:
            return
        old = self.word
        await bot.send_message(
            self.chat_id, f"⏭ Слово «{old}» пропущено.", parse_mode="HTML"
        )
        self._pick_word()
        await self._send_word_to_leader(bot)

    def scoreboard(self) -> str:
        if not self.scores:
            return "Пока никто не угадал."
        ranked = sorted(self.scores.items(), key=lambda kv: kv[1], reverse=True)
        lines = []
        for uid, score in ranked:
            name = self.players.get(uid).name if uid in self.players else str(uid)
            lines.append(f"• {name}: {score}")
        return "🏆 <b>Счёт:</b>\n" + "\n".join(lines)
