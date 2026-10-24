"""Реестр игр LazyGame."""
from .base import BaseGame, Phase, Player, RoomManager
from .bunker import BunkerGame
from .crocodile import CrocodileGame
from .guess_number import GuessNumberGame
from .hangman import HangmanGame
from .mafia import MafiaGame
from .quiz import QuizGame
from .rps import RPSGame
from .spy import SpyGame
from .truth_or_dare import TruthOrDareGame

# Групповые игры (меню /newgame). Чтобы добавить игру — допиши её сюда.
GAME_REGISTRY: dict[str, type[BaseGame]] = {
    CrocodileGame.slug: CrocodileGame,
    BunkerGame.slug: BunkerGame,
    MafiaGame.slug: MafiaGame,
    HangmanGame.slug: HangmanGame,
    TruthOrDareGame.slug: TruthOrDareGame,
    SpyGame.slug: SpyGame,
}

# Соло-игры для ЛС с ботом (меню /play).
SOLO_REGISTRY: dict[str, type[BaseGame]] = {
    HangmanGame.slug: HangmanGame,
    QuizGame.slug: QuizGame,
    GuessNumberGame.slug: GuessNumberGame,
    RPSGame.slug: RPSGame,
}

__all__ = [
    "BaseGame", "Phase", "Player", "RoomManager",
    "CrocodileGame", "BunkerGame", "MafiaGame", "HangmanGame",
    "TruthOrDareGame", "QuizGame", "GuessNumberGame", "RPSGame", "SpyGame",
    "GAME_REGISTRY", "SOLO_REGISTRY",
]
