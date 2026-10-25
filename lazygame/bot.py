"""LazyGame — точка входа Telegram-бота.

Запуск:  python -m lazygame.bot
Токен берётся из .env (переменная BOT_TOKEN). В коде токена нет и быть не должно.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from io import BytesIO

from telegram import (
    BotCommand,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonWebApp,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .cards import render_admin_panel, render_records, render_welcome
from . import leaderboard
from .config import ADMIN_ID, BOT_TOKEN, WEBAPP_URL
from .games import (
    AnagramGame,
    BunkerGame,
    CrocodileGame,
    GAME_REGISTRY,
    GuessNumberGame,
    HangmanGame,
    MafiaGame,
    MemoryGame,
    NeverGame,
    Phase,
    Player,
    QuizGame,
    ReactionGame,
    RoomManager,
    RPSGame,
    SOLO_REGISTRY,
    SpyGame,
    TruthOrDareGame,
    WhoisGame,
)
from .i18n import LANGUAGES, t
from .settings import settings
from .stats import stats

# игры, у которых контент пока только на русском
RU_CONTENT_GAMES = {"bunker", "mafia", "truthdare", "spy"}
MODE_GAMES = {"spy"}  # игры, где перед стартом выбирают режим

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("lazygame")

rooms = RoomManager()

ADMIN_STATUSES = {"administrator", "creator"}

WELCOME_GAMES = [
    ("Крокодил", "объясняй слово без слов"),
    ("Бункер", "переживи катастрофу"),
    ("Мафия", "найди мафию в городе"),
    ("Виселица", "угадай слово по буквам"),
    ("Правда/Действие", "выбери и выполни"),
    ("Викторина", "соло в личке с ботом"),
]

_WELCOME_BYTES: bytes | None = None


def _welcome_photo() -> BytesIO:
    """Кэшированное приветственное фото (рендерится один раз)."""
    global _WELCOME_BYTES
    if _WELCOME_BYTES is None:
        _WELCOME_BYTES = render_welcome(WELCOME_GAMES).getvalue()
    bio = BytesIO(_WELCOME_BYTES)
    bio.name = "welcome.png"
    return bio


def _webapp_reply_keyboard() -> ReplyKeyboardMarkup | None:
    """Reply-клавиатура с кнопкой мини-аппа (только если задан WEBAPP_URL)."""
    if not WEBAPP_URL:
        return None
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🎮 Открыть LazyGame", web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True,
    )


def _player_from_user(user) -> Player:
    name = user.full_name or user.username or str(user.id)
    return Player(user_id=user.id, name=name)


DIFFICULTY_GAMES = {"crocodile", "hangman", "anagram"}
GAME_MAX_AGE = 3 * 3600     # сек: после этого зависшая игра авто-очищается
SWEEP_EVERY = 300           # как часто подметать зависшие игры
LOBBY_TIMEOUT = 90          # сек на набор игроков
MENU_CD = 30                # сек между открытиями меню одним человеком
MUTE_SECONDS = 60           # мут постороннего, писавшего во время закрытой игры

_menu_owner: dict[int, int] = {}   # message_id -> user_id (чья это панель)
_menu_cd: dict[int, float] = {}    # user_id -> время последнего открытия меню


def _own(message, user_id: int) -> None:
    _menu_owner[message.message_id] = user_id


def _is_owner(query) -> bool:
    owner = _menu_owner.get(query.message.message_id)
    return owner is None or owner == query.from_user.id


async def _deny_foreign(query) -> bool:
    """True и показывает алерт, если это не панель нажавшего."""
    if _is_owner(query):
        return False
    lang = settings.get_lang(query.message.chat.id)
    await query.answer(t(lang, "not_your_menu"), show_alert=True)
    return True


def _cooldown_left(user_id: int) -> int:
    left = MENU_CD - (time.monotonic() - _menu_cd.get(user_id, 0.0))
    return max(0, int(left + 0.999))


async def _user_is_admin(context, chat_id: int, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ADMIN_STATUSES
    except Exception:  # noqa: BLE001
        return False


async def _lobby_timeout(context, game) -> None:
    """Отменяет игру, если за LOBBY_TIMEOUT не набралось минимум игроков."""
    try:
        await asyncio.sleep(LOBBY_TIMEOUT)
    except asyncio.CancelledError:
        return
    if rooms.get(game.chat_id) is game and game.phase == Phase.LOBBY \
            and not game.can_start():
        await _unpin_lobby(context, game)
        rooms.clear(game.chat_id)
        await context.bot.send_message(
            game.chat_id, t(game.lang, "lobby_cancelled", n=game.min_players))


async def _sweep_loop(app) -> None:
    """Периодически убирает завершённые и зависшие игры (защита от утечек)."""
    while True:
        try:
            await asyncio.sleep(SWEEP_EVERY)
            for cid in list(rooms._rooms):  # noqa: SLF001
                game = rooms.get(cid)
                if game is None:
                    continue
                stale = (game.phase == Phase.FINISHED
                         or (time.time() - game.created_at) > GAME_MAX_AGE)
                if stale:
                    if getattr(game, "_pinned", False):
                        try:
                            await app.bot.unpin_chat_message(cid, game._lobby_msg_id)
                        except Exception:
                            pass
                    _record_continuous(game)
                    rooms.clear(cid)
        except asyncio.CancelledError:
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("sweep error: %s", exc)


def _cancel_lobby_timer(game) -> None:
    task = getattr(game, "_lobby_task", None)
    if task and not task.done():
        task.cancel()


async def _bot_is_admin(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, context.bot.id)
        return member.status in ADMIN_STATUSES
    except Exception as exc:  # noqa: BLE001
        logger.warning("Не удалось проверить права в чате %s: %s", chat_id, exc)
        return False


def _max_for(chat_id: int, cls) -> int:
    """Настроенный максимум игроков для игры (с учётом лимитов класса)."""
    configured = settings.get_max(chat_id, cls.slug, cls.max_players)
    return max(cls.min_players, min(configured, cls.max_players))


# ======================================================================
# Приветствие и права администратора
# ======================================================================
async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Реагирует на добавление бота в группу / выдачу прав админа."""
    upd = update.my_chat_member
    if upd is None or upd.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    old = upd.old_chat_member.status
    new = upd.new_chat_member.status
    chat_id = upd.chat.id

    just_added = old in ("left", "kicked") and new in ("member", "administrator")
    promoted = old == "member" and new in ADMIN_STATUSES

    if new in ("left", "kicked"):
        stats.remove_chat(chat_id)
    else:
        stats.touch_chat(upd.chat)

    if just_added and new == "administrator":
        await context.bot.send_message(
            chat_id,
            "👋 Привет! Я <b>LazyGame</b> — бот с играми для компаний.\n"
            "Права админа есть ✅ Пишите /newgame и выбирайте игру!",
            parse_mode="HTML",
        )
    elif just_added:
        await context.bot.send_message(
            chat_id,
            "👋 Я <b>LazyGame</b>! Спасибо, что добавили.\n\n"
            "⚠️ Чтобы я видел сообщения в чате (для Крокодила и Виселицы) и мог "
            "вести игры — <b>сделайте меня администратором</b>:\n"
            "Настройки группы → Администраторы → Добавить → выберите меня.\n\n"
            "После этого напишите /newgame.",
            parse_mode="HTML",
        )
    elif promoted:
        await context.bot.send_message(
            chat_id,
            "✅ Теперь я администратор — всё готово! Пишите /newgame.",
        )


