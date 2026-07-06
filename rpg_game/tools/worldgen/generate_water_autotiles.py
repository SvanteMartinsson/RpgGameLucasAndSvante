#!/usr/bin/env python3
"""generate_water_autotiles.py — build a COMPLETE, SEAMLESS water autotile set
deterministically from the crisp deep-water surface (same spirit as
crispen_water.py).

Source: water_bridge_32x32_crisp.png tile (0,0) is the clean tileable deep-water
surface (measured: meanRGB ~(55,125,118), alpha {255}, self-tiles). We reuse its
exact pixels for every water texel -> zero palette drift, real water texture.

Seamlessness rule (the whole trick): the shoreline crosses every tile BORDER at
a CONSTANT canonical offset C (= tile midpoint, 16px). Two neighbours therefore
always meet there. The organic wiggle lives only in the tile INTERIOR and is
pinned to 0 at the borders, so the strand is slightly irregular but never
dead-straight, and stays pixel-sharp ({0,255} alpha, like crispen).

Complete blob set (15 tiles): full water; 4 straight edges (land N/S/E/W);
4 outer/convex corners; 4 inner/concave corners (lake coves); 2 channels
(1-tile river, land N+S and land E+W). Enough for straight river, meandering
(wide) river via corners, and arbitrary lake shapes.

Bridges are left untouched in the crisp sheet; this writes a SEPARATE new sheet.
Deterministic + idempotent: same bytes (md5) every run.
"""
from __future__ import annotations

import hashlib
import os
import random

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame  # noqa: E402

SRC = "rpg_game/assets/tiles/generated/water_bridge_32x32_crisp.png"
OUT = "rpg_game/assets/tiles/generated/water_autotile_32x32.png"

TS = 32          # tile size
C = 16           # canonical shoreline crossing offset at every border
AMP = 2          # interior wiggle amplitude (px); subtle, not dead-straight
CHAN_HALF = 7    # half-width of a 1-tile channel's water band (px)
SEED = 1

# 4x4 atlas (col,row); 15 used, slot 15 left empty.
ATLAS = {
    "full":   (0, 0), "edge_N": (1, 0), "edge_E": (2, 0), "edge_S": (3, 0),
    "edge_W": (0, 1), "out_NW": (1, 1), "out_NE": (2, 1), "out_SE": (3, 1),
    "out_SW": (0, 2), "in_NW":  (1, 2), "in_NE":  (2, 2), "in_SE":  (3, 2),
    "in_SW":  (0, 3), "chan_H": (1, 3), "chan_V": (2, 3),
}
COLS = ROWS = 4


def _wiggle(seed: int) -> list[int]:
    """Deterministic integer displacement along 0..TS-1, pinned to 0 at the two
    ends so any two tiles abut continuously at the canonical crossing."""
    rng = random.Random(seed)
    ctrl_step = 8
    ctrl = {t: rng.uniform(-AMP, AMP) for t in range(0, TS + 1, ctrl_step)}
    ctrl[0] = ctrl[TS - 1] = 0.0  # pin endpoints
    out = []
    keys = sorted(ctrl)
    for t in range(TS):
        # linear interp between surrounding control points
        lo = max(k for k in keys if k <= t)
        hi = min(k for k in keys if k >= t)
        if lo == hi:
            v = ctrl[lo]
        else:
            f = (t - lo) / (hi - lo)
            v = ctrl[lo] * (1 - f) + ctrl[hi] * f
        out.append(int(round(v)))
    out[0] = out[TS - 1] = 0
    return out


WIG_X = _wiggle(SEED)        # used for horizontal shorelines (varies with x)
WIG_Y = _wiggle(SEED + 1)    # used for vertical shorelines (varies with y)


def is_water(name: str, x: int, y: int) -> bool:
    """Mask: True if pixel (x,y) of tile `name` is water. Lx/My are the wiggling
    shorelines; every border evaluates to the canonical crossing C."""
    Lx = C + WIG_X[x]   # horizontal shoreline height at column x
    My = C + WIG_Y[y]   # vertical shoreline position at row y
    if name == "full":
        return True
    # straight edges (which side is LAND)
    if name == "edge_N":  # land north -> water south
        return y >= Lx
    if name == "edge_S":  # land south -> water north
        return y <= Lx
    if name == "edge_W":  # land west -> water east
        return x >= My
    if name == "edge_E":  # land east -> water west
        return x <= My
    # outer/convex corners: land on TWO adjacent sides, water in opposite quarter
    if name == "out_NW":  # land N&W -> water SE
        return (x >= My) and (y >= Lx)
    if name == "out_NE":  # land N&E -> water SW
        return (x <= My) and (y >= Lx)
    if name == "out_SW":  # land S&W -> water NE
        return (x >= My) and (y <= Lx)
    if name == "out_SE":  # land S&E -> water NW
        return (x <= My) and (y <= Lx)
    # inner/concave corners: land in ONE quarter, water in the other three (coves)
    if name == "in_NW":   # land NW quarter
        return (x >= My) or (y >= Lx)
    if name == "in_NE":   # land NE quarter
        return (x <= My) or (y >= Lx)
    if name == "in_SW":   # land SW quarter
        return (x >= My) or (y <= Lx)
    if name == "in_SE":   # land SE quarter
        return (x <= My) or (y <= Lx)
    # channels: 1-tile-wide river band, land on the two opposite sides
    if name == "chan_H":  # land N+S, water flows E-W
        return (C - CHAN_HALF + WIG_X[x]) <= y <= (C + CHAN_HALF + WIG_X[x])
    if name == "chan_V":  # land E+W, water flows N-S
        return (C - CHAN_HALF + WIG_Y[y]) <= x <= (C + CHAN_HALF + WIG_Y[y])
    raise ValueError(name)


def build(src_path: str = SRC) -> "pygame.Surface":
    src = pygame.image.load(src_path).convert_alpha()
    # deep-water source pixels (tile 0,0): exact RGB, real texture, zero drift
    deep = [[src.get_at((x, y))[:3] for y in range(TS)] for x in range(TS)]
    sheet = pygame.Surface((COLS * TS, ROWS * TS), pygame.SRCALPHA)
    sheet.fill((0, 0, 0, 0))
    sheet.lock()
    for name, (cx, cy) in ATLAS.items():
        ox, oy = cx * TS, cy * TS
        for y in range(TS):
            for x in range(TS):
                if is_water(name, x, y):
                    r, g, b = deep[x][y]
                    sheet.set_at((ox + x, oy + y), (r, g, b, 255))
                else:
                    sheet.set_at((ox + x, oy + y), (0, 0, 0, 0))
    sheet.unlock()
    return sheet


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))  # for convert_alpha()
    sheet = build()
    pygame.image.save(sheet, OUT)
    with open(OUT, "rb") as f:
        md5 = hashlib.md5(f.read()).hexdigest()
    print(f"wrote {OUT}  ({COLS}x{ROWS} atlas, {len(ATLAS)} tiles)  md5 {md5}")
    pygame.quit()


if __name__ == "__main__":
    main()
