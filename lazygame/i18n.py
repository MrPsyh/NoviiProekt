"""Локализация интерфейса и словесных игр (RU / EN / UK).

t(lang, key, **kwargs) возвращает строку на нужном языке с подстановкой.
Если ключа/языка нет — откат на русский, затем на сам ключ.
"""
from __future__ import annotations

LANGUAGES = {
    "ru": "Русский 🇷🇺",
    "en": "English 🇬🇧",
    "uk": "Українська 🇺🇦",
}
DEFAULT_LANG = "ru"

DIFFICULTIES = ("easy", "medium", "hard")

T: dict[str, dict[str, str]] = {
    # --- общий интерфейс ---
    "choose_lang": {
        "ru": "🌍 Выбери язык игры:",
        "en": "🌍 Choose game language:",
        "uk": "🌍 Оберіть мову гри:",
    },
    "choose_game": {
        "ru": "🎲 Выбери игру:",
        "en": "🎲 Choose a game:",
        "uk": "🎲 Оберіть гру:",
    },
    "choose_diff": {
        "ru": "🎚 Выбери сложность:",
        "en": "🎚 Choose difficulty:",
        "uk": "🎚 Оберіть складність:",
    },
    "diff_easy": {"ru": "😊 Лёгкая", "en": "😊 Easy", "uk": "😊 Легка"},
    "diff_medium": {"ru": "🙂 Средняя", "en": "🙂 Medium", "uk": "🙂 Середня"},
    "diff_hard": {"ru": "😈 Сложная", "en": "😈 Hard", "uk": "😈 Складна"},
    "need_admin": {
        "ru": "⚠️ Сначала сделайте меня <b>администратором</b> группы — иначе я не вижу "
              "сообщения и игры не заработают.\nНастройки группы → Администраторы → "
              "Добавить → выберите меня.",
        "en": "⚠️ Make me a group <b>administrator</b> first — otherwise I can't see "
              "messages and games won't work.\nGroup Settings → Administrators → Add → pick me.",
        "uk": "⚠️ Спершу зробіть мене <b>адміністратором</b> групи — інакше я не бачу "
              "повідомлення і ігри не працюватимуть.\nНалаштування групи → Адміністратори → "
              "Додати → оберіть мене.",
    },
    "already_active": {
        "ru": "В этом чате уже идёт игра. Заверши её командой /stop.",
        "en": "A game is already running in this chat. Finish it with /stop.",
        "uk": "У цьому чаті вже триває гра. Заверши її командою /stop.",
    },
    "no_active": {
        "ru": "Активной игры нет.",
        "en": "No active game.",
        "uk": "Активної гри немає.",
    },
    "only_host": {
        "ru": "Это может сделать только ведущий.",
        "en": "Only the host can do this.",
        "uk": "Це може зробити лише ведучий.",
    },
    "min_players": {
        "ru": "Нужно минимум {n} игроков.",
        "en": "Need at least {n} players.",
        "uk": "Потрібно щонайменше {n} гравців.",
    },
    "stopped": {
        "ru": "Игра остановлена. /newgame — начать заново.",
        "en": "Game stopped. /newgame to start again.",
        "uk": "Гру зупинено. /newgame — почати заново.",
    },
    "btn_join": {"ru": "✅ Войти", "en": "✅ Join", "uk": "✅ Увійти"},
    "btn_leave": {"ru": "🚪 Выйти", "en": "🚪 Leave", "uk": "🚪 Вийти"},
    "btn_start": {"ru": "▶️ Начать", "en": "▶️ Start", "uk": "▶️ Почати"},
    "btn_settings": {"ru": "⚙️ Настройки", "en": "⚙️ Settings", "uk": "⚙️ Налаштування"},
    "lobby_hint": {
        "ru": "Нажимайте «Войти», затем ведущий — «Начать».",
        "en": "Tap “Join”, then the host taps “Start”.",
        "uk": "Натискайте «Увійти», потім ведучий — «Почати».",
    },
    "lobby_players": {
        "ru": "Игроков: {cur}/{max} (нужно минимум {min})",
        "en": "Players: {cur}/{max} (min {min})",
        "uk": "Гравців: {cur}/{max} (мінімум {min})",
    },
    "lobby_host": {"ru": "Ведущий", "en": "Host", "uk": "Ведучий"},
    "started": {"ru": "▶️ Игра началась!", "en": "▶️ Game started!", "uk": "▶️ Гру почато!"},
    "content_ru_only": {
        "ru": "",
        "en": "ℹ️ This game's content is in Russian for now.\n",
        "uk": "ℹ️ Контент цієї гри поки що російською.\n",
    },

    # --- Крокодил ---
    "croc_leader": {
        "ru": "Ведущий: {m}\nОбъясняет слово — угадывайте в чате!",
        "en": "Host: {m}\nExplaining the word — guess in the chat!",
        "uk": "Ведучий: {m}\nПояснює слово — вгадуйте в чаті!",
    },
    "croc_pm_caption": {
        "ru": "Объясняй слово в чате, не называя его и однокоренные!\n/skip — пропустить.",
        "en": "Explain the word in the chat without naming it or its forms!\n/skip to skip.",
        "uk": "Пояснюй слово в чаті, не називаючи його та спільнокореневі!\n/skip — пропустити.",
    },
    "croc_no_pm": {
        "ru": "⚠️ {m}, напиши мне /start в ЛС и нажми «Новое слово».",
        "en": "⚠️ {m}, send me /start in private and tap “New word”.",
        "uk": "⚠️ {m}, напиши мені /start у приват і натисни «Нове слово».",
    },
    "croc_guessed": {
        "ru": "🎉 {m} угадал слово «<b>{word}</b>»!\nОчков: {score}\nТеперь {name} — ведущий.",
        "en": "🎉 {m} guessed the word “<b>{word}</b>”!\nScore: {score}\nNow {name} is the host.",
        "uk": "🎉 {m} вгадав слово «<b>{word}</b>»!\nОчок: {score}\nТепер {name} — ведучий.",
    },
    "croc_skipped": {
        "ru": "⏭ Слово «{word}» пропущено.",
        "en": "⏭ Word “{word}” skipped.",
        "uk": "⏭ Слово «{word}» пропущено.",
    },
    "score_title": {"ru": "🏆 <b>Счёт:</b>", "en": "🏆 <b>Score:</b>", "uk": "🏆 <b>Рахунок:</b>"},
    "score_empty": {
        "ru": "Пока никто не угадал.",
        "en": "No one has scored yet.",
        "uk": "Поки ніхто не вгадав.",
    },

    # --- Виселица ---
    "hang_start": {
        "ru": "🪢 Загадано слово из {n} букв.\nПишите буквы в чат! Можно назвать слово целиком.\nОшибок до проигрыша: {max}.",
        "en": "🪢 A word of {n} letters.\nType letters in the chat! You can also guess the whole word.\nWrong guesses allowed: {max}.",
        "uk": "🪢 Загадано слово з {n} літер.\nПишіть літери в чат! Можна назвати слово цілком.\nПомилок до програшу: {max}.",
    },
    "hang_hit": {
        "ru": "✅ {name} открыл букву «{letter}» (×{count}).",
        "en": "✅ {name} revealed letter “{letter}” (×{count}).",
        "uk": "✅ {name} відкрив літеру «{letter}» (×{count}).",
    },
    "hang_miss": {
        "ru": "❌ {name}: буквы «{letter}» нет. Ошибка {stage}/{max}.",
        "en": "❌ {name}: no letter “{letter}”. Mistake {stage}/{max}.",
        "uk": "❌ {name}: літери «{letter}» немає. Помилка {stage}/{max}.",
    },
    "hang_win": {
        "ru": "🎉 Победа! Слово «<b>{word}</b>» отгадал(а) {name}.",
        "en": "🎉 Win! {name} guessed the word “<b>{word}</b>”.",
        "uk": "🎉 Перемога! Слово «<b>{word}</b>» відгадав(ла) {name}.",
    },
    "hang_lose": {
        "ru": "💀 Поражение! Слово было «<b>{word}</b>».",
        "en": "💀 Defeat! The word was “<b>{word}</b>”.",
        "uk": "💀 Поразка! Слово було «<b>{word}</b>».",
    },
    "replay": {
        "ru": "/newgame — сыграть ещё.",
        "en": "/newgame to play again.",
        "uk": "/newgame — зіграти ще.",
    },
    "replay_solo": {
        "ru": "/play — сыграть ещё.",
        "en": "/play to play again.",
        "uk": "/play — зіграти ще.",
    },

    # --- Угадай число ---
    "num_start": {
        "ru": "🔢 Я загадал число от 1 до 100. Угадай за {n} попыток!\nПиши число в чат.",
        "en": "🔢 I picked a number from 1 to 100. Guess it in {n} tries!\nType a number.",
        "uk": "🔢 Я загадав число від 1 до 100. Вгадай за {n} спроб!\nПиши число в чат.",
    },
    "num_higher": {"ru": "⬆️ Моё число больше.", "en": "⬆️ My number is higher.", "uk": "⬆️ Моє число більше."},
    "num_lower": {"ru": "⬇️ Моё число меньше.", "en": "⬇️ My number is lower.", "uk": "⬇️ Моє число менше."},
    "num_win": {
        "ru": "🎉 Верно! Это было {n}. Попыток: {tries}.\n/play — ещё раз.",
        "en": "🎉 Correct! It was {n}. Tries: {tries}.\n/play to play again.",
        "uk": "🎉 Правильно! Це було {n}. Спроб: {tries}.\n/play — ще раз.",
    },
    "num_lose": {
        "ru": "💀 Попытки кончились! Я загадал {n}.\n/play — ещё раз.",
        "en": "💀 Out of tries! My number was {n}.\n/play to play again.",
        "uk": "💀 Спроби скінчились! Я загадав {n}.\n/play — ще раз.",
    },
    "num_tries_left": {"ru": "Осталось попыток: {n}", "en": "Tries left: {n}", "uk": "Залишилось спроб: {n}"},

    # --- Камень-ножницы-бумага ---
    "rps_start": {
        "ru": "✊ Камень-ножницы-бумага! До {n} побед. Твой ход:",
        "en": "✊ Rock-paper-scissors! First to {n} wins. Your move:",
        "uk": "✊ Камінь-ножиці-папір! До {n} перемог. Твій хід:",
    },
    "rps_round": {
        "ru": "Ты: {you} | Я: {me} — {res}\nСчёт: {ps}:{bs}",
        "en": "You: {you} | Me: {me} — {res}\nScore: {ps}:{bs}",
        "uk": "Ти: {you} | Я: {me} — {res}\nРахунок: {ps}:{bs}",
    },
    "rps_you_win": {"ru": "ты выиграл 🎉", "en": "you win 🎉", "uk": "ти виграв 🎉"},
    "rps_you_lose": {"ru": "ты проиграл", "en": "you lose", "uk": "ти програв"},
    "rps_draw": {"ru": "ничья", "en": "draw", "uk": "нічия"},
    "rps_final_win": {
        "ru": "🏆 Ты победил со счётом {ps}:{bs}!\n/play — реванш.",
        "en": "🏆 You won {ps}:{bs}!\n/play for a rematch.",
        "uk": "🏆 Ти переміг з рахунком {ps}:{bs}!\n/play — реванш.",
    },
    "rps_final_lose": {
        "ru": "😈 Я победил со счётом {bs}:{ps}!\n/play — реванш.",
        "en": "😈 I won {bs}:{ps}!\n/play for a rematch.",
        "uk": "😈 Я переміг з рахунком {bs}:{ps}!\n/play — реванш.",
    },
    "rps_rock": {"ru": "🪨 Камень", "en": "🪨 Rock", "uk": "🪨 Камінь"},
    "rps_paper": {"ru": "📄 Бумага", "en": "📄 Paper", "uk": "📄 Папір"},
    "rps_scissors": {"ru": "✂️ Ножницы", "en": "✂️ Scissors", "uk": "✂️ Ножиці"},
}


def t(lang: str, key: str, **kwargs) -> str:
    entry = T.get(key, {})
    text = entry.get(lang) or entry.get(DEFAULT_LANG) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