# ======================================================================
# Базовые команды
# ======================================================================
async def _deeplink_join(update: Update, context: ContextTypes.DEFAULT_TYPE, arg: str) -> None:
    """Вход в набор по ссылке t.me/bot?start=join_<chat_id> (открывает ЛС)."""
    try:
        chat_id = int(arg.split("_", 1)[1])
    except (ValueError, IndexError):
        await update.message.reply_text("Ссылка набора недействительна.")
        return
    game = rooms.get(chat_id)
    if not game or game.phase != Phase.LOBBY:
        await update.message.reply_text("Набор в этом чате уже закрыт или не найден.")
        return
    if game.add_player(_player_from_user(update.effective_user)):
        await update.message.reply_text(
            f"✅ Ты записан в «{game.title}»! Возвращайся в чат и жди старта.\n"
            f"Роль/карточку пришлю сюда, в личку.")
        await _render_lobby(context, game)
    else:
        await update.message.reply_text("Ты уже в списке или мест нет.")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    if (update.effective_chat.type == ChatType.PRIVATE
            and args and args[0].startswith("join_")):
        await _deeplink_join(update, context, args[0])
        return
    if update.effective_chat.type == ChatType.PRIVATE:
        caption = (
            "Привет! Я <b>LazyGame</b> 🎲\n\n"
            "🎮 <b>В личке</b> со мной можно играть соло — жми /play "
            "(Виселица и Викторина).\n"
            "👥 <b>В группе</b> — весёлые игры на компанию: добавь меня, сделай "
            "админом и напиши /newgame.\n\n"
            "<blockquote>Совет: держи этот чат открытым — сюда я присылаю слова "
            "и роли во время игр.</blockquote>"
        )
        markup = None
        if WEBAPP_URL:
            markup = InlineKeyboardMarkup([[InlineKeyboardButton(
                "🎮 Войти в соло-игры", web_app=WebAppInfo(url=WEBAPP_URL))]])
        await update.message.reply_photo(
            _welcome_photo(), caption=caption, parse_mode="HTML", reply_markup=markup
        )
    else:
        await update.message.reply_photo(
            _welcome_photo(),
            caption="🎲 <b>LazyGame</b> тут! Пиши /newgame — выберем игру.",
            parse_mode="HTML",
        )


def _two_col(items: list[tuple[str, str]], prefix: str,
             tail: list[list[InlineKeyboardButton]] | None = None) -> InlineKeyboardMarkup:
    """Кнопки в 2 столбца: игра игра / игра игра / ... + необязательный хвост."""
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(items[i][1], callback_data=f"{prefix}:{items[i][0]}")]
        if i + 1 < len(items):
            row.append(InlineKeyboardButton(items[i + 1][1],
                                            callback_data=f"{prefix}:{items[i + 1][0]}"))
        rows.append(row)
    if tail:
        rows.extend(tail)
    return InlineKeyboardMarkup(rows)


def _diff_markup(lang: str, prefix: str, slug: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "diff_easy"), callback_data=f"{prefix}:{slug}:easy")],
        [InlineKeyboardButton(t(lang, "diff_medium"), callback_data=f"{prefix}:{slug}:medium")],
        [InlineKeyboardButton(t(lang, "diff_hard"), callback_data=f"{prefix}:{slug}:hard")],
    ])


