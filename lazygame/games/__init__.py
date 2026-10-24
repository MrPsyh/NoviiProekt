"""Реестр игр LazyGame."""
from .base import BaseGame, Phase, Player, RoomManager
from .bunker import BunkerGame
from .crocodile import CrocodileGame
from .hangman import HangmanGame
from .mafia import MafiaGame
from .truth_or_dare import TruthOrDareGame

# slug -> класс игры. Чтобы добавить новую игру, допиши её сюда.
GAME_REGISTRY: dict[str, type[BaseGame]] = {
    CrocodileGame.slug: CrocodileGame,
    BunkerGame.slug: BunkerGame,
    MafiaGame.slug: MafiaGame,
    HangmanGame.slug: HangmanGame,
    TruthOrDareGame.slug: TruthOrDareGame,
}

__all__ = [
    "BaseGame", "Phase", "Player", "RoomManager",
    "CrocodileGame", "BunkerGame", "MafiaGame", "HangmanGame",
    "TruthOrDareGame", "GAME_REGISTRY",
]
