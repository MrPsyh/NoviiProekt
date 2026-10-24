"""Генерация карточек-картинок для игр (через Pillow).

Каждая карточка персонажа «Бункера» рендерится в PNG, чтобы сообщение
в чате было с фото, а не просто текстом.
"""
from __future__ import annotations

import os
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 900, 1200
BG = (24, 26, 34)
PANEL = (34, 37, 48)
ACCENT = (255, 193, 59)
TEXT = (235, 235, 240)
MUTED = (150, 155, 170)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Пытаемся найти системный шрифт, иначе дефолтный Pillow."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
          max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def render_character_card(name: str, attrs: dict[str, str],
                          reveal_order: list[tuple[str, str]]) -> BytesIO:
    """Рисует карточку персонажа «Бункера» и возвращает PNG в BytesIO."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    title_font = _font(54, bold=True)
    label_font = _font(30, bold=True)
    value_font = _font(34)

    # Шапка
    draw.rectangle([0, 0, WIDTH, 140], fill=PANEL)
    draw.text((40, 35), "🏚 БУНКЕР", font=title_font, fill=ACCENT)
    draw.text((40, 100), name, font=label_font, fill=MUTED)

    y = 180
    margin = 40
    panel_w = WIDTH - margin * 2
    for key, label in reveal_order:
        value = attrs.get(key, "—")
        value_lines = _wrap(draw, value, value_font, panel_w - 40)
        block_h = 60 + len(value_lines) * 42 + 20

        draw.rounded_rectangle(
            [margin, y, margin + panel_w, y + block_h],
            radius=16, fill=PANEL,
        )
        draw.text((margin + 20, y + 14), label.upper(), font=label_font, fill=ACCENT)
        ty = y + 56
        for line in value_lines:
            draw.text((margin + 20, ty), line, font=value_font, fill=TEXT)
            ty += 42
        y += block_h + 16

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    buffer.name = "card.png"
    return buffer


def render_word_card(word: str, difficulty: str) -> BytesIO:
    """Карточка со словом для «Крокодила» (показывается только ведущему в ЛС)."""
    img = Image.new("RGB", (WIDTH, 500), BG)
    draw = ImageDraw.Draw(img)

    label_font = _font(36, bold=True)
    word_font = _font(72, bold=True)

    draw.text((40, 50), "🐊 КРОКОДИЛ — твоё слово:", font=label_font, fill=ACCENT)

    lines = _wrap(draw, word.upper(), word_font, WIDTH - 80)
    y = 200
    for line in lines:
        w = draw.textlength(line, font=word_font)
        draw.text(((WIDTH - w) / 2, y), line, font=word_font, fill=TEXT)
        y += 90

    diff_map = {"easy": "лёгкое", "medium": "среднее", "hard": "сложное"}
    draw.text((40, 420), f"Сложность: {diff_map.get(difficulty, difficulty)}",
              font=label_font, fill=MUTED)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    buffer.name = "word.png"
    return buffer
