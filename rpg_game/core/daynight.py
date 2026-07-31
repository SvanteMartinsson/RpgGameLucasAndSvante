"""B136a: the day/night clock — a pure, deterministic rule over one float.

The whole cycle is a single number: `world_time_seconds`, the position inside a
14-minute day (7 min of daylight, 7 min of dark). Four phases run in a fixed
order and DAWN/DUSK are carved out of the halves they open, so the daylight half
is dawn+day and the dark half is dusk+night:

    dawn  [  0,  45)   the light comes back
    day   [ 45, 420)   full daylight
    dusk  [420, 465)   the warning — the towns have not closed yet
    night [465, 840)   dark; the towns are shut

Nothing here rolls dice and nothing here mutates: `advance()` maps
(time, dt) -> time. That matters for two reasons — a phase transition can never
perturb a seeded stream (map generation, spawns, sims stay bit-identical), and
the clock is a pure function of accumulated MOVEMENT time, so a player standing
still is standing in a frozen world (the shell only feeds dt on frames the
player actually moved; see EncounterCooldown for the same pattern).

`world_time_seconds` = 0.0 is MORNING (the first instant of dawn). That is also
what an old save without the field deserializes to, so a pre-B136 save wakes up
at daybreak rather than in a random dark.

Two derived vocabularies keep the consumers from re-deciding the boundaries:
  * `towns_closed(phase)` — only `night` shuts a town. Dusk is deliberately a
    free warning: the sky changes while the shutters are still open.
  * `spawn_phase(phase)` — dawn/day -> "day", dusk/night -> "night". The night
    roster comes out AT dusk, which is what makes the warning worth reading.
"""

from __future__ import annotations

# Phase order is the cycle order; the table below is its only length authority.
PHASE_ORDER: tuple[str, ...] = ("dawn", "day", "dusk", "night")

# Lucas's target: ~7 min day + ~7 min night, dawn/dusk 30-60 s INSIDE the halves.
DAWN_SECONDS = 45.0
DAY_SECONDS = 375.0      # dawn + day  = 420 s = 7 min of daylight
DUSK_SECONDS = 45.0
NIGHT_SECONDS = 375.0    # dusk + night = 420 s = 7 min of dark

PHASE_SECONDS: dict[str, float] = {
    "dawn": DAWN_SECONDS,
    "day": DAY_SECONDS,
    "dusk": DUSK_SECONDS,
    "night": NIGHT_SECONDS,
}

CYCLE_SECONDS = sum(PHASE_SECONDS[phase] for phase in PHASE_ORDER)   # 840.0

# t = 0.0 is the first instant of dawn: the safety valves (rest, respawn) snap
# here, and a save with no time field defaults here.
MORNING_PHASE = "dawn"
MORNING_SECONDS = 0.0

# Human labels for the HUD indicator (presentation renders, core names).
PHASE_LABELS: dict[str, str] = {
    "dawn": "Dawn",
    "day": "Day",
    "dusk": "Dusk",
    "night": "Night",
}


def normalize(seconds: float) -> float:
    """Wrap a raw time into [0, CYCLE_SECONDS). Non-finite/garbage -> morning."""
    try:
        value = float(seconds)
    except (TypeError, ValueError):
        return MORNING_SECONDS
    if value != value or value in (float("inf"), float("-inf")):   # NaN / inf
        return MORNING_SECONDS
    return value % CYCLE_SECONDS


def phase_start(phase: str) -> float:
    """The cycle offset a phase begins at (unknown phase -> morning)."""
    offset = 0.0
    for name in PHASE_ORDER:
        if name == phase:
            return offset
        offset += PHASE_SECONDS[name]
    return MORNING_SECONDS


def phase_at(seconds: float) -> str:
    """Which phase the clock is in."""
    position = normalize(seconds)
    for phase in PHASE_ORDER:
        length = PHASE_SECONDS[phase]
        if position < length:
            return phase
        position -= length
    return PHASE_ORDER[-1]   # pragma: no cover - normalize() precludes this


def phase_progress(seconds: float) -> float:
    """How far INTO the current phase the clock is, in [0.0, 1.0).

    This is the gradient input: the tint interpolates over it so dusk darkens
    smoothly instead of snapping at the boundary.
    """
    position = normalize(seconds)
    for phase in PHASE_ORDER:
        length = PHASE_SECONDS[phase]
        if position < length:
            return position / length
        position -= length
    return 0.0   # pragma: no cover - normalize() precludes this


def advance(seconds: float, dt: float) -> float:
    """Move the clock forward by `dt` seconds of MOVEMENT time (wraps).

    Negative or non-finite dt is ignored — time never runs backwards, so no
    caller can rewind out of the night by feeding a bad frame delta.
    """
    try:
        step = float(dt)
    except (TypeError, ValueError):
        return normalize(seconds)
    if step != step or step <= 0.0 or step == float("inf"):
        return normalize(seconds)
    return normalize(normalize(seconds) + step)


def towns_closed(phase: str) -> bool:
    """Whether town services are shut. NIGHT only — dusk is the free warning."""
    return phase == "night"


def spawn_phase(phase: str) -> str:
    """The spawn roster a phase rolls: "day" or "night".

    Dusk already rolls the NIGHT roster — the things that come out in the dark
    come out as it falls, so the sky change is a real telegraph and not just
    decoration. Dawn is over: it rolls day.
    """
    return "night" if phase in ("dusk", "night") else "day"


def is_dark(phase: str) -> bool:
    """Dark enough for night ambience/tint to dominate (dusk counts)."""
    return phase in ("dusk", "night")
