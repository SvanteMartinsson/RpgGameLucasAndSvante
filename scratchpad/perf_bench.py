#!/usr/bin/env python3
"""Headless blit benchmark for the overworld draw path (read-only, measures only).

Mirrors _draw_map's hot loop: for each layer, blit every non-empty tile onto a
1x 'world' surface (no viewport culling = today's behaviour), then compares
against a CULLED loop that only blits tiles inside the camera window.

No game state mutated, no map written. Run under dummy SDL.
"""
import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame

pygame.init()
pygame.display.set_mode((1, 1))
TW = TH = 32
LAYERS = 3  # ground + walls + decor_over (worst case: treat all as dense)

# A representative tile (convert for realistic blit cost).
tile = pygame.Surface((TW, TH)).convert()
tile.fill((40, 80, 40))


def bench(map_w, map_h, view_tiles_w, view_tiles_h, frames=120):
    """Return (full_ms, culled_ms, full_blits, culled_blits) per frame."""
    view_px_w, view_px_h = view_tiles_w * TW, view_tiles_h * TH
    world = pygame.Surface((view_px_w, view_px_h)).convert()
    # camera centered roughly mid-map
    ox = max(0, (map_w * TW - view_px_w) // 2)
    oy = max(0, (map_h * TH - view_px_h) // 2)

    # --- FULL (no cull): blit every tile of every layer, like today ---
    t0 = time.perf_counter()
    full_blits = 0
    for _ in range(frames):
        for _layer in range(LAYERS):
            for y in range(map_h):
                for x in range(map_w):
                    world.blit(tile, (x * TW - ox, y * TH - oy))
                    full_blits += 1
    full_ms = (time.perf_counter() - t0) * 1000 / frames
    full_blits //= frames

    # --- CULLED: only tiles overlapping the camera window ---
    left = max(0, ox // TW)
    right = min(map_w, (ox + view_px_w) // TW + 1)
    top = max(0, oy // TH)
    bottom = min(map_h, (oy + view_px_h) // TH + 1)
    t0 = time.perf_counter()
    culled_blits = 0
    for _ in range(frames):
        for _layer in range(LAYERS):
            for y in range(top, bottom):
                for x in range(left, right):
                    world.blit(tile, (x * TW - ox, y * TH - oy))
                    culled_blits += 1
    culled_ms = (time.perf_counter() - t0) * 1000 / frames
    culled_blits //= frames
    return full_ms, culled_ms, full_blits, culled_blits


# Visible window ~ what the zoom shows on a large/Retina window:
# zoom caps at 5, so a ~1920px-wide window shows ~12 tiles; height ~ a bit more.
# Use a generous 18x14 visible window so culled numbers are not understated.
VIEW_W, VIEW_H = 18, 14

CASES = [
    ("current   48x32", 48, 32),
    ("proposed  72x48", 72, 48),
    ("proposed  80x56", 80, 56),
    ("large     96x64", 96, 64),
]

print(f"{'map':<18}{'tiles':>8}{'full blits':>12}{'full ms':>10}"
      f"{'cull blits':>12}{'cull ms':>10}")
print("-" * 70)
for label, mw, mh in CASES:
    full_ms, cull_ms, fb, cb = bench(mw, mh, VIEW_W, VIEW_H)
    print(f"{label:<18}{mw*mh:>8}{fb:>12}{full_ms:>9.2f}"
          f"{cb:>12}{cull_ms:>9.2f}")

print()
print("note: blit count = tiles x 3 layers. dummy-SDL software blits are slower")
print("than GPU, so treat ms as RELATIVE (scaling), not absolute frame budget.")
