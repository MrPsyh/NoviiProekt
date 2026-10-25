#!/usr/bin/env python3
"""Скачивает оригинальные портреты бравлеров в lazygame/assets/brawlers/<id>.png.

Запусти на СВОЁМ компьютере (где CDN доступен):
    python scripts/download_brawlers.py

Источник — Brawlify CDN (официальные ассеты Supercell). Если шаблон ссылки
поменяется, поправь BASE_URL ниже. Альтернатива — скачать официальный
Supercell Fan Kit (https://supercell.com/en/fan-content-policy/) и разложить
портреты как lazygame/assets/brawlers/<id>.png.

Изображения — собственность Supercell, используются по Fan Content Policy.
"""
from __future__ import annotations

import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lazygame.data.brawl import BRAWLERS  # noqa: E402

# Шаблоны ссылок на портреты (пробуем по очереди)
BASE_URLS = [
    "https://cdn.brawlify.com/brawlers/borderless/{id}.png",
    "https://cdn.brawlify.com/brawler/borderless/{id}.png",
    "https://cdn.brawlify.com/brawlers/{id}.png",
]

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "lazygame", "assets", "brawlers")
HEADERS = {"User-Agent": "Mozilla/5.0 (LazyGame fan project)"}


def fetch(brawler_id: int) -> bytes | None:
    for tmpl in BASE_URLS:
        url = tmpl.format(id=brawler_id)
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status == 200:
                    data = resp.read()
                    if data[:8] == b"\x89PNG\r\n\x1a\n" or len(data) > 1000:
                        return data
        except Exception:
            continue
    return None


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    ok, fail = 0, []
    for bid, en, ru, _ in BRAWLERS:
        path = os.path.join(OUT_DIR, f"{bid}.png")
        if os.path.exists(path):
            ok += 1
            continue
        data = fetch(bid)
        if data:
            with open(path, "wb") as f:
                f.write(data)
            print(f"✓ {ru} ({en}) -> {bid}.png")
            ok += 1
        else:
            print(f"✗ {ru} ({en}) — не удалось скачать")
            fail.append(f"{ru} ({bid})")
        time.sleep(0.2)
    print(f"\nГотово: {ok}/{len(BRAWLERS)}. Папка: {OUT_DIR}")
    if fail:
        print("Не скачаны:", ", ".join(fail))
        print("Поправь BASE_URLS или возьми их из официального Fan Kit.")


if __name__ == "__main__":
    main()
