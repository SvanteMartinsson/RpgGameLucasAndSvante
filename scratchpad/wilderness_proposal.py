#!/usr/bin/env python3
"""RENDER-ONLY wilderness-first overworld proposal (STEG 1 omtag).

Reads NOTHING from the TMX and WRITES NOTHING. Pure mockup of the NEW
principle: open roamable wilderness is the DEFAULT surface; terrain
(organic forest belts, STRAIGHT rivers + bridges, stone patches) shapes
ORGANIC areas to weave through. No corridors, no rectangles, no
encounter-grass. Towns embedded in wilderness with open margins,
scattered (clusters de-clustered) while preserving graph adjacency and
faction groupings. Emits scratchpad/wilderness_proposal.html.
"""
import math
import os
import random

random.seed(42)  # deterministic mockup

W, H = 80, 56          # proposed size (see report); current is 48x32
SEAM_Y = 36            # core rows 0-35, heath rows 36-55 (passable)

# --- Scattered town positions (proposed) ------------------------------
# Spread out; right-side clusters de-clustered. Adjacency-preserving
# (graph edges remain crossable through open wilderness + bridges).
CORE = {
    "burg_5":   (26, 18),  # Hordanita (hub / respawn)
    "burg_117": (10, 8),   # Yeblegali (NW; Magikerklave approach)
    "burg_160": (38, 22),  # Gaste (central junction)
    "burg_235": (50, 16),  # Jinosa
    "burg_379": (57, 7),   # Condillosca  (was clustered x34-44)
    "burg_146": (66, 12),  # Rotequero    (de-clustered)
    "burg_67":  (60, 26),  # Fongorinos   (de-clustered; links heath)
    "burg_200": (73, 6),   # Estables (NE)
    "burg_219": (74, 17),  # Tierva
    "burg_320": (70, 31),  # Parguillas (SE mire / respawn)
}
HEATH = {
    "burg_54":  (14, 42),  # Guaredama   \
    "burg_121": (24, 47),  # Alherralba   } Bondemilis (west cluster, respawn)
    "burg_385": (17, 51),  # Cantida     /
    "burg_149": (33, 44),  # Salles      / (links core burg_67)
    "burg_293": (50, 43),  # Urrequena   \
    "burg_105": (63, 47),  # Chuequeroma  } Harrow (east cluster, de-clustered)
    "burg_53":  (73, 51),  # Barroncami  /
}
TOWNS = {**CORE, **HEATH}
NAMES = {
    "burg_5": "Hordanita", "burg_117": "Yeblegali", "burg_160": "Gaste",
    "burg_235": "Jinosa", "burg_379": "Condillosca", "burg_146": "Rotequero",
    "burg_67": "Fongorinos", "burg_200": "Estables", "burg_219": "Tierva",
    "burg_320": "Parguillas", "burg_54": "Guaredama", "burg_121": "Alherralba",
    "burg_385": "Cantida", "burg_149": "Salles", "burg_293": "Urrequena",
    "burg_105": "Chuequeroma", "burg_53": "Barroncami",
}
FACTION = {  # heath faction grouping (preserved)
    "burg_54": "Bondemilis", "burg_121": "Bondemilis", "burg_385": "Bondemilis",
    "burg_149": "Bondemilis", "burg_293": "Harrow", "burg_105": "Harrow",
    "burg_53": "Harrow",
}

grid = [["open" for _ in range(W)] for _ in range(H)]


def in_bounds(x, y):
    return 0 <= x < W and 0 <= y < H


# --- Map border = true edge (impassable) ------------------------------
for x in range(W):
    grid[0][x] = grid[H - 1][x] = "wall"
for y in range(H):
    grid[y][0] = grid[y][W - 1] = "wall"


# --- Organic forest blobs (union of jittered circles) -----------------
# Minority obstacle texture you WEAVE AROUND, not corridors. Soft edges.
def blob(cx, cy, r, kind="forest"):
    for y in range(max(1, cy - r - 1), min(H - 1, cy + r + 2)):
        for x in range(max(1, cx - r - 1), min(W - 1, cx + r + 2)):
            d = math.hypot(x - cx, y - cy)
            # jitter the radius per-cell so the edge is organic, not a disc
            if d <= r + random.uniform(-1.1, 0.6):
                grid[y][x] = kind


