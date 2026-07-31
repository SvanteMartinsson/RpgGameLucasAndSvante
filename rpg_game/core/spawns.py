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


# B136e: the two spawn phases. The clock has four phases; spawning only needs to
# know dark from light, and core.daynight.spawn_phase does that mapping (dusk
# already rolls NIGHT — the things that come out in the dark come out as it
# falls). "day" is the phase-less default, so every existing caller keeps its
# exact behaviour.
DAY = "day"
NIGHT = "night"


@dataclass(frozen=True)
class SpawnArea:
    """One drawn rectangle: inclusive tile bounds + its weighted roster.
    `color` is the sketch colour, used only by the zone-map render tool.
    `level_min`/`level_max` (optional) band the rolled enemy level inside this
    area; 0 = unset. An area band outranks the region's and the template's.

    B136e: `night_enemies` is the area's roster after dark. Empty = this area
    does not change with the hour and rolls `enemies` around the clock. It
    changes WHICH SPECIES roll and nothing else — the level band above is shared
    by both rosters, and `band_at` never even looks at the phase, so a night
    spawn cannot be a stronger spawn."""
    id: str
    rect: tuple[int, int, int, int]          # x0, y0, x1, y1 (inclusive)
    enemies: tuple[tuple[str, int], ...]     # (enemy_id, weight)
    color: tuple[int, int, int] = (200, 200, 200)
    level_min: int = 0
    level_max: int = 0
    night_enemies: tuple[tuple[str, int], ...] = ()

    def covers(self, tile: tuple[int, int]) -> bool:
        x, y = tile
        x0, y0, x1, y1 = self.rect
        return x0 <= x <= x1 and y0 <= y <= y1

    def roster(self, phase: str = DAY) -> tuple[tuple[str, int], ...]:
        """This area's roster for a spawn phase. Falls back to the day roster
        when the area has no night variant."""
        if phase == NIGHT and self.night_enemies:
            return self.night_enemies
        return self.enemies


def pool_at(
    areas: tuple[SpawnArea, ...],
    fallbacks: dict[str, tuple[tuple[str, int], ...]],
    tile: tuple[int, int],
    region_place_id: str,
    phase: str = DAY,
    night_fallbacks: dict[str, tuple[tuple[str, int], ...]] | None = None,
) -> tuple[tuple[str, int], ...]:
    """The weighted pool for a tile: union of all covering areas (same enemy in
    several areas -> weights sum), else the wild region's fallback pool.

    B136e: `phase` ("day"/"night") selects each area's roster. With the default
    phase the result is byte-identical to the pre-B136e function for every tile,
    which is what keeps the day delta curve untouched. The level band is NOT a
    parameter here — it comes from `band_at`, which is phase-blind by design.
    """
    weights: dict[str, int] = {}
    for area in areas:
        if area.covers(tile):
            for enemy_id, weight in area.roster(phase):
                weights[enemy_id] = weights.get(enemy_id, 0) + weight
    if weights:
        return tuple(sorted(weights.items()))
    if phase == NIGHT and night_fallbacks:
        night_pool = night_fallbacks.get(region_place_id)
        if night_pool:
            return night_pool
    return fallbacks.get(region_place_id, ())


def band_at(
    areas: tuple[SpawnArea, ...],
    tile: tuple[int, int],
) -> tuple[int, int] | None:
    """The level band for a tile: the union of every covering area's band
    (lowest min, highest max), mirroring how overlapping rosters mix. None when
    no covering area sets a band — callers then fall through to region/template."""
    lows, highs = [], []
    for area in areas:
        if area.covers(tile) and (area.level_min or area.level_max):
            lows.append(area.level_min or area.level_max)
            highs.append(area.level_max or area.level_min)
    if not lows:
        return None
    return min(lows), max(highs)


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
