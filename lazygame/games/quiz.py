"""Соло-игра «Викторина» (в ЛС с ботом).

Бот задаёт вопросы с 4 вариантами, игрок отвечает кнопками. В конце — результат.
"""
from __future__ import annotations

import random

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from ..data.quiz import QUESTIONS
from .base import BaseGame, Phase, Player

LETTERS = ["А", "Б", "В", "Г"]
ROUNDS = 7


class QuizGame(BaseGame):
    title = "🧠 Викторина"
    slug = "quiz"
    min_players = 1
    max_players = 1

    def __init__(self, chat_id: int, host: Player):
        super().__init__(chat_id, host)
        self.questions: list = []
        self.index = 0
        self.score = 0
        self.answered = False

    async def start(self, bot: Bot) -> None:
        self.phase = Phase.RUNNING
        self.questions = random.sample(QUESTIONS, min(ROUNDS, len(QUESTIONS)))
        self.index = 0
        self.score = 0
        await self.send_question(bot)

    async def send_question(self, bot: Bot) -> None:
        self.answered = False
        q, options, _ = self.questions[self.index]
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{LETTERS[i]}. {opt}", callback_data=f"qz:{i}")]
            for i, opt in enumerate(options)
        ])
        await bot.send_message(
            self.chat_id,
            f"<b>Вопрос {self.index + 1}/{len(self.questions)}</b>\n\n"
            f"<blockquote>{q}</blockquote>",
            parse_mode="HTML",
            reply_markup=kb,
        )

    async def answer(self, bot: Bot, user_id: int, choice: int) -> None:
        if self.phase != Phase.RUNNING or self.answered:
            return
        if user_id != self.host.user_id:
            return
        self.answered = True
        q, options, correct = self.questions[self.index]
        if choice == correct:
            self.score += 1
            head = "✅ <b>Верно!</b>"
        else:
            head = (f"❌ <b>Неверно.</b> Правильный ответ: "
                    f"<b>{LETTERS[correct]}. {options[correct]}</b>")
        await bot.send_message(self.chat_id, head, parse_mode="HTML")

        self.index += 1
        if self.index >= len(self.questions):
            await self._finish(bot)
        else:
            await self.send_question(bot)

    async def _finish(self, bot: Bot) -> None:
        self.phase = Phase.FINISHED
        total = len(self.questions)
        if self.score == total:
            verdict = "🏆 Идеально! Ты эрудит!"
        elif self.score >= total * 0.6:
            verdict = "👍 Отличный результат!"
        elif self.score >= total * 0.3:
            verdict = "🙂 Неплохо, но есть куда расти."
        else:
            verdict = "📚 Самое время подтянуть знания!"
        await bot.send_message(
            self.chat_id,
            f"<b>Викторина окончена!</b>\n\n"
            f"Твой результат: <b>{self.score}/{total}</b>\n{verdict}\n\n"
            f"/play — сыграть ещё раз.",
            parse_mode="HTML",
        )
