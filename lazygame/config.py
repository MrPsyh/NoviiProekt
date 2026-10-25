"""Загрузка конфигурации из окружения (.env)."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
# URL мини-аппа (Telegram Web App). Если задан — появится кнопка «Открыть LazyGame».
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()

# ID админа бота (кому доступна админ-панель). Берётся из .env, иначе — дефолт владельца.
_admin_env = os.getenv("ADMIN_ID", "").strip()
ADMIN_ID = int(_admin_env) if _admin_env.isdigit() else 8835953665

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не задан. Скопируй .env.example в .env и вставь токен от @BotFather.\n"
        "Токен НИКОГДА не хранится в коде — только в .env (который игнорируется git)."
    )
