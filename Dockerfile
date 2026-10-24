FROM python:3.12-slim

# Шрифты нужны Pillow для отрисовки карточек/виселицы
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY lazygame ./lazygame

# Токен передаётся через переменную окружения BOT_TOKEN (не хранится в образе!)
CMD ["python", "-m", "lazygame.bot"]
