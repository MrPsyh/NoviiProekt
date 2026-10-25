"""Игра «Бункер».

Случается катастрофа, в бункере мест меньше, чем игроков. У каждого — карточка
персонажа (профессия, здоровье, хобби, фобия, багаж и т.д.), которая приходит
в ЛС картинкой. По кругу игроки раскрывают по одной характеристике, обсуждают
и голосованием выкидывают слабых. Остаться должны те, кто поместится в бункер.
"""
from __future__ import annotations

import random

from telegram import Bot
from telegram.error import TelegramError

from ..cards import render_character_card
from ..data import bunker_data as bd
from .base import BaseGame, Phase, Player


def _generate_character() -> dict[str, str]:
    age = random.choice(bd.AGES)
    return {
        "profession": random.choice(bd.PROFESSIONS),
        "gender_age": random.choice(bd.GENDER_AGE).format(age=age),
        "health": random.choice(bd.HEALTH),
        "hobby": random.choice(bd.HOBBIES),
        "phobia": random.choice(bd.PHOBIAS),
        "baggage": random.choice(bd.BAGGAGE),
        "fact": random.choice(bd.FACTS),
        "special": random.choice(bd.SPECIAL_CARDS),
    }


class BunkerGame(BaseGame):
    title = "🏚 Бункер"
    slug = "bunker"
    min_players = 3
    restrict_outsiders = True
    max_players = 16

    def __init__(self, chat_id: int, host: Player, lang: str = "ru"):
        super().__init__(chat_id, host, lang)
        self.scenario: str = ""
        self.bunker_lines: list[str] = []
        self.capacity: int = 0
        # кого ещё не выгнали
        self.alive: set[int] = set()
        # user_id -> множество раскрытых ключей характеристик
        self.revealed: dict[int, set[str]] = {}
        # состояние голосования
        self.vote_active: bool = False
        self.votes: dict[int, int] = {}       # voter_id -> target_id
        self.voted_users: set[int] = set()

    # --- запуск --------------------------------------------------------
    def _build_scenario(self) -> None:
        self.scenario = random.choice(bd.CATASTROPHES)
        years = random.choice(bd.BUNKER_YEARS)
        size = random.choice(bd.BUNKER_SIZES)
        people = random.choice(bd.BUNKER_PEOPLE_LIMIT)
        facilities = random.choice(bd.BUNKER_FACILITIES)
        self.capacity = int(people)
        self.bunker_lines = [
            bd.BUNKER_INFO[0].format(years=years),
            bd.BUNKER_INFO[1].format(size=size),
            bd.BUNKER_INFO[2].format(people=people),
            bd.BUNKER_INFO[3].format(facilities=facilities),
        ]

    async def start(self, bot: Bot) -> None:
        self.phase = Phase.RUNNING
        self._build_scenario()
        self.alive = set(self.players.keys())
        # капасити не может быть больше, чем игроков минус 1
        self.capacity = min(self.capacity, max(1, len(self.players) - 1))

        for player in self.players.values():
            player.data["char"] = _generate_character()
            self.revealed[player.user_id] = set()

        intro = (
            f"☢️ <b>КАТАСТРОФА</b>\n<blockquote>{self.scenario}</blockquote>\n"
            f"<b>О бункере:</b>\n" + "\n".join(f"• {l}" for l in self.bunker_lines) +
            f"\n\n🚪 Мест в бункере: <b>{self.capacity}</b> из {len(self.players)} игроков.\n"
            f"Остальных придётся оставить снаружи.\n\n"
            f"Карточки персонажей отправлены вам в личку. "
            f"По очереди раскрывайте характеристики (/reveal) и убеждайте остальных, "
            f"что именно вы достойны места. Затем — голосование (/vote)."
        )
        await bot.send_message(self.chat_id, intro, parse_mode="HTML")

        for player in self.players.values():
            await self._send_card_to_player(bot, player)

    async def _send_card_to_player(self, bot: Bot, player: Player) -> None:
        image = render_character_card(player.name, player.data["char"], bd.REVEAL_ORDER)
        try:
            await bot.send_photo(
                chat_id=player.user_id,
                photo=image,
                caption="Это твой персонаж. Раскрывай характеристики в чате командой /reveal.",
            )
        except TelegramError:
            await bot.send_message(
                self.chat_id,
                f"⚠️ {player.mention}, напиши мне /start в ЛС — "
                f"я не смог отправить тебе карточку.",
                parse_mode="HTML",
            )

    # --- раскрытие характеристик --------------------------------------
    def next_hidden_attr(self, user_id: int) -> tuple[str, str] | None:
        revealed = self.revealed.get(user_id, set())
        for key, label in bd.REVEAL_ORDER:
            if key not in revealed:
                return key, label
        return None

    async def reveal(self, bot: Bot, user_id: int) -> None:
        if self.phase != Phase.RUNNING or user_id not in self.alive:
            return
        attr = self.next_hidden_attr(user_id)
        if attr is None:
            await bot.send_message(
                self.chat_id, "Ты уже раскрыл все характеристики.", parse_mode="HTML"
            )
            return
        key, label = attr
        self.revealed[user_id].add(key)
        player = self.players[user_id]
        value = player.data["char"][key]
        await bot.send_message(
            self.chat_id,
            f"🔓 {player.mention} раскрывает <b>{label}</b>: {value}",
            parse_mode="HTML",
        )

    # --- голосование ---------------------------------------------------
    def start_vote(self) -> bool:
        if self.phase != Phase.RUNNING or self.vote_active:
            return False
        self.vote_active = True
        self.votes = {}
        self.voted_users = set()
        return True

    def register_vote(self, voter_id: int, target_id: int) -> bool:
        if not self.vote_active:
            return False
        if voter_id not in self.alive or target_id not in self.alive:
            return False
        if voter_id in self.voted_users:
            return False
        self.votes[voter_id] = target_id
        self.voted_users.add(voter_id)
        return True

    def all_voted(self) -> bool:
        return self.voted_users >= self.alive

    def tally(self) -> tuple[int | None, dict[int, int]]:
        counts: dict[int, int] = {}
        for target in self.votes.values():
            counts[target] = counts.get(target, 0) + 1
        if not counts:
            return None, counts
        top = max(counts.values())
        leaders = [uid for uid, c in counts.items() if c == top]
        if len(leaders) != 1:
            return None, counts  # ничья — никого не выгоняем
        return leaders[0], counts

    async def finish_vote(self, bot: Bot) -> None:
        if not self.vote_active:
            return
        self.vote_active = False
        kicked, counts = self.tally()

        lines = ["📊 <b>Итоги голосования:</b>"]
        for uid, c in sorted(counts.items(), key=lambda kv: kv[1], reverse=True):
            name = self.players[uid].name
            lines.append(f"• {name}: {c}")
        await bot.send_message(self.chat_id, "\n".join(lines), parse_mode="HTML")

        if kicked is None:
            await bot.send_message(
                self.chat_id, "🤝 Ничья — в этот раз никого не выгнали.",
                parse_mode="HTML",
            )
        else:
            self.alive.discard(kicked)
            await bot.send_message(
                self.chat_id,
                f"🚫 {self.players[kicked].mention} отправляется наружу. Прощай!",
                parse_mode="HTML",
            )

        await self._check_end(bot)

    async def _check_end(self, bot: Bot) -> None:
        if len(self.alive) <= self.capacity:
            self.phase = Phase.FINISHED
            self.record_scores({u: 1 for u in self.alive})
            survivors = "\n".join(f"• {self.players[u].mention}" for u in self.alive)
            await bot.send_message(
                self.chat_id,
                f"🏁 <b>Игра окончена!</b>\nВ бункере остались:\n{survivors}\n\n"
                f"Поздравляем выживших! /newgame — сыграть ещё.",
                parse_mode="HTML",
            )

    def alive_players(self) -> list[Player]:
        return [self.players[u] for u in self.alive]
