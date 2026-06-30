#!/usr/bin/env python3
"""overworld_layout.py — #3 world expansion, option A (parametric terrain).

Derives the 240x208 overworld layout from a few parameters instead of the old
80x56 hand-pinned geometry: zone bands, an organic derived coastline, a derived
seam channel, the ONE hand-specified north-born river -> central heath lake, and
bridges DERIVED by reachability (carved on the shortest water crossing wherever a
region would otherwise be cut off). Deterministic.

This module only computes the layout grid + metadata and can render a schematic
PNG for review. It writes NO TMX — the TMX/core_zone regeneration is a separate
step taken only AFTER the render is approved (the LAYOUT-FORK halt).
"""
from __future__ import annotations

import collections
import heapq
import json
import math
import os

_DATA = os.path.join(os.path.dirname(__file__), "rpg_game/data")
WORLD_JSON = os.path.join(_DATA, "world.json")
ZONE_JSON = os.path.join(_DATA, "maps/core_zone.json")

W, H = 240, 208
SEAM_Y = 100                      # grave_heath begins here (overrides x-bands)
SEAM_AMP = 2.0                    # gentle wobble of the seam line
# North x-bands (y < seam): cainos | mork_skog | cursed_mire
BAND_CAINOS_MAX = 82
BAND_MORK_MAX = 158


def _load_zone():
    """Towns/gates/start are read from core_zone.json — the single source of truth
    (this module is both the proposal tool and the TMX geometry source)."""
    z = json.load(open(ZONE_JSON, encoding="utf-8"))
    towns = {t["place_id"]: (t["tile"][0], t["tile"][1], t["label"]) for t in z["towns"]}
    gates = {g["message_key"]: (g["tile"][0], g["tile"][1]) for g in z["gates"]}
    start = z["respawn_place_id"]
    return towns, gates, start


TOWNS, GATES, START_ID = _load_zone()
# Intended N<->S walk-routes that world.json doesn't list as menu connections but
# which the walk-map should still bridge, so the south-east isn't a long westerly
# detour (Lucas-approved eastern crossings). Used only for bridge derivation; the
# world.json menu data is left untouched.
EXTRA_ROUTES = {("burg_320", "burg_105"), ("burg_219", "burg_53")}

# Towns whose B8 procedural cluster must fit (need ~12x10 clear land).
CLUSTER_TOWN_IDS = ("burg_5", "burg_67")
# Cluster extent relative to the anchor (from town_cluster.CLUSTER_TEMPLATE).
CLUSTER_DX = (-3, 10)
CLUSTER_DY = (-6, 5)

# ---- the ONE hand-specified inner river: born at the seam south of Fongorinos
# (x~136), winding south to a central heath lake at ~(135,164).
RIVER_PTS = [(136, 100), (139, 111), (132, 122), (138, 133),
             (132, 144), (136, 154), (135, 161)]
RIVER_HALF = 1.1
LAKE = (135, 164, 11, 6)          # cx, cy, rx, ry

# ---- derived coastline (organic, framing the map) ----
SEA_BASE = 4.0
SEA_EDGE = {"N": (0.0, 11.0), "S": (2.3, 23.0), "W": (4.1, 37.0), "E": (1.2, 53.0)}
GATE_DRY_R = 7.0                  # dry mouth radius around a gate
TOWN_DRY_R = 5.0                  # keep a town off the coast

# Autotile: a CELL's tile is chosen from which of its 4 CORNERS are water. Adjacent
# cells share two corners, so borders match by construction (seamless). Shared with
# the TMX generator so reachability/bridges and the rendered water are the SAME field.
WIDX = {"full": 0, "edge_N": 1, "edge_E": 2, "edge_S": 3, "edge_W": 4,
        "out_NW": 5, "out_NE": 6, "out_SE": 7, "out_SW": 8,
        "in_NW": 9, "in_NE": 10, "in_SE": 11, "in_SW": 12, "chan_H": 13, "chan_V": 14}
CORNER_MAP = {
    (1, 1, 1, 1): "full", (0, 0, 1, 1): "edge_N", (1, 1, 0, 0): "edge_S",
    (1, 0, 0, 1): "edge_E", (0, 1, 1, 0): "edge_W", (0, 0, 1, 0): "out_NW",
    (0, 0, 0, 1): "out_NE", (0, 1, 0, 0): "out_SW", (1, 0, 0, 0): "out_SE",
    (0, 1, 1, 1): "in_NW", (1, 0, 1, 1): "in_NE", (1, 1, 1, 0): "in_SW", (1, 1, 0, 1): "in_SE",
}


def _hash01(x, y):
    v = math.sin(x * 127.1 + y * 311.7) * 43758.5453
    return v - math.floor(v)


