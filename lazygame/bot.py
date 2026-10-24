"""LazyGame — точка входа Telegram-бота.

Запуск:  python -m lazygame.bot
Токен берётся из .env (переменная BOT_TOKEN). В коде токена нет и быть не должно.
"""
from __future__ import annotations

import logging
from io import BytesIO

from telegram import (
    BotCommand,
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

from .cards import render_welcome
from .config import BOT_TOKEN, WEBAPP_URL
from .games import (
    BunkerGame,
    CrocodileGame,
    GAME_REGISTRY,
    GuessNumberGame,
    HangmanGame,
    MafiaGame,
    Phase,
    Player,
    QuizGame,
    RoomManager,
    RPSGame,
    SOLO_REGISTRY,
    TruthOrDareGame,
)
from .i18n import LANGUAGES, t
from .settings import settings

# игры, у которых контент пока только на русском
RU_CONTENT_GAMES = {"bunker", "mafia", "truthdare"}

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
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        kb = _webapp_reply_keyboard()
        await update.message.reply_photo(
            _welcome_photo(), caption=caption, parse_mode="HTML", reply_markup=kb
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


def _diff_markup(lang: str, prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(lang, "diff_easy"), callback_data=f"{prefix}:easy")],
        [InlineKeyboardButton(t(lang, "diff_medium"), callback_data=f"{prefix}:medium")],
        [InlineKeyboardButton(t(lang, "diff_hard"), callback_data=f"{prefix}:hard")],
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
    items = [(slug, cls.title) for slug, cls in SOLO_REGISTRY.items()]
    await update.message.reply_text(
        "🎮 <b>Соло-игры</b>\nВыбери, во что сыграем:",
        parse_mode="HTML", reply_markup=_two_col(items, "solo"),
    )


async def _start_solo(context, chat_id, user, slug, difficulty=None) -> None:
    lang = settings.get_lang(chat_id)
    cls = SOLO_REGISTRY[slug]
    if slug == HangmanGame.slug:
        game = cls(chat_id, _player_from_user(user), lang, difficulty or "medium")
    else:
        game = cls(chat_id, _player_from_user(user), lang)
    rooms.set(chat_id, game)
    await game.start(context.bot)


async def on_choose_solo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    slug = query.data.split(":", 1)[1]
    chat_id = query.message.chat.id
    cls = SOLO_REGISTRY.get(slug)
    if not cls or rooms.has_active(chat_id):
        await query.edit_message_text("Не получилось начать. Напиши /play заново.")
        return
    lang = settings.get_lang(chat_id)
    if slug == HangmanGame.slug:  # у виселицы спрашиваем сложность
        await query.edit_message_text(t(lang, "choose_diff"),
                                      reply_markup=_diff_markup(lang, "sd"))
        return
    await query.edit_message_text(f"▶️ {cls.title}")
    await _start_solo(context, chat_id, query.from_user, slug)


async def on_solo_diff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    difficulty = query.data.split(":", 1)[1]
    chat_id = query.message.chat.id
    if rooms.has_active(chat_id):
        await query.edit_message_text("Не получилось начать. Напиши /play заново.")
        return
    await query.edit_message_text(f"▶️ {HangmanGame.title}")
    await _start_solo(context, chat_id, query.from_user, HangmanGame.slug, difficulty)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎲 <b>LazyGame — команды</b>\n\n"
        "/newgame — групповая игра (выбор языка RU/EN/UK → игра)\n"
        "/play — соло-игра в личке\n"
        "/settings — настройки (лимиты игроков)\n"
        "/go — начать игру (ведущий)\n"
        "/stop — остановить игру (ведущий)\n\n"
        "<b>👥 В группе:</b> Крокодил, Бункер, Мафия, Виселица, Правда/Действие\n"
        "<b>🙂 Соло в ЛС:</b> Виселица, Викторина, Угадай число, Камень-ножницы-бумага\n\n"
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
    lang = settings.get_lang(chat_id)
    if not await _bot_is_admin(context, chat_id):
        await update.message.reply_text(t(lang, "need_admin"), parse_mode="HTML")
        return
    if rooms.has_active(chat_id):
        await update.message.reply_text(t(lang, "already_active"))
        return
    # шаг 1 — выбор языка
    await update.message.reply_text(t(lang, "choose_lang"), reply_markup=_lang_markup())


async def on_choose_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":", 1)[1]
    chat_id = query.message.chat.id
    settings.set_lang(chat_id, lang)
    # шаг 2 — выбор игры (2 столбца)
    await query.edit_message_text(t(lang, "choose_game"), reply_markup=_game_menu_markup(lang))


