"""LazyGame — точка входа Telegram-бота.

Запуск:  python -m lazygame.bot
Токен берётся из .env (переменная BOT_TOKEN). В коде токена нет и быть не должно.
"""
from __future__ import annotations

import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import BOT_TOKEN
from .games import (
    BunkerGame,
    CrocodileGame,
    GAME_REGISTRY,
    MafiaGame,
    Phase,
    Player,
    RoomManager,
)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("lazygame")

rooms = RoomManager()

GAME_TITLES = {slug: cls.title for slug, cls in GAME_REGISTRY.items()}


def _player_from_update(update: Update) -> Player:
    user = update.effective_user
    name = user.full_name or user.username or str(user.id)
    return Player(user_id=user.id, name=name)


# ======================================================================
# Базовые команды
# ======================================================================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type == ChatType.PRIVATE:
        await update.message.reply_text(
            "Привет! Я LazyGame 🎲\n\n"
            "Добавь меня в групповой чат и напиши /newgame, чтобы выбрать игру:\n"
            "🐊 Крокодил · 🏚 Бункер · 🔪 Мафия\n\n"
            "Важно: напиши мне /start здесь (в личке) заранее — тогда я смогу "
            "присылать тебе слова и роли."
        )
    else:
        await cmd_help(update, context)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🎲 <b>LazyGame — команды</b>\n\n"
        "/newgame — выбрать и создать игру\n"
        "/join — присоединиться к набору\n"
        "/go — начать игру (только ведущий)\n"
        "/stop — остановить текущую игру\n\n"
        "<b>Крокодил:</b> /skip — пропустить слово, /score — счёт\n"
        "<b>Бункер:</b> /reveal — раскрыть характеристику, /vote — голосование\n"
        "<b>Мафия:</b> действия ночью — в личке, голосование днём — кнопками",
        parse_mode="HTML",
    )


async def cmd_newgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type == ChatType.PRIVATE:
        await update.message.reply_text("Игры запускаются в групповом чате. Добавь меня в группу!")
        return

    chat_id = update.effective_chat.id
    if rooms.has_active(chat_id):
        await update.message.reply_text("В этом чате уже идёт игра. Заверши её командой /stop.")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(CrocodileGame.title, callback_data="ng:crocodile")],
        [InlineKeyboardButton(BunkerGame.title, callback_data="ng:bunker")],
        [InlineKeyboardButton(MafiaGame.title, callback_data="ng:mafia")],
    ])
    await update.message.reply_text("Выбери игру:", reply_markup=keyboard)


def _lobby_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Войти", callback_data="lj"),
            InlineKeyboardButton("🚪 Выйти", callback_data="ll"),
        ],
        [InlineKeyboardButton("▶️ Начать", callback_data="lg")],
    ])


async def on_choose_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    slug = query.data.split(":", 1)[1]
    chat_id = query.message.chat.id

    if rooms.has_active(chat_id):
        await query.edit_message_text("В этом чате уже идёт игра. Сначала /stop.")
        return

    host = Player(query.from_user.id, query.from_user.full_name)
    game = GAME_REGISTRY[slug](chat_id, host)
    rooms.set(chat_id, game)

    await query.edit_message_text(
        game.lobby_text() + "\n\nНажимайте «Войти», затем ведущий — «Начать».",
        parse_mode="HTML",
        reply_markup=_lobby_markup(),
    )


# ======================================================================
# Лобби
# ======================================================================
async def _refresh_lobby(query, game) -> None:
    try:
        await query.edit_message_text(
            game.lobby_text() + "\n\nНажимайте «Войти», затем ведущий — «Начать».",
            parse_mode="HTML",
            reply_markup=_lobby_markup(),
        )
    except Exception:
        pass  # сообщение не изменилось — Telegram ругается, игнорируем


async def on_lobby_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat.id
    game = rooms.get(chat_id)
    if not game or game.phase != Phase.LOBBY:
        await query.answer("Набор уже закрыт.", show_alert=True)
        return
    player = Player(query.from_user.id, query.from_user.full_name)
    if game.add_player(player):
        await query.answer("Ты в игре!")
        await _refresh_lobby(query, game)
    else:
        await query.answer("Ты уже в списке или мест нет.")