def seam_y(x):
    return SEAM_Y + SEAM_AMP * math.sin(x / 23.0)


def zone_at(x, y):
    """Ground theme for a land cell (no water)."""
    if y >= seam_y(x):
        return "grave_heath"
    if x <= BAND_CAINOS_MAX:
        return "cainos"
    if x <= BAND_MORK_MAX:
        return "mork_skog"
    return "cursed_mire"


def _sea_depth(t, edge):
    ph, salt = SEA_EDGE[edge]
    return (SEA_BASE + 2.4 * math.sin(t / 7.0 + ph) + 1.2 * math.sin(t / 3.1 + ph * 1.7)
            + (_hash01(t * 1.7, salt) - 0.5) * 2.4)


def _nearest_edge(gx, gy):
    dN, dS, dW, dE = gy, H - gy, gx, W - gx
    m = min(dN, dS, dW, dE)
    if m == dN:
        return m, gx, "N"
    if m == dS:
        return m, gx, "S"
    if m == dW:
        return m, gy, "W"
    return m, gy, "E"


def _sea(gx, gy, dry):
    m, t, edge = _nearest_edge(gx, gy)
    depth = _sea_depth(t, edge)
    for (ax, ay, rad) in dry:
        depth = min(depth, math.hypot(gx - ax, gy - ay) - rad)
    return m < depth


def _seg_d(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _river_d(gx, gy):
    return min(_seg_d(gx, gy, *RIVER_PTS[i], *RIVER_PTS[i + 1])
               for i in range(len(RIVER_PTS) - 1))


def water_at(gx, gy, dry):
    """True if this cell is water (sea | seam channel | river | lake)."""
    # sealed border: the outermost ring is always sea (so the player can't walk off
    # the map) EXCEPT a gate's dry mouth, which keeps an opening to the edge.
    if gx <= 0 or gx >= W or gy <= 0 or gy >= H:
        if not any(math.hypot(gx - ax, gy - ay) < rad for (ax, ay, rad) in dry
                   if rad == GATE_DRY_R):
            return True
    # lake
    if ((gx - LAKE[0]) / LAKE[2]) ** 2 + ((gy - LAKE[1]) / LAKE[3]) ** 2 <= 1.0:
        return True
    # river
    if _river_d(gx, gy) <= RIVER_HALF:
        return True
    # seam channel (thin), pulled dry around towns so none is split on its doorstep
    if 1 <= gx <= W - 2 and abs(gy - seam_y(gx)) <= RIVER_HALF:
        if not any(math.hypot(gx - ax, gy - ay) < TOWN_DRY_R for ax, ay, _r in dry
                   if _r == TOWN_DRY_R):
            return True
    # sea frame
    if _sea(gx, gy, dry):
        return True
    return False


def snap_town(x, y, water, taken, min_gap=6):
    """Nudge a town off water and away from other towns (spiral search)."""
    def ok(cx, cy):
        return (0 < cx < W - 1 and 0 < cy < H - 1 and (cx, cy) not in water
                and all(abs(cx - tx) + abs(cy - ty) >= min_gap for tx, ty in taken))
    if ok(x, y):
        return x, y
    for r in range(1, 30):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                if ok(x + dx, y + dy):
                    return x + dx, y + dy
    return x, y  # give up (reported by verify)


def water_field(dry):
    """Corner-sampled water -> per-cell autotile. Returns (corner_wet grid,
    cell_water set, cell_name dict). A cell is water if ANY of its 4 corners is
    wet; its tile name comes from CORNER_MAP (saddles -> full). This is the single
    field both reachability/bridges and the TMX autotile read."""
    cw = [[water_at(gx, gy, dry) for gx in range(W + 1)] for gy in range(H + 1)]
    cell_water, cell_name = set(), {}
    for y in range(H):
        for x in range(W):
            pat = (int(cw[y][x]), int(cw[y][x + 1]), int(cw[y + 1][x + 1]), int(cw[y + 1][x]))
            if sum(pat) == 0:
                continue
            cell_water.add((x, y))
            cell_name[(x, y)] = CORNER_MAP.get(pat, "full")
    return cw, cell_water, cell_name


def _one_water_body(water, cell_name):
    """Drop isolated interior water puddles. Seed the flood from the lake AND the
    sealed border sea — gate dry mouths legitimately split the coastal ring into
    arcs, so border arcs are kept; only free-floating interior puddles are removed."""
    cx, cy, rx, ry = LAKE
    seed = {(x, y) for (x, y) in water if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0}
    seed |= {(x, y) for (x, y) in water if x == 0 or x == W - 1 or y == 0 or y == H - 1}
    seen = set(seed)
    dq = collections.deque(seed)
    while dq:
        x, y = dq.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) in water and (nx, ny) not in seen:
                seen.add((nx, ny))
                dq.append((nx, ny))
    return seen, {c: cell_name[c] for c in seen}


