"""Игра «Мафия».

Роли: мафия, доктор, комиссар (детектив), мирные жители.
Ночью мафия выбирает жертву, доктор лечит, комиссар проверяет — всё в ЛС.
Днём все обсуждают и голосуют, кого казнить. Город побеждает, если мафии не
осталось; мафия — если её не меньше, чем мирных.
"""
from __future__ import annotations

import random

from telegram import Bot
from telegram.error import TelegramError

from .base import BaseGame, Phase, Player

ROLE_MAFIA = "mafia"
ROLE_DOCTOR = "doctor"
ROLE_DETECTIVE = "detective"
ROLE_CIVILIAN = "civilian"

ROLE_NAMES = {
    ROLE_MAFIA: "🔪 Мафия",
    ROLE_DOCTOR: "💉 Доктор",
    ROLE_DETECTIVE: "🕵️ Комиссар",
    ROLE_CIVILIAN: "👤 Мирный житель",
}


class MafiaGame(BaseGame):
    title = "🔪 Мафия"
    slug = "mafia"
    min_players = 4
    restrict_outsiders = True
    max_players = 35

    def __init__(self, chat_id: int, host: Player, lang: str = "ru"):
        super().__init__(chat_id, host, lang)
        self.alive: set[int] = set()
        self.is_night: bool = False
        # ночные действия
        self.mafia_votes: dict[int, int] = {}   # mafia_id -> target
        self.doctor_save: int | None = None
        self.detective_checked: int | None = None
        # дневное голосование
        self.day_votes: dict[int, int] = {}
        self.day_voted: set[int] = set()

    # --- распределение ролей ------------------------------------------
    def _assign_roles(self) -> None:
        ids = list(self.players.keys())
        random.shuffle(ids)
        n = len(ids)
        mafia_count = max(1, n // 4)  # ~25% мафии

        roles: list[str] = [ROLE_MAFIA] * mafia_count
        roles.append(ROLE_DOCTOR)
        if n >= 6:
            roles.append(ROLE_DETECTIVE)
        while len(roles) < n:
            roles.append(ROLE_CIVILIAN)
        random.shuffle(roles)

        for uid, role in zip(ids, roles):
            self.players[uid].data["role"] = role
            self.players[uid].data["alive"] = True

    def mafia_members(self, alive_only: bool = True) -> list[Player]:
        return [
            p for p in self.players.values()
            if p.data.get("role") == ROLE_MAFIA
            and (not alive_only or p.user_id in self.alive)
        ]

    async def start(self, bot: Bot) -> None:
        self.phase = Phase.RUNNING
        self._assign_roles()
        self.alive = set(self.players.keys())

        for player in self.players.values():
            role = player.data["role"]
            text = f"Твоя роль: <b>{ROLE_NAMES[role]}</b>\n"
            if role == ROLE_MAFIA:
                teammates = [m.name for m in self.mafia_members() if m.user_id != player.user_id]
                if teammates:
                    text += "Твоя команда: " + ", ".join(teammates)
                else:
                    text += "Ты действуешь в одиночку."
            elif role == ROLE_DOCTOR:
                text += "Ночью ты можешь спасти одного игрока."
            elif role == ROLE_DETECTIVE:
                text += "Ночью ты можешь проверить роль одного игрока."
            else:
                text += "Твоя задача — вычислить мафию на дневном голосовании."
            try:
                await bot.send_message(player.user_id, text, parse_mode="HTML")
            except TelegramError:
                await bot.send_message(
                    self.chat_id,
                    f"⚠️ {player.mention}, напиши мне /start в ЛС, "
                    f"иначе не узнаешь свою роль!",
                    parse_mode="HTML",
                )

        await bot.send_message(
            self.chat_id,
            f"🔪 <b>Мафия началась!</b>\nИгроков: {len(self.players)}. "
            f"Роли разосланы в ЛС.\n\nНаступает ночь...",
            parse_mode="HTML",
        )
        await self.begin_night(bot)

    # --- ночь ----------------------------------------------------------
    async def begin_night(self, bot: Bot) -> None:
        self.is_night = True
        self.mafia_votes = {}
        self.doctor_save = None
        self.detective_checked = None
        await bot.send_message(
            self.chat_id,
            "🌙 <b>Ночь.</b> Город спит. Мафия, доктор и комиссар — "
            "проверьте личные сообщения и сделайте выбор.",
            parse_mode="HTML",
        )
        # разослать интерактивные подсказки — кнопки строит bot.py
        await self._prompt_night_actors(bot)

    async def _prompt_night_actors(self, bot: Bot) -> None:
        # фактические кнопки отправляет bot.py через night_targets();
        # здесь только сигнализируем, кому нужно действовать
        self._night_prompt_needed = True

    def night_targets(self, actor_id: int) -> list[Player]:
        """Список возможных целей для ночного действия (живые)."""
        return [self.players[u] for u in self.alive if u != actor_id or True]

    def submit_mafia(self, mafia_id: int, target_id: int) -> None:
        if mafia_id in self.alive and target_id in self.alive:
            self.mafia_votes[mafia_id] = target_id

    def submit_doctor(self, target_id: int) -> None:
        if target_id in self.alive:
            self.doctor_save = target_id

    def submit_detective(self, target_id: int) -> str | None:
        if target_id in self.alive:
            self.detective_checked = target_id
            return self.players[target_id].data.get("role")
        return None

    def _mafia_target(self) -> int | None:
        if not self.mafia_votes:
            return None
        counts: dict[int, int] = {}
        for t in self.mafia_votes.values():
            counts[t] = counts.get(t, 0) + 1
        top = max(counts.values())
        leaders = [uid for uid, c in counts.items() if c == top]
        return random.choice(leaders)

    async def resolve_night(self, bot: Bot) -> None:
        if not self.is_night:
            return
        self.is_night = False
        target = self._mafia_target()

        if target is not None and target != self.doctor_save:
            self.alive.discard(target)
            await bot.send_message(
                self.chat_id,
                f"☀️ Наступает утро. Этой ночью погиб "
                f"{self.players[target].mention} "
                f"({ROLE_NAMES[self.players[target].data['role']]}).",
                parse_mode="HTML",
            )
        else:
            await bot.send_message(
                self.chat_id,
                "☀️ Наступает утро. Этой ночью никто не погиб!",
                parse_mode="HTML",
            )

        if await self._check_win(bot):
            return
        await self.begin_day(bot)

    # --- день ----------------------------------------------------------
    async def begin_day(self, bot: Bot) -> None:
        self.day_votes = {}
        self.day_voted = set()
        alive_list = "\n".join(f"• {self.players[u].mention}" for u in self.alive)
        await bot.send_message(
            self.chat_id,
            f"🗳 <b>День.</b> Обсуждайте и голосуйте, кого казнить.\n\n"
            f"В живых:\n{alive_list}",
            parse_mode="HTML",
        )

    def register_day_vote(self, voter_id: int, target_id: int) -> bool:
        if self.is_night or voter_id not in self.alive or target_id not in self.alive:
            return False
        if voter_id in self.day_voted:
            return False
        self.day_votes[voter_id] = target_id
        self.day_voted.add(voter_id)
        return True

    def all_day_voted(self) -> bool:
        return self.day_voted >= self.alive

    async def resolve_day(self, bot: Bot) -> None:
        counts: dict[int, int] = {}
        for t in self.day_votes.values():
            counts[t] = counts.get(t, 0) + 1

        if counts:
            top = max(counts.values())
            leaders = [uid for uid, c in counts.items() if c == top]
            if len(leaders) == 1:
                kicked = leaders[0]
                self.alive.discard(kicked)
                await bot.send_message(
                    self.chat_id,
                    f"⚖️ Город казнил {self.players[kicked].mention} "
                    f"({ROLE_NAMES[self.players[kicked].data['role']]}).",
                    parse_mode="HTML",
                )
            else:
                await bot.send_message(
                    self.chat_id, "⚖️ Голоса разделились — никого не казнили.",
                    parse_mode="HTML",
                )
        else:
            await bot.send_message(
                self.chat_id, "⚖️ Никто не проголосовал — день прошёл впустую.",
                parse_mode="HTML",
            )

        if await self._check_win(bot):
            return
        await self.begin_night(bot)

    # --- победа --------------------------------------------------------
    async def _check_win(self, bot: Bot) -> bool:
        mafia_alive = len(self.mafia_members())
        others_alive = len(self.alive) - mafia_alive

        winner: str | None = None
        if mafia_alive == 0:
            winner = "🏙 Победил город! Вся мафия обезврежена."
        elif mafia_alive >= others_alive:
            winner = "🔪 Победила мафия! Город захвачен."

        if winner:
            self.phase = Phase.FINISHED
            mafia_won = mafia_alive >= others_alive and mafia_alive > 0
            self.record_scores({
                p.user_id: 1 for p in self.players.values()
                if (p.data.get("role") == ROLE_MAFIA) == mafia_won
            })
            roles = "\n".join(
                f"• {p.name} — {ROLE_NAMES[p.data['role']]}"
                for p in self.players.values()
            )
            await bot.send_message(
                self.chat_id,
                f"🏁 <b>Игра окончена!</b>\n{winner}\n\n"
                f"Все роли:\n{roles}\n\n/newgame — сыграть ещё.",
                parse_mode="HTML",
            )
            return True
        return False
