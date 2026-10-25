"""Тесты персистентности (SQLite) и локализации."""
from lazygame.i18n import DIFFICULTIES, LANGUAGES, t
from lazygame.settings import settings
from lazygame.stats import stats


class _Chat:
    def __init__(self, cid, title, ctype="supergroup"):
        self.id, self.title, self.type = cid, title, ctype


def test_settings_lang_and_max():
    settings.set_lang(555, "uk")
    assert settings.get_lang(555) == "uk"
    assert settings.get_lang(999) == "ru"  # дефолт
    settings.set_max(555, "mafia", 20)
    assert settings.get_max(555, "mafia", 35) == 20
    assert settings.get_max(555, "crocodile", 35) == 35


def test_cycle_max_wraps():
    settings.set_max(777, "mafia", 35)
    nxt = settings.cycle_max(777, "mafia", 35, 35, 4)
    assert nxt == 8  # после максимума — по кругу к первому пресету


def test_stats_counts():
    stats.touch_chat(_Chat(-200, "Чат А"))
    stats.touch_chat(_Chat(-201, "Чат Б"))
    stats.game_started("mafia", -200, [10, 11])
    stats.game_started("mafia", -200, [11, 12])
    snap = stats.base_snapshot()
    assert snap["by_game"]["mafia"] >= 2
    assert snap["users_total"] >= 3
    assert "-200" in stats.chats
    stats.remove_chat(-200)
    assert "-200" not in stats.chats


def test_leaderboard_accumulates_and_ranks():
    from lazygame import leaderboard
    leaderboard.record("quiz", 111, [(1, "Аня", 5), (2, "Боря", 3)])
    leaderboard.record("quiz", 222, [(1, "Аня", 4)])  # другой чат
    world = leaderboard.world_top("quiz")
    names = [r["name"] for r in world]
    assert names[0] == "Аня"  # 5+4=9, топ мира
    chat = leaderboard.chat_top("quiz", 111)
    assert {r["name"] for r in chat} == {"Аня", "Боря"}
    # игра вне рейтинга не пишется
    leaderboard.record("whois", 111, [(1, "Аня", 5)])
    assert "whois" not in leaderboard.games_with_scores()


def test_i18n_all_languages_have_keys():
    # ключевые строки должны существовать на всех языках без падения
    for lang in LANGUAGES:
        assert t(lang, "choose_game")
        assert t(lang, "btn_join")
        assert t(lang, "min_players", n=4)
    # неизвестный ключ возвращает сам ключ
    assert t("ru", "no_such_key_xyz") == "no_such_key_xyz"
    assert set(DIFFICULTIES) == {"easy", "medium", "hard"}