def build_layout():
    """Derive the full layout. Returns a dict with the per-cell grids + metadata."""
    dry = [(x, y, GATE_DRY_R) for (x, y) in GATES.values()]
    dry += [(x, y, TOWN_DRY_R) for (x, y, _l) in TOWNS.values()]

    corner_wet, water, cell_name = water_field(dry)
    # drop orphan water puddles so all water is ONE body (flood from the lake; any
    # water cell not reached is an isolated coast nibble -> treat it as land).
    water, cell_name = _one_water_body(water, cell_name)

    # snap towns off water / apart, preserving order (start first so it anchors)
    towns, taken = {}, []
    order = [START_ID] + [p for p in TOWNS if p != START_ID]
    for pid in order:
        x, y, label = TOWNS[pid]
        sx, sy = snap_town(x, y, water, taken)
        towns[pid] = (sx, sy, label)
        taken.append((sx, sy))

    gates = dict(GATES)
    start = towns[START_ID][:2]

    # derived bridges, two passes:
    #  1) ROUTE bridges — carve the water a town<->town connection actually crosses
    #     (bridges sit on real inter-town routes, spread across the map), and
    #  2) REACHABILITY fallback — if anything is still cut off, carve the shortest
    #     water crossing to the start's component (0-1 Dijkstra). Guarantees a
    #     never-broken map without relying on a single chokepoint.
    bridges = _route_bridges(water, towns)
    targets = [t[:2] for t in towns.values()] + list(gates.values())
    bridges |= _ensure_reachable(water, start, targets, seed_bridges=bridges)

    return {"W": W, "H": H, "water": water, "cell_name": cell_name,
            "corner_wet": corner_wet, "bridges": bridges,
            "towns": towns, "gates": gates, "start": start, "dry": dry,
            "zone_at": zone_at}


def _town_connections():
    """Undirected town<->town pairs from world.json (by place_id)."""
    world = json.load(open(WORLD_JSON, encoding="utf-8"))
    seen = set()
    for p in world["places"]:
        if p["id"] not in TOWNS:
            continue
        for c in p.get("connections", []):
            if c["to"] in TOWNS:
                seen.add(tuple(sorted((p["id"], c["to"]))))
    seen |= EXTRA_ROUTES                       # Lucas-approved eastern crossings
    return seen


def _line(a, b):
    (ax, ay), (bx, by) = a, b
    steps = max(abs(ax - bx), abs(ay - by)) or 1
    return [(round(ax + (bx - ax) * i / steps), round(ay + (by - ay) * i / steps))
            for i in range(steps + 1)]


def _route_bridges(water, towns):
    """Carve every water cell a town<->town straight route crosses (plus a 1-cell
    apron) so each crossing is a real, walkable bridge on an actual route."""
    bridges = set()
    for a, b in _town_connections():
        for (x, y) in _line(towns[a][:2], towns[b][:2]):
            if (x, y) in water:
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if (x + dx, y + dy) in water:
                            bridges.add((x + dx, y + dy))
    return bridges


def _land_component(water, bridges, src):
    """All cells reachable from src over non-water (or bridge) cells, 4-connected."""
    passable = lambda c: (0 <= c[0] < W and 0 <= c[1] < H
                          and (c not in water or c in bridges))
    seen = {src}
    dq = collections.deque([src])
    while dq:
        x, y = dq.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (nx, ny) not in seen and passable((nx, ny)):
                seen.add((nx, ny))
                dq.append((nx, ny))
    return seen


def _ensure_reachable(water, start, targets, seed_bridges=frozenset()):
    """Carve minimal bridges so every target shares the start's land component,
    starting from any bridges already carved (route bridges)."""
    bridges = set(seed_bridges)
    comp = _land_component(water, bridges, start)
    for tgt in targets:
        if tgt in comp:
            continue
        path = _min_crossing_path(water, bridges, tgt, comp)
        if path is None:
            continue  # unreachable even by bridging (reported by verify)
        for cell in path:
            if cell in water:
                bridges.add(cell)
        comp = _land_component(water, bridges, start)
    return bridges


def _min_crossing_path(water, bridges, src, goal_set):
    """0-1 Dijkstra from src to any cell in goal_set; edge cost = 1 to step INTO a
    (non-bridge) water cell, else 0. Returns the cell path with fewest water cells."""
    INF = float("inf")
    dist = {src: 0}
    prev = {}
    pq = [(0, src)]
    while pq:
        d, c = heapq.heappop(pq)
        if c in goal_set:
            path = [c]
            while path[-1] in prev:
                path.append(prev[path[-1]])
            return list(reversed(path))
        if d > dist.get(c, INF):
            continue
        x, y = c
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= nx < W and 0 <= ny < H):
                continue
            nc = (nx, ny)
            step = 1 if (nc in water and nc not in bridges) else 0
            nd = d + step
            if nd < dist.get(nc, INF):
                dist[nc] = nd
                prev[nc] = c
                heapq.heappush(pq, (nd, nc))
    return None


