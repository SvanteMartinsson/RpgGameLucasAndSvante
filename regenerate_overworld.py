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
PATH_NEAR = [44, 45, 36, 37]      # denser cobble stub leaving a town
PATH_FAR = [52, 53, 60, 61]       # scattered overgrown cobble mid-route

WATER_FG = 4739                   # water_autotile firstgid (WIDX offsets)
BRIDGE_FG = 4755                  # water_bridge firstgid
PLANK_H, PLANK_V = 13, 14         # full self-railed decks: E-W deck / N-S deck

# ---- pocket-based vegetation (this slice) --------------------------------
# Per-zone plant/props sheet firstgids (registered in the TMX, left intact).
PLANT_FG = {"cainos": 2691, "mork_skog": 3203, "cursed_mire": 3715, "grave_heath": 4227}
PROPS_FG = {"cainos": 2947, "mork_skog": 3459, "cursed_mire": 3971, "grave_heath": 4483}
# Tile indices verified OPAQUE on the current 512x512 sheets (measured per-tile;
# the old 1847c8c indices pointed at empty cells -> invisible collision).
BUSHES = [103, 105, 107]      # plant sheet — solid single-tile shrubs (decor)
# Clean FREESTANDING single-tile boulders only (242-245). 208/224/225/249 are
# pieces of multi-tile rock formations — placed alone they show cut seams/borders
# (the "buggy box" artifact). 240/241/247/248 are too transparent (phantom collision).
ROCKS = [242, 243, 244, 245]  # props sheet — single-tile boulders (walls, >=32% fill)
# Different obstacle for the grave_heath: clean opaque single-tile gravestones (a
# graveyard ring instead of boulders) — "olika hinder".
GRAVES = [89, 103, 135, 137]
# Rock pockets are laid as a near-full RING (round obstacle) rather than a filled
# blob: props on the perimeter band, open centre, occasional gaps -> "nästan runt".
RING_BAND = 1.4
RING_DENSITY = 0.5            # ~every other stone -> uneven ring with walkable gaps

# Feature pockets: a FEW concentrated patches per zone (bush snår / sten-utskott /
# blomäng) with OPEN ground dominating between them — landmarks, not even speckle.
# Counts/radii/densities are PLACEHOLDERS (Lucas tunes on the render).
POCKETS_PER_ZONE = {"cainos": 8, "mork_skog": 6, "cursed_mire": 5, "grave_heath": 7}
POCKET_KINDS = ["bush", "rock", "flower"]   # weighted toward bush/flower below
POCKET_KIND_WEIGHTS = [3, 2, 3]
POCKET_RADIUS = (4, 9)            # tiles (jittered per cell so edges are ragged)
TOWN_MARGIN = 12                  # keep pockets off a town's cluster footprint + doorstep

# Density INSIDE a pocket vs the open ground between pockets.
DENSITY = {
    "bush":   {"bush": 0.32, "ground_detail": 0.10, "flower_share": 0.3},
    "rock":   {"rock": 0.16, "ground_detail": 0.34, "flower_share": 0.05},
    "flower": {"ground_detail": 0.55, "flower_share": 0.85},
    "open":   {"ground_detail": 0.04, "flower_share": 0.25},
}


def _csv(grid, W):
    return ",\n".join(",".join(str(grid[y][x]) for x in range(W)) for y in range(len(grid)))


def _deck_gid(x, y):
    """Full-deck plank for a bridge cell: N-S deck (walk N-S) over the E-W seam
    channel; E-W deck (walk E-W) over the N-S river/lake."""
    on_seam = abs(y - L.seam_y(x)) <= L.RIVER_HALF + 1.5
    return BRIDGE_FG + (PLANK_V if on_seam else PLANK_H)


def _seed_pockets(W, H, water, protected, rng):
    """Sow a few feature-pocket centres per zone on open land. Returns a list of
    (cx, cy, kind, radius)."""
    pockets = []
    for zone, n in POCKETS_PER_ZONE.items():
        placed, tries = 0, 0
        while placed < n and tries < n * 200:
            tries += 1
            x, y = rng.randint(3, W - 4), rng.randint(3, H - 4)
            if L.zone_at(x, y) != zone or (x, y) in water or (x, y) in protected:
                continue
            kind = rng.choices(POCKET_KINDS, weights=POCKET_KIND_WEIGHTS)[0]
            pockets.append((x, y, kind, rng.randint(*POCKET_RADIUS)))
            placed += 1
    return pockets


