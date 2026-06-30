#!/usr/bin/env python3
"""RENDER-ONLY corridor proposal for the overworld rework (STEG 1).

Reads NOTHING from the TMX and WRITES NOTHING to it. Pure mockup:
computes an L-path corridor net from the real town tile coords + the
world.json graph edges, overlays proposed rivers / bridges / open
wilderness pockets / encounter-grass tufts, and emits an annotated
48x32 HTML grid to scratchpad/corridor_proposal.html.

Town coords + edges are transcribed from core_zone.json / world.json
(verified by STEG 0). This is a layout proposal, not a generator.
"""

W, H = 48, 32
CORE_H = 20  # rows 0-19 core, 20-31 heath

# --- Town tiles (place_id -> (x,y)) from core_zone.json ---------------
CORE_TOWNS = {
    "burg_5":   (14, 10),  # Hordanita (hub, respawn)
    "burg_117": (6, 6),    # Yeblegali
    "burg_160": (21, 14),  # Gaste (W-E road junction)
    "burg_235": (30, 12),  # Jinosa
    "burg_379": (34, 6),   # Condillosca
    "burg_146": (39, 10),  # Rotequero (store)
    "burg_67":  (38, 16),  # Fongorinos (store)
    "burg_200": (44, 6),   # Estables (camp)
    "burg_219": (45, 13),  # Tierva (camp)
    "burg_320": (42, 17),  # Parguillas (camp, respawn, mire)
}
HEATH_TOWNS = {
    "burg_54":  (8, 24),   # Guaredama
    "burg_121": (14, 26),  # Alherralba (heath capital, store)
    "burg_385": (10, 29),  # Cantida
    "burg_149": (20, 28),  # Salles
    "burg_293": (28, 24),  # Urrequena (heath hub)
    "burg_105": (40, 27),  # Chuequeroma
    "burg_53":  (44, 30),  # Barroncami
}
TOWNS = {**CORE_TOWNS, **HEATH_TOWNS}
NAMES = {
    "burg_5": "Hordanita", "burg_117": "Yeblegali", "burg_160": "Gaste",
    "burg_235": "Jinosa", "burg_379": "Condillosca", "burg_146": "Rotequero",
    "burg_67": "Fongorinos", "burg_200": "Estables", "burg_219": "Tierva",
    "burg_320": "Parguillas", "burg_54": "Guaredama", "burg_121": "Alherralba",
    "burg_385": "Cantida", "burg_149": "Salles", "burg_293": "Urrequena",
    "burg_105": "Chuequeroma", "burg_53": "Barroncami",
}

# --- Graph edges realized as routes (only placed endpoints) -----------
# (a, b, kind): kind drives styling. road = main, trail = side.
EDGES = [
    ("burg_5", "burg_117", "road"),
    ("burg_5", "burg_160", "road"),
    ("burg_160", "burg_235", "road"),
    ("burg_235", "burg_379", "trail"),
    ("burg_379", "burg_146", "trail"),
    ("burg_146", "burg_200", "trail"),
    ("burg_146", "burg_67", "trail"),   # near-neighbours, realize as short trail
    ("burg_67", "burg_320", "trail"),
    ("burg_320", "burg_219", "trail"),
    ("burg_149", "burg_67", "trail"),   # heath <-> core EAST crossing
    # heath
    ("burg_121", "burg_54", "trail"),
    ("burg_121", "burg_385", "trail"),
    ("burg_121", "burg_149", "trail"),
    ("burg_293", "burg_385", "trail"),
    ("burg_293", "burg_105", "trail"),
    ("burg_105", "burg_53", "trail"),
    ("burg_117", "burg_54", "trail"),   # heath <-> core WEST crossing (spine)
]

# --- Proposed rivers (STRAIGHT only; corners avoided) -----------------
# Vertical river fencing the cursed_mire (east) off; bridge lets the
# burg_67<->burg_320 trail cross. River occupies a column band.
RIVER_CELLS = set()
BRIDGE_CELLS = set()


