#!/usr/bin/env python3
"""crispen_water.py — snap the AI water/bridge sheet's soft alpha edge to crisp
pixel-art edges, deterministically (same spirit as recolor_themes.py).

The source sheet's shoreline is a soft ~4px alpha gradient (0,64,128,184,224,255),
which reads as a blurry fringe when the overworld is zoomed 3-4x. We threshold each
pixel's alpha to hard 0/255 — keeping the organic shoreline SHAPE the AI drew, but
snapping it to the pixel grid. RGB is preserved (palette is already in-family:
water luma ~104, bridges ~85, both fine — no recolor). Optional 1px ordered dither
along the threshold band (default off) softens the step if a hard edge looks too
sharp; render shows whether it's needed.

Reads the raw sheet, writes a SEPARATE crisp sheet (raw kept for re-runs).
Idempotent: thresholding always reads the raw and produces the same output.
"""
from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame  # noqa: E402

RAW = "rpg_game/assets/tiles/generated/water_bridge_32x32_alpha_tilesheet.png"
OUT = "rpg_game/assets/tiles/generated/water_bridge_32x32_crisp.png"
THRESHOLD = 128          # alpha >= THRESHOLD -> 255, else 0
DITHER = False           # 1px ordered dither in the threshold band (default: hard edge)
_DITHER_BAND = 40        # |alpha - THRESHOLD| <= this -> eligible for dither


def crispen(surface: "pygame.Surface", threshold: int = THRESHOLD, dither: bool = DITHER) -> "pygame.Surface":
    surface = surface.convert_alpha()
    w, h = surface.get_size()
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    surface.lock()
    out.lock()
    for y in range(h):
        for x in range(w):
            r, g, b, a = surface.get_at((x, y))
            keep = a >= threshold
            if dither and abs(a - threshold) <= _DITHER_BAND:
                keep = ((x + y) % 2 == 0) if a >= threshold else (((x + y) % 2 == 0) and a >= threshold - _DITHER_BAND)
            out.set_at((x, y), (r, g, b, 255 if keep else 0))
    surface.unlock()
    out.unlock()
    return out


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))  # needed for convert_alpha()
    result = crispen(pygame.image.load(RAW))
    pygame.image.save(result, OUT)
    print(f"crispened {os.path.basename(RAW)} -> {os.path.basename(OUT)} "
          f"(threshold {THRESHOLD}, dither {DITHER})")
    pygame.quit()


if __name__ == "__main__":
    main()