# ----------------------------- schematic render -----------------------------
ZONE_COLOR = {
    "cainos": (120, 168, 92), "mork_skog": (58, 104, 70),
    "cursed_mire": (120, 96, 140), "grave_heath": (150, 134, 96),
}
WATER_COLOR = (70, 120, 190)
BRIDGE_COLOR = (150, 110, 70)


def render_png(layout, path, scale=3):
    import pygame
    pygame.init()
    surf = pygame.Surface((W * scale, H * scale))
    water, bridges = layout["water"], layout["bridges"]
    for y in range(H):
        for x in range(W):
            if (x, y) in bridges:
                col = BRIDGE_COLOR
            elif (x, y) in water:
                col = WATER_COLOR
            else:
                col = ZONE_COLOR[zone_at(x, y)]
            surf.fill(col, (x * scale, y * scale, scale, scale))
    # band boundary hints (north only)
    for bx in (BAND_CAINOS_MAX, BAND_MORK_MAX):
        for y in range(0, SEAM_Y):
            surf.fill((255, 255, 255), (bx * scale, y * scale, 1, scale))
    # towns
    for pid, (x, y, _label) in layout["towns"].items():
        hub = pid in CLUSTER_TOWN_IDS
        r = (5 if hub else 3) * scale // 3
        col = (245, 210, 70) if pid == START_ID else ((255, 140, 60) if hub else (220, 60, 60))
        pygame.draw.circle(surf, col, (x * scale + scale // 2, y * scale + scale // 2), max(2, r))
    # gates
    for (x, y) in layout["gates"].values():
        gx = min(max(x, 1), W - 2)
        gy = min(max(y, 1), H - 2)
        pygame.draw.rect(surf, (40, 40, 40),
                         (gx * scale - 2, gy * scale - 2, scale + 4, scale + 4))
    pygame.image.save(surf, path)
    pygame.quit()


def verify(layout):
    """Return a (ok, lines) reachability + placement report."""
    water, bridges = layout["water"], layout["bridges"]
    towns, gates, start = layout["towns"], layout["gates"], layout["start"]
    comp = _land_component(water, bridges, start)
    lines, ok = [], True

    for pid, (x, y, label) in towns.items():
        reach = (x, y) in comp
        inwater = (x, y) in water
        z = zone_at(x, y)
        flag = "" if (reach and not inwater) else "  <-- PROBLEM"
        if not reach or inwater:
            ok = False
        lines.append(f"  {pid:9} ({x:3},{y:3}) {label:12} {z:11} reach={reach} water={inwater}{flag}")
    for key, (x, y) in gates.items():
        gx, gy = min(max(x, 1), W - 2), min(max(y, 1), H - 2)
        reach = (gx, gy) in comp
        if not reach:
            ok = False
        lines.append(f"  {key:20} ({x:3},{y:3}) reach={reach}{'' if reach else '  <-- PROBLEM'}")

    # min town spacing
    pts = [(t[0], t[1]) for t in towns.values()]
    mind = min(abs(a[0] - b[0]) + abs(a[1] - b[1])
               for i, a in enumerate(pts) for b in pts[i + 1:])
    lines.append(f"  min town spacing (manhattan) = {mind}")

    # cluster fit for hub towns
    for pid in CLUSTER_TOWN_IDS:
        ax, ay, _ = towns[pid]
        clear = all((ax + dx, ay + dy) not in water
                    for dx in range(*CLUSTER_DX) for dy in range(*CLUSTER_DY))
        if not clear:
            ok = False
        lines.append(f"  cluster fit {pid} @({ax},{ay}): {'clear' if clear else 'WATER IN FOOTPRINT'}")

    lines.append(f"  bridges carved: {len(bridges)} cells")
    lines.append(f"  water cells: {len(water)}  ({100*len(water)/(W*H):.1f}% of map)")
    return ok, lines


if __name__ == "__main__":
    import time
    t0 = time.time()
    layout = build_layout()
    dt = time.time() - t0
    ok, lines = verify(layout)
    print(f"layout build: {dt*1000:.0f} ms  ({W}x{H} = {W*H} tiles)")
    print("\n".join(lines))
    print("OK" if ok else "*** PROBLEMS ABOVE ***")
    render_png(layout, "/tmp/overworld_layout.png", scale=3)
    print("rendered /tmp/overworld_layout.png")
