"""Тесты игровой логики LazyGame (без сети)."""
import asyncio

from conftest import FakeBot

from lazygame.games import (
    AnagramGame, BunkerGame, CrocodileGame, GuessNumberGame, HangmanGame,
    MafiaGame, MemoryGame, NeverGame, Phase, Player, QuizGame, ReactionGame,
    RPSGame, SpyGame, WhoisGame,
)


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _fill(game, n):
    for i in range(2, n + 1):
        game.add_player(Player(i, f"P{i}"))


# --- Крокодил ---------------------------------------------------------
def test_crocodile_guess_and_norepeat():
    g = CrocodileGame(1, Player(1, "H"), "ru", "easy")
    g.word = "осьминог"
    assert g.check_guess("осьминог")
    assert g.check_guess("это осьминог!")
    assert not g.check_guess("кит")
    pool = g._words()["easy"]
    seen = set()
    for _ in range(len(pool)):
        g._pick_word()
        seen.add(g.word)
    assert len(seen) == len(pool)  # ни одного повтора за круг


def test_crocodile_languages():
    for lang in ("ru", "en", "uk"):
        g = CrocodileGame(1, Player(1, "H"), lang, "medium")
        g._pick_word()
        assert g.word


# --- Виселица ---------------------------------------------------------
def test_hangman_win_and_lose():
    g = HangmanGame(1, Player(1, "H"), "ru", "easy")
    run(g.start(FakeBot()))
    g.word, g.guessed, g.stage, g.wrong = "кот", set(), 0, []
    run(g.handle_input(FakeBot(), Player(1, "H"), "кот"))
    assert g.phase == Phase.FINISHED

    g2 = HangmanGame(1, Player(1, "H"), "ru", "easy")
    run(g2.start(FakeBot()))
    g2.word, g2.guessed, g2.stage, g2.wrong = "кот", set(), 0, []
    for bad in "йцукенгшщзхъфывапролджэ":
        if g2.phase != Phase.RUNNING:
            break
        run(g2._guess_letter(FakeBot(), Player(1, "H"), bad, "кот"))
    assert g2.stage <= 10


# --- Мафия (сквозная) -------------------------------------------------
def test_mafia_full_game():
    g = MafiaGame(1, Player(1, "H"), "ru")
    _fill(g, 8)
    run(g.start(FakeBot()))
    for _ in range(40):
        if g.phase != Phase.RUNNING:
            break
        if g.is_night:
            for m in g.mafia_members():
                tgt = next((u for u in g.alive if g.players[u].data["role"] != "mafia"), None)
                if tgt:
                    g.submit_mafia(m.user_id, tgt)
            run(g.resolve_night(FakeBot()))
        if g.phase != Phase.RUNNING:
            break
        mafia_alive = [p.user_id for p in g.mafia_members()]
        target = mafia_alive[0] if mafia_alive else list(g.alive)[0]
        for u in list(g.alive):
            g.register_day_vote(u, target)
        run(g.resolve_day(FakeBot()))
    assert g.phase == Phase.FINISHED


# --- Бункер (сквозная) ------------------------------------------------
def test_bunker_full_game():
    g = BunkerGame(1, Player(1, "H"), "ru")
    _fill(g, 6)
    run(g.start(FakeBot()))
    assert g.capacity >= 1
    for _ in range(20):
        if g.phase != Phase.RUNNING:
            break
        for u in list(g.alive):
            run(g.reveal(FakeBot(), u))
        g.start_vote()
        victim = list(g.alive)[-1]
        for u in list(g.alive):
            g.register_vote(u, victim)
        run(g.finish_vote(FakeBot()))
    assert g.phase == Phase.FINISHED
    assert len(g.alive) <= g.capacity


# --- Шпион ------------------------------------------------------------
def test_spy_known_mode():
    g = SpyGame(1, Player(1, "H"), "ru", "known")
    _fill(g, 5)
    run(g.start(FakeBot()))
    assert g.spy_id in g.players and g.brawler
    g.start_vote()
    for u in list(g.alive):
        g.register_vote(u, g.spy_id)
    run(g.finish_vote(FakeBot()))
    assert g.await_guess  # пойман, есть шанс угадать
    wrong = next(i for i, b in enumerate(g.guess_options) if b != g.brawler)
    run(g.spy_guess(FakeBot(), wrong))
    assert g.phase == Phase.FINISHED


def test_spy_unknown_mode_escape():
    g = SpyGame(1, Player(1, "H"), "ru", "unknown")
    _fill(g, 5)
    run(g.start(FakeBot()))
    g.start_vote()
    nonspy = next(u for u in g.alive if u != g.spy_id)
    for u in list(g.alive):
        g.register_vote(u, nonspy)
    run(g.finish_vote(FakeBot()))
    assert g.phase == Phase.FINISHED


# --- Соло игры --------------------------------------------------------
def test_quiz():
    g = QuizGame(1, Player(1, "S"))
    run(g.start(FakeBot()))
    while g.phase == Phase.RUNNING:
        _, _, correct = g.questions[g.index]
        run(g.answer(FakeBot(), 1, correct))
    assert g.score == len(g.questions)


def test_guess_number():
    g = GuessNumberGame(1, Player(1, "S"))
    run(g.start(FakeBot()))
    g.secret = 42
    run(g.handle_input(FakeBot(), Player(1, "S"), "42"))
    assert g.phase == Phase.FINISHED


def test_rps_finishes():
    g = RPSGame(1, Player(1, "S"))
    run(g.start(FakeBot()))
    for _ in range(50):
        if g.phase != Phase.RUNNING:
            break
        run(g.play(FakeBot(), 1, "rock"))
    assert g.phase == Phase.FINISHED


def test_anagram():
    g = AnagramGame(1, Player(1, "S"), "ru", "easy")
    run(g.start(FakeBot()))
    while g.phase == Phase.RUNNING:
        run(g.handle_input(FakeBot(), Player(1, "S"), g.words[g.index]))
    assert g.score == len(g.words)


def test_memory():
    g = MemoryGame(1, Player(1, "S"))
    g.phase, g.seq, g.idx = Phase.RUNNING, [0, 2], 0
    run(g.tap(FakeBot(), 0))
    assert g.idx == 1
    run(g.tap(FakeBot(), 0))  # ждали 2
    assert g.phase == Phase.FINISHED


# --- Пати / реакция ---------------------------------------------------
def test_whois():
    g = WhoisGame(1, Player(1, "H"), "ru")
    _fill(g, 4)
    run(g.start(FakeBot()))
    for u in (1, 2, 3, 4):
        g.register_vote(u, 2)
    assert not g.register_vote(1, 3)  # второй голос не принят
    run(g.reveal(FakeBot()))
    assert g.index == 1


def test_never():
    g = NeverGame(1, Player(1, "H"), "ru")
    _fill(g, 3)
    run(g.start(FakeBot()))
    g.react(1, "yes")
    g.react(2, "no")
    g.react(1, "no")  # переключение
    assert len(g.yes) == 0 and len(g.no) == 2
    run(g.reveal_next(FakeBot()))
    assert g.index == 1


def test_reaction_press():
    g = ReactionGame(1, Player(1, "H"), "ru")
    _fill(g, 3)
    g.phase, g.open = Phase.RUNNING, True
    g._event = asyncio.Event()
    assert g.press(2, "P2") == "win"
    assert g.press(3, "P3") == "late"
    assert g.scores.get(2) == 1
