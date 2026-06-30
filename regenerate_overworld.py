#!/usr/bin/env python3
"""regenerate_overworld.py — rebuild overworld.tmx for the #3 expansion (240x208,
option A: parametric terrain).

All geometry is DERIVED by overworld_layout.build_layout() — zone bands, an organic
coastline, the seam channel, the one north-born river -> central heath lake, and
bridges carved on real inter-town routes. This script paints that layout into the
three TMX layers (ground / walls / decor_over) and autotiles the water with the SAME
corner field the layout used, so the rendered water matches reachability exactly.

Reads town/gate/seam data from core_zone.json (single source of truth). Tilesets in
the TMX are left intact — only map dims + the three layer CSVs are rewritten.
Deterministic (seeded). NO combat/encounter-pool (world.json) changes.
"""
import json
import random
import re

import overworld_layout as L

TMX = "rpg_game/data/maps/overworld.tmx"
WORLD = "rpg_game/data/world.json"

# Ground grass firstgids per zone (the 64-tile grass sheets; idx 0-31 grass, 32-63
# cobble — same layout in every zone, so detail/cobble indices are zone-agnostic).
GRASS = {"cainos": 3, "mork_skog": 1923, "cursed_mire": 771, "grave_heath": 387}
GBASE = 0
GROUND_STONE = [6, 12, 13, 21, 28, 31, 7, 22, 30]   # pale pebbles/stones
GROUND_FLOWER = [14, 20, 23, 29]                    # flowers (sparse colour)
DETAIL_DENSITY = 0.18
FLOWER_SHARE = 0.28
PATH_NEAR = [44, 45, 36, 37]      # denser cobble stub leaving a town
PATH_FAR = [52, 53, 60, 61]       # scattered overgrown cobble mid-route

WATER_FG = 4739                   # water_autotile firstgid (WIDX offsets)
BRIDGE_FG = 4755                  # water_bridge firstgid
PLANK_H, PLANK_V = 13, 14         # full self-railed decks: E-W deck / N-S deck


def _csv(grid, W):
    return ",\n".join(",".join(str(grid[y][x]) for x in range(W)) for y in range(len(grid)))


def _deck_gid(x, y):
    """Full-deck plank for a bridge cell: N-S deck (walk N-S) over the E-W seam
    channel; E-W deck (walk E-W) over the N-S river/lake."""
    on_seam = abs(y - L.seam_y(x)) <= L.RIVER_HALF + 1.5
    return BRIDGE_FG + (PLANK_V if on_seam else PLANK_H)


def main():
    lay = L.build_layout()
    W, H = lay["W"], lay["H"]
    towns = {pid: (t[0], t[1]) for pid, t in lay["towns"].items()}
    town_tiles = set(towns.values())
    gates = list(lay["gates"].values())
    start = lay["start"]
    water, cell_name, bridges = lay["water"], lay["cell_name"], lay["bridges"]

    # ---- GROUND: themed grass with sparse visible detail ----
    gd = random.Random(81)
    ground = [[0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            base = GRASS[L.zone_at(x, y)]
            if gd.random() < DETAIL_DENSITY:
                pool = GROUND_FLOWER if gd.random() < FLOWER_SHARE else GROUND_STONE
                idx = gd.choice(pool)
            else:
                idx = GBASE
            ground[y][x] = base + idx

    # ---- broken PATH HINTS along town<->town connections (cobble, no collision) ----
    world = json.load(open(WORLD, encoding="utf-8"))
    places = {p["id"]: p for p in world["places"]}
    edges, seen_e = [], set()
    for pid, p in places.items():
        for conn in p.get("connections", []):
            a, b = pid, conn["to"]
            key = tuple(sorted((a, b)))
            if key in seen_e or a not in towns or b not in towns:
                continue
            seen_e.add(key)
            edges.append((a, b))
    pr = random.Random(82)
    for a, b in edges:
        (ax, ay), (bx, by) = towns[a], towns[b]
        steps = max(abs(ax - bx), abs(ay - by)) or 1
        for i in range(steps + 1):
            t = i / steps
            x = round(ax + (bx - ax) * t)
            y = round(ay + (by - ay) * t)
            if (x, y) in town_tiles or not (0 < x < W - 1 and 0 < y < H - 1):
                continue
            if (x, y) in water and (x, y) not in bridges:
                continue  # don't paint cobble onto open water
            mid = 2 * min(t, 1 - t)
            if pr.random() < 0.85 - 0.7 * mid:
                pool = PATH_NEAR if mid < 0.4 else PATH_FAR
                ground[y][x] = GRASS[L.zone_at(x, y)] + pr.choice(pool)

    # ---- WALLS (water + collision) + DECOR (bridge decks) ----
    walls = [[0] * W for _ in range(H)]
    decor = [[0] * W for _ in range(H)]
    for (x, y), name in cell_name.items():
        if (x, y) in bridges:
            continue
        walls[y][x] = WATER_FG + L.WIDX[name]   # water: rendered + blocks (per threshold)
    for (x, y) in bridges:
        decor[y][x] = _deck_gid(x, y)           # deck over grass, under player
        walls[y][x] = 0                         # walkable

    # ---- reachability: conservative flood-fill (every water cell blocks) ----
    blocked = {(x, y) for y in range(H) for x in range(W) if walls[y][x] != 0}
    import collections
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
    src = re.sub(r'(<map [^>]*?)\bwidth="\d+" height="\d+"',
                 lambda m: f'{m.group(1)}width="{W}" height="{H}"', src, count=1)
    for lid, name, grid in (("1", "ground", ground), ("2", "walls", walls), ("3", "decor_over", decor)):
        src = re.sub(r'(<layer id="%s" name="%s")[^>]*(>)' % (lid, name),
                     lambda m: f'{m.group(1)} width="{W}" height="{H}"{m.group(2)}', src, count=1)
        src = re.sub(r'(<layer id="%s" name="%s"[^>]*>\s*<data encoding="csv">)\s*.*?\s*(</data>)' % (lid, name),
                     lambda m: m.group(1) + "\n" + _csv(grid, W) + "\n  " + m.group(2), src, count=1, flags=re.S)
    open(TMX, "w", encoding="utf-8").write(src)

    walkable = 100 * (1 - len(blocked) / (W * H))
    print(f"OK {W}x{H}: {len(town_tiles)} towns + {len(gates)} gates reachable; "
          f"{len(water)} water cells ({len(bridges)} bridge), walkable ~{walkable:.1f}%")


if __name__ == "__main__":
    main()