FORESTS = [  # (cx, cy, r) — placed BETWEEN towns as weave-texture
    (20, 28, 5), (33, 33, 4),        # core south woods
    (44, 9, 4), (52, 27, 4),         # core central/east copses
    (67, 20, 4),                     # eastern wilds
    (40, 50, 5), (57, 39, 4),        # heath moor-woods
    (8, 49, 3),                      # west heath thicket
]
for cx, cy, r in FORESTS:
    blob(cx, cy, r, "forest")

STONES = [(15, 16, 2), (60, 33, 2), (30, 52, 2)]  # small stone patches
for cx, cy, r in STONES:
    blob(cx, cy, r, "stone")


# --- Straight rivers + bridges (only straight; corners avoided) -------
def h_river(y, x0, x1, bridges):
    for x in range(x0, x1 + 1):
        grid[y][x] = "bridge" if x in bridges else "river"


def v_river(x, y0, y1, bridges):
    for y in range(y0, y1 + 1):
        grid[y][x] = "bridge" if y in bridges else "river"


# Core/heath frontier river along the seam (partial width). The two
# zone-crossing edges get bridges so the seam stays PASSABLE:
#   Yeblegali<->Guaredama (west, ~x12) and Salles<->Fongorinos (east, ~x47).
h_river(SEAM_Y, 6, 56, bridges={12, 13, 47, 48})
# SE mire moat: straight vertical river, bridge on the Parguillas approach.
v_river(66, 22, 35, bridges={31})

# --- Town open margins (force open ring around each town) -------------
for (tx, ty) in TOWNS.values():
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            nx, ny = tx + dx, ty + dy
            if in_bounds(nx, ny) and grid[ny][nx] not in ("river",):
                grid[ny][nx] = "open"
    grid[ty][tx] = "town"

# --- Gates (true zone borders; data, moved outward later) -------------
GATES = {(40, 0): "N", (W - 1, 28): "W-deep", (12, H - 1): "S-Verralda"}
for (gx, gy), _ in GATES.items():
    grid[gy][gx] = "gate"

place_at = {v: k for k, v in TOWNS.items()}

COLORS = {
    "open":   "#9bbf6a",  # default roamable wilderness (the majority)
    "forest": "#1f3d24",  # dense forest you weave around
    "stone":  "#6b6f76",
    "river":  "#2a6fb0",
    "bridge": "#b5651d",
    "town":   "#ffd54a",
    "gate":   "#ff5d5d",
    "wall":   "#10160f",  # map edge
}

cells = []
for y in range(H):
    for x in range(W):
        k = grid[y][x]
        label = ""
        title = f"({x},{y}) {k}"
        if (x, y) in place_at:
            pid = place_at[(x, y)]
            fac = FACTION.get(pid, "core")
            title = f"({x},{y}) {NAMES[pid]} [{pid}] - {fac}"
            label = "T"
        elif k == "gate":
            label = "G"
            title = f"({x},{y}) gate {GATES[(x,y)]}"
        elif k == "bridge":
            label = "="
        cells.append(
            f'<div class="c {k}" style="grid-column:{x+1};grid-row:{y+1};'
            f'background:{COLORS[k]}" title="{title}">{label}</div>'
        )

legend = [
    ("open", "Öppen roambar vildmark (DEFAULT-ytan; encounters rullar här)"),
    ("forest", "Tät skog (organisk, väv runt) — minoritet"),
    ("stone", "Stenparti (textur)"),
    ("river", "Rak flod (äkta gräns)"),
    ("bridge", "Bro (gångbar passage över flod)"),
    ("town", "Stad, inbäddad med öppen mark runt (utspridd)"),
    ("gate", "Zon-grind (data, flyttas utåt)"),
    ("wall", "Kartkant"),
]
legend_html = "".join(
    f'<div class="li"><span class="sw" style="background:{COLORS[k]}"></span>{t}</div>'
    for k, t in legend
)

