#!/usr/bin/env python3
"""extend_verralda.py — append a walkable grave_heath skeleton south of the core.

Additive and invariant-safe: the existing map (rows 0..H-1 of every layer) is
kept BYTE-IDENTICAL; only new southern rows are generated. This is deliberately
NOT a beautify re-run — beautify regenerates the whole map from a seed, which
would reshuffle the existing area. We read the current overworld.tmx, keep its
rows verbatim, and paint new grave_heath ground rows beneath them.

Skeleton scope: ground only (recolor-lifted grave_heath grass), a bordered field
with a walkable seam under the old gate_south tile, and a fresh frontier-gate hole
on the new bottom border. No props/trees (grave_heath prop tilesets aren't
registered) and no enemies — same as the core began, a plain field.

Idempotent-ish: re-running re-derives the same south rows (fixed seed) and leaves
the kept rows untouched. Originals restore via git.
"""
from __future__ import annotations

import random
import re

TMX = "rpg_game/data/maps/overworld.tmx"
SOUTH_ROWS = 12                 # new rows appended below the core (y = H .. H+11)
BORDER_GID = 2                  # placeholder wall tile, matches the existing border
GRAVE_HEATH_GRASS_FIRSTGID = 387
SEAM_X = 13                     # column under the old gate_south [13, 19]
FRONTIER_GATE_X = 13            # hole in the new bottom border -> future-zone gate

# Grass tile indices, same conventions as beautify_overworld.py's core ground.
GBASE, GVAR, GDET = 0, [1, 2, 3], [4, 5, 6, 7, 12, 13, 20, 21, 22, 28, 29]
random.seed(20)  # deterministic heath variation (offline generation, not game RNG)


def _layer(src: str, name: str):
    m = re.search(
        r'(<layer id="\d+" name="%s"[^>]*>\s*<data encoding="csv">\s*)(.*?)(\s*</data>)' % name,
        src, re.S,
    )
    grid = [[int(v) for v in r.rstrip(",").split(",")] for r in m.group(2).strip().split("\n")]
    return m, grid


def _ggid(idx: int) -> int:
    return GRAVE_HEATH_GRASS_FIRSTGID + idx


def _heath_ground_row(w: int) -> list[int]:
    row = []
    for _x in range(w):
        r = random.random()
        idx = random.choice(GDET) if r < 0.04 else (random.choice(GVAR) if r < 0.30 else GBASE)
        row.append(_ggid(idx))
    return row


def _heath_walls_row(w: int, y: int, last_y: int) -> list[int]:
    row = [0] * w
    row[0] = row[w - 1] = BORDER_GID                 # left/right border columns
    if y == last_y:                                   # new bottom border
        for x in range(w):
            row[x] = BORDER_GID
        row[FRONTIER_GATE_X] = 0                      # frontier-gate hole (blocked via data)
    return row


def main() -> None:
    src = open(TMX, encoding="utf-8").read()
    # \b so the match can't land inside tilewidth="32"/tileheight="32".
    w = int(re.search(r'<map [^>]*\bwidth="(\d+)"', src).group(1))
    h = int(re.search(r'<map [^>]*\bheight="(\d+)"', src).group(1))
    new_h = h + SOUTH_ROWS
    last_y = new_h - 1

    layers = {name: _layer(src, name) for name in ("ground", "walls", "decor_over")}
    for name, (_m, grid) in layers.items():
        for y in range(h, new_h):
            if name == "ground":
                grid.append(_heath_ground_row(w))
            elif name == "walls":
                grid.append(_heath_walls_row(w, y, last_y))
            else:  # decor_over: no canopies in the skeleton
                grid.append([0] * w)

    # Reachability over walkable (walls == 0) from the start tile; Alherralba and
    # every existing town must stay reachable (the seam connects core <-> heath).
    walls = layers["walls"][1]
    blocked = {(x, y) for y in range(new_h) for x in range(w) if walls[y][x] != 0}
    start = (14, 10)
    seen, queue = {start}, [start]
    while queue:
        x, y = queue.pop()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < new_h and (nx, ny) not in blocked and (nx, ny) not in seen:
                seen.add((nx, ny)); queue.append((nx, ny))
    assert (14, 26) in seen, "Alherralba tile unreachable"
    assert (SEAM_X, h) in seen, "heath not reachable through the seam"

    # Write layers back via re.sub (re-searches the current src each time, so no
    # stale positions), then bump the map height. Each layer's own height attr is
    # bumped inside its opener; the data body is replaced with the extended grid.
    def csv(grid):
        return ",\n".join(",".join(str(grid[y][x]) for x in range(w)) for y in range(len(grid)))

    for name, (_m, grid) in layers.items():
        pattern = (r'(<layer id="\d+" name="%s"[^>]*>\s*<data encoding="csv">\s*)(.*?)(\s*</data>)'
                   % name)

        def repl(mm, grid=grid):
            opener = mm.group(1).replace(f'height="{h}"', f'height="{new_h}"')
            return opener + csv(grid) + mm.group(3)

        src = re.sub(pattern, repl, src, count=1, flags=re.S)
    src = re.sub(r'(<map [^>]*\bheight=)"%d"' % h, r'\1"%d"' % new_h, src, count=1)

    open(TMX, "w", encoding="utf-8").write(src)
    print(f"extended map {w}x{h} -> {w}x{new_h}: +{SOUTH_ROWS} grave_heath rows, "
          f"seam at x={SEAM_X}, frontier gate hole at x={FRONTIER_GATE_X} on y={last_y}")


if __name__ == "__main__":
    main()
