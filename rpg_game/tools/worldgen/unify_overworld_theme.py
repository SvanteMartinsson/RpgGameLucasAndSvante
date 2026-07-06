#!/usr/bin/env python3
"""unify_overworld_theme.py — remove the per-zone ground colouring.

The overworld map had three baked visual themes (cainos / mork_skog /
cursed_mire) selected by column, which produced a hard seam between the olive
core and the green west. This reverts that: every mork_skog / cursed_mire
GROUND-grass, PLANT and PROPS tile is remapped to its cainos equivalent at the
SAME tile index, so the exact tree/rock/path layout is preserved but rendered
with one uniform (cainos) palette.

Scope: art/asset wiring only. It edits tile GIDs in the ground/walls/decor_over
layers of overworld.tmx. It does NOT touch:
  - the map border (its own theme-neutral tileset),
  - tileset declarations (count stays the same; the themed sheets stay
    registered-but-unused so re-theming later is trivial),
  - core_zone.json wild_regions / level bands (encounters & difficulty are
    unchanged — only the look is unified).

Reproducible and idempotent: cainos tiles are already cainos, so re-running is a
no-op. Originals restore via `git checkout` either way.
"""
from __future__ import annotations

import re

TMX = "rpg_game/data/maps/overworld.tmx"
LAYERS = ("ground", "walls", "decor_over")
# Themes folded back into cainos, by sheet category.
FOLD = {
    "grass": ("cainos_grass", ("mork_skog_grass", "cursed_mire_grass")),
    "plant": ("cainos_plant", ("mork_skog_plant", "cursed_mire_plant")),
    "props": ("cainos_props", ("mork_skog_props", "cursed_mire_props")),
}


def _tilesets(src: str) -> dict[str, tuple[int, int]]:
    """name -> (firstgid, tilecount) from the tileset declarations."""
    out: dict[str, tuple[int, int]] = {}
    for fg, name, count in re.findall(
        r'<tileset firstgid="(\d+)" name="([^"]+)"[^>]*tilecount="(\d+)"', src
    ):
        out[name] = (int(fg), int(count))
    return out


def _build_remap(src: str) -> dict[int, int]:
    ts = _tilesets(src)
    remap: dict[int, int] = {}
    for _category, (target, sources) in FOLD.items():
        if target not in ts:
            continue
        target_fg = ts[target][0]
        for source in sources:
            if source not in ts:
                continue
            fg, count = ts[source]
            for idx in range(count):
                remap[fg + idx] = target_fg + idx
    return remap


def _layer_csv(src: str, name: str) -> tuple[re.Match, list[list[int]]]:
    match = re.search(
        r'(<layer id="\d+" name="%s"[^>]*>\s*<data encoding="csv">\s*)(.*?)(\s*</data>)' % name,
        src, re.S,
    )
    rows = match.group(2).strip().split("\n")
    grid = [[int(v) for v in r.rstrip(",").split(",")] for r in rows]
    return match, grid


def main() -> None:
    src = open(TMX, encoding="utf-8").read()
    remap = _build_remap(src)
    changed = 0
    for name in LAYERS:
        match, grid = _layer_csv(src, name)
        for row in grid:
            for i, gid in enumerate(row):
                if gid in remap:
                    row[i] = remap[gid]
                    changed += 1
        csv = ",\n".join(",".join(str(v) for v in row) for row in grid)
        src = src[: match.start(2)] + csv + src[match.end(2):]
    open(TMX, "w", encoding="utf-8").write(src)
    print(f"unified overworld theme: remapped {changed} tiles across {len(LAYERS)} layers")


if __name__ == "__main__":
    main()