async def cmd_play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Соло-игры в личке с ботом."""
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.message.reply_text("Соло-игры — только в личке со мной. Напиши мне /play 🙂")
        return
    chat_id = update.effective_chat.id
    if rooms.has_active(chat_id):
        await update.message.reply_text("У тебя уже идёт игра. Заверши её: /stop")
        return
    left = _cooldown_left(update.effective_user.id)
    if left > 0:
        await update.message.reply_text(t(settings.get_lang(chat_id), "cooldown", n=left))
        return
    _menu_cd[update.effective_user.id] = time.monotonic()
    items = [(slug, cls.title) for slug, cls in SOLO_REGISTRY.items()]
    msg = await update.message.reply_text(
        "🎮 <b>Соло-игры</b>\nВыбери, во что сыграем:",
        parse_mode="HTML", reply_markup=_two_col(items, "solo"),
    )
    _own(msg, update.effective_user.id)


async def _start_solo(context, chat_id, user, slug, difficulty=None) -> None:
    lang = settings.get_lang(chat_id)
    cls = SOLO_REGISTRY[slug]
    if slug in DIFFICULTY_GAMES:
        game = cls(chat_id, _player_from_user(user), lang, difficulty or "medium")
    else:
        game = cls(chat_id, _player_from_user(user), lang)
    rooms.set(chat_id, game)
    stats.game_started(slug, chat_id, [user.id])
    await game.start(context.bot)


async def on_choose_solo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if await _deny_foreign(query):
        return
    await query.answer()
    slug = query.data.split(":", 1)[1]
    chat_id = query.message.chat.id
    cls = SOLO_REGISTRY.get(slug)
    if not cls or rooms.has_active(chat_id):
        await query.edit_message_text("Не получилось начать. Напиши /play заново.")
        return
    lang = settings.get_lang(chat_id)
    if slug in DIFFICULTY_GAMES:  # спрашиваем сложность
        await query.edit_message_text(t(lang, "choose_diff"),
                                      reply_markup=_diff_markup(lang, "sd", slug))
        return
    await query.edit_message_text(f"▶️ {cls.title}")
    await _start_solo(context, chat_id, query.from_user, slug)


async def on_solo_diff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if await _deny_foreign(query):
        return
    await query.answer()
    _, slug, difficulty = query.data.split(":")
    chat_id = query.message.chat.id
    if rooms.has_active(chat_id):
        await query.edit_message_text("Не получилось начать. Напиши /play заново.")
        return
    await query.edit_message_text(f"▶️ {SOLO_REGISTRY[slug].title}")
    await _start_solo(context, chat_id, query.from_user, slug, difficulty)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎲 <b>LazyGame — команды</b>\n\n"
        "/newgame — групповая игра (выбор языка RU/EN/UK → игра)\n"
        "/play — соло-игра в личке\n"
        "/settings — настройки (лимиты игроков)\n"
        "/go — начать игру (ведущий)\n"
        "/stop — остановить игру (ведущий)\n\n"
        "<b>👥 В группе:</b> Крокодил, Бункер, Мафия, Виселица, Правда/Действие, "
        "Шпион, Реакция, Кто из нас?, Я никогда не…\n"
        "<b>🙂 Соло в ЛС:</b> Виселица, Викторина, Угадай число, Камень-ножницы-бумага, "
        "Повтори, Анаграммы\n\n"
        "<b>Крокодил:</b> /skip — пропустить слово, /score — счёт\n"
        "<b>Бункер:</b> /reveal — раскрыть характеристику, /vote — голосование\n"
        "<b>Виселица:</b> пишите буквы в чат (10 попыток)\n"
        "<b>Мафия:</b> ночь — в личке, день — голосование кнопками",
        parse_mode="HTML",
    )


def _lang_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(name, callback_data=f"nl:{code}")]
         for code, name in LANGUAGES.items()]
    )


def _game_menu_markup(lang: str) -> InlineKeyboardMarkup:
    items = [(slug, cls.title) for slug, cls in GAME_REGISTRY.items()]
    tail = [[InlineKeyboardButton(t(lang, "btn_settings"), callback_data="settings")]]
    return _two_col(items, "ng", tail)


async def cmd_newgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type == ChatType.PRIVATE:
        await update.message.reply_text("Игры запускаются в групповом чате. Добавь меня в группу!")
        return
    chat_id = update.effective_chat.id
    stats.touch_chat(update.effective_chat)
    lang = settings.get_lang(chat_id)
    if not await _bot_is_admin(context, chat_id):
        await update.message.reply_text(t(lang, "need_admin"), parse_mode="HTML")
        return
    if rooms.has_active(chat_id):
        await update.message.reply_text(t(lang, "already_active"))
        return
    left = _cooldown_left(update.effective_user.id)
    if left > 0:
        await update.message.reply_text(t(lang, "cooldown", n=left))
        return
    _menu_cd[update.effective_user.id] = time.monotonic()
    # шаг 1 — выбор языка
    msg = await update.message.reply_text(t(lang, "choose_lang"), reply_markup=_lang_markup())
    _own(msg, update.effective_user.id)


async def on_choose_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if await _deny_foreign(query):
        return
    await query.answer()
    lang = query.data.split(":", 1)[1]
    chat_id = query.message.chat.id
    settings.set_lang(chat_id, lang)
    # шаг 2 — выбор игры (2 столбца)
    await query.edit_message_text(t(lang, "choose_game"), reply_markup=_game_menu_markup(lang))


def _mode_markup(lang: str, slug: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🕵️ Шпион знает, что он шпион",
                              callback_data=f"nm:{slug}:known")],
        [InlineKeyboardButton("🙈 Шпион не знает, что он шпион",
                              callback_data=f"nm:{slug}:unknown")],
    ])


async def _create_group_lobby(context, query, chat_id, slug, lang,
                              difficulty=None, mode=None) -> None:
    cls = GAME_REGISTRY[slug]
    host = _player_from_user(query.from_user)
    if slug in DIFFICULTY_GAMES:
        game = cls(chat_id, host, lang, difficulty or "medium")
    elif slug in MODE_GAMES:
        game = cls(chat_id, host, lang, mode or "known")
    else:
        game = cls(chat_id, host, lang)
    game.max_players = _max_for(chat_id, cls)
    rooms.set(chat_id, game)
    note = t(lang, "content_ru_only") if (lang != "ru" and slug in RU_CONTENT_GAMES) else ""
    game._lobby_msg_id = query.message.message_id
    await query.edit_message_text(
        note + game.lobby_text() + "\n\n" + t(lang, "lobby_hint"),
        parse_mode="HTML", reply_markup=_lobby_kb(context, game),
    )
    # закрепляем набор, как у популярных ботов
    try:
        await context.bot.pin_chat_message(chat_id, game._lobby_msg_id,
                                           disable_notification=True)
        game._pinned = True
    except Exception:
        game._pinned = False
    # таймер автоотмены, если не наберётся минимум игроков
    game._lobby_task = asyncio.create_task(_lobby_timeout(context, game))


async def on_choose_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if await _deny_foreign(query):
        return
    await query.answer()
    slug = query.data.split(":", 1)[1]
    chat_id = query.message.chat.id
    lang = settings.get_lang(chat_id)
    if rooms.has_active(chat_id):
        await query.edit_message_text(t(lang, "already_active"))
        return
    if slug in DIFFICULTY_GAMES:  # сложность для Крокодила и Виселицы
        await query.edit_message_text(t(lang, "choose_diff"),
                                      reply_markup=_diff_markup(lang, "nd", slug))
        return
    if slug in MODE_GAMES:  # режим для Шпиона
        await query.edit_message_text("🎭 Выбери режим:",
                                      reply_markup=_mode_markup(lang, slug))
        return
    await _create_group_lobby(context, query, chat_id, slug, lang)


async def on_newgame_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if await _deny_foreign(query):
        return
    await query.answer()
    _, slug, mode = query.data.split(":")
    chat_id = query.message.chat.id
    lang = settings.get_lang(chat_id)
    if rooms.has_active(chat_id):
        await query.edit_message_text(t(lang, "already_active"))
        return
    await _create_group_lobby(context, query, chat_id, slug, lang, mode=mode)


async def on_newgame_diff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if await _deny_foreign(query):
        return
    await query.answer()
    _, slug, difficulty = query.data.split(":")
    chat_id = query.message.chat.id
    lang = settings.get_lang(chat_id)
    if rooms.has_active(chat_id):
        await query.edit_message_text(t(lang, "already_active"))
        return
    await _create_group_lobby(context, query, chat_id, slug, lang, difficulty)


# ======================================================================
# Настройки группы
# ======================================================================
def _settings_view(chat_id: int) -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "⚙️ <b>Настройки чата</b>\n\n"
        "Максимум игроков по играм (нажми, чтобы изменить):\n"
    )
    rows = []
    for slug, cls in GAME_REGISTRY.items():
        cur = _max_for(chat_id, cls)
        text += f"• {cls.title}: мин {cls.min_players} / макс {cur}\n"
        rows.append([InlineKeyboardButton(
            f"{cls.title}: макс {cur} ▸",
            callback_data=f"st:{slug}",
        )])
    rows.append([InlineKeyboardButton("✅ Готово", callback_data="st:done")])
    return text, InlineKeyboardMarkup(rows)


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type == ChatType.PRIVATE:
        await update.message.reply_text("Настройки доступны в групповом чате.")
        return
    text, markup = _settings_view(update.effective_chat.id)
    msg = await update.message.reply_text(text, parse_mode="HTML", reply_markup=markup)
    _own(msg, update.effective_user.id)


async def on_settings_open(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if await _deny_foreign(query):
        return
    await query.answer()
    text, markup = _settings_view(query.message.chat.id)
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=markup)


async def on_settings_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if await _deny_foreign(query):
        return
    chat_id = query.message.chat.id
    arg = query.data.split(":", 1)[1]

    if arg == "done":
        await query.answer("Сохранено")
        await query.edit_message_text("⚙️ Настройки сохранены. Пишите /newgame.")
        return

    cls = GAME_REGISTRY.get(arg)
    if not cls:
        await query.answer()
        return
    current = _max_for(chat_id, cls)
    new_val = settings.cycle_max(chat_id, arg, current, cls.max_players, cls.min_players)
    await query.answer(f"{cls.title}: макс {new_val}")
    text, markup = _settings_view(chat_id)
    try:
        await query.edit_message_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        pass


# ======================================================================
# Лобби
# ======================================================================
def _join_deeplink(username: str, chat_id: int) -> str:
    return f"https://t.me/{username}?start=join_{chat_id}"


def _lobby_markup(lang: str = "ru", deeplink: str | None = None) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(t(lang, "btn_join"), callback_data="lj"),
        InlineKeyboardButton(t(lang, "btn_leave"), callback_data="ll"),
    ]]
    if deeplink:
        rows.append([InlineKeyboardButton(t(lang, "btn_join_pm"), url=deeplink)])
    rows.append([InlineKeyboardButton(t(lang, "btn_start"), callback_data="lg")])
    return InlineKeyboardMarkup(rows)


def _lobby_kb(context, game) -> InlineKeyboardMarkup:
    username = getattr(context.bot, "username", None)
    deeplink = _join_deeplink(username, game.chat_id) if username else None
    return _lobby_markup(game.lang, deeplink)


async def _render_lobby(context, game) -> None:
    """Перерисовывает закреплённое сообщение-набор по сохранённому id."""
    msg_id = getattr(game, "_lobby_msg_id", None)
    if msg_id is None:
        return
    try:
        await context.bot.edit_message_text(
            chat_id=game.chat_id, message_id=msg_id,
            text=game.lobby_text() + "\n\n" + t(game.lang, "lobby_hint"),
            parse_mode="HTML", reply_markup=_lobby_kb(context, game),
        )
    except Exception:
        pass  # не изменилось — Telegram ругается, игнорируем


async def _unpin_lobby(context, game) -> None:
    if getattr(game, "_pinned", False):
        try:
            await context.bot.unpin_chat_message(game.chat_id, game._lobby_msg_id)
        except Exception:
            pass


async def on_lobby_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not game or game.phase != Phase.LOBBY:
        await query.answer("Набор уже закрыт.", show_alert=True)
        return
    if game.add_player(_player_from_user(query.from_user)):
        await query.answer("Ты в игре!")
        await _render_lobby(context, game)
    else:
        await query.answer("Ты уже в списке или мест нет.")


async def on_lobby_leave(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not game or game.phase != Phase.LOBBY:
        await query.answer("Набор уже закрыт.", show_alert=True)
        return
    if game.remove_player(query.from_user.id):
        await query.answer("Ты вышел.")
        await _render_lobby(context, game)
    else:
        await query.answer("Тебя и не было в списке.")


def _record_continuous(game) -> None:
    """Крокодил не завершается сам — фиксируем его очки при остановке/очистке."""
    if isinstance(game, CrocodileGame) and getattr(game, "scores", None):
        game.record_scores(dict(game.scores))


async def _launch_game(context: ContextTypes.DEFAULT_TYPE, game) -> None:
    _cancel_lobby_timer(game)
    await _unpin_lobby(context, game)
    stats.game_started(game.slug, game.chat_id, list(game.players.keys()))
    await game.start(context.bot)
    if isinstance(game, MafiaGame):
        await _send_mafia_night_prompts(context.bot, game)


async def on_lobby_go(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not game:
        await query.answer("Игры нет.", show_alert=True)
        return
    if query.from_user.id != game.host.user_id:
        await query.answer(t(game.lang, "only_host"), show_alert=True)
        return
    if not game.can_start():
        await query.answer(t(game.lang, "min_players", n=game.min_players), show_alert=True)
        return
    await query.answer()
    await query.edit_message_text(
        game.lobby_text() + "\n\n" + t(game.lang, "started"), parse_mode="HTML")
    await _launch_game(context, game)


async def cmd_go(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    game = rooms.get(update.effective_chat.id)
    if not game or game.phase != Phase.LOBBY:
        await update.message.reply_text("Сначала создай игру через /newgame.")
        return
    if update.effective_user.id != game.host.user_id:
        await update.message.reply_text(t(game.lang, "only_host"))
        return
    if not game.can_start():
        await update.message.reply_text(t(game.lang, "min_players", n=game.min_players))
        return
    await update.message.reply_text(t(game.lang, "started"))
    await _launch_game(context, game)


# ======================================================================
# Текстовый ввод: Крокодил и Виселица
# ======================================================================
async def _mute_outsider(context, update, game) -> None:
    """Удаляет сообщение постороннего и выдаёт мут на MUTE_SECONDS."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    try:
        await update.message.delete()
    except Exception:  # noqa: BLE001
        pass
    try:
        until = datetime.now(timezone.utc) + timedelta(seconds=MUTE_SECONDS)
        await context.bot.restrict_chat_member(
            chat_id, user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until,
        )
        await context.bot.send_message(
            chat_id, t(game.lang, "outsider_muted", name=user.full_name))
    except Exception:  # noqa: BLE001
        pass  # нет прав мутить / это админ — тихо игнорируем


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    game = rooms.get(update.effective_chat.id)
    if game is None or game.phase != Phase.RUNNING:
        return
    is_private = update.effective_chat.type == ChatType.PRIVATE
    user_id = update.effective_user.id
    # в закрытых играх (Мафия/Бункер) посторонним писать нельзя
    if not is_private and game.restrict_outsiders and not game.is_participant(user_id):
        await _mute_outsider(context, update, game)
        return
    player = _player_from_user(update.effective_user)
    if isinstance(game, HangmanGame):
        # Виселица работает и в группе, и соло в ЛС
        await game.handle_input(context.bot, player, update.message.text)
    elif isinstance(game, (GuessNumberGame, AnagramGame)) and is_private:
        await game.handle_input(context.bot, player, update.message.text)
    elif isinstance(game, CrocodileGame) and not is_private:
        await game.handle_guess(context.bot, player, update.message.text)


