"""Базовые классы игрового движка: игрок, комната, менеджер комнат."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class Phase(Enum):
    """Фаза игры внутри комнаты."""
    LOBBY = auto()      # идёт набор игроков
    RUNNING = auto()    # игра идёт
    FINISHED = auto()   # игра окончена


@dataclass
class Player:
    user_id: int
    name: str
    # Произвольные данные конкретной игры (роль, карта персонажа и т.п.)
    data: dict = field(default_factory=dict)

    @property
    def mention(self) -> str:
        return f'<a href="tg://user?id={self.user_id}">{self.name}</a>'


class BaseGame:
    """Общий каркас для всех игр.

    Конкретная игра наследуется и реализует текст лобби, старт и игровую логику.
    Экземпляр создаётся на конкретный групповой чат (chat_id).
    """

    #: человекочитаемое имя, минимум/максимум игроков
    title: str = "Игра"
    slug: str = "base"
    min_players: int = 2
    max_players: int = 20

    def __init__(self, chat_id: int, host: Player, lang: str = "ru"):
        self.chat_id = chat_id
        self.host = host
        self.lang = lang
        self.phase = Phase.LOBBY
        self.players: dict[int, Player] = {host.user_id: host}

    # --- лобби ---------------------------------------------------------
    def add_player(self, player: Player) -> bool:
        if self.phase != Phase.LOBBY:
            return False
        if len(self.players) >= self.max_players:
            return False
        if player.user_id in self.players:
            return False
        self.players[player.user_id] = player
        return True

    def remove_player(self, user_id: int) -> bool:
        if self.phase != Phase.LOBBY:
            return False
        return self.players.pop(user_id, None) is not None

    def can_start(self) -> bool:
        return (
            self.phase == Phase.LOBBY
            and len(self.players) >= self.min_players
        )

    def lobby_text(self) -> str:
        from ..i18n import LANGUAGES, t
        names = "\n".join(f"• {p.mention}" for p in self.players.values())
        players_line = t(self.lang, "lobby_players", cur=len(self.players),
                         max=self.max_players, min=self.min_players)
        host_label = t(self.lang, "lobby_host")
        lang_name = LANGUAGES.get(self.lang, self.lang)
        return (
            f"<b>{self.title}</b>  ·  {lang_name}\n"
            f"{players_line}\n"
            f"━━━━━━━━━━━━━━\n"
            f"{names}\n"
            f"━━━━━━━━━━━━━━\n"
            f"{host_label}: {self.host.mention}"
        )


class RoomManager:
    """Хранит по одной активной игре на групповой чат."""

    def __init__(self) -> None:
        self._rooms: dict[int, BaseGame] = {}

    def get(self, chat_id: int) -> BaseGame | None:
        return self._rooms.get(chat_id)

    def set(self, chat_id: int, game: BaseGame) -> None:
        self._rooms[chat_id] = game

    def clear(self, chat_id: int) -> None:
        self._rooms.pop(chat_id, None)

    def has_active(self, chat_id: int) -> bool:
        game = self._rooms.get(chat_id)
        return game is not None and game.phase != Phase.FINISHED