# faction chips
fac_color = {"Bondemilis": "#d98c5f", "Harrow": "#9b6bd9", "core": "#888"}
fchips = "".join(
    f'<span class="fc" style="border-color:{fac_color[f]}">{f}</span>'
    for f in ("Bondemilis", "Harrow")
)

html = f"""<div class="wrap">
<h1>Vildmark-först &mdash; overworld-proposal ({W}&times;{H})</h1>
<p class="sub">RENDERAD MOCKUP. Ingen karta &auml;ndrad. <b>&Ouml;ppen vildmark = default</b> (ljusgr&ouml;nt, du g&aring;r n&auml;stan &ouml;verallt; m&ouml;ten rullar region-baserat d&auml;r). Terr&auml;ng formar <b>organiska</b> omr&aring;den att v&auml;va genom: t&auml;ta skogar (m&ouml;rkgr&ouml;na blobar, ej rektanglar), <b>raka</b> floder + broar d&auml;r de korsar grafkanter, stenpartier. St&auml;der utspridda med &ouml;ppen mark runt. <b>Inga korridorer, inga rektanglar, inget encounter-gr&auml;s.</b> R&ouml;d streckad linje y={SEAM_Y} = k&auml;rna/hed-s&ouml;m (passerbar via broar vid de tv&aring; zon-korsande kanterna).</p>
<div class="fac">Hed-fraktioner bevarade: {fchips}</div>
<div class="grid">{''.join(cells)}
<div class="seam" style="grid-row:{SEAM_Y+1};grid-column:1 / {W+1}"></div>
</div>
<div class="legend">{legend_html}</div>
</div>
<style>
.wrap{{font-family:-apple-system,system-ui,sans-serif;color:#e8e8e8;background:#161616;padding:18px;max-width:100%}}
h1{{font-size:20px;margin:0 0 4px}}
.sub{{font-size:12px;color:#b3b3b3;margin:0 0 10px;max-width:1000px;line-height:1.55}}
.fac{{margin:0 0 12px;font-size:12px}}
.fc{{display:inline-block;border:1.5px solid;border-radius:10px;padding:1px 9px;margin-right:8px}}
.gridwrap{{overflow-x:auto}}
.grid{{display:grid;grid-template-columns:repeat({W},11px);grid-template-rows:repeat({H},11px);
gap:1px;background:#000;padding:6px;border-radius:6px;width:max-content;position:relative;overflow-x:auto}}
.c{{width:11px;height:11px;font-size:8px;line-height:11px;text-align:center;color:#222;font-weight:700}}
.town{{outline:1.5px solid #fff;z-index:3}}
.gate,.bridge{{color:#fff}}
.seam{{border-top:2px dashed #ff5d5d;align-self:start;pointer-events:none}}
.legend{{display:flex;flex-wrap:wrap;gap:9px 22px;margin-top:16px;max-width:1000px}}
.li{{font-size:12px;display:flex;align-items:center;gap:7px}}
.sw{{width:14px;height:14px;border-radius:3px;display:inline-block;border:1px solid #000}}
</style>"""

out = os.path.join(os.path.dirname(__file__), "wilderness_proposal.html")
with open(out, "w") as f:
    f.write(html)

# summary
from collections import Counter
counts = Counter(grid[y][x] for y in range(H) for x in range(W))
total = W * H
walkable = counts["open"] + counts["bridge"] + counts["town"]
print(f"size {W}x{H} = {total} tiles (current 48x32 = 1536; x{total/1536:.2f})")
for k in ("open", "forest", "stone", "river", "bridge", "town", "gate", "wall"):
    print(f"  {k:<8} {counts[k]:>5}  {100*counts[k]/total:4.1f}%")
print(f"walkable-ish (open+bridge+town): {walkable} = {100*walkable/total:.1f}%")
print(f"wrote {out}")
