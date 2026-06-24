#!/usr/bin/env python3
"""extend_verralda.py — build the grave_heath region south of the core.

Additive and invariant-safe: the CORE rows (0..CORE_HEIGHT-1) of every layer are
kept BYTE-IDENTICAL; only the southern heath rows are (re)generated. This is
deliberately NOT a beautify re-run — beautify regenerates the whole map from a
seed, which would reshuffle the core and break byte-identity.

Idempotent: it reads the current map, keeps the core rows, DISCARDS any existing
heath rows, and regenerates the heath fresh. So running on the bare skeleton or
on an already-populated heath yields the same 48x32 result — no double-extending.

Heath content: recolor-lifted grave_heath ground + a DISTINCT density that reads
as open, contested farmland — SPARSER trees than the core's forest, more scattered
stone/scrub. Trunks -> walls (collision + drawn); canopies -> decor_over (no
collision, drawn over ground); rocks/bushes -> walls as obstacles. A protected
spine + halos keep Alherralba, the frontier gate and the north seam reachable.
"""
from __future__ import annotations

import collections
import random
import re

TMX = "rpg_game/data/maps/overworld.tmx"
CORE_HEIGHT = 20                # rows 0..19 are the core, preserved verbatim
SOUTH_ROWS = 12                 # heath rows (y = 20 .. 31)
NEW_H = CORE_HEIGHT + SOUTH_ROWS
BORDER_GID = 2                  # placeholder wall tile, matches the existing border
GRASS_FIRSTGID = 387            # grave_heath_grass (already registered)
PLANT_FIRSTGID = 4227           # grave_heath_plant  (next free; registered below)
PROPS_FIRSTGID = 4483           # grave_heath_props
SEAM_X = 13                     # column under the old gate_south [13, 19]
FRONTIER_GATE_X = 13            # hole in the bottom border -> future-zone gate
ALHERRALBA = (14, 26)           # respawn-hub town tile in the heath

PROP_TILESETS = [
    (PLANT_FIRSTGID, "grave_heath_plant",
     "../../assets/props/generated/01-TX-Plant-with-Shadow__grave_heath.png"),
    (PROPS_FIRSTGID, "grave_heath_props",
     "../../assets/props/generated/03-TX-Props-with-Shadow__grave_heath.png"),
]

# Grass tile indices, same conventions as the core ground.
GBASE, GVAR, GDET = 0, [1, 2, 3], [4, 5, 6, 7, 12, 13, 20, 21, 22, 28, 29]

# Tree stamps (cainos/grave_heath share layout): trunk -> walls, canopy -> decor.
# Same fixed stamps as the core after the detached-top-row fix (no dy=-4 row).
TREES = [
    {"trunk": 66, "canopy": [(-1, -3, 17), (0, -3, 18), (1, -3, 19),
                             (-1, -2, 33), (0, -2, 34), (1, -2, 35),
                             (-1, -1, 49), (0, -1, 50), (1, -1, 51)]},
    {"trunk": 70, "canopy": [(-1, -3, 21), (0, -3, 22), (1, -3, 23),
                             (-1, -2, 37), (0, -2, 38), (1, -2, 39),
                             (-1, -1, 53), (0, -1, 54), (1, -1, 55)]},
    {"trunk": 74, "canopy": [(-1, -3, 25), (0, -3, 26), (1, -3, 27),
                             (-1, -2, 41), (0, -2, 42), (1, -2, 43),
                             (0, -1, 58), (1, -1, 59)]},
]
BUSHES = [97, 98, 99, 101, 103, 105, 107]               # plant ark
ROCKS = [240, 241, 242, 243, 244, 245, 247, 248, 249]   # props ark
GRAVES = [135, 137, 167]                                # props ark (cairns/markers)

# Verralda is OPEN, contested farmland — its own density/mix, not the core forest:
# few trees, but more scattered stone/scrub. (Core: 9 trees, DENSITY 0.06.)
HEATH_TREES = 4
PROP_DENSITY = 0.07
random.seed(20)  # deterministic heath generation (offline, not the game RNG)


def _layers(src):
    out = {}
    for name in ("ground", "walls", "decor_over"):
        m = re.search(r'name="%s"[^>]*>\s*<data encoding="csv">\s*(.*?)\s*</data>' % name, src, re.S)
        out[name] = [[int(v) for v in r.rstrip(",").split(",")] for r in m.group(1).strip().split("\n")]
    return out


def _heath_ground_row(w):
    row = []
    for _x in range(w):
        r = random.random()
        idx = random.choice(GDET) if r < 0.04 else (random.choice(GVAR) if r < 0.30 else GBASE)
        row.append(GRASS_FIRSTGID + idx)
    return row


def _tree_footprint(stamp, tx, ty):
    cells = {(tx, ty)}
    for dx, dy, _ in stamp["canopy"]:
        cells.add((tx + dx, ty + dy))
    return cells


