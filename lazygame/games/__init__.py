"""Реестр игр LazyGame."""
from .base import BaseGame, Phase, Player, RoomManager
from .bunker import BunkerGame
from .crocodile import CrocodileGame
from .mafia import MafiaGame

# slug -> класс игры. Чтобы добавить новую игру, допиши её сюда.
GAME_REGISTRY: dict[str, type[BaseGame]] = {
    CrocodileGame.slug: CrocodileGame,
    BunkerGame.slug: BunkerGame,
    MafiaGame.slug: MafiaGame,
}

__all__ = [
    "BaseGame", "Phase", "Player", "RoomManager",
    "CrocodileGame", "BunkerGame", "MafiaGame", "GAME_REGISTRY",
]
