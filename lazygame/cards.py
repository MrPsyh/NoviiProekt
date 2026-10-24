"""Генерация картинок для LazyGame (Pillow).

Всё рисуется на холсте ×2 с последующим уменьшением (LANCZOS) — это даёт
сглаживание фигур и текста. Эмодзи в картинках не используем (Pillow рисует их
«квадратиками»); вместо них — типографика и цветные акценты.
"""
from __future__ import annotations

import math
import os
import random
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

# ---- палитра ----------------------------------------------------------
BG_TOP = (33, 23, 64)
BG_BOT = (12, 10, 24)
PANEL = (46, 40, 70)
PANEL2 = (58, 50, 86)
STROKE = (96, 84, 140)
TEXT = (237, 235, 247)
MUTED = (168, 162, 196)

VIOLET = (142, 112, 255)
GOLD = (255, 206, 97)
PINK = (255, 99, 146)
GREEN = (86, 214, 160)
CYAN = (80, 206, 232)
RED = (240, 110, 110)

# «тетрадная» бумага и карандаш для скетч-виселицы
PAPER = (240, 236, 223)
PAPER_LINE = (203, 214, 226)
PENCIL = (46, 44, 52)

# тема (акцент) для каждой игры по slug
THEME = {
    "crocodile": GREEN,
    "bunker": GOLD,
    "mafia": RED,
    "hangman": CYAN,
    "truthdare": PINK,
    "quiz": VIOLET,
}

_FONT_CACHE: dict[tuple[int, bool], ImageFont.FreeTypeFont] = {}


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    font: ImageFont.FreeTypeFont | None = None
    for path in candidates:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                break
            except OSError:
                continue
    if font is None:
        font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


