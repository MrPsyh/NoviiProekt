"""Игра «Шпион» (на основе Brawl Stars), в стиле Spyfall.

Все игроки, кроме шпиона, получают в ЛС одного и того же бравлера (с фото).
По очереди намекают на него, не называя имени, и вычисляют шпиона голосованием.
Два режима: шпион ЗНАЕТ, что он шпион, либо НЕ ЗНАЕТ (получает другого бравлера).

Изображения бравлеров — собственность Supercell, подключаются из
assets/brawlers/<id>.png по Fan Content Policy (неофициальный фан-проект).
"""
from __future__ import annotations

import os
import random
from io import BytesIO

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from ..cards import render_brawler_card
from ..data.brawl import BRAWLERS
from .base import BaseGame, Phase, Player

_ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets", "brawlers")


def _brawler_photo(brawler):
    """Оригинальный арт из assets/brawlers/<id>.png, иначе нейтральная карточка."""
    bid, _en, ru, rarity = brawler
    path = os.path.join(_ASSETS, f"{bid}.png")
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                bio = BytesIO(f.read())
            bio.name = f"{bid}.png"
            return bio
        except OSError:
            pass
    return render_brawler_card(ru, rarity)


class SpyGame(BaseGame):
    title = "🕵️ Шпион (Brawl Stars)"
    slug = "spy"
    min_players = 3
    max_players = 12
    restrict_outsiders = True

    def __init__(self, chat_id: int, host: Player, lang: str = "ru", mode: str = "known"):
        super().__init__(chat_id, host, lang)
        self.mode = mode                # known | unknown
        self.brawler = None
        self.spy_id: int | None = None
        self.alive: set[int] = set()
        self.vote_active = False
        self.votes: dict[int, int] = {}
        self.voted: set[int] = set()
        self.await_guess = False
        self.guess_options: list = []

    async def start(self, bot: Bot) -> None:
        self.phase = Phase.RUNNING
        self.brawler = random.choice(BRAWLERS)
        ids = list(self.players)
        self.spy_id = random.choice(ids)
        self.alive = set(ids)

        for uid in ids:
            player = self.players[uid]
            if uid == self.spy_id and self.mode == "known":
                try:
                    await bot.send_message(
                        uid,
                        "🕵️ Ты <b>ШПИОН</b>!\nТы не знаешь, кого загадали. "
                        "Слушай намёки, не выдай себя — и попробуй угадать бравлера.",
                        parse_mode="HTML",
                    )
                except TelegramError:
                    await self._warn_pm(bot, player)
                continue
            # обычный игрок, либо шпион в режиме «не знает» (другой бравлер)
            if uid == self.spy_id and self.mode == "unknown":
                shown = random.choice([b for b in BRAWLERS if b != self.brawler])
            else:
                shown = self.brawler
            try:
                await bot.send_photo(
                    uid, _brawler_photo(shown),
                    caption=f"Твой персонаж: <b>{shown[2]}</b> ({shown[3]})\n"
                            f"Намекай на него, не называя имени!",
                    parse_mode="HTML",
                )
            except TelegramError:
                await self._warn_pm(bot, player)

        mode_txt = ("шпион знает, что он шпион" if self.mode == "known"
                    else "шпион не знает, что он шпион")
        intro = (
            "🕵️ <b>Шпион</b> начался!\n"
            "Все, кроме одного, получили одного и того же бравлера Brawl Stars. "
            "По очереди намекайте на него, <b>не называя имени</b>, и вычислите шпиона.\n\n"
            f"Режим: <i>{mode_txt}</i>.\n"
            "Когда наговоритесь — ведущий жмёт «Голосовать»."
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🗳 Голосовать за шпиона", callback_data="svstart")
        ]])
        await bot.send_message(self.chat_id, intro, parse_mode="HTML", reply_markup=kb)

    async def _warn_pm(self, bot: Bot, player: Player) -> None:
        await bot.send_message(
            self.chat_id,
            f"⚠️ {player.mention}, напиши мне /start в ЛС — не смог прислать роль.",
            parse_mode="HTML",
        )

    # --- голосование ---------------------------------------------------
    def start_vote(self) -> bool:
        if self.phase != Phase.RUNNING or self.vote_active or self.await_guess:
            return False
        self.vote_active = True
        self.votes = {}
        self.voted = set()
        return True

    def register_vote(self, voter_id: int, target_id: int) -> bool:
        if not self.vote_active or voter_id not in self.alive or target_id not in self.alive:
            return False
        if voter_id in self.voted:
            return False
        self.votes[voter_id] = target_id
        self.voted.add(voter_id)
        return True

    def all_voted(self) -> bool:
        return self.voted >= self.alive

    def _tally(self) -> int | None:
        counts: dict[int, int] = {}
        for t in self.votes.values():
            counts[t] = counts.get(t, 0) + 1
        if not counts:
            return None
        top = max(counts.values())
        leaders = [uid for uid, c in counts.items() if c == top]
        return leaders[0] if len(leaders) == 1 else None

    def alive_players(self) -> list[Player]:
        return [self.players[u] for u in self.alive]

    async def finish_vote(self, bot: Bot) -> None:
        if not self.vote_active:
            return
        self.vote_active = False
        leader = self._tally()

        if leader == self.spy_id:
            if self.mode == "known":
                # шпиона поймали, но у него шанс угадать бравлера
                self.await_guess = True
                opts = random.sample([b for b in BRAWLERS if b != self.brawler], 5)
                opts.append(self.brawler)
                random.shuffle(opts)
                self.guess_options = opts
                buttons = [[InlineKeyboardButton(b[2], callback_data=f"sg:{i}")]
                           for i, b in enumerate(opts)]
                await bot.send_message(
                    self.chat_id,
                    f"🎯 Шпион — {self.players[self.spy_id].mention}! "
                    f"Но у него шанс угадать персонажа и украсть победу...",
                    parse_mode="HTML",
                )
                try:
                    await bot.send_message(
                        self.spy_id, "🎯 Угадай, кого загадали:",
                        reply_markup=InlineKeyboardMarkup(buttons))
                except TelegramError:
                    await self._end(bot, players_win=True,
                                    note="(шпион недоступен в ЛС)")
                return
            await self._end(bot, players_win=True)
        else:
            await self._end(bot, players_win=False)

    async def spy_guess(self, bot: Bot, idx: int) -> None:
        if not self.await_guess or not (0 <= idx < len(self.guess_options)):
            return
        self.await_guess = False
        guess = self.guess_options[idx]
        if guess == self.brawler:
            await self._end(bot, players_win=False,
                            note=f"Шпион угадал персонажа ({guess[2]}) и побеждает!")
        else:
            await self._end(bot, players_win=True,
                            note=f"Шпион промахнулся (назвал {guess[2]}).")

    async def _end(self, bot: Bot, players_win: bool, note: str = "") -> None:
        self.phase = Phase.FINISHED
        if players_win:
            self.record_scores({u: 1 for u in self.players if u != self.spy_id})
        else:
            self.record_scores({self.spy_id: 1})
        winner = "🏙 Мирные победили!" if players_win else "🕵️ Шпион победил!"
        prefix = (note + "\n\n") if note else ""
        await bot.send_message(
            self.chat_id,
            f"{prefix}Шпионом был: {self.players[self.spy_id].mention}\n"
            f"Загадан был: <b>{self.brawler[2]}</b> ({self.brawler[3]})\n\n"
            f"{winner}\n\n/newgame — сыграть ещё.",
            parse_mode="HTML",
        )
