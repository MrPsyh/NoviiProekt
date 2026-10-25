FROM python:3.12-slim

# Шрифты нужны Pillow для отрисовки карточек
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY lazygame ./lazygame

# Данные (SQLite) кладём в отдельную папку, которую на хостинге монтируют как
# постоянный том — тогда настройки, статистика и рекорды переживают рестарт.
ENV LAZYGAME_DB=/app/data/lazygame.db
RUN mkdir -p /app/data
VOLUME ["/app/data"]

# Токен передаётся через переменную окружения BOT_TOKEN (не хранится в образе!)
CMD ["python", "-m", "lazygame.bot"]