async def _create_group_lobby(query, chat_id, slug, lang, difficulty=None) -> None:
    cls = GAME_REGISTRY[slug]
    host = _player_from_user(query.from_user)
    if slug == HangmanGame.slug:
        game = cls(chat_id, host, lang, difficulty or "medium")
    else:
        game = cls(chat_id, host, lang)
    game.max_players = _max_for(chat_id, cls)
    rooms.set(chat_id, game)
    note = t(lang, "content_ru_only") if (lang != "ru" and slug in RU_CONTENT_GAMES) else ""
    await query.edit_message_text(
        note + game.lobby_text() + "\n\n" + t(lang, "lobby_hint"),
        parse_mode="HTML", reply_markup=_lobby_markup(lang),
    )


async def on_choose_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    slug = query.data.split(":", 1)[1]
    chat_id = query.message.chat.id
    lang = settings.get_lang(chat_id)
    if rooms.has_active(chat_id):
        await query.edit_message_text(t(lang, "already_active"))
        return
    if slug == HangmanGame.slug:  # сложность для виселицы
        await query.edit_message_text(t(lang, "choose_diff"),
                                      reply_markup=_diff_markup(lang, "nd"))
        return
    await _create_group_lobby(query, chat_id, slug, lang)


async def on_newgame_diff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    difficulty = query.data.split(":", 1)[1]
    chat_id = query.message.chat.id
    lang = settings.get_lang(chat_id)
    if rooms.has_active(chat_id):
        await query.edit_message_text(t(lang, "already_active"))
        return
    await _create_group_lobby(query, chat_id, HangmanGame.slug, lang, difficulty)


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
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=markup)


async def on_settings_open(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text, markup = _settings_view(query.message.chat.id)
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=markup)


async def on_settings_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
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
def _lobby_markup(lang: str = "ru") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(t(lang, "btn_join"), callback_data="lj"),
            InlineKeyboardButton(t(lang, "btn_leave"), callback_data="ll"),
        ],
        [InlineKeyboardButton(t(lang, "btn_start"), callback_data="lg")],
    ])


async def _refresh_lobby(query, game) -> None:
    try:
        await query.edit_message_text(
            game.lobby_text() + "\n\n" + t(game.lang, "lobby_hint"),
            parse_mode="HTML",
            reply_markup=_lobby_markup(game.lang),
        )
    except Exception:
        pass  # сообщение не изменилось — Telegram ругается, игнорируем


async def on_lobby_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    game = rooms.get(query.message.chat.id)
    if not game or game.phase != Phase.LOBBY:
        await query.answer("Набор уже закрыт.", show_alert=True)
        return
    if game.add_player(_player_from_user(query.from_user)):
        await query.answer("Ты в игре!")
        await _refresh_lobby(query, game)
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
        await _refresh_lobby(query, game)
    else:
        await query.answer("Тебя и не было в списке.")


async def _launch_game(context: ContextTypes.DEFAULT_TYPE, game) -> None:
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
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    game = rooms.get(update.effective_chat.id)
    if game is None or game.phase != Phase.RUNNING:
        return
    is_private = update.effective_chat.type == ChatType.PRIVATE
    player = _player_from_user(update.effective_user)
    if isinstance(game, HangmanGame):
        # Виселица работает и в группе, и соло в ЛС
        await game.handle_input(context.bot, player, update.message.text)
    elif isinstance(game, GuessNumberGame) and is_private:
        await game.handle_input(context.bot, player, update.message.text)
    elif isinstance(game, CrocodileGame) and not is_private:
        await game.handle_guess(context.bot, player, update.message.text)


async def cmd_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    game = rooms.get(update.effective_chat.id)
    if isinstance(game, CrocodileGame):
        await game.skip_word(context.bot, update.effective_user.id)


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
    if update.effective_user.id != game.host.user_id:
        await update.message.reply_text(t(game.lang, "only_host"))
        return
    rooms.clear(chat_id)
    await update.message.reply_text(t(game.lang, "stopped"))


# ======================================================================
# Запуск
# ======================================================================
async def _post_init(app: Application) -> None:
    """Прописывает меню команд (всплывает при вводе «/») и кнопку мини-аппа."""
    await app.bot.set_my_commands([
        BotCommand("newgame", "Групповая игра"),
        BotCommand("play", "Соло-игра в личке"),
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


def build_application() -> Application:
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(_post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("newgame", cmd_newgame))
    app.add_handler(CommandHandler("play", cmd_play))
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app


def main() -> None:
    logger.info("LazyGame запускается...")
    app = build_application()
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
