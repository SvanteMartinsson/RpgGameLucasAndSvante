#!/usr/bin/env python3
"""regenerate_overworld.py — rebuild overworld.tmx at the approved 80x56 FOUNDATION:
open roamable wilderness as default, organic forest masses to weave around, and
the 17 towns at their approved scattered coords. NO rivers/mountains/houses
(edge phase). Combat/RNG/encounter pools (world.json) untouched.

Paradigm vs the old beautify (scatter-props-protect-paths): here the default is
OPEN. Ground is uniform cainos (core) + grave_heath (heath y>=36). Walls hold
only the map border (gid 2) with gate holes + a few organic forest-mass blobs
(solid trunk tiles, never on a town margin, gate halo, or the two zone-crossing
lines). decor_over holds the canopies. Reachability flood-fill asserts every town
+ gate is reachable from spawn. Tilesets (incl. the registered water_autotile)
are left intact — only map dims + the three layer CSVs are rewritten.

Deterministic (seeded). Reads core_zone.json for the town/gate/seam data.
"""
import collections
import json
import random
import re

random.seed(80)
TMX = "rpg_game/data/maps/overworld.tmx"
ZONE = "rpg_game/data/maps/core_zone.json"
W, H = 80, 56
SEAM_Y = 36                       # core rows 0..35, Verralda heath 36..55
BORDER_GID = 2                    # placeholder solid block (matches old border)

GRASS = {"cainos": 3, "grave_heath": 387}   # ground firstgids (uniform per band)
PLANT = {"cainos": 2691, "grave_heath": 4227}
GBASE, GVAR, GDET = 0, [1, 2, 3], [4, 5, 6, 7, 12, 13, 20, 21]
TRUNK, CANOPY = 66, 34            # solid trunk (walls) + dense canopy (decor_over)

# Organic forest masses (cx, cy, r) placed BETWEEN towns. Minority terrain you
# weave around; kept off town margins + the two zone-crossing lines.
FORESTS = [(20, 28, 5), (44, 10, 4), (52, 31, 4), (67, 21, 4),
           (40, 50, 5), (8, 50, 3), (33, 14, 3), (58, 40, 3), (30, 6, 3)]


def theme_ground(x, y):
    return "grave_heath" if y >= SEAM_Y else "cainos"


def theme_plant(y):
    return "grave_heath" if y >= SEAM_Y else "cainos"


def read_layer_csv(src, name):
    m = re.search(r'<layer id="\d+" name="%s"[^>]*>\s*<data encoding="csv">\s*(.*?)\s*</data>' % name, src, re.S)
    rows = m.group(1).strip().split("\n")
    return [[int(v) for v in r.rstrip(",").split(",")] for r in rows]


def line_cells(a, b):
    (ax, ay), (bx, by) = a, b
    steps = max(abs(ax - bx), abs(ay - by)) or 1
    cells = set()
    for i in range(steps + 1):
        x = round(ax + (bx - ax) * i / steps)
        y = round(ay + (by - ay) * i / steps)
        for dx in (-1, 0, 1):
            cells.add((x + dx, y))
    return cells


def main():
    zone = json.load(open(ZONE, encoding="utf-8"))
    towns = {t["place_id"]: tuple(t["tile"]) for t in zone["towns"]}
    town_tiles = set(towns.values())
    gates = [tuple(g["tile"]) for g in zone["gates"]]
    start = tuple(zone["start_tile"])

    # protected = towns (+2-ring open margin), start, gate halos, and the two
    # zone-crossing corridors-of-intent (kept clear so the seam stays passable).
    protected = set()
    for (tx, ty) in town_tiles | {start}:
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                protected.add((tx + dx, ty + dy))
    for (gx, gy) in gates:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                protected.add((gx + dx, gy + dy))
    for a, b in (("burg_117", "burg_54"), ("burg_149", "burg_67")):
        protected |= line_cells(towns[a], towns[b])

    # ---- GROUND: open grass, uniform per band ----
    ground = [[0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            base = GRASS[theme_ground(x, y)]
            r = random.random()
            idx = random.choice(GDET) if r < 0.04 else (random.choice(GVAR) if r < 0.28 else GBASE)
            ground[y][x] = base + idx

    # ---- WALLS: border + gate holes + organic forest masses ----
    walls = [[0] * W for _ in range(H)]
    for x in range(W):
        walls[0][x] = walls[H - 1][x] = BORDER_GID
    for y in range(H):
        walls[y][0] = walls[y][W - 1] = BORDER_GID
    for (gx, gy) in gates:
        walls[gy][gx] = 0  # carve the gate hole (presentation blocks it w/ message)

    decor = [[0] * W for _ in range(H)]
    forest_cells = set()
    for cx, cy, r in FORESTS:
        for y in range(max(1, cy - r - 1), min(H - 1, cy + r + 2)):
            for x in range(max(1, cx - r - 1), min(W - 1, cx + r + 2)):
                if (x - cx) ** 2 + (y - cy) ** 2 <= (r + random.uniform(-1.2, 0.4)) ** 2:
                    if (x, y) not in protected:
                        forest_cells.add((x, y))
    for (x, y) in forest_cells:
        base = PLANT[theme_plant(y)]
        walls[y][x] = base + TRUNK     # solid -> collision + render
        decor[y][x] = base + CANOPY    # leafy top, over the trunk

    # ---- reachability: flood-fill from start over walls==0 ----
    blocked = {(x, y) for y in range(H) for x in range(W) if walls[y][x] != 0}
    seen = {start}
    dq = collections.deque([start])
    while dq:
        x, y = dq.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in blocked and (nx, ny) not in seen:
                seen.add((nx, ny))
                dq.append((nx, ny))
    unreachable = [p for p, t in towns.items() if t not in seen]
    gate_bad = [g for g in gates if g not in seen]
    assert not unreachable, f"towns walled off: {unreachable}"
    assert not gate_bad, f"gates unreachable: {gate_bad}"

    # ---- writeback: map dims + the three layer CSVs (tilesets untouched) ----
    src = open(TMX, encoding="utf-8").read()

    def csv(grid):
        return ",\n".join(",".join(str(grid[y][x]) for x in range(W)) for y in range(H))

    src = re.sub(r'(<map [^>]*?)\bwidth="\d+" height="\d+"',
                 lambda m: f'{m.group(1)}width="{W}" height="{H}"', src, count=1)
    for lid, name, grid in (("1", "ground", ground), ("2", "walls", walls), ("3", "decor_over", decor)):
        src = re.sub(r'(<layer id="%s" name="%s")[^>]*(>)' % (lid, name),
                     lambda m: f'{m.group(1)} width="{W}" height="{H}"{m.group(2)}', src, count=1)
        src = re.sub(r'(<layer id="%s" name="%s"[^>]*>\s*<data encoding="csv">\s*).*?(\s*</data>)' % (lid, name),
                     lambda m: m.group(1) + csv(grid) + "\n" + m.group(2), src, count=1, flags=re.S)

    open(TMX, "w", encoding="utf-8").write(src)
    print(f"OK 80x56: {len(town_tiles)} towns + {len(gates)} gates reachable; "
          f"{len(forest_cells)} forest-mass trunks; walkable ~"
          f"{100*(1 - len(blocked)/(W*H)):.1f}% (incl. border)")


if __name__ == "__main__":
    main()
