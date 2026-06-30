#!/usr/bin/env python3
"""Seam proof + visual render for the water autotile set (read-only on assets).

Autotiles three water-region scenes (straight river, meandering wide river,
lake with coves) using the generated set's 15 tiles, asserts every shared
border's alpha profile matches across neighbours, and renders each scene over
a land background to scratchpad PNGs.
"""
import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame

pygame.init(); pygame.display.set_mode((1, 1))
TS = 32
SHEET = "rpg_game/assets/tiles/generated/water_autotile_32x32.png"
sheet = pygame.image.load(SHEET).convert_alpha()
ATLAS = {
    "full": (0, 0), "edge_N": (1, 0), "edge_E": (2, 0), "edge_S": (3, 0),
    "edge_W": (0, 1), "out_NW": (1, 1), "out_NE": (2, 1), "out_SE": (3, 1),
    "out_SW": (0, 2), "in_NW": (1, 2), "in_NE": (2, 2), "in_SE": (3, 2),
    "in_SW": (0, 3), "chan_H": (1, 3), "chan_V": (2, 3),
}


def tile(name):
    cx, cy = ATLAS[name]
    return sheet.subsurface(pygame.Rect(cx * TS, cy * TS, TS, TS))


def alpha_profile(name, side):
    """1/0 water mask along a tile border (N/S/E/W edge of the tile)."""
    t = tile(name)
    if side == "N":
        return tuple(1 if t.get_at((i, 0))[3] else 0 for i in range(TS))
    if side == "S":
        return tuple(1 if t.get_at((i, TS - 1))[3] else 0 for i in range(TS))
    if side == "W":
        return tuple(1 if t.get_at((0, i))[3] else 0 for i in range(TS))
    if side == "E":
        return tuple(1 if t.get_at((TS - 1, i))[3] else 0 for i in range(TS))


# Corner-based blob mapping: a tile is decided by whether each of its 4 CORNERS
# is water. Adjacent tiles share the two corners along their common edge, so the
# touching border is identical BY CONSTRUCTION -> seamless. (nw,ne,se,sw) -> tile.
CORNER_MAP = {
    (1, 1, 1, 1): "full",
    (0, 0, 1, 1): "edge_N",   # bottom two water -> land north
    (1, 1, 0, 0): "edge_S",   # top two water
    (1, 0, 0, 1): "edge_E",   # left two corners water -> water WEST -> land east
    (0, 1, 1, 0): "edge_W",   # right two corners water -> water EAST -> land west
    (0, 0, 1, 0): "out_NW",   # only SE corner water -> water in SE quarter
    (0, 0, 0, 1): "out_NE",   # only SW
    (0, 1, 0, 0): "out_SW",   # only NE
    (1, 0, 0, 0): "out_SE",   # only NW
    (0, 1, 1, 1): "in_NW",    # NW corner land, rest water
    (1, 0, 1, 1): "in_NE",    # NE land
    (1, 1, 1, 0): "in_SW",    # SW land
    (1, 1, 0, 1): "in_SE",    # SE land
    # (1,0,1,0) and (0,1,0,1) are saddles -> not in a minimal blob set
}


def autotile(corner):
    """corner[gy][gx] is water-truth at corner grid points (W+1 x H+1).
    Returns placed{(x,y):name}, list of saddle cells (unrepresentable)."""
    H = len(corner) - 1
    W = len(corner[0]) - 1
    placed, saddles = {}, []
    for y in range(H):
        for x in range(W):
            nw = int(corner[y][x]); ne = int(corner[y][x + 1])
            se = int(corner[y + 1][x + 1]); sw = int(corner[y + 1][x])
            if nw + ne + se + sw == 0:
                continue  # all land -> no tile
            name = CORNER_MAP.get((nw, ne, se, sw))
            if name is None:
                saddles.append((x, y))
            else:
                placed[(x, y)] = name
    return placed, saddles