def add_v_river(x, y0, y1, bridges):
    for y in range(y0, y1 + 1):
        if y in bridges:
            BRIDGE_CELLS.add((x, y))
        else:
            RIVER_CELLS.add((x, y))


def add_h_river(y, x0, x1, bridges):
    for x in range(x0, x1 + 1):
        if x in bridges:
            BRIDGE_CELLS.add((x, y))
        else:
            RIVER_CELLS.add((x, y))


# Mire moat: vertical river at x=41 (cursed_mire starts x>=41), rows 8-19,
# bridge at y=17 so the burg_67 -> burg_320 trail crosses into the mire.
add_v_river(41, 8, 19, bridges={17})
# Core/heath frontier river along y=19 on the WEST half, bridge at x=8
# (the burg_117 -> burg_54 spine) so the only clean south crossing is gated
# by terrain. East half left open (burg_149<->burg_67 uses its own path).
add_h_river(19, 4, 16, bridges={8})


# --- L-path corridor carving (Manhattan, horiz then vert) -------------
def l_path(a, b):
    (ax, ay), (bx, by) = a, b
    cells = set()
    for x in range(min(ax, bx), max(ax, bx) + 1):
        cells.add((x, ay))
    for y in range(min(ay, by), max(ay, by) + 1):
        cells.add((bx, y))
    return cells


corridor = set()
for a, b, kind in EDGES:
    corridor |= l_path(TOWNS[a], TOWNS[b])

# Bridges must stay walkable even if a river cell overlaps a corridor.
corridor |= BRIDGE_CELLS

# --- Town halos (kept open, no walls) ---------------------------------
halo = set()
for (x, y) in TOWNS.values():
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < H:
                halo.add((nx, ny))

# --- Open wilderness pockets (RuneScape halves: roam freely) ----------
# Rectangular pockets deliberately NOT walled and NOT corridor: explorable.
POCKETS = [
    # (x0, y0, x1, y1, label)
    (24, 2, 33, 9, "N forest glade"),
    (2, 12, 12, 18, "W meadow"),
    (32, 20, 39, 26, "SE heath moor"),
    (16, 21, 24, 25, "central heath flat"),
]
pocket_cells = set()
for (x0, y0, x1, y1, _lbl) in POCKETS:
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            pocket_cells.add((x, y))

# --- Encounter-grass tufts (Kanto): edge of corridors / pocket mouths -
# Illustrative tuft anchors where wild fights would live.
GRASS = [
    (10, 10), (18, 14), (26, 12), (33, 9), (36, 13),  # core route shoulders
    (6, 22), (12, 23), (24, 26), (31, 25), (38, 28),   # heath route shoulders
    (29, 6), (8, 15),                                   # pocket mouths
]
grass_cells = set(GRASS)

# --- Gate tiles -------------------------------------------------------
GATES = {(14, 0): "N", (47, 10): "W", (13, 31): "S"}


def classify(x, y):
    if (x, y) in GATES:
        return "gate"
    if (x, y) in TOWNS.values():
        return "town"
    if (x, y) in BRIDGE_CELLS:
        return "bridge"
    if (x, y) in RIVER_CELLS:
        return "river"
    if (x, y) in grass_cells:
        return "grass"
    if (x, y) in corridor:
        return "corridor"
    if (x, y) in halo:
        return "halo"
    if (x, y) in pocket_cells:
        return "pocket"
    return "wall"  # everything else = proposed WALL (treed/blocked)


COLORS = {
    "town": ("#ffd54a", "T"), "gate": ("#ff5d5d", "G"),
    "bridge": ("#b5651d", "="), "river": ("#2a6fb0", "~"),
    "grass": ("#7ec850", "\""), "corridor": ("#d9c9a3", "."),
    "halo": ("#efe7cf", " "), "pocket": ("#3f7d4f", " "),
    "wall": ("#243024", " "),
}

place_at = {v: k for k, v in TOWNS.items()}