async def cmd_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    game = rooms.get(update.effective_chat.id)
    if isinstance(game, CrocodileGame):
        await game.skip_word(context.bot, update.effective_user.id)
    elif isinstance(game, AnagramGame):
        await game.skip(context.bot)


async def on_croc_replace(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not isinstance(game, CrocodileGame):
        await query.answer()
        return
    if query.from_user.id != game.leader_id:
        await query.answer(t(game.lang, "only_host"), show_alert=True)
        return
    await query.answer("🔄")
    await game.skip_word(context.bot, query.from_user.id)


async def cmd_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    game = rooms.get(update.effective_chat.id)
    if isinstance(game, (CrocodileGame, HangmanGame)):
        await update.message.reply_text(game.scoreboard(), parse_mode="HTML")


# ======================================================================
# Бункер
# ======================================================================
async def cmd_reveal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    game = rooms.get(update.effective_chat.id)
    if isinstance(game, BunkerGame):
        await game.reveal(context.bot, update.effective_user.id)


async def cmd_vote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    game = rooms.get(update.effective_chat.id)
    if not isinstance(game, BunkerGame) or game.phase != Phase.RUNNING:
        return
    if update.effective_user.id != game.host.user_id:
        await update.message.reply_text("Голосование запускает ведущий.")
        return
    if not game.start_vote():
        await update.message.reply_text("Голосование уже идёт.")
        return
    buttons = [
        [InlineKeyboardButton(p.name, callback_data=f"bv:{p.user_id}")]
        for p in game.alive_players()
    ]
    buttons.append([InlineKeyboardButton("🏁 Завершить голосование", callback_data="bres")])
    await update.message.reply_text(
        "🗳 Кого оставляем снаружи? Голосуйте:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def on_bunker_vote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not isinstance(game, BunkerGame):
        await query.answer()
        return
    target_id = int(query.data.split(":", 1)[1])
    if game.register_vote(query.from_user.id, target_id):
        await query.answer(f"Твой голос принят: {game.players[target_id].name}")
        if game.all_voted():
            await game.finish_vote(context.bot)
    else:
        await query.answer("Голос не принят (уже голосовал или ты выбыл).")


async def on_bunker_resolve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not isinstance(game, BunkerGame):
        await query.answer()
        return
    if query.from_user.id != game.host.user_id:
        await query.answer("Завершить может только ведущий.", show_alert=True)
        return
    await query.answer()
    await game.finish_vote(context.bot)


# ======================================================================
# Правда или Действие
# ======================================================================
async def on_truthdare(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not isinstance(game, TruthOrDareGame):
        await query.answer()
        return
    action = query.data.split(":", 1)[1]
    if action == "next":
        await query.answer()
        await game.next_turn(context.bot)
        return
    ok = await game.choose(context.bot, query.from_user.id, action)
    if ok:
        await query.answer()
    else:
        await query.answer("Сейчас не твой ход!", show_alert=True)


# ======================================================================
# Викторина (соло)
# ======================================================================
async def on_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not isinstance(game, QuizGame):
        await query.answer()
        return
    await query.answer()
    choice = int(query.data.split(":", 1)[1])
    await game.answer(context.bot, query.from_user.id, choice)


async def on_rps(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not isinstance(game, RPSGame):
        await query.answer()
        return
    await query.answer()
    move = query.data.split(":", 1)[1]
    await game.play(context.bot, query.from_user.id, move)


# ======================================================================
# Шпион
# ======================================================================
async def on_spy_vote_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not isinstance(game, SpyGame):
        await query.answer()
        return
    if query.from_user.id != game.host.user_id:
        await query.answer(t(game.lang, "only_host"), show_alert=True)
        return
    if not game.start_vote():
        await query.answer()
        return
    await query.answer()
    buttons = [[InlineKeyboardButton(p.name, callback_data=f"sv:{p.user_id}")]
               for p in game.alive_players()]
    buttons.append([InlineKeyboardButton("🏁 Завершить голосование", callback_data="svend")])
    await context.bot.send_message(
        game.chat_id, "🗳 Кто шпион? Голосуют все:",
        reply_markup=InlineKeyboardMarkup(buttons))


async def on_spy_vote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not isinstance(game, SpyGame):
        await query.answer()
        return
    target_id = int(query.data.split(":", 1)[1])
    if game.register_vote(query.from_user.id, target_id):
        await query.answer(f"Голос за {game.players[target_id].name}")
        if game.all_voted():
            await game.finish_vote(context.bot)
    else:
        await query.answer("Голос не принят.")


async def on_spy_vote_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not isinstance(game, SpyGame):
        await query.answer()
        return
    if query.from_user.id != game.host.user_id:
        await query.answer(t(game.lang, "only_host"), show_alert=True)
        return
    await query.answer()
    await game.finish_vote(context.bot)


async def on_spy_guess(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    # кнопка приходит в ЛС шпиону — ищем его активную игру
    game = None
    for cid in list(rooms._rooms):  # noqa: SLF001
        g = rooms.get(cid)
        if isinstance(g, SpyGame) and g.await_guess and query.from_user.id == g.spy_id:
            game = g
            break
    if game is None:
        await query.answer()
        return
    await query.answer()
    idx = int(query.data.split(":", 1)[1])
    await game.spy_guess(context.bot, idx)


# ======================================================================
# Реакция / Повтори / Кто из нас / Я никогда не
# ======================================================================
async def on_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not isinstance(game, ReactionGame):
        await query.answer()
        return
    result = game.press(query.from_user.id,
                        query.from_user.full_name or query.from_user.first_name)
    if result == "win":
        await query.answer("⚡ Ты первый!")
    elif result == "notin":
        await query.answer("Ты не в игре.", show_alert=True)
    else:
        await query.answer("Поздно 🙂")


async def on_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not isinstance(game, MemoryGame):
        await query.answer()
        return
    await query.answer()
    await game.tap(context.bot, int(query.data.split(":", 1)[1]))


async def on_whois_vote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not isinstance(game, WhoisGame):
        await query.answer()
        return
    target_id = int(query.data.split(":", 1)[1])
    if game.register_vote(query.from_user.id, target_id):
        await query.answer(f"Голос за {game.players[target_id].name}")
    else:
        await query.answer("Голос уже учтён.")


async def on_whois_result(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not isinstance(game, WhoisGame):
        await query.answer()
        return
    if query.from_user.id != game.host.user_id:
        await query.answer(t(game.lang, "only_host"), show_alert=True)
        return
    await query.answer()
    await game.reveal(context.bot)


async def on_never_react(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not isinstance(game, NeverGame):
        await query.answer()
        return
    kind = query.data.split(":", 1)[1]
    game.react(query.from_user.id, kind)
    await query.answer("🙋 Было" if kind == "yes" else "🙅 Не было")


async def on_never_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not isinstance(game, NeverGame):
        await query.answer()
        return
    if query.from_user.id != game.host.user_id:
        await query.answer(t(game.lang, "only_host"), show_alert=True)
        return
    await query.answer()
    await game.reveal_next(context.bot)


# ======================================================================
# Мини-апп: приём данных (tg.sendData)
# ======================================================================
async def on_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    raw = msg.web_app_data.data if msg and msg.web_app_data else None
    if not raw:
        return
    import json
    try:
        slug = json.loads(raw).get("game")
    except (ValueError, AttributeError):
        slug = None

    chat_id = update.effective_chat.id
    if slug in SOLO_REGISTRY and update.effective_chat.type == ChatType.PRIVATE:
        if rooms.has_active(chat_id):
            await msg.reply_text("У тебя уже идёт игра. Заверши её: /stop")
            return
        await msg.reply_text(f"▶️ Из мини-аппа запускаю: <b>{SOLO_REGISTRY[slug].title}</b>",
                             parse_mode="HTML")
        await _start_solo(context, chat_id, update.effective_user, slug)
    elif slug in GAME_REGISTRY:
        cls = GAME_REGISTRY[slug]
        await msg.reply_text(
            f"«{cls.title}» — игра для компании. Добавь меня в групповой чат "
            f"и напиши там /newgame 👥",
            parse_mode="HTML",
        )
    else:
        await msg.reply_text("Не понял игру из мини-аппа. Попробуй /play или /newgame.")


# ======================================================================
# Мафия
# ======================================================================
async def _send_mafia_night_prompts(bot, game: MafiaGame) -> None:
    """Рассылает ночные кнопки мафии, доктору и комиссару в ЛС."""
    for actor in game.players.values():
        if actor.user_id not in game.alive:
            continue
        role = actor.data.get("role")
        targets = [p for p in game.players.values() if p.user_id in game.alive]
        if role == "mafia":
            prefix, title = "mk", "🔪 Кого убить этой ночью?"
        elif role == "doctor":
            prefix, title = "md", "💉 Кого вылечить этой ночью?"
        elif role == "detective":
            prefix, title = "mc", "🕵️ Чью роль проверить?"
        else:
            continue
        buttons = [
            [InlineKeyboardButton(p.name, callback_data=f"{prefix}:{p.user_id}")]
            for p in targets
        ]
        try:
            await bot.send_message(actor.user_id, title,
                                   reply_markup=InlineKeyboardMarkup(buttons))
        except Exception:
            pass
    await bot.send_message(
        game.chat_id,
        "Когда все сделают ход — ведущий жмёт кнопку.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🌅 Завершить ночь", callback_data="mres")]]
        ),
    )


def _active_mafia_for_user(user_id: int) -> MafiaGame | None:
    """Находит активную «Мафию», где состоит пользователь (для ночных ЛС-кнопок)."""
    for chat_id in list(rooms._rooms.keys()):  # noqa: SLF001
        game = rooms.get(chat_id)
        if isinstance(game, MafiaGame) and user_id in game.players:
            return game
    return None


async def on_mafia_kill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = _active_mafia_for_user(query.from_user.id)
    if not game:
        await query.answer()
        return
    target_id = int(query.data.split(":", 1)[1])
    game.submit_mafia(query.from_user.id, target_id)
    await query.answer(f"Цель: {game.players[target_id].name}")


async def on_mafia_doctor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = _active_mafia_for_user(query.from_user.id)
    if not game:
        await query.answer()
        return
    target_id = int(query.data.split(":", 1)[1])
    game.submit_doctor(target_id)
    await query.answer(f"Лечишь: {game.players[target_id].name}")


async def on_mafia_detective(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = _active_mafia_for_user(query.from_user.id)
    if not game:
        await query.answer()
        return
    target_id = int(query.data.split(":", 1)[1])
    role = game.submit_detective(target_id)
    from .games.mafia import ROLE_NAMES
    await query.answer(f"{game.players[target_id].name} — {ROLE_NAMES.get(role, '?')}",
                       show_alert=True)


async def _send_mafia_day_buttons(bot, game: MafiaGame) -> None:
    buttons = [
        [InlineKeyboardButton(game.players[u].name, callback_data=f"dv:{u}")]
        for u in game.alive
    ]
    buttons.append([InlineKeyboardButton("⚖️ Завершить день", callback_data="dres")])
    await bot.send_message(
        game.chat_id, "🗳 Голосуйте, кого казнить:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def on_mafia_resolve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not isinstance(game, MafiaGame):
        await query.answer()
        return
    if query.from_user.id != game.host.user_id:
        await query.answer("Только ведущий.", show_alert=True)
        return
    await query.answer()
    if game.is_night:
        await game.resolve_night(context.bot)
        if game.phase == Phase.RUNNING:
            await _send_mafia_day_buttons(context.bot, game)


async def on_mafia_day_vote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not isinstance(game, MafiaGame):
        await query.answer()
        return
    target_id = int(query.data.split(":", 1)[1])
    if game.register_day_vote(query.from_user.id, target_id):
        await query.answer(f"Голос за {game.players[target_id].name}")
        if game.all_day_voted():
            await game.resolve_day(context.bot)
            if game.phase == Phase.RUNNING:
                await _send_mafia_night_prompts(context.bot, game)
    else:
        await query.answer("Голос не принят.")


async def on_mafia_day_resolve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not isinstance(game, MafiaGame):
        await query.answer()
        return
    if query.from_user.id != game.host.user_id:
        await query.answer("Только ведущий.", show_alert=True)
        return
    await query.answer()
    await game.resolve_day(context.bot)
    if game.phase == Phase.RUNNING:
        await _send_mafia_night_prompts(context.bot, game)


# ======================================================================
# Стоп
# ======================================================================
async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    game = rooms.get(chat_id)
    if not game:
        await update.message.reply_text(t(settings.get_lang(chat_id), "no_active"))
        return
    user_id = update.effective_user.id
    is_host = user_id == game.host.user_id
    # остановить может ведущий ИЛИ любой админ группы
    is_admin = False
    if not is_host and update.effective_chat.type != ChatType.PRIVATE:
        is_admin = await _user_is_admin(context, chat_id, user_id)
    if not is_host and not is_admin:
        await update.message.reply_text(t(game.lang, "only_host"))
        return
    _cancel_lobby_timer(game)
    await _unpin_lobby(context, game)
    _record_continuous(game)
    rooms.clear(chat_id)
    await update.message.reply_text(
        t(game.lang, "stopped_by_admin" if (is_admin and not is_host) else "stopped"))


# ======================================================================
# Запуск
# ======================================================================
# ======================================================================
# Админ-панель (доступна только ADMIN_ID)
# ======================================================================
async def _build_admin_data(context) -> dict:
    chats_info, members_total, chats_admin = [], 0, 0
    bot_id = context.bot.id
    for cid in stats.group_chat_ids():
        meta = stats.chats.get(str(cid), {})
        title = meta.get("title", str(cid))
        games = meta.get("games", 0)
        is_admin, members = False, 0
        try:
            cm = await context.bot.get_chat_member(cid, bot_id)
            is_admin = cm.status in ADMIN_STATUSES
            members = await context.bot.get_chat_member_count(cid)
            try:
                chat = await context.bot.get_chat(cid)
                title = chat.title or title
            except Exception:  # noqa: BLE001
                pass
        except Exception:  # noqa: BLE001
            is_admin = False  # бота убрали из чата
        if is_admin:
            chats_admin += 1
            members_total += members
        chats_info.append({"title": title, "members": members,
                           "admin": is_admin, "games": games})
    chats_info.sort(key=lambda c: (c["admin"], c["members"]), reverse=True)
    active_now = sum(1 for cid in list(rooms._rooms) if rooms.has_active(cid))  # noqa: SLF001
    data = stats.base_snapshot()
    data.update({
        "chats_admin": chats_admin,
        "members_total": members_total,
        "active_now": active_now,
        "chats": chats_info,
    })
    return data


def _admin_summary(data: dict) -> str:
    return (
        "✅ <b>Доступ разрешён.</b>\n\n"
        "📊 <b>Админ-панель LazyGame</b>\n"
        f"• Чатов (бот админ): <b>{data['chats_admin']}</b>\n"
        f"• Участников суммарно: <b>{data['members_total']}</b>\n"
        f"• Игр запущено: <b>{data['games_total']}</b>\n"
        f"• Активных игр сейчас: <b>{data['active_now']}</b>\n"
        f"• Уникальных игроков: <b>{data['users_total']}</b>"
    )


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None or user.id != ADMIN_ID:
        return  # не админ — молча игнорируем
    data = await _build_admin_data(context)
    buttons = None
    if WEBAPP_URL and update.effective_chat.type == ChatType.PRIVATE:
        import base64
        import json as _json
        payload = base64.urlsafe_b64encode(
            _json.dumps(data, ensure_ascii=False).encode()).decode()
        url = WEBAPP_URL.rstrip("/") + "/admin.html?d=" + payload
        buttons = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📊 Открыть админ-панель",
                                   web_app=WebAppInfo(url=url))]])
    try:
        await update.message.reply_photo(
            render_admin_panel(data), caption=_admin_summary(data),
            parse_mode="HTML", reply_markup=buttons)
    except Exception:  # noqa: BLE001
        await update.message.reply_text(_admin_summary(data), parse_mode="HTML",
                                        reply_markup=buttons)


# ======================================================================
# Рекорды / лидерборд
# ======================================================================
def _clean_name(slug: str) -> str:
    return leaderboard.RANKED_GAMES[slug].split(maxsplit=1)[-1]


def _top_rows(slug: str, scope: str, chat_id: int) -> list[dict]:
    if scope == "chat":
        return leaderboard.chat_top(slug, chat_id)
    return leaderboard.world_top(slug)


def _scope_label(scope: str) -> str:
    # без эмодзи — используется в подписи картинки (Pillow рисует эмодзи квадратом)
    return "Этот чат" if scope == "chat" else "Весь мир"


def _records_webapp_button(chat_id: int, is_private: bool) -> InlineKeyboardButton | None:
    if not WEBAPP_URL:
        return None
    import base64
    import json as _json
    snap = leaderboard.build_snapshot(chat_id)
    payload = base64.urlsafe_b64encode(_json.dumps(snap, ensure_ascii=False).encode()).decode()
    url = WEBAPP_URL.rstrip("/") + "/records.html?d=" + payload
    if len(url) > 3800:  # не раздуваем ссылку сверх меры
        url = WEBAPP_URL.rstrip("/") + "/records.html"
    if is_private:
        return InlineKeyboardButton("📊 Открыть страницу рекордов", web_app=WebAppInfo(url=url))
    return InlineKeyboardButton("📊 Открыть страницу рекордов", url=url)


def _top_markup(slug: str, scope: str, chat_id: int, is_private: bool) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(("• " if scope == "chat" else "") + "🏠 Чат",
                             callback_data=f"tv:{slug}:chat"),
        InlineKeyboardButton(("• " if scope == "world" else "") + "🌍 Мир",
                             callback_data=f"tv:{slug}:world"),
    ]]
    slugs = list(leaderboard.RANKED_GAMES)
    for i in range(0, len(slugs), 2):
        row = []
        for s in slugs[i:i + 2]:
            mark = "• " if s == slug else ""
            row.append(InlineKeyboardButton(mark + leaderboard.RANKED_GAMES[s],
                                            callback_data=f"tv:{s}:{scope}"))
        rows.append(row)
    btn = _records_webapp_button(chat_id, is_private)
    if btn:
        rows.append([btn])
    return InlineKeyboardMarkup(rows)


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    is_private = update.effective_chat.type == ChatType.PRIVATE
    scope = "world" if is_private else "chat"
    # игра по умолчанию — первая, где есть результаты, иначе первая в списке
    ranked = list(leaderboard.RANKED_GAMES)
    with_scores = leaderboard.games_with_scores()
    slug = next((s for s in ranked if s in with_scores), ranked[0])
    rows = _top_rows(slug, scope, chat_id)
    await update.message.reply_photo(
        render_records(_clean_name(slug), _scope_label(scope), rows),
        caption="🏆 <b>Рекорды</b> — выбери игру и масштаб кнопками ниже.",
        parse_mode="HTML",
        reply_markup=_top_markup(slug, scope, chat_id, is_private))