def _owning_pocket(x, y, pockets):
    """The pocket a cell belongs to: the nearest one whose (jittered) radius covers
    it, else None. Ragged edges via a per-cell hash on the radius."""
    best, best_slack = None, 0.0
    for p in pockets:
        cx, cy, _kind, radius = p
        d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
        edge = radius + (L._hash01(x, y) - 0.5) * 2.0   # +/-1 tile ragged border
        slack = edge - d
        if slack > best_slack:
            best, best_slack = p, slack
    return best


def main():
    lay = L.build_layout()
    W, H = lay["W"], lay["H"]
    towns = {pid: (t[0], t[1]) for pid, t in lay["towns"].items()}
    town_tiles = set(towns.values())
    gates = list(lay["gates"].values())
    start = lay["start"]
    water, cell_name, bridges = lay["water"], lay["cell_name"], lay["bridges"]

    # ---- PROTECTED cells (no props/pockets): town cluster footprints + doorstep,
    # gates, the start tile. Path cells are added after the path pass. ----
    protected = {start}
    for (gx, gy) in gates:
        protected.add((gx, gy))
    for (tx, ty) in town_tiles:
        for dx in range(-TOWN_MARGIN, TOWN_MARGIN + 1):
            for dy in range(-TOWN_MARGIN, TOWN_MARGIN + 1):
                protected.add((tx + dx, ty + dy))

    # ---- FEATURE POCKETS: a few bush/rock/flower patches per zone, open between ----
    pockets = _seed_pockets(W, H, water, protected, random.Random(83))
    owner_at = {(x, y): _owning_pocket(x, y, pockets)
                for y in range(H) for x in range(W)}
    kind_at = {xy: (owner[2] if owner else "open") for xy, owner in owner_at.items()}

    # ---- GROUND: themed grass; detail density follows the pocket kind ----
    gd = random.Random(81)
    ground = [[0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            base = GRASS[L.zone_at(x, y)]
            cfg = DENSITY[kind_at[(x, y)]]
            if gd.random() < cfg.get("ground_detail", 0.0):
                pool = GROUND_FLOWER if gd.random() < cfg.get("flower_share", 0.0) else GROUND_STONE
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
    path_cells = set()
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
            path_cells.add((x, y))   # keep props off the road
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

    # ---- POCKET PROPS: rock/grave RINGS (blocking, walls) + bush thickets (decor) ----
    blockset = protected | path_cells
    rp = random.Random(84)
    rock_n = bush_n = 0
    for y in range(H):
        for x in range(W):
            if (x, y) in blockset or walls[y][x] != 0 or (x, y) in bridges:
                continue
            zone = L.zone_at(x, y)
            owner = owner_at[(x, y)]
            kind = owner[2] if owner else "open"
            if kind == "rock":
                # Place props on the pocket's perimeter ring -> a near-round obstacle
                # with an open centre. Heath rings are gravestones; elsewhere boulders.
                cx, cy, _k, radius = owner
                d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                if abs(d - (radius - 1)) <= RING_BAND and rp.random() < RING_DENSITY:
                    obstacles = GRAVES if zone == "grave_heath" else ROCKS
                    walls[y][x] = PROPS_FG[zone] + rp.choice(obstacles)
                    rock_n += 1
            elif kind == "bush" and decor[y][x] == 0 and rp.random() < DENSITY["bush"]["bush"]:
                decor[y][x] = PLANT_FG[zone] + rp.choice(BUSHES)  # busksnår (single-tile, walkable)
                bush_n += 1

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
          f"{len(water)} water cells ({len(bridges)} bridge); "
          f"{len(pockets)} pockets, {rock_n} rocks (walls), {bush_n} bushes (decor); "
          f"walkable ~{walkable:.1f}%")


if __name__ == "__main__":
    main()
