"""B55: encounter pacing as engine logic.

WHEN a wild enemy appears is a game rule, not rendering: the per-step rate is 0
on a town cluster and its margin, 0 next to any town anchor, ramps to the zone
base over a few tiles, and is reduced on roads (the B12 heatmap). This module
owns that rule; the pygame shell just asks "encounter now? (tile)" each step,
and the simulator can count encounters per journey.

The map geometry is captured once in an `EncounterMap` (plain tile sets — no
TMX/pygame types); the zone base rate stays a call parameter so runtime tuning
(and tests that pin the rate) keep working.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

SAFE_RADIUS = 1     # town + adjacent tiles: no encounters
RAMP_TILES = 3      # tiles over which the rate ramps from 0 to full
PATH_FACTOR = 0.6   # -40% on a road/path tile


@dataclass(frozen=True)
class EncounterMap:
    """The tile geometry encounter pacing reads: town anchors, the no-encounter
    zone (clusters + margin, B32) and road/path tiles."""
    town_tiles: frozenset
    safe_tiles: frozenset = frozenset()
    path_tiles: frozenset = frozenset()


def nearest_town_dist(emap: EncounterMap, tile) -> int:
    """Chebyshev distance to the nearest town anchor (99 with no towns)."""
    tx, ty = tile
    return min((max(abs(tx - x), abs(ty - y)) for (x, y) in emap.town_tiles), default=99)


def encounter_rate_at(emap: EncounterMap, tile, base_rate: float,
                      *, on_path: bool | None = None) -> float:
    """Per-step encounter chance at a tile (the B12 heatmap). `on_path` overrides
    the map's road lookup — the shell passes its own road predicate through it,
    which keeps that seam mockable in tests."""
    if tile in emap.safe_tiles:
        return 0.0
    dist = nearest_town_dist(emap, tile)
    if dist <= SAFE_RADIUS:
        return 0.0
    ramp = min(1.0, (dist - SAFE_RADIUS) / RAMP_TILES)
    rate = base_rate * ramp
    if (tile in emap.path_tiles) if on_path is None else on_path:
        rate *= PATH_FACTOR
    return rate


def should_encounter(emap: EncounterMap, tile, base_rate: float,
                     rng: random.Random, *, in_town: bool = False) -> bool:
    """One per-step roll. In town: never, and NO rng draw (stream-identical to the
    pre-B55 shell). In the wild: exactly one draw against the tile's rate."""
    if in_town:
        return False
    return rng.random() < encounter_rate_at(emap, tile, base_rate)


# --- journey measurement (for the simulator) ---------------------------------

def journey_encounter_load(emap: EncounterMap, route, base_rate: float) -> float:
    """Deterministic expected number of encounters along a route (sum of per-step
    rates) — the tuning-friendly measure of how dangerous a journey is."""
    return sum(encounter_rate_at(emap, tile, base_rate) for tile in route)


def simulate_journey(emap: EncounterMap, route, base_rate: float,
                     rng: random.Random) -> int:
    """Walk a route with seeded rolls and count the encounters that would fire."""
    return sum(1 for tile in route if should_encounter(emap, tile, base_rate, rng))


# --- B104: post-battle encounter cooldown -------------------------------------

# B129: back to 1.0 (B124 tried 2.0). Lucas playtest: 2 s (~9 tiles) was too
# long a dead walk; 1 s (~4.5 tiles at 144 px/s over 32px tiles) already broke
# the back-to-back encounters. The per-tile roll (rate 0.06) still governs the
# ~17-tile expected gap after the gate lifts.
ENCOUNTER_COOLDOWN_SECONDS = 1.0


class EncounterCooldown:
    """B104: after a battle ends, one second of ACCUMULATED MOVEMENT time must
    pass before the encounter slot can fire again — and the slot is shared, so
    the gate covers B67 travel events too. Standing still does not count down:
    the clock is movement time, not wall time. While active the shell skips the
    roll entirely (no rng draw), so the first roll after the cooldown is simply
    the next draw of the seeded stream — identical to a step without cooldown.
    """

    def __init__(self, duration: float = ENCOUNTER_COOLDOWN_SECONDS) -> None:
        self.duration = float(duration)
        self._remaining = 0.0

    def start(self) -> None:
        self._remaining = self.duration

    def tick_movement(self, dt: float) -> None:
        """Count down by `dt` seconds of movement. Call only on frames where
        the player actually moved."""
        if self._remaining > 0.0 and dt > 0.0:
            self._remaining = max(0.0, self._remaining - dt)

    @property
    def active(self) -> bool:
        return self._remaining > 0.0