cells_html = []
for y in range(H):
    for x in range(W):
        kind = classify(x, y)
        color, glyph = COLORS[kind]
        title = f"({x},{y}) {kind}"
        label = ""
        if (x, y) in place_at:
            pid = place_at[(x, y)]
            title = f"({x},{y}) {NAMES.get(pid, pid)} [{pid}]"
            label = "T"
        elif kind == "gate":
            label = "G"
        elif kind == "bridge":
            label = "="
        zone = "heath" if y >= CORE_H else "core"
        cells_html.append(
            f'<div class="c {kind}" style="grid-column:{x+1};grid-row:{y+1};'
            f'background:{color}" title="{title} [{zone}]">{label}</div>'
        )

legend_items = [
    ("town", "Stad (town-tile, oförändrad)"),
    ("gate", "Gate / chokepoint (data, flyttas utåt)"),
    ("corridor", "Route ur grafen (L-path, gångbar)"),
    ("bridge", "Bro (gångbar passage över flod)"),
    ("river", "Rak flod (vägg, terräng som styr)"),
    ("grass", "Encounter-gräs (Kanto: fienderna bor här)"),
    ("pocket", "Öppen vildmarks-ficka (RuneScape: fri roam)"),
    ("halo", "Stadshalo (hålls öppen)"),
    ("wall", "Föreslagen vägg (träd/hinder, murar resten)"),
]
legend_html = "".join(
    f'<div class="li"><span class="sw" style="background:{COLORS[k][0]}"></span>{txt}</div>'
    for k, txt in legend_items
)

html = f"""<div class="wrap">
<h1>Korridor-proposal &mdash; overworld (48&times;32)</h1>
<p class="sub">RENDERAD MOCKUP. Ingen karta &auml;ndrad. Routes = L-paths ur world.json-grafen mellan
de 17 placerade st&auml;derna. Floder = raka v&auml;ggar, broar = passage. Gr&ouml;na f&auml;lt = &ouml;ppna
vildmarks-fickor (fri roam). Ljusgr&ouml;na tussar = encounter-gr&auml;s. R&ouml;d linje y=19/20 = k&auml;rna/hed-s&ouml;m.</p>
<div class="grid">{''.join(cells_html)}
<div class="seam" style="grid-row:{CORE_H+1};grid-column:1 / {W+1}"></div>
</div>
<div class="legend">{legend_html}</div>
</div>
<style>
.wrap{{font-family:-apple-system,system-ui,sans-serif;color:#e8e8e8;background:#1a1a1a;padding:18px;max-width:100%}}
h1{{font-size:20px;margin:0 0 4px}}
.sub{{font-size:12px;color:#aaa;margin:0 0 14px;max-width:900px;line-height:1.5}}
.grid{{display:grid;grid-template-columns:repeat({W},16px);grid-template-rows:repeat({H},16px);
gap:1px;background:#000;padding:6px;border-radius:6px;width:max-content;position:relative;overflow-x:auto}}
.c{{width:16px;height:16px;font-size:9px;line-height:16px;text-align:center;color:#222;font-weight:700}}
.town{{outline:2px solid #fff;z-index:3}}
.gate,.bridge{{color:#fff}}
.seam{{border-top:2px dashed #ff5d5d;align-self:start;pointer-events:none}}
.legend{{display:flex;flex-wrap:wrap;gap:10px 22px;margin-top:16px;max-width:900px}}
.li{{font-size:12px;display:flex;align-items:center;gap:7px}}
.sw{{width:15px;height:15px;border-radius:3px;display:inline-block;border:1px solid #000}}
</style>"""

import os
out = os.path.join(os.path.dirname(__file__), "corridor_proposal.html")
with open(out, "w") as f:
    f.write(html)

# Console summary
print(f"corridor cells: {len(corridor)}")
print(f"river cells: {len(RIVER_CELLS)}  bridges: {len(BRIDGE_CELLS)}")
print(f"pocket cells: {len(pocket_cells)}  grass tufts: {len(grass_cells)}")
walls = sum(1 for y in range(H) for x in range(W) if classify(x, y) == "wall")
print(f"proposed wall cells: {walls}")
print(f"wrote {out}")
