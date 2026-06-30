#!/usr/bin/env python3
"""RENDER-ONLY foundation proposal: the enlarged, spread overworld BASE that
rivers/mountains/houses get placed onto LATER (edge phase). Reads/writes no map.

Shows ONLY the foundation: open roamable wilderness (default), organic forest
masses, and the 17 towns at their proposed scattered tile coords. Marks spawn
and the two zone-crossing edges. NO rivers, NO mountains, NO houses yet.
Emits scratchpad/foundation_proposal.html.
"""
import math
import os
import random

random.seed(7)
W, H = 80, 56
SEAM_Y = 36  # core rows 0-35, heath rows 36-55 (passable)

CORE = {
    "burg_5": (26, 18), "burg_117": (10, 8), "burg_160": (38, 22),
    "burg_235": (50, 16), "burg_379": (57, 7), "burg_146": (66, 12),
    "burg_67": (60, 26), "burg_200": (73, 6), "burg_219": (74, 17),
    "burg_320": (70, 31),
}
HEATH = {
    "burg_54": (14, 42), "burg_121": (24, 47), "burg_385": (17, 51),
    "burg_149": (33, 44), "burg_293": (50, 43), "burg_105": (63, 47),
    "burg_53": (73, 51),
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
FACTION = {"burg_54": "Bondemilis", "burg_121": "Bondemilis", "burg_385": "Bondemilis",
           "burg_149": "Bondemilis", "burg_293": "Harrow", "burg_105": "Harrow",
           "burg_53": "Harrow"}
RESPAWN = {"burg_5", "burg_320", "burg_121"}
SPAWN = "burg_5"
# The two zone-crossing edges that MUST stay passable across the seam.
ZONE_EDGES = [("burg_117", "burg_54"), ("burg_149", "burg_67")]

grid = [["open"] * W for _ in range(H)]
for x in range(W):
    grid[0][x] = grid[H - 1][x] = "edge"
for y in range(H):
    grid[y][0] = grid[y][W - 1] = "edge"


def blob(cx, cy, r):
    for y in range(max(1, cy - r - 1), min(H - 1, cy + r + 2)):
        for x in range(max(1, cx - r - 1), min(W - 1, cx + r + 2)):
            if math.hypot(x - cx, y - cy) <= r + random.uniform(-1.2, 0.5):
                grid[y][x] = "forest"


# Organic forest masses placed BETWEEN towns (weave-texture, the only terrain
# in the foundation). Kept clear of town margins + the two zone-crossing lines.
for cx, cy, r in [(20, 28, 5), (44, 10, 4), (52, 30, 4), (67, 21, 4),
                  (40, 50, 5), (8, 50, 3), (33, 14, 3), (58, 40, 3)]:
    blob(cx, cy, r)

# carve open margins around towns (no forest hugging a town)
for (tx, ty) in TOWNS.values():
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            nx, ny = tx + dx, ty + dy
            if 0 < nx < W - 1 and 0 < ny < H - 1:
                grid[ny][nx] = "open"

# keep the two zone-crossing corridors-of-intent open (straight-ish line of sight)
for a, b in ZONE_EDGES:
    (ax, ay), (bx, by) = TOWNS[a], TOWNS[b]
    steps = max(abs(ax - bx), abs(ay - by))
    for i in range(steps + 1):
        x = round(ax + (bx - ax) * i / steps)
        y = round(ay + (by - ay) * i / steps)
        for dx in (-1, 0, 1):
            if 0 < x + dx < W - 1 and 0 < y < H - 1:
                grid[y][x + dx] = "open"

for (tx, ty), pid in {v: k for k, v in TOWNS.items()}.items():
    grid[ty][tx] = "town"

place_at = {v: k for k, v in TOWNS.items()}
COLORS = {"open": "#9bbf6a", "forest": "#1f3d24", "edge": "#10160f",
          "town": "#ffd54a", "spawn": "#ff8c1a", "respawn": "#7ec8ff"}

cells = []
for y in range(H):
    for x in range(W):
        k = grid[y][x]
        label, title = "", f"({x},{y}) {k}"
        color = COLORS[k]
        if (x, y) in place_at:
            pid = place_at[(x, y)]
            fac = FACTION.get(pid, "core")
            tag = "SPAWN" if pid == SPAWN else ("respawn" if pid in RESPAWN else fac)
            title = f"({x},{y}) {NAMES[pid]} [{pid}] - {tag}"
            color = COLORS["spawn"] if pid == SPAWN else (
                COLORS["respawn"] if pid in RESPAWN else COLORS["town"])
            label = "S" if pid == SPAWN else ("R" if pid in RESPAWN else "T")
        cells.append(f'<div class="c" style="grid-column:{x+1};grid-row:{y+1};'
                     f'background:{color}" title="{title}">{label}</div>')

# zone-edge dashed connectors (drawn as a note; lines approximated by marking endpoints)
edge_note = " · ".join(f"{NAMES[a]}⇄{NAMES[b]}" for a, b in ZONE_EDGES)

legend = [("open", "Öppen roambar vildmark (default)"),
          ("forest", "Organisk skogsmassa (väv runt)"),
          ("town", "Stad (utspridd, öppen marginal)"),
          ("spawn", "SPAWN (Hordanita)"),
          ("respawn", "Respawn-stad"),
          ("edge", "Kartkant")]
legend_html = "".join(
    f'<div class="li"><span class="sw" style="background:{COLORS[k]}"></span>{t}</div>'
    for k, t in legend)

html = f"""<div class="wrap">
<h1>Fundament &mdash; förstorad &amp; spridd overworld ({W}&times;{H})</h1>
<p class="sub">RENDERAD MOCKUP, ej committad. Endast <b>fundamentet</b>: öppen vildmark (default), organiska skogsmassor, och de 17 städerna på sina föreslagna utspridda tile-koordinater. <b>Inga floder, berg eller hus än</b> (de placeras i edge-fasen på vatten-setet + Lucas assets). Röd streckad linje y={SEAM_Y} = kärna/hed-söm. Zon-korsande kanter (hålls passerbara): {edge_note}.</p>
<div class="grid">{''.join(cells)}
<div class="seam" style="grid-row:{SEAM_Y+1};grid-column:1 / {W+1}"></div>
</div>
<div class="legend">{legend_html}</div>
</div>
<style>
.wrap{{font-family:-apple-system,system-ui,sans-serif;color:#e8e8e8;background:#161616;padding:18px;max-width:100%}}
h1{{font-size:20px;margin:0 0 4px}}
.sub{{font-size:12px;color:#b3b3b3;margin:0 0 12px;max-width:1000px;line-height:1.55}}
.grid{{display:grid;grid-template-columns:repeat({W},11px);grid-template-rows:repeat({H},11px);
gap:1px;background:#000;padding:6px;border-radius:6px;width:max-content;position:relative;overflow-x:auto}}
.c{{width:11px;height:11px;font-size:8px;line-height:11px;text-align:center;color:#222;font-weight:700}}
.c[title*="SPAWN"],.c[title*="respawn"]{{outline:1.5px solid #fff;z-index:3}}
.seam{{border-top:2px dashed #ff5d5d;align-self:start;pointer-events:none}}
.legend{{display:flex;flex-wrap:wrap;gap:9px 22px;margin-top:16px;max-width:1000px}}
.li{{font-size:12px;display:flex;align-items:center;gap:7px}}
.sw{{width:14px;height:14px;border-radius:3px;display:inline-block;border:1px solid #000}}
</style>"""

out = os.path.join(os.path.dirname(__file__), "foundation_proposal.html")
with open(out, "w") as f:
    f.write(html)

from collections import Counter
c = Counter(grid[y][x] for y in range(H) for x in range(W))
tot = W * H
print(f"size {W}x{H} = {tot} (x{tot/1536:.2f} of 48x32)")
for k in ("open", "forest", "town", "edge"):
    print(f"  {k:<7} {c[k]:>5}  {100*c[k]/tot:4.1f}%")
print(f"open walkable: {100*(c['open']+c['town'])/tot:.1f}%")
print(f"wrote {out}")