def seam_check(placed):
    """Every orthogonally-adjacent placed pair must share an identical border."""
    fails = []
    for (x, y), name in placed.items():
        for (dx, dy, a, b) in [(1, 0, "E", "W"), (0, 1, "S", "N")]:
            nb = placed.get((x + dx, y + dy))
            if nb and alpha_profile(name, a) != alpha_profile(nb, b):
                fails.append(((x, y), name, (x + dx, y + dy), nb, a))
    return fails


def render(placed, W, H, path, bg=(120, 150, 80)):
    surf = pygame.Surface((W * TS, H * TS))
    surf.fill(bg)
    for (x, y), name in placed.items():
        surf.blit(tile(name), (x * TS, y * TS))
    pygame.image.save(surf, path)


# Scenes are defined as a WATER FIELD sampled on the CORNER grid ((W+1)x(H+1)).
import math


def corner_grid(W, H, field):
    return [[field(gx, gy) for gx in range(W + 1)] for gy in range(H + 1)]


# ---- (a) straight wide river, flows N-S ------------------------------
river = corner_grid(7, 9, lambda gx, gy: 2 <= gx <= 5)

# ---- (b) meandering wide river: smooth sine centreline, ~4 wide ------
def meander_field(gx, gy):
    cx = 4.5 + 2.4 * math.sin(gy * 0.55)
    return abs(gx - cx) <= 2.0

meander = corner_grid(11, 12, meander_field)

# ---- (c) lake with a cove: ellipse blob minus a smooth concave bite --
def lake_field(gx, gy):
    cx, cy = 5.5, 4.5
    inside = ((gx - cx) ** 2) / 18 + ((gy - cy) ** 2) / 10 <= 1.0
    cove = ((gx - 8.5) ** 2 + (gy - 4.5) ** 2) <= 4.0   # land bite on east -> inner corners
    return inside and not cove

lake = corner_grid(12, 9, lake_field)

# ---- (d) BONUS: thin 1-tile channel (straight), proves chan tiles ----
thin = corner_grid(3, 8, lambda gx, gy: False)  # placeholder; channels placed directly below

scenes = [
    ("straight_river", river),
    ("meander_river", meander),
    ("lake_coves", lake),
]

all_ok = True
print("=== WATER AUTOTILE SEAM TEST (corner-based) ===\n")
for name, cg in scenes:
    H, W = len(cg) - 1, len(cg[0]) - 1
    placed, saddles = autotile(cg)
    fails = seam_check(placed)
    used = sorted(set(placed.values()))
    out = f"scratchpad/scene_{name}.png"
    render(placed, W, H, out)
    status = "OK" if (not fails and not saddles) else "FAIL"
    if fails or saddles:
        all_ok = False
    print(f"[{status}] {name}: {len(placed)} tiles, {len(used)} kinds")
    print(f"        kinds: {used}")
    print(f"        saddle cells (unrepresentable): {saddles}")
    print(f"        seam mismatches: {len(fails)}")
    for f in fails[:5]:
        print(f"          {f}")
    print(f"        -> {out}\n")

# ---- channels: straight thin river self-tiles (vertical + horizontal) -
chV = {(0, i): "chan_V" for i in range(8)}
chH = {(i, 0): "chan_H" for i in range(8)}
fV, fH = seam_check(chV), seam_check(chH)
render(chV, 1, 8, "scratchpad/scene_channel_V.png")
render(chH, 8, 1, "scratchpad/scene_channel_H.png")
print(f"[{'OK' if not fV else 'FAIL'}] channel_V self-tiles vertically: mismatches {len(fV)}")
print(f"[{'OK' if not fH else 'FAIL'}] channel_H self-tiles horizontally: mismatches {len(fH)}")
if fV or fH:
    all_ok = False

# Self-tile check for full water
full_ok = (alpha_profile("full", "N") == alpha_profile("full", "S") ==
           alpha_profile("full", "E") == alpha_profile("full", "W") ==
           tuple([1] * TS))
print(f"full water self-tiles (all borders fully water): {full_ok}")
print(f"\nALL SCENES SEAMLESS: {all_ok and full_ok}")
