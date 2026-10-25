# 🚀 Деплой LazyGame 24/7

Бот работает на long-polling — внешний HTTP-порт не нужен. Нужен только
постоянно запущенный процесс `python -m lazygame.bot` и переменная `BOT_TOKEN`.

Данные (настройки, статистика, рекорды) лежат в SQLite по пути `LAZYGAME_DB`
(в образе — `/app/data/lazygame.db`). Чтобы они переживали перезапуск/передеплой,
к папке `/app/data` подключают **постоянный том/диск** (это настроено в конфигах).

> ⚠️ Токен — это пароль. Задавай его только в переменных/секретах хостинга,
> никогда в коде или в git. Засвеченный токен отзови в @BotFather.

---

## Вариант A — Railway (проще всего, с телефона, ~5 минут)

1. Зайди на **railway.app**, залогинься через GitHub.
2. **New Project → Deploy from GitHub repo** → выбери `MrPsyh/NoviiProekt`,
   ветку с кодом.
3. Railway увидит `Dockerfile` и соберёт образ. Если спросит тип — это **worker**
   (фоновый процесс), команда уже в `Procfile`.
4. Вкладка **Variables** → добавь `BOT_TOKEN` = твой токен. По желанию `ADMIN_ID`,
   `WEBAPP_URL`.
5. **Variables** → добавь `LAZYGAME_DB=/app/data/lazygame.db`, затем
   **Settings → Volumes** → New Volume, mount path `/app/data` (чтобы рекорды не
   сбрасывались).
6. Deploy. Готово — бот живёт постоянно.

## Вариант B — Fly.io (через CLI, удобно отдавать деплой автоматике)

```bash
# один раз
fly auth login
fly launch --no-deploy          # создаст приложение из fly.toml (имя поменяй)
fly volumes create lazygame_data --size 1 --region fra
fly secrets set BOT_TOKEN=xxxxx # и при желании ADMIN_ID / WEBAPP_URL
fly deploy
```

`fly.toml` уже в репозитории (том `/app/data`, процесс `python -m lazygame.bot`).

## Вариант C — Render (Blueprint)

1. **render.com → New → Blueprint** → выбери репозиторий (там есть `render.yaml`).
2. Задай `BOT_TOKEN` (и `ADMIN_ID`/`WEBAPP_URL`) как secret.
3. Deploy. Диск `/app/data` описан в `render.yaml`.
   На бесплатном плане дисков нет — тогда убери блок `disk` (данные будут
   сбрасываться при передеплое) или возьми платный план.

## Вариант D — свой сервер / VPS (Docker)

```bash
git clone <repo> && cd NoviiProekt
echo "BOT_TOKEN=xxxxx" > .env          # + ADMIN_ID / WEBAPP_URL при желании
docker compose up -d --build           # фоновый запуск, автоперезапуск, том для БД
docker compose logs -f                 # логи
docker compose down                    # остановить
```

---

## Мини-апп (необязательно)

Папку `webapp/` (игровой хаб, админ-панель, страница рекордов) выложи на любой
HTTPS-хостинг — проще всего **GitHub Pages** (Settings → Pages). Полученный
адрес пропиши в `WEBAPP_URL`, и в боте появятся кнопки открытия мини-аппа.

## Проверка

После деплоя напиши боту `/start` в ЛС и `/newgame` в группе (сделав его там
админом). Логи деплоя не должны содержать `Conflict` — он означает, что бот
запущен в двух местах сразу (оставь один экземпляр на токен).
