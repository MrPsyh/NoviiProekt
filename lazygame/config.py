"""Загрузка конфигурации из окружения (.env)."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()
# URL мини-аппа (Telegram Web App). Если задан — появится кнопка «Открыть LazyGame».
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не задан. Скопируй .env.example в .env и вставь токен от @BotFather.\n"
        "Токен НИКОГДА не хранится в коде — только в .env (который игнорируется git)."
    )

ADMIN_ID = int(ADMIN_ID) if ADMIN_ID.isdigit() else None