def _place_trees(w, protected):
    """Sparse, footprint-aware trees wholly inside the heath interior.
    Returns (trunks{(x,y):gid}, canopy{(x,y):gid}, footprint set)."""
    trunks, canopy, footprint_all = {}, {}, set()
    placed = attempts = 0
    while placed < HEATH_TREES and attempts < 400:
        attempts += 1
        tx = random.randint(2, w - 3)
        # Trunk low enough that the canopy (up to dy=-3) stays at y>=CORE_HEIGHT.
        ty = random.randint(CORE_HEIGHT + 3, NEW_H - 2)
        stamp = random.choice(TREES)
        fp = _tree_footprint(stamp, tx, ty)
        halo = {(x + dx, y + dy) for (x, y) in fp for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
        if any(not (1 <= x < w - 1 and CORE_HEIGHT <= y < NEW_H - 1) for x, y in fp):
            continue
        if fp & protected or halo & footprint_all:
            continue
        trunks[(tx, ty)] = PLANT_FIRSTGID + stamp["trunk"]
        for dx, dy, idx in stamp["canopy"]:
            canopy[(tx + dx, ty + dy)] = PLANT_FIRSTGID + idx
        footprint_all |= fp
        placed += 1
    return trunks, canopy, footprint_all


def _obstacle_pool():
    pool = []
    pool += [(PLANT_FIRSTGID, i) for i in BUSHES] * 2     # scrub
    pool += [(PROPS_FIRSTGID, i) for i in ROCKS] * 3      # more scattered stone
    pool += [(PROPS_FIRSTGID, i) for i in GRAVES] * 1     # occasional contested-land marker
    return pool


def _register_tilesets(src):
    if "grave_heath_plant" in src:
        return src
    block = ""
    for fg, name, source in PROP_TILESETS:
        block += (f' <tileset firstgid="{fg}" name="{name}" tilewidth="32" tileheight="32" '
                  f'tilecount="256" columns="16">\n  <image source="{source}" '
                  f'width="512" height="512"/>\n </tileset>\n')
    return src.replace('<layer id="1" name="ground"', block + '<layer id="1" name="ground"', 1)


def main():
    src = open(TMX, encoding="utf-8").read()
    src = _register_tilesets(src)
    w = int(re.search(r'<map [^>]*\bwidth="(\d+)"', src).group(1))
    cur_h = int(re.search(r'<map [^>]*\bheight="(\d+)"', src).group(1))
    layers = _layers(src)

    # Protected spine + halos: north seam down to the frontier gate, branch to
    # Alherralba. Props/trees never land here, so nothing gets walled in.
    protected = set()
    spine = [(SEAM_X, y) for y in range(CORE_HEIGHT, NEW_H)]          # seam -> frontier gate
    spine += [(14, y) for y in range(CORE_HEIGHT, ALHERRALBA[1] + 1)]  # branch to Alherralba
    for (cx, cy) in spine + [ALHERRALBA, (FRONTIER_GATE_X, NEW_H - 1), (SEAM_X, CORE_HEIGHT - 1)]:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                protected.add((cx + dx, cy + dy))

    trunks, canopy, tree_fp = _place_trees(w, protected)
    protected |= tree_fp  # props avoid whole trees

    pool = _obstacle_pool()
    props = {}
    for y in range(CORE_HEIGHT, NEW_H - 1):
        for x in range(1, w - 1):
            if (x, y) in protected or (x, y) in trunks:
                continue
            if random.random() < PROP_DENSITY:
                fg, idx = random.choice(pool)
                props[(x, y)] = fg + idx

    # Rebuild each layer: core rows verbatim + freshly generated heath rows.
    new_grids = {}
    for name, grid in layers.items():
        rows = [grid[y][:] for y in range(CORE_HEIGHT)]  # core, byte-identical
        for y in range(CORE_HEIGHT, NEW_H):
            if name == "ground":
                rows.append(_heath_ground_row(w))
            elif name == "walls":
                row = [0] * w
                row[0] = row[w - 1] = BORDER_GID
                if y == NEW_H - 1:                         # bottom border + frontier hole
                    row = [BORDER_GID] * w
                    row[FRONTIER_GATE_X] = 0
                rows.append(row)
            else:  # decor_over
                rows.append([0] * w)
        new_grids[name] = rows
    for (x, y), gid in trunks.items():
        new_grids["walls"][y][x] = gid                     # trunk: collision + drawn
    for (x, y), gid in props.items():
        new_grids["walls"][y][x] = gid                     # rock/bush: obstacle
    for (x, y), gid in canopy.items():
        new_grids["decor_over"][y][x] = gid                # canopy: drawn, no collision

    # Reachability over walkable cells from the start tile.
    walls = new_grids["walls"]
    blocked = {(x, y) for y in range(NEW_H) for x in range(w) if walls[y][x] != 0}
    seen, q = {(14, 10)}, collections.deque([(14, 10)])
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < NEW_H and (nx, ny) not in blocked and (nx, ny) not in seen:
                seen.add((nx, ny)); q.append((nx, ny))
    assert ALHERRALBA in seen, "Alherralba unreachable"
    assert (SEAM_X, CORE_HEIGHT) in seen, "heath not reachable through the seam"

    # Write layers + map height back.
    def csv(rows):
        return ",\n".join(",".join(str(rows[y][x]) for x in range(w)) for y in range(len(rows)))

    for name, rows in new_grids.items():
        pattern = (r'(<layer id="\d+" name="%s"[^>]*>\s*<data encoding="csv">\s*)(.*?)(\s*</data>)' % name)

        def repl(mm, rows=rows):
            opener = mm.group(1).replace(f'height="{cur_h}"', f'height="{NEW_H}"')
            return opener + csv(rows) + mm.group(3)

        src = re.sub(pattern, repl, src, count=1, flags=re.S)
    src = re.sub(r'(<map [^>]*\bheight=)"%d"' % cur_h, r'\1"%d"' % NEW_H, src, count=1)

    open(TMX, "w", encoding="utf-8").write(src)
    print(f"heath {w}x{NEW_H}: {len(trunks)} trees, {len(props)} props "
          f"(density {PROP_DENSITY}), Alherralba + frontier reachable")


if __name__ == "__main__":
    main()
