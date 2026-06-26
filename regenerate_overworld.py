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
import math
import random
import re

random.seed(80)
TMX = "rpg_game/data/maps/overworld.tmx"
ZONE = "rpg_game/data/maps/core_zone.json"
WORLD = "rpg_game/data/world.json"
W, H = 80, 56
SEAM_Y = 36                       # core rows 0..35, Verralda heath 36..55
BORDER_GID = 2                    # placeholder solid block (matches old border)

GRASS = {"cainos": 3, "grave_heath": 387}   # ground firstgids (uniform per band)
PLANT = {"cainos": 2691, "grave_heath": 4227}
# Grass-sheet tile indices (all within the grass tileset, so ground stays
# {cainos_grass, grave_heath_grass}). idx 0-31 are grass; 32-63 are cobble.
GBASE = 0
# Only tiles with a genuinely VISIBLE mark count (measured: idx 1-27 grass "tufts"
# are pixel-identical to base at zoom). Stone/pebble tiles read as earthy ground
# texture; flowers add colour sparingly so it stays wilderness, not a meadow.
GROUND_STONE = [6, 12, 13, 21, 28, 31, 7, 22, 30]               # pale pebbles/stones
GROUND_FLOWER = [14, 20, 23, 29]                                # yellow/orange flowers
DETAIL_DENSITY = 0.18      # share of cells carrying a visible detail mark
FLOWER_SHARE = 0.28        # of those, how many are flowers (rest stones)
# Broken/overgrown path remnants: fuller cobble near towns, scattered cobble mid-way.
PATH_NEAR = [44, 45, 36, 37]      # a path-stub leaving a town
PATH_FAR = [52, 53, 60, 61]       # scattered cobble in grass -> overgrown remnant
TRUNK, CANOPY = 66, 34            # solid trunk (walls) + dense canopy (decor_over)
# Three tree-canopy variants (3x3 crown tiles incl. baked trunk+shadow at the
# bottom row). Used as a blob-autotile: a forest cell picks the crown tile that
# matches which sides are forest, so the mass core is dense (center tile) and the
# edges get the leafy rounded outline tiles -> organic, non-blocky edges + depth.
TREE_CROWNS = [
    [17, 18, 19, 33, 34, 35, 49, 50, 51],
    [21, 22, 23, 37, 38, 39, 53, 54, 55],
    [25, 26, 27, 41, 42, 43, 57, 58, 59],
]
BUSHES = [83, 85, 87, 91]         # small flora for the sparse forest fringe
# Emergent treetops for the dense interior: a sunlit crown dome (lighter top tile)
# over a shadowed lower-foliage base, per canopy variant. Scattered over the flat
# body mat they read as many layered crowns with depth instead of one green disk.
CROWN_TOP = [18, 22, 26]          # rounded sunlit dome  (variant 0/1/2)
CROWN_BASE = [50, 54, 58]         # shadowed lower foliage that grounds the dome
TREETOP_DENSITY = 0.22            # share of deep-interior cells that raise a dome


