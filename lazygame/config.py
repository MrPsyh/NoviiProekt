"""Загрузка конфигурации из окружения (.env)."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не задан. Скопируй .env.example в .env и вставь токен от @BotFather.\n"
        "Токен НИКОГДА не хранится в коде — только в .env (который игнорируется git)."
    )

ADMIN_ID = int(ADMIN_ID) if ADMIN_ID.isdigit() else None
