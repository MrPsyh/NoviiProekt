"""Реестр игр LazyGame."""
from .anagram import AnagramGame
from .base import BaseGame, Phase, Player, RoomManager
from .bunker import BunkerGame
from .crocodile import CrocodileGame
from .guess_number import GuessNumberGame
from .hangman import HangmanGame
from .mafia import MafiaGame
from .memory import MemoryGame
from .never import NeverGame
from .quiz import QuizGame
from .reaction import ReactionGame
from .rps import RPSGame
from .spy import SpyGame
from .truth_or_dare import TruthOrDareGame
from .whois import WhoisGame

# Групповые игры (меню /newgame). Чтобы добавить игру — допиши её сюда.
GAME_REGISTRY: dict[str, type[BaseGame]] = {
    CrocodileGame.slug: CrocodileGame,
    BunkerGame.slug: BunkerGame,
    MafiaGame.slug: MafiaGame,
    HangmanGame.slug: HangmanGame,
    TruthOrDareGame.slug: TruthOrDareGame,
    SpyGame.slug: SpyGame,
    ReactionGame.slug: ReactionGame,
    WhoisGame.slug: WhoisGame,
    NeverGame.slug: NeverGame,
}

# Соло-игры для ЛС с ботом (меню /play).
SOLO_REGISTRY: dict[str, type[BaseGame]] = {
    HangmanGame.slug: HangmanGame,
    QuizGame.slug: QuizGame,
    GuessNumberGame.slug: GuessNumberGame,
    RPSGame.slug: RPSGame,
    MemoryGame.slug: MemoryGame,
    AnagramGame.slug: AnagramGame,
}

__all__ = [
    "BaseGame", "Phase", "Player", "RoomManager",
    "CrocodileGame", "BunkerGame", "MafiaGame", "HangmanGame",
    "TruthOrDareGame", "QuizGame", "GuessNumberGame", "RPSGame", "SpyGame",
    "ReactionGame", "WhoisGame", "NeverGame", "MemoryGame", "AnagramGame",
    "GAME_REGISTRY", "SOLO_REGISTRY",
]