def crown_tile(x, y, forest):
    """Pick a crown tile for forest cell (x,y) by which orthogonal neighbours are
    also forest (marching-tiles), with a coherent per-region variant."""
    grp = TREE_CROWNS[int(_hash01(x // 3, y // 3) * 3) % 3]
    row = 0 if (x, y - 1) not in forest else (2 if (x, y + 1) not in forest else 1)
    col = 0 if (x - 1, y) not in forest else (2 if (x + 1, y) not in forest else 1)
    return grp[row * 3 + col]


def _deep_interior(x, y, forest):
    """True when (x,y) and all 8 neighbours are forest -> a flat body cell, safe to
    overlay a dome without eating the leafy marching edges or the south trunk front."""
    return all((x + dx, y + dy) in forest
               for dx in (-1, 0, 1) for dy in (-1, 0, 1))


def _crown_variant(x, y):
    """The canopy variant crown_tile() uses at (x,y) — coherent in ~3x3 blocks so the
    depth tiles share the same palette as the surrounding body."""
    return int(_hash01(x // 3, y // 3) * 3) % 3


def scatter_treetops(inner, forest, decor):
    """Give the dense interior vertical depth so the mass reads as many layered crowns,
    not a flat mat. Two decor-only passes over inner FORESTS only (the edge band stays
    a clean solid wall); both are pure _hash01/_vnoise fields, so walls/collision and
    the seeded RNG stream (paths/water/forest) are untouched.

    1) Sun/shade DAPPLE: a coherent value-noise field (offset off the zone field)
       relights deep-interior body cells -> sunlit domes on the highs, shaded foliage
       in the hollows, body in between -> rolling canopy relief.
    2) Emergent TREETOPS: sparser, spaced domes grounded by a shadow base -> distinct
       individual trees standing above the canopy, each with a trunk/shadow front."""
    interior = [(x, y) for (x, y) in inner if _deep_interior(x, y, forest)]
    for (x, y) in interior:                       # pass 1: sun/shade dapple
        v = _crown_variant(x, y)
        n = _vnoise(x * 1.3 + 40.0, y * 1.3 + 15.0)
        base = PLANT[theme_at(x, y)]
        if n < 0.34:
            decor[y][x] = base + CROWN_BASE[v]    # shaded hollow
        elif n > 0.66:
            decor[y][x] = base + CROWN_TOP[v]     # sunlit dome

    anchors = {(x, y) for (x, y) in interior
               if _hash01(x * 1.7 + 3, y * 1.3 + 7) < TREETOP_DENSITY}
    anchors = {(x, y) for (x, y) in anchors       # space them out -> individual trees
               if (x - 1, y) not in anchors and (x, y - 1) not in anchors}
    for (x, y) in anchors:                         # pass 2: emergent treetop + shadow
        v = _crown_variant(x, y)
        decor[y][x] = PLANT[theme_at(x, y)] + CROWN_TOP[v]
        if (x, y + 1) not in anchors and _deep_interior(x, y + 1, forest):
            decor[y + 1][x] = PLANT[theme_at(x, y + 1)] + CROWN_BASE[v]

# Organic forest masses (cx, cy, r) placed BETWEEN towns. Minority terrain you
# weave around; kept off town margins + the two zone-crossing lines.
FORESTS = [(20, 28, 5), (44, 10, 4), (52, 31, 4), (67, 21, 4),
           (40, 50, 5), (8, 50, 3), (33, 14, 3), (58, 40, 3), (30, 6, 3)]


# Gradual core<->heath transition: instead of a hard line at the seam, a band
# (BAND_N..BAND_S) dithers BOTH ground grass and flora between the two themes by a
# share that rises monotonically with y (10% heath at the north edge -> 50% at the
# seam -> 90% at the south edge). Outside the band the theme is pure. The dither is
# a deterministic per-cell hash, so it never perturbs the seeded RNG stream (paths
# / forest blobs / water stay byte-identical). General over any adjacent pair.
BAND_N, BAND_S = 28, 44


def _hash01(x, y):
    v = math.sin(x * 127.1 + y * 311.7) * 43758.5453
    return v - math.floor(v)


NOISE_CELL = 5  # coarse lattice spacing -> patches ~5 tiles wide (coastline feel)


def _vnoise(x, y):
    """Deterministic smooth value noise in [0,1): hashed lattice + smoothstep
    bilinear interpolation. Neighbouring cells get similar values, so a threshold
    of it yields coherent organic patches, not per-cell salt-and-pepper."""
    gx, gy = x / NOISE_CELL, y / NOISE_CELL
    x0, y0 = math.floor(gx), math.floor(gy)
    fx, fy = gx - x0, gy - y0
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)  # smoothstep
    v00, v10 = _hash01(x0, y0), _hash01(x0 + 1, y0)
    v01, v11 = _hash01(x0, y0 + 1), _hash01(x0 + 1, y0 + 1)
    return (v00 * (1 - sx) + v10 * sx) * (1 - sy) + (v01 * (1 - sx) + v11 * sx) * sy


def heath_share(y):
    if y <= BAND_N:
        return 0.0
    if y >= BAND_S:
        return 1.0
    return 0.1 + 0.8 * (y - BAND_N) / (BAND_S - BAND_N)   # 0.1 -> 0.5 (seam) -> 0.9


def theme_at(x, y):
    """Zone theme for a cell. In the band, a coherent value-noise field thresholded
    by the (monotonic) heath share -> the two grasses interfinger as organic
    patches with a moving coastline, never a checkerboard."""
    return "grave_heath" if _vnoise(x, y) < heath_share(y) else "cainos"


def theme_ground(x, y):
    return theme_at(x, y)


def theme_plant(y, x=0):
    return theme_at(x, y)


def read_layer_csv(src, name):
    m = re.search(r'<layer id="\d+" name="%s"[^>]*>\s*<data encoding="csv">\s*(.*?)\s*</data>' % name, src, re.S)
    rows = m.group(1).strip().split("\n")
    return [[int(v) for v in r.rstrip(",").split(",")] for r in rows]


# ===================== EDGE TERRAIN (cliffs) =========================
# Cliff stamps registered as tilesets (firstgid). Footprints precomputed from the
# art (>=25% opaque cell -> solid/walls + visible; wispy fringe -> decor_over) so
# this generator stays pygame-free. gid of a stamp cell = firstgid + ty*cols + tx.
def _rect(cols, ys):
    return [(tx, ty) for ty in ys for tx in range(cols)]

CLIFFS = {
    # long horizontal wall (8x4): solid body rows 1-3
    "horizontal": {"fg": 4779, "cols": 8, "rows": 4,
                   "solid": _rect(8, (1, 2, 3)), "fringe": []},
    # L-corner (6x6): horizontal top + a leg turning down on the right
    "corner": {"fg": 4811, "cols": 6, "rows": 6,
               "solid": _rect(6, (1, 2, 3)) + [(3, 4), (4, 4), (5, 4), (1, 5), (2, 5), (3, 5), (4, 5), (5, 5)],
               "fringe": [(1, 4), (2, 4), (0, 5)]},
    # vertical pillar/wall (4x6): solid body, narrower top row
    "vertical": {"fg": 4847, "cols": 4, "rows": 6,
                 "solid": [(1, 0), (2, 0)] + _rect(4, (1, 2, 3, 4, 5)), "fringe": [(0, 0), (3, 0)]},
}


def place_cliff(name, ox, oy, walls, decor):
    """Stamp a cliff: solid cells block (walls, drawn under the player), wispy
    fringe is decoration only (decor_over). Off-map cells are clipped."""
    c = CLIFFS[name]
    for (tx, ty) in c["solid"]:
        x, y = ox + tx, oy + ty
        if 0 <= x < W and 0 <= y < H:
            walls[y][x] = c["fg"] + ty * c["cols"] + tx
    for (tx, ty) in c["fringe"]:
        x, y = ox + tx, oy + ty
        if 0 <= x < W and 0 <= y < H and walls[y][x] == 0:
            decor[y][x] = c["fg"] + ty * c["cols"] + tx


# ===================== WATER (edge phase v3) =========================
WATER_FG = 4739
WIDX = {"full": 0, "edge_N": 1, "edge_E": 2, "edge_S": 3, "edge_W": 4,
        "out_NW": 5, "out_NE": 6, "out_SE": 7, "out_SW": 8,
        "in_NW": 9, "in_NE": 10, "in_SE": 11, "in_SW": 12, "chan_H": 13, "chan_V": 14}
# Corner pattern (nw,ne,se,sw water?) -> tile. Adjacent tiles share two corners,
# so touching borders match by construction (seamless). Saddles -> full.
CORNER_MAP = {
    (1, 1, 1, 1): "full", (0, 0, 1, 1): "edge_N", (1, 1, 0, 0): "edge_S",
    (1, 0, 0, 1): "edge_E", (0, 1, 1, 0): "edge_W", (0, 0, 1, 0): "out_NW",
    (0, 0, 0, 1): "out_NE", (0, 1, 0, 0): "out_SW", (1, 0, 0, 0): "out_SE",
    (0, 1, 1, 1): "in_NW", (1, 0, 1, 1): "in_NE", (1, 1, 1, 0): "in_SW", (1, 1, 0, 1): "in_SE",
}
BRIDGE_FG = 4755
PLANK_H, PLANK_V = 13, 14            # horizontal / vertical bridge planks
LAKE = (72, 55, 12, 7)               # cx, cy, rx, ry
LANDTUNGA = (73, 51, 2.3, 1.6)       # Barroncami land (not water)
SEAM_CY, SEAM_AMP = 36.0, 1.3
SEAM_FLAT = ((10, 15), (55, 60))     # straighten the seam near its two bridges
CORE_PTS = [(20, 2), (18, 10), (23, 19), (27, 24), (27, 31), (24, 35)]
HEATH_PTS = [(46, 37), (45, 42), (45, 47), (45, 52), (53, 54), (63, 54)]
RIVER_HALF = 1.0
# Bridges as boxes that carve ALL water they cross (full body + soft shores),
# so the deck reaches dry bank to dry bank. The deck is 2-wide (the lane); the
# river is straight under it. (x0,x1,y0,y1 inclusive, plank, flow axis of river).
# flow 'EW' = river runs east-west (seam) -> 2-wide lane in x; 'NS' = river runs
# north-south (inner/edge) -> 2-wide lane in y.
BRIDGES = [
    (12, 13, 33, 38, PLANK_V, "EW"),   # seam west  (core<->heath)
    (57, 58, 33, 38, PLANK_V, "EW"),   # seam east  (core<->heath)
    (24, 29, 27, 28, PLANK_H, "NS"),   # core inner river
    (42, 47, 43, 44, PLANK_H, "NS"),   # heath inner river (W<->E heath)
    (75, 78, 27, 28, PLANK_H, "NS"),   # right edge river (deep_west gate)
]


def _seg_d(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _poly_d(pts, gx, gy):
    return min(_seg_d(gx, gy, *pts[i], *pts[i + 1]) for i in range(len(pts) - 1))


def _seam_y(gx):
    for a, b in SEAM_FLAT:
        if a <= gx <= b:
            return SEAM_CY
    return SEAM_CY + SEAM_AMP * math.sin(gx / 5.0)


def _in_landtunga(gx, gy):
    # ellipse + a short north neck so Barroncami connects to the east-heath shore.
    if ((gx - LANDTUNGA[0]) / LANDTUNGA[2]) ** 2 + ((gy - LANDTUNGA[1]) / LANDTUNGA[3]) ** 2 <= 1.0:
        return True
    return 72 <= gx <= 74 and 46 <= gy <= 53


def water_corner(gx, gy):
    if _in_landtunga(gx, gy):
        return False
    # lake
    if ((gx - LAKE[0]) / LAKE[2]) ** 2 + ((gy - LAKE[1]) / LAKE[3]) ** 2 <= 1.0:
        return True
    # seam flood (straightened near the two bridges)
    if 1 <= gx <= 78 and abs(gy - _seam_y(gx)) <= RIVER_HALF:
        return True
    # core + heath inner rivers
    if _poly_d(CORE_PTS, gx, gy) <= RIVER_HALF:
        return True
    if _poly_d(HEATH_PTS, gx, gy) <= RIVER_HALF:
        return True
    # right edge river (gentle meander around x=77), down into the lake. Capped at
    # gx<=78 so the deep_west gate column (x=79) stays dry + reachable via its bridge.
    if 2 <= gy <= 49 and gx <= 78 and abs(gx - (77.0 + 0.6 * math.sin(gy / 4.0))) <= 1.0:
        return True
    return False


def build_water(ground, walls, decor):
    """Autotile the water field into walls (visible + collision), carve bridges
    into ground (walkable). Returns (placed water cells, lake cells)."""
    cw = [[water_corner(gx, gy) for gx in range(W + 1)] for gy in range(H + 1)]
    placed = {}
    for y in range(H):
        for x in range(W):
            pat = (int(cw[y][x]), int(cw[y][x + 1]), int(cw[y + 1][x + 1]), int(cw[y + 1][x]))
            if sum(pat) == 0:
                continue
            placed[(x, y)] = CORNER_MAP.get(pat, "full")  # saddle -> full water
    # bridge cells = every water cell inside a bridge box (carve the whole crossing)
    bridge_cells = set()
    for x0, x1, y0, y1, plank, _flow in BRIDGES:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if (x, y) in placed:
                    bridge_cells.add((x, y))
    for (x, y), name in placed.items():
        if (x, y) in bridge_cells:
            continue
        walls[y][x] = WATER_FG + WIDX[name]   # water: visible under player + blocks
        decor[y][x] = 0                       # no canopy floating on water
    for x0, x1, y0, y1, plank, _flow in BRIDGES:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if (x, y) in placed:
                    decor[y][x] = BRIDGE_FG + plank  # over grass, under player
                    walls[y][x] = 0                  # walkable (no collision)
    # the right edge river IS the east boundary where it runs -> drop the wall ring
    for y in range(2, 50):
        if walls[y][W - 1] == BORDER_GID:
            walls[y][W - 1] = 0
    lake = {(x, y) for (x, y) in placed
            if ((x - LAKE[0]) / LAKE[2]) ** 2 + ((y - LAKE[1]) / LAKE[3]) ** 2 <= 1.0}
    return placed, bridge_cells, lake


def assert_water_invariants(placed, bridge_cells, lake, gates):
    # 1) every water cell connects to the lake (no dead river ends)
    water = set(placed)
    seen = set(lake)
    dq = collections.deque(lake)
    while dq:
        x, y = dq.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) in water and (nx, ny) not in seen:
                seen.add((nx, ny))
                dq.append((nx, ny))
    orphan = water - seen
    assert not orphan, f"water not connected to lake: {sorted(orphan)[:8]} ({len(orphan)})"
    # 2) bridges: 2-wide deck on a straight segment, river continues both ends,
    #    dry land on both banks (no bend under bridge).
    for x0, x1, y0, y1, plank, flow in BRIDGES:
        if flow == "EW":       # river east-west; deck 2-wide in x; banks N/S
            assert x1 == x0 + 1, f"seam bridge deck not 2-wide: {(x0, x1)}"
            # river continues straight west and east of the deck at the full rows
            wet_rows = [y for y in range(y0, y1 + 1) if (x0, y) in water]
            assert wet_rows, f"seam bridge {x0} has no water"
            for ry in wet_rows:
                assert (x0 - 1, ry) in water and (x1 + 1, ry) in water, \
                    f"seam bridge x={x0} not on straight channel at y={ry}"
        else:                  # river north-south; deck 2-wide in y; banks W/E
            assert y1 == y0 + 1, f"bridge deck not 2-wide: {(y0, y1)}"
            wet_cols = [x for x in range(x0, x1 + 1) if (x, y0) in water]
            assert wet_cols, f"bridge rows {y0}-{y1} cross no water"
            for rx in wet_cols:
                assert (rx, y0 - 1) in water and (rx, y1 + 1) in water, \
                    f"bridge y={y0} not on straight channel at x={rx}"
    # 3) gates not drowned
    for g in gates:
        assert g not in water, f"gate drowned: {g}"


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
    # Keep the bridge bank->town corridors forest-free (forests yield to them just
    # as they yield to towns/paths). Each line stays within ONE river-bounded
    # region so it never needs an extra crossing -> all towns reach a bridge bank.
    for (bx, by), pid in [((23, 27), "burg_117"), ((30, 27), "burg_5"),
                          ((12, 32), "burg_117"), ((12, 39), "burg_54"),
                          ((57, 32), "burg_67"), ((57, 39), "burg_293"),
                          ((41, 43), "burg_149"), ((48, 43), "burg_293"),
                          ((74, 27), "burg_320")]:
        protected |= line_cells((bx, by), towns[pid])

    # ---- GROUND: textured open grass (visible detail, not monochrome) ----
    # Dedicated RNG so detail-density tuning never perturbs the (approved) path
    # hints + forest masses, which keep using the module RNG.
    gd = random.Random(81)
    ground = [[0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            base = GRASS[theme_ground(x, y)]
            if gd.random() < DETAIL_DENSITY:
                pool = GROUND_FLOWER if gd.random() < FLOWER_SHARE else GROUND_STONE
                idx = gd.choice(pool)
            else:
                idx = GBASE
            ground[y][x] = base + idx

    # ---- broken PATH HINTS toward neighbour towns (ground layer, no collision) ----
    # For each world.json connection between two on-map towns, lay sparse cobble
    # along the line: a denser stub leaving each town, tapering to scattered,
    # overgrown remnants (with gaps) in the middle. Reads "a road ran this way",
    # not a paved corridor. Town tiles themselves stay clear.
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
    for a, b in edges:
        (ax, ay), (bx, by) = towns[a], towns[b]
        steps = max(abs(ax - bx), abs(ay - by)) or 1
        for i in range(steps + 1):
            t = i / steps
            x = round(ax + (bx - ax) * t)
            y = round(ay + (by - ay) * t)
            if (x, y) in town_tiles or not (0 < x < W - 1 and 0 < y < H - 1):
                continue
            mid = 2 * min(t, 1 - t)                  # 0 at a town, 1 at the midpoint
            if random.random() < 0.85 - 0.7 * mid:   # dense at ends, sparse + gappy mid
                pool = PATH_NEAR if mid < 0.4 else PATH_FAR
                ground[y][x] = GRASS[theme_ground(x, y)] + random.choice(pool)

    # ---- WALLS: natural edge terrain (cliffs + dense forest) + forest masses ----
    # No hard 1-tile border ring any more — the map edge is already blocked by the
    # bounds check; the boundary is now organic. Cliff stamps round the corners and
    # dense forest bands wall the long edges, with openings at the three gates.
    walls = [[0] * W for _ in range(H)]
    decor = [[0] * W for _ in range(H)]

    # Cliff corner accents (discrete stamps, not a tiling set): L-corner top-left,
    # a long wall above Estables (top-right), a pillar bottom-left. Bottom-right is
    # the lake. Placed first so the forest bands flow around them.
    place_cliff("corner", 0, 0, walls, decor)
    place_cliff("horizontal", 66, 0, walls, decor)
    place_cliff("vertical", 0, 49, walls, decor)

    # CONTINUOUS dense forest edge band (2 cells deep) along the full long edges, so
    # the cliffs are embedded in it (no grass gap) and every corner is sealed: the
    # band wraps to the right edge across the top (rounding the open top-right to the
    # edge-river), down the whole left edge, and along the bottom up to the lake.
    # Right edge = the edge-river. Clear openings only at the two land gates.
    GATE_OPEN = {(26, 0): range(23, 30), (24, 55): range(21, 28)}
    band = set()
    for x in range(0, 80):                        # top edge -> the full width (both corners)
        if x not in GATE_OPEN[(26, 0)]:
            band |= {(x, 0), (x, 1)}
    for y in range(0, 56):                         # left edge -> full height (corner to corner)
        band |= {(0, y), (1, y)}
    for x in range(0, 60):                          # bottom edge -> up to the lake (x>=60)
        if x not in GATE_OPEN[(24, 55)]:
            band |= {(x, 54), (x, 55)}

    # Inner forest MASSES (organic blobs you weave around) are kept as a distinct set
    # from the edge BAND (the clean solid map-edge wall). Only the masses get the
    # emergent-treetop depth pass; the band stays a flat solid wall so a future slice
    # can't accidentally open the map edge by reshaping forest decor.
    inner_forest = set()
    for cx, cy, r in FORESTS:
        for y in range(max(1, cy - r - 1), min(H - 1, cy + r + 2)):
            for x in range(max(1, cx - r - 1), min(W - 1, cx + r + 2)):
                if (x - cx) ** 2 + (y - cy) ** 2 <= (r + random.uniform(-1.2, 0.4)) ** 2:
                    if (x, y) not in protected:
                        inner_forest.add((x, y))
    band_cells = {c for c in band if c not in protected}
    forest_cells = inner_forest | band_cells
    # Collision footprint is the blob (unchanged -> reachability identical); the
    # crown is recomposed as a marching-tile blob so edges are leafy/organic, the
    # core dense, with per-zone flora dithered through the transition band.
    for (x, y) in forest_cells:
        if walls[y][x] != 0:       # don't overwrite a cliff stamp
            continue
        base = PLANT[theme_at(x, y)]
        walls[y][x] = base + CANOPY                      # dense green: collision + fill (hidden under crown; no grey trunk poking through wispy edges)
        decor[y][x] = base + crown_tile(x, y, forest_cells)  # leafy crown over the player (south edge shows trunk+shadow)
    # Depth pass: emergent crown domes over the dense interior of the MASSES only.
    scatter_treetops(inner_forest, forest_cells, decor)
    # Sparse bush fringe just outside the blob: visual overhang, non-blocking, so
    # the mass fades into grass instead of ending on a hard edge.
    fringe = {(x + dx, y + dy) for (x, y) in forest_cells for dx in (-1, 0, 1) for dy in (-1, 0, 1)
              if (x + dx, y + dy) not in forest_cells}
    for (x, y) in fringe:
        if not (0 <= x < W and 0 <= y < H) or (x, y) in protected:
            continue
        if walls[y][x] == 0 and decor[y][x] == 0 and _hash01(x, y) < 0.35:
            base = PLANT[theme_at(x, y)]
            decor[y][x] = base + BUSHES[int(_hash01(y, x) * len(BUSHES))]

    # ---- WATER (edge phase v3): rivers + lake + bridges ----
    placed, bridge_cells, lake = build_water(ground, walls, decor)
    assert_water_invariants(placed, bridge_cells, lake, gates)

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
        # Consume surrounding whitespace OUTSIDE the capture groups so the data
        # block is rewritten to a fixed shape every run (idempotent — no blank
        # line creeps in before </data> on re-runs).
        src = re.sub(r'(<layer id="%s" name="%s"[^>]*>\s*<data encoding="csv">)\s*.*?\s*(</data>)' % (lid, name),
                     lambda m: m.group(1) + "\n" + csv(grid) + "\n  " + m.group(2), src, count=1, flags=re.S)

    open(TMX, "w", encoding="utf-8").write(src)
    print(f"OK 80x56: {len(town_tiles)} towns + {len(gates)} gates reachable; "
          f"{len(forest_cells)} forest-mass trunks; walkable ~"
          f"{100*(1 - len(blocked)/(W*H)):.1f}% (incl. border)")


if __name__ == "__main__":
    main()
