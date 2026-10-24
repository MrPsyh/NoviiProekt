"""Игра «Виселица» (кооперативная).

Бот загадывает слово, игроки по очереди пишут в чат буквы (или слово целиком).
За каждую ошибку достраивается виселица (6 этапов). Угадали слово — победа,
достроили виселицу — поражение. Каждое состояние присылается картинкой.
"""
from __future__ import annotations

import random

from telegram import Bot

from ..cards import render_hangman
from ..data.hangman_words import HANGMAN_WORDS
from .base import BaseGame, Phase, Player

MAX_STAGE = 6


class HangmanGame(BaseGame):
    title = "🪢 Виселица"
    slug = "hangman"
    min_players = 1
    max_players = 30

    def __init__(self, chat_id: int, host: Player):
        super().__init__(chat_id, host)
        self.word = ""
        self.guessed: set[str] = set()
        self.wrong: list[str] = []
        self.stage = 0
        self.scores: dict[int, int] = {}

    def _masked(self) -> str:
        return "".join(ch if ch in self.guessed else "_" for ch in self.word)

    def _is_solved(self) -> bool:
        return all(ch in self.guessed for ch in self.word)

    async def start(self, bot: Bot) -> None:
        self.phase = Phase.RUNNING
        self.word = random.choice(HANGMAN_WORDS).lower()
        self.guessed = set()
        self.wrong = []
        self.stage = 0
        await bot.send_photo(
            self.chat_id,
            render_hangman(self._masked(), self.wrong, self.stage, MAX_STAGE),
            caption=(
                f"🪢 Загадано слово из {len(self.word)} букв.\n"
                f"Пишите буквы в чат! Можно назвать слово целиком.\n"
                f"Ошибок до проигрыша: {MAX_STAGE}."
            ),
        )

    async def handle_input(self, bot: Bot, player: Player, text: str) -> None:
        if self.phase != Phase.RUNNING:
            return
        guess = text.strip().lower().replace("ё", "е")
        word_norm = self.word.replace("ё", "е")

        # буквы кириллицы/латиницы
        if len(guess) == 1 and guess.isalpha():
            await self._guess_letter(bot, player, guess, word_norm)
        elif guess == word_norm:
            self.guessed = set(self.word)
            self._award(player, 3)
            await self._finish(bot, won=True, by=player)

    async def _guess_letter(self, bot: Bot, player: Player, letter: str,
                            word_norm: str) -> None:
        if letter in self.guessed:
            return  # уже называли — молча игнорируем
        self.guessed.add(letter)

        if letter in word_norm:
            count = word_norm.count(letter)
            self._award(player, count)
            caption = f"✅ {player.name} открыл букву «{letter.upper()}» (×{count})."
            if self._is_solved():
                await self._finish(bot, won=True, by=player)
                return
        else:
            self.wrong.append(letter)
            self.stage += 1
            caption = f"❌ {player.name}: буквы «{letter.upper()}» нет. Ошибка {self.stage}/{MAX_STAGE}."
            if self.stage >= MAX_STAGE:
                await self._finish(bot, won=False, by=player)
                return

        await bot.send_photo(
            self.chat_id,
            render_hangman(self._masked(), self.wrong, self.stage, MAX_STAGE),
            caption=caption,
        )

    def _award(self, player: Player, pts: int) -> None:
        if player.user_id not in self.players:
            self.players[player.user_id] = player
        self.scores[player.user_id] = self.scores.get(player.user_id, 0) + pts

    async def _finish(self, bot: Bot, won: bool, by: Player) -> None:
        self.phase = Phase.FINISHED
        head = (
            f"🎉 Победа! Слово «<b>{self.word}</b>» отгадал(а) {by.name}."
            if won else
            f"💀 Поражение! Виселица достроена. Слово было «<b>{self.word}</b>»."
        )
        await bot.send_photo(
            self.chat_id,
            render_hangman(self.word, self.wrong, self.stage, MAX_STAGE),
            caption=head + "\n\n" + self.scoreboard() + "\n\n/newgame — ещё раз.",
            parse_mode="HTML",
        )

    def scoreboard(self) -> str:
        if not self.scores:
            return "Очков пока нет."
        ranked = sorted(self.scores.items(), key=lambda kv: kv[1], reverse=True)
        lines = [
            f"• {self.players[u].name if u in self.players else u}: {s}"
            for u, s in ranked
        ]
        return "🏆 <b>Очки:</b>\n" + "\n".join(lines)
