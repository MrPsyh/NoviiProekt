"""Общая настройка тестов: временная БД и фейковый токен до импортов lazygame."""
import os
import tempfile

os.environ["LAZYGAME_DB"] = os.path.join(tempfile.gettempdir(), "lazygame_test.db")
os.environ.setdefault("BOT_TOKEN", "test-token")

# чистим временную БД перед прогоном
try:
    os.remove(os.environ["LAZYGAME_DB"])
except OSError:
    pass


class FakeBot:
    """Мини-заглушка Telegram-бота: считает отправленные сообщения и фото."""

    def __init__(self):
        self.messages = []
        self.photos = []

    async def send_message(self, chat_id=None, text=None, *a, **k):
        self.messages.append(text if text is not None else (a[0] if a else ""))

    async def send_photo(self, chat_id=None, photo=None, *a, **k):
        self.photos.append(k.get("caption", ""))