async def on_lobby_leave(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat.id
    game = rooms.get(chat_id)
    if not game or game.phase != Phase.LOBBY:
        await query.answer("Набор уже закрыт.", show_alert=True)
        return
    if game.remove_player(query.from_user.id):
        await query.answer("Ты вышел.")
        await _refresh_lobby(query, game)
    else:
        await query.answer("Тебя и не было в списке.")


async def on_lobby_go(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat.id
    game = rooms.get(chat_id)
    if not game:
        await query.answer("Игры нет.", show_alert=True)
        return
    if query.from_user.id != game.host.user_id:
        await query.answer("Начать может только ведущий.", show_alert=True)
        return
    if not game.can_start():
        await query.answer(f"Нужно минимум {game.min_players} игроков.", show_alert=True)
        return

    await query.answer()
    await query.edit_message_text(game.lobby_text() + "\n\n▶️ Игра началась!", parse_mode="HTML")
    await game.start(context.bot)
    if isinstance(game, MafiaGame):
        await _send_mafia_night_prompts(context.bot, game)


# ======================================================================
# Крокодил
# ======================================================================
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type == ChatType.PRIVATE:
        return
    chat_id = update.effective_chat.id
    game = rooms.get(chat_id)
    if not isinstance(game, CrocodileGame) or game.phase != Phase.RUNNING:
        return
    player = _player_from_update(update)
    await game.handle_guess(context.bot, player, update.message.text)


async def cmd_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    game = rooms.get(update.effective_chat.id)
    if isinstance(game, CrocodileGame):
        await game.skip_word(context.bot, update.effective_user.id)


async def cmd_score(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    game = rooms.get(update.effective_chat.id)
    if isinstance(game, CrocodileGame):
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
    # кнопка завершения ночи — в группе, для ведущего
    await bot.send_message(
        game.chat_id,
        "Когда все сделают ход — ведущий жмёт кнопку.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🌅 Завершить ночь", callback_data="mres")]]
        ),
    )


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
    role_name = ROLE_NAMES.get(role, "?")
    await query.answer(f"{game.players[target_id].name} — {role_name}", show_alert=True)


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


def _active_mafia_for_user(user_id: int) -> MafiaGame | None:
    """Находит активную игру «Мафия», в которой состоит пользователь.

    Нужно для ночных кнопок, которые приходят в ЛС (там нет chat_id группы).
    """
    for chat_id in list(rooms._rooms.keys()):  # noqa: SLF001
        game = rooms.get(chat_id)
        if isinstance(game, MafiaGame) and user_id in game.players:
            return game
    return None


# ======================================================================
# Стоп
# ======================================================================
async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    game = rooms.get(chat_id)
    if not game:
        await update.message.reply_text("Активной игры нет.")
        return
    if update.effective_user.id != game.host.user_id:
        await update.message.reply_text("Остановить игру может только ведущий.")
        return
    rooms.clear(chat_id)
    await update.message.reply_text("Игра остановлена. /newgame — начать заново.")


# ======================================================================
# Запуск
# ======================================================================
def build_application() -> Application:
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("newgame", cmd_newgame))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("skip", cmd_skip))
    app.add_handler(CommandHandler("score", cmd_score))
    app.add_handler(CommandHandler("reveal", cmd_reveal))
    app.add_handler(CommandHandler("vote", cmd_vote))

    app.add_handler(CallbackQueryHandler(on_choose_game, pattern=r"^ng:"))
    app.add_handler(CallbackQueryHandler(on_lobby_join, pattern=r"^lj$"))
    app.add_handler(CallbackQueryHandler(on_lobby_leave, pattern=r"^ll$"))
    app.add_handler(CallbackQueryHandler(on_lobby_go, pattern=r"^lg$"))

    app.add_handler(CallbackQueryHandler(on_bunker_vote, pattern=r"^bv:"))
    app.add_handler(CallbackQueryHandler(on_bunker_resolve, pattern=r"^bres$"))

    app.add_handler(CallbackQueryHandler(on_mafia_kill, pattern=r"^mk:"))
    app.add_handler(CallbackQueryHandler(on_mafia_doctor, pattern=r"^md:"))
    app.add_handler(CallbackQueryHandler(on_mafia_detective, pattern=r"^mc:"))
    app.add_handler(CallbackQueryHandler(on_mafia_resolve, pattern=r"^mres$"))
    app.add_handler(CallbackQueryHandler(on_mafia_day_vote, pattern=r"^dv:"))
    app.add_handler(CallbackQueryHandler(on_mafia_day_resolve, pattern=r"^dres$"))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    return app


def main() -> None:
    logger.info("LazyGame запускается...")
    app = build_application()
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