class Canvas:
    """Обёртка над Pillow с суперсэмплингом: координаты задаются в «логических»
    пикселях, рисуется на холсте ×ss, финал уменьшается с антиалиасингом."""

    def __init__(self, w: int, h: int, ss: int = 2):
        self.w, self.h, self.ss = w, h, ss
        self.img = Image.new("RGB", (w * ss, h * ss), BG_BOT)
        self.d = ImageDraw.Draw(self.img, "RGBA")

    def gradient(self, top: tuple, bottom: tuple) -> None:
        s = self.ss
        H, W = self.h * s, self.w * s
        for y in range(H):
            t = y / max(1, H - 1)
            self.d.line(
                [(0, y), (W, y)],
                fill=(
                    int(top[0] + (bottom[0] - top[0]) * t),
                    int(top[1] + (bottom[1] - top[1]) * t),
                    int(top[2] + (bottom[2] - top[2]) * t),
                ),
            )

    def circle(self, cx, cy, r, fill) -> None:
        s = self.ss
        self.d.ellipse([(cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s], fill=fill)

    def rrect(self, box, radius, fill=None, outline=None, width=1) -> None:
        s = self.ss
        self.d.rounded_rectangle(
            [box[0] * s, box[1] * s, box[2] * s, box[3] * s],
            radius=radius * s, fill=fill, outline=outline,
            width=max(1, width * s),
        )

    def ellipse(self, box, fill=None, outline=None, width=1) -> None:
        s = self.ss
        self.d.ellipse([c * s for c in box], fill=fill, outline=outline, width=max(1, width * s))

    def line(self, pts, fill, width=1) -> None:
        s = self.ss
        self.d.line([(x * s, y * s) for x, y in pts], fill=fill, width=max(1, width * s))

    def text(self, pos, text, size, fill, bold=False) -> None:
        s = self.ss
        self.d.text((pos[0] * s, pos[1] * s), text, font=_font(size * s, bold), fill=fill)

    def text_center(self, cx, y, text, size, fill, bold=False) -> None:
        s = self.ss
        f = _font(size * s, bold)
        tw = self.d.textlength(text, font=f)
        self.d.text((cx * s - tw / 2, y * s), text, font=f, fill=fill)

    def textlen(self, text, size, bold=False) -> float:
        return self.d.textlength(text, font=_font(size * self.ss, bold)) / self.ss

    def wrap(self, text, size, max_w, bold=False) -> list[str]:
        f = _font(size * self.ss, bold)
        limit = max_w * self.ss
        lines, cur = [], ""
        for word in text.split():
            trial = f"{cur} {word}".strip()
            if self.d.textlength(trial, font=f) <= limit:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
        return lines or [""]

    def finalize(self, name="card.png") -> BytesIO:
        out = self.img.resize((self.w, self.h), Image.LANCZOS)
        buf = BytesIO()
        out.save(buf, format="PNG")
        buf.seek(0)
        buf.name = name
        return buf


def _header(c: Canvas, badge: str, title: str, subtitle: str, accent: tuple,
            x: int = 48, y: int = 48) -> None:
    """Рисует шапку: цветной бейдж-монограмма + заголовок + подзаголовок."""
    size = 92
    c.rrect([x, y, x + size, y + size], radius=24, fill=accent)
    c.text_center(x + size / 2, y + 20, badge, 46, (20, 16, 32), bold=True)
    tx = x + size + 26
    c.text((tx, y + 6), title, 42, TEXT, bold=True)
    c.text((tx, y + 58), subtitle, 24, MUTED)


# ======================================================================
# Приветствие
# ======================================================================
def render_welcome(games: list[tuple[str, str]]) -> BytesIO:
    """Горизонтальное приветствие. games: список (название, короткое_описание)."""
    c = Canvas(1200, 675)
    c.gradient(BG_TOP, BG_BOT)
    c.circle(1080, 90, 200, (142, 112, 255, 36))
    c.circle(90, 640, 220, (255, 99, 146, 28))
    c.circle(1120, 660, 150, (255, 206, 97, 24))

    # монограмма + заголовок
    c.rrect([56, 46, 152, 142], radius=26, fill=VIOLET)
    c.text_center(104, 66, "LG", 56, (18, 14, 30), bold=True)
    c.text((172, 54), "LazyGame", 60, TEXT, bold=True)
    c.text((176, 128), "Игры для компаний прямо в Telegram", 26, MUTED)

    # игры в 2 колонки × 3 ряда
    colors = [GREEN, GOLD, RED, CYAN, PINK, VIOLET]
    cols_x = [56, 622]
    pill_w, pill_h = 522, 108
    top, gap = 222, 18
    for i, (name, desc) in enumerate(games[:6]):
        col, row = i % 2, i // 2
        x = cols_x[col]
        y = top + row * (pill_h + gap)
        accent = colors[i % len(colors)]
        c.rrect([x, y, x + pill_w, y + pill_h], radius=22, fill=PANEL)
        c.rrect([x, y, x + 8, y + pill_h], radius=4, fill=accent)
        c.circle(x + 50, y + 54, 20, accent)
        c.text((x + 88, y + 20), name, 32, TEXT, bold=True)
        c.text((x + 88, y + 62), desc, 23, MUTED)

    c.text_center(600, 622, "Напиши /newgame и выбери игру", 28, GOLD, bold=True)
    return c.finalize("welcome.png")


_GAME_SHORT = {
    "crocodile": "Крокодил", "bunker": "Бункер", "mafia": "Мафия",
    "hangman": "Виселица", "truthdare": "Правда/Д", "quiz": "Викторина",
    "guessnum": "Число", "rps": "КНБ",
}


def render_admin_panel(data: dict) -> BytesIO:
    """Картинка админ-панели: плитки статистики + список чатов."""
    chats = data.get("chats", [])[:8]
    rows = len(chats)
    height = 420 + rows * 64 + 40
    c = Canvas(1000, max(520, height))
    c.gradient(BG_TOP, BG_BOT)
    c.circle(900, 120, 180, (142, 112, 255, 32))

    _header(c, "A", "Админ-панель", "LazyGame · статистика", VIOLET)

    tiles = [
        ("Чатов (админ)", str(data.get("chats_admin", 0)), GREEN),
        ("Участников", str(data.get("members_total", 0)), GOLD),
        ("Игр запущено", str(data.get("games_total", 0)), CYAN),
        ("Активно сейчас", str(data.get("active_now", 0)), PINK),
    ]
    margin, gap = 48, 20
    tw = (1000 - margin * 2 - gap * 3) / 4
    ty = 170
    for i, (label, value, accent) in enumerate(tiles):
        x = margin + i * (tw + gap)
        c.rrect([x, ty, x + tw, ty + 120], radius=18, fill=PANEL)
        c.rrect([x, ty, x + tw, ty + 6], radius=3, fill=accent)
        c.text_center(x + tw / 2, ty + 26, value, 48, accent, bold=True)
        c.text_center(x + tw / 2, ty + 92, label, 20, MUTED)

    # разбивка по играм
    by_game = data.get("by_game", {})
    if by_game:
        parts = [f"{_GAME_SHORT.get(s, s)}: {n}"
                 for s, n in sorted(by_game.items(), key=lambda kv: kv[1], reverse=True)]
        c.text((margin, 318), "По играм:  " + "   ".join(parts), 22, MUTED)

    # список чатов
    c.text((margin, 366), "Чаты, где бот админ:", 26, TEXT, bold=True)
    y = 404
    if not chats:
        c.text((margin, y), "пока нет данных", 24, MUTED)
    for ch in chats:
        c.rrect([margin, y, 1000 - margin, y + 54], radius=14, fill=PANEL)
        dot = GREEN if ch.get("admin") else RED
        c.circle(margin + 28, y + 27, 9, dot)
        title = ch.get("title", "—")
        if c.textlen(title, 24, bold=True) > 580:
            while title and c.textlen(title + "…", 24, bold=True) > 580:
                title = title[:-1]
            title += "…"
        c.text((margin + 52, y + 14), title, 24, TEXT, bold=True)
        c.text((1000 - margin - 280, y + 14),
               f"{ch.get('members', 0)} чел.    {ch.get('games', 0)} игр", 24, GOLD)
        y += 64

    return c.finalize("admin.png")


def render_avatar() -> BytesIO:
    """Квадратная аватарка бота (Telegram обрежет в круг — важное в центре)."""
    c = Canvas(640, 640)
    # мягкий радиальный-подобный фон
    c.gradient((120, 92, 230), (58, 40, 120))
    c.circle(320, 320, 300, (255, 255, 255, 10))
    c.circle(320, 320, 230, (255, 255, 255, 12))

    # центральная «карточка» с монограммой
    c.rrect([180, 150, 460, 430], radius=56, fill=(24, 18, 44))
    c.text_center(320, 196, "LG", 150, GOLD, bold=True)

    # цветные игровые «фишки» вокруг
    c.circle(170, 180, 26, GREEN)
    c.circle(470, 180, 26, CYAN)
    c.circle(165, 470, 26, PINK)
    c.circle(475, 470, 26, GOLD)

    c.text_center(320, 470, "LazyGame", 46, TEXT, bold=True)
    c.text_center(320, 530, "играй в компании", 26, (220, 214, 240))
    return c.finalize("avatar.png")


# ======================================================================
# Карточка персонажа «Бункер»
# ======================================================================
def render_character_card(name: str, attrs: dict[str, str],
                          reveal_order: list[tuple[str, str]]) -> BytesIO:
    accent = THEME["bunker"]
    c = Canvas(900, 1240)
    c.gradient(BG_TOP, BG_BOT)
    c.circle(820, 120, 160, (255, 206, 97, 26))

    _header(c, "B", "БУНКЕР", name, accent)

    y = 192
    margin = 48
    panel_w = c.w - margin * 2
    for key, label in reveal_order:
        value = attrs.get(key, "—")
        lines = c.wrap(value, 30, panel_w - 48)
        block_h = 58 + len(lines) * 38 + 18
        c.rrect([margin, y, margin + panel_w, y + block_h], radius=18, fill=PANEL)
        c.rrect([margin, y, margin + 8, y + block_h], radius=4, fill=accent)
        c.text((margin + 28, y + 14), label.upper(), 22, accent, bold=True)
        ty = y + 52
        for line in lines:
            c.text((margin + 28, ty), line, 30, TEXT)
            ty += 38
        y += block_h + 14

    return c.finalize("bunker.png")


# ======================================================================
# Карточка слова «Крокодил»
# ======================================================================
def render_word_card(word: str, difficulty: str) -> BytesIO:
    accent = THEME["crocodile"]
    c = Canvas(900, 540)
    c.gradient(BG_TOP, BG_BOT)
    c.circle(800, 460, 180, (86, 214, 160, 28))

    _header(c, "C", "КРОКОДИЛ", "твоё слово — объясни, не называя", accent)

    c.rrect([48, 210, 852, 400], radius=28, fill=PANEL)
    c.text_center(450, 258, word.upper(), 76, accent, bold=True)

    diff_map = {"easy": "лёгкое", "medium": "среднее", "hard": "сложное"}
    c.text((48, 450), f"Сложность: {diff_map.get(difficulty, difficulty)}", 26, MUTED)
    c.text((48, 486), "Однокоренные слова называть нельзя!", 24, MUTED)
    return c.finalize("word.png")


# ======================================================================
# Виселица
# ======================================================================
def _letter_tiles(c: Canvas, text: str, x: int, y: int, accent: tuple,
                  tile: int = 56, gap: int = 10) -> None:
    for i, ch in enumerate(text.upper()):
        bx = x + i * (tile + gap)
        if ch == "_":
            c.rrect([bx, y, bx + tile, y + tile], radius=12, fill=PANEL2)
            c.line([(bx + 12, y + tile - 12), (bx + tile - 12, y + tile - 12)], accent, 4)
        else:
            c.rrect([bx, y, bx + tile, y + tile], radius=12, fill=accent)
            c.text_center(bx + tile / 2, y + 10, ch, 34, (18, 14, 30), bold=True)


def _sk_seg(c: Canvas, p1, p2, rng: random.Random, color=PENCIL, width=3,
           jitter=3.5, passes=2) -> None:
    """Один «карандашный» отрезок: несколько проходов с дрожанием."""
    (x1, y1), (x2, y2) = p1, p2
    for _ in range(passes):
        n = 4
        pts = []
        for i in range(n + 1):
            t = i / n
            pts.append((
                x1 + (x2 - x1) * t + rng.uniform(-jitter, jitter),
                y1 + (y2 - y1) * t + rng.uniform(-jitter, jitter),
            ))
        c.line(pts, color, width)


def _sk_path(c: Canvas, pts, rng: random.Random, **kw) -> None:
    for i in range(len(pts) - 1):
        _sk_seg(c, pts[i], pts[i + 1], rng, **kw)


def _sk_circle(c: Canvas, cx, cy, r, rng: random.Random, color=PENCIL, width=3,
               jitter=2.5, passes=2) -> None:
    for _ in range(passes):
        n = 24
        start = rng.uniform(0, 0.6)
        pts = []
        for i in range(n + 1):
            a = start + i / n * 2 * math.pi * 1.04
            pts.append((
                cx + math.cos(a) * r + rng.uniform(-jitter, jitter),
                cy + math.sin(a) * r + rng.uniform(-jitter, jitter),
            ))
        c.line(pts, color, width)


def render_hangman(masked: str, wrong_letters: list[str], stage: int,
                   max_stage: int = 6) -> BytesIO:
    accent = THEME["hangman"]
    c = Canvas(760, 880)
    c.gradient(BG_TOP, BG_BOT)
    # один и тот же «почерк» для всех этапов одного слова
    rng = random.Random(1000 + len(masked) * 7 + max_stage)

    _header(c, "H", "ВИСЕЛИЦА", f"ошибок: {stage}/{max_stage}", accent)

    # лист бумаги
    c.rrect([60, 168, 700, 690], radius=22, fill=PAPER)
    for ly in range(220, 690, 46):
        c.line([(84, ly), (676, ly)], PAPER_LINE, 1)
    c.line([(150, 176), (150, 682)], (233, 175, 175), 2)  # поля тетради

    # Виселица строится карандашом по мере ошибок (до 10 этапов).
    # Чтобы при меньшем max_stage всё равно получалась полная картинка,
    # масштабируем номера этапов постройки под фактический max_stage.
    def on(step: int) -> bool:
        # step — из 10; показываем, если ошибок набрали достаточно
        return stage >= round(step * max_stage / 10)

    cx, cy = 470, 336
    if on(1):
        _sk_path(c, [(180, 650), (470, 650)], rng, width=4)          # 1 основание
    if on(2):
        _sk_path(c, [(230, 650), (230, 250)], rng, width=4)          # 2 столб
    if on(3):
        _sk_path(c, [(228, 250), (472, 250)], rng, width=4)          # 3 перекладина
    if on(4):
        _sk_path(c, [(230, 320), (300, 250)], rng, width=3)          # 4 укосина
    if on(5):
        _sk_path(c, [(470, 250), (470, 302)], rng, width=3, jitter=2.5)  # 5 верёвка
    if on(6):
        _sk_circle(c, cx, cy, 34, rng)                               # 6 голова
    if on(7):
        _sk_path(c, [(cx, cy + 34), (cx, cy + 170)], rng, width=4)   # 7 туловище
    if on(8):
        _sk_path(c, [(cx, cy + 70), (cx - 58, cy + 128)], rng, width=4)  # 8 рука
    if on(9):
        _sk_path(c, [(cx, cy + 70), (cx + 58, cy + 128)], rng, width=4)  # 9 рука
    if on(10):
        _sk_path(c, [(cx, cy + 170), (cx - 50, cy + 250)], rng, width=4)  # 10 ноги
        _sk_path(c, [(cx, cy + 170), (cx + 50, cy + 250)], rng, width=4)
        # грустное лицо на проигрыше
        _sk_circle(c, cx - 12, cy - 6, 3, rng, width=2, jitter=1)
        _sk_circle(c, cx + 12, cy - 6, 3, rng, width=2, jitter=1)
        _sk_path(c, [(cx - 13, cy + 18), (cx, cy + 10), (cx + 13, cy + 18)], rng,
                 width=2, jitter=1.5)

    # слово плитками (перенос при длинном)
    per_row = 11
    tile, gap = 52, 8
    chars = list(masked)
    start_y = 724
    for row in range((len(chars) + per_row - 1) // per_row):
        chunk = "".join(chars[row * per_row:(row + 1) * per_row])
        row_w = len(chunk) * (tile + gap) - gap
        _letter_tiles(c, chunk, int((c.w - row_w) / 2), start_y + row * (tile + gap),
                      accent, tile, gap)

    if wrong_letters:
        c.text((176, 150), "Ошибки: " + " ".join(l.upper() for l in wrong_letters), 24, RED)
    return c.finalize("hangman.png")
