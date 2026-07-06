"""B48: per-area enemy spawning — Lucas's hand-drawn, overlapping regions.

The world's wild encounters are authored as weighted rectangles in
maps/core_zone.json (`spawn_areas`): the pool at a tile is the UNION of every
area covering it (weights for the same enemy SUM), and a tile no area covers
falls back to its wild region's `spawn_fallbacks` pool. Overlap is a feature —
the border between two areas mixes both rosters.

Pure rules over loaded data: the presentation supplies the tile (core tracks
places, not tiles) and hands the pool to the engine's encounter creation.
Tile-less callers (terminal mode, sims) skip pools entirely and keep the old
place-pool path.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class SpawnArea:
    """One drawn rectangle: inclusive tile bounds + its weighted roster.
    `color` is the sketch colour, used only by the zone-map render tool."""
    id: str
    rect: tuple[int, int, int, int]          # x0, y0, x1, y1 (inclusive)
    enemies: tuple[tuple[str, int], ...]     # (enemy_id, weight)
    color: tuple[int, int, int] = (200, 200, 200)

    def covers(self, tile: tuple[int, int]) -> bool:
        x, y = tile
        x0, y0, x1, y1 = self.rect
        return x0 <= x <= x1 and y0 <= y <= y1


def pool_at(
    areas: tuple[SpawnArea, ...],
    fallbacks: dict[str, tuple[tuple[str, int], ...]],
    tile: tuple[int, int],
    region_place_id: str,
) -> tuple[tuple[str, int], ...]:
    """The weighted pool for a tile: union of all covering areas (same enemy in
    several areas -> weights sum), else the wild region's fallback pool."""
    weights: dict[str, int] = {}
    for area in areas:
        if area.covers(tile):
            for enemy_id, weight in area.enemies:
                weights[enemy_id] = weights.get(enemy_id, 0) + weight
    if weights:
        return tuple(sorted(weights.items()))
    return fallbacks.get(region_place_id, ())


def weighted_pick(pool: tuple[tuple[str, int], ...], rng: random.Random) -> str:
    """One enemy id from a weighted pool (single rng draw)."""
    total = sum(weight for _enemy_id, weight in pool)
    roll = rng.random() * total
    upto = 0.0
    for enemy_id, weight in pool:
        upto += weight
        if roll < upto:
            return enemy_id
    return pool[-1][0]