async def on_top_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from telegram import InputMediaPhoto
    query = update.callback_query
    await query.answer()
    _, slug, scope = query.data.split(":")
    chat_id = query.message.chat.id
    is_private = query.message.chat.type == ChatType.PRIVATE
    rows = _top_rows(slug, scope, chat_id)
    media = InputMediaPhoto(
        render_records(_clean_name(slug), _scope_label(scope), rows),
        caption="🏆 <b>Рекорды</b> — выбери игру и масштаб кнопками ниже.",
        parse_mode="HTML")
    try:
        await query.edit_message_media(
            media, reply_markup=_top_markup(slug, scope, chat_id, is_private))
    except Exception:
        pass


async def _post_init(app: Application) -> None:
    """Прописывает меню команд (всплывает при вводе «/») и кнопку мини-аппа."""
    await app.bot.set_my_commands([
        BotCommand("newgame", "Групповая игра"),
        BotCommand("play", "Соло-игра в личке"),
        BotCommand("top", "Рекорды и топы"),
        BotCommand("settings", "Настройки (лимиты игроков)"),
        BotCommand("go", "Начать игру"),
        BotCommand("stop", "Остановить игру"),
        BotCommand("skip", "Крокодил: пропустить слово"),
        BotCommand("score", "Показать счёт"),
        BotCommand("reveal", "Бункер: раскрыть характеристику"),
        BotCommand("vote", "Бункер: голосование"),
        BotCommand("help", "Помощь"),
    ])
    if WEBAPP_URL:
        try:
            await app.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="🎮 Играть", web_app=WebAppInfo(url=WEBAPP_URL)
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось поставить кнопку мини-аппа: %s", exc)
    # фоновая очистка зависших игр
    asyncio.create_task(_sweep_loop(app))


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Глобальный обработчик — логируем и не падаем на единичных ошибках."""
    logger.warning("Ошибка при обработке апдейта: %s", context.error)


def build_application() -> Application:
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(_post_init).build()
    app.add_error_handler(on_error)

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("newgame", cmd_newgame))
    app.add_handler(CommandHandler("play", cmd_play))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CommandHandler("records", cmd_top))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("go", cmd_go))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("skip", cmd_skip))
    app.add_handler(CommandHandler("score", cmd_score))
    app.add_handler(CommandHandler("reveal", cmd_reveal))
    app.add_handler(CommandHandler("vote", cmd_vote))

    app.add_handler(CallbackQueryHandler(on_choose_lang, pattern=r"^nl:"))
    app.add_handler(CallbackQueryHandler(on_choose_game, pattern=r"^ng:"))
    app.add_handler(CallbackQueryHandler(on_newgame_diff, pattern=r"^nd:"))
    app.add_handler(CallbackQueryHandler(on_choose_solo, pattern=r"^solo:"))
    app.add_handler(CallbackQueryHandler(on_solo_diff, pattern=r"^sd:"))
    app.add_handler(CallbackQueryHandler(on_quiz_answer, pattern=r"^qz:"))
    app.add_handler(CallbackQueryHandler(on_rps, pattern=r"^rps:"))
    app.add_handler(CallbackQueryHandler(on_croc_replace, pattern=r"^cnew$"))
    app.add_handler(CallbackQueryHandler(on_newgame_mode, pattern=r"^nm:"))
    app.add_handler(CallbackQueryHandler(on_spy_vote_start, pattern=r"^svstart$"))
    app.add_handler(CallbackQueryHandler(on_spy_vote_end, pattern=r"^svend$"))
    app.add_handler(CallbackQueryHandler(on_spy_vote, pattern=r"^sv:"))
    app.add_handler(CallbackQueryHandler(on_spy_guess, pattern=r"^sg:"))
    app.add_handler(CallbackQueryHandler(on_reaction, pattern=r"^rx$"))
    app.add_handler(CallbackQueryHandler(on_memory, pattern=r"^mem:"))
    app.add_handler(CallbackQueryHandler(on_whois_vote, pattern=r"^wv:"))
    app.add_handler(CallbackQueryHandler(on_whois_result, pattern=r"^wresult$"))
    app.add_handler(CallbackQueryHandler(on_never_react, pattern=r"^nv:"))
    app.add_handler(CallbackQueryHandler(on_never_next, pattern=r"^nnext$"))
    app.add_handler(CallbackQueryHandler(on_top_view, pattern=r"^tv:"))
    app.add_handler(CallbackQueryHandler(on_settings_open, pattern=r"^settings$"))
    app.add_handler(CallbackQueryHandler(on_settings_change, pattern=r"^st:"))
    app.add_handler(CallbackQueryHandler(on_lobby_join, pattern=r"^lj$"))
    app.add_handler(CallbackQueryHandler(on_lobby_leave, pattern=r"^ll$"))
    app.add_handler(CallbackQueryHandler(on_lobby_go, pattern=r"^lg$"))

    app.add_handler(CallbackQueryHandler(on_bunker_vote, pattern=r"^bv:"))
    app.add_handler(CallbackQueryHandler(on_bunker_resolve, pattern=r"^bres$"))

    app.add_handler(CallbackQueryHandler(on_truthdare, pattern=r"^td:"))

    app.add_handler(CallbackQueryHandler(on_mafia_kill, pattern=r"^mk:"))
    app.add_handler(CallbackQueryHandler(on_mafia_doctor, pattern=r"^md:"))
    app.add_handler(CallbackQueryHandler(on_mafia_detective, pattern=r"^mc:"))
    app.add_handler(CallbackQueryHandler(on_mafia_resolve, pattern=r"^mres$"))
    app.add_handler(CallbackQueryHandler(on_mafia_day_vote, pattern=r"^dv:"))
    app.add_handler(CallbackQueryHandler(on_mafia_day_resolve, pattern=r"^dres$"))

    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, on_webapp_data))
    # слово «админ»/«admin» — вход в админ-панель (реагирует только на ADMIN_ID)
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^\s*(админ|admin)\s*$"), cmd_admin))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app


def main() -> None:
    logger.info("LazyGame запускается...")
    app = build_application()
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
