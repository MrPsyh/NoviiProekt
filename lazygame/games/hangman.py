"""Игра «Виселица» (кооперативная / соло).

Бот загадывает слово, игроки пишут буквы (или слово целиком). За каждую ошибку
достраивается виселица. 10 попыток. Язык и сложность задаются при создании.
"""
from __future__ import annotations

import random

from telegram import Bot

from ..cards import render_hangman
from ..data.hangman_words import HANGMAN_WORDS
from ..i18n import t
from .base import BaseGame, Phase, Player

MAX_STAGE = 10


class HangmanGame(BaseGame):
    title = "🪢 Виселица"
    slug = "hangman"
    min_players = 1
    max_players = 30

    def __init__(self, chat_id: int, host: Player, lang: str = "ru",
                 difficulty: str = "medium"):
        super().__init__(chat_id, host, lang)
        self.difficulty = difficulty
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
        pool = HANGMAN_WORDS.get(self.lang, HANGMAN_WORDS["ru"])
        words = pool.get(self.difficulty) or pool["medium"]
        self.word = random.choice(words).lower()
        self.guessed, self.wrong, self.stage = set(), [], 0
        await bot.send_photo(
            self.chat_id,
            render_hangman(self._masked(), self.wrong, self.stage, MAX_STAGE),
            caption=t(self.lang, "hang_start", n=len(self.word.replace(" ", "")),
                      max=MAX_STAGE),
        )

    async def handle_input(self, bot: Bot, player: Player, text: str) -> None:
        if self.phase != Phase.RUNNING:
            return
        guess = text.strip().lower()
        word_norm = self.word.replace("ё", "е")
        guess_norm = guess.replace("ё", "е")

        if len(guess_norm) == 1 and guess_norm.isalpha():
            await self._guess_letter(bot, player, guess_norm, word_norm)
        elif guess_norm == word_norm:
            self.guessed = set(self.word)
            self._award(player, 3)
            await self._finish(bot, won=True, by=player)

    async def _guess_letter(self, bot: Bot, player: Player, letter: str,
                            word_norm: str) -> None:
        if letter in self.guessed:
            return
        self.guessed.add(letter)
        if letter in word_norm:
            count = word_norm.count(letter)
            self._award(player, count)
            caption = t(self.lang, "hang_hit", name=player.name,
                        letter=letter.upper(), count=count)
            if self._is_solved():
                await self._finish(bot, won=True, by=player)
                return
        else:
            self.wrong.append(letter)
            self.stage += 1
            caption = t(self.lang, "hang_miss", name=player.name,
                        letter=letter.upper(), stage=self.stage, max=MAX_STAGE)
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
        key = "hang_win" if won else "hang_lose"
        head = t(self.lang, key, word=self.word, name=by.name)
        replay = t(self.lang, "replay")
        await bot.send_photo(
            self.chat_id,
            render_hangman(self.word, self.wrong, self.stage, MAX_STAGE),
            caption=f"{head}\n\n{self.scoreboard()}\n\n{replay}",
            parse_mode="HTML",
        )

    def scoreboard(self) -> str:
        if not self.scores:
            return t(self.lang, "score_empty")
        ranked = sorted(self.scores.items(), key=lambda kv: kv[1], reverse=True)
        lines = [
            f"• {self.players[u].name if u in self.players else u}: {s}"
            for u, s in ranked
        ]
        return t(self.lang, "score_title") + "\n" + "\n".join(lines)
