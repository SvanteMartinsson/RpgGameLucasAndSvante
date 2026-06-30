"""Trait-driven enemy resistances.

`traits` (max 2 per enemy) are the single source of truth for elemental
matchups; the `resistances` dict the combat pipeline reads is *derived* from
them at load time (see data_loader). Nothing here touches damage resolution —
this is pure data derivation.

Model: each trait contributes a step per damage type on the scale

    resist -1 · normal 0 · effective +1 · super +2 · bane +3

Steps from multiple traits are summed per damage type, clamped to [-1, +3],
then mapped to a fixed resistance multiplier. IMMUNE is absolute: if any trait
grants immunity to a type the derived multiplier is 0.0 regardless of steps.
A damage type no trait touches stays neutral (1.0) — so e.g. `lightning`,
which appears in no profile, is always 1.0.
"""

from __future__ import annotations

# Sentinel for absolute immunity (beats any summed step).
IMMUNE = object()

# Step -> resistance multiplier the pipeline reads.
STEP_TO_MULTIPLIER = {-1: 0.65, 0: 1.0, 1: 1.25, 2: 1.5, 3: 2.0}

_STEP_MIN, _STEP_MAX = -1, 3

# Trait profiles: trait -> {damage_type: step | IMMUNE}.
TRAIT_PROFILES: dict[str, dict[str, object]] = {
    "beast":  {"fire": 3, "poison": 1, "frost": -1},
    "plant":  {"fire": 3, "frost": -1},
    "swamp":  {"frost": 3, "fire": -1, "poison": -1},
    "undead": {"holy": 3, "poison": IMMUNE, "frost": -1},
    "spirit": {"holy": 2, "physical": -1},
    "cursed": {"holy": 2, "physical": -1},
    "vermin": {"fire": 1, "poison": -1},
}


def resistances_from_traits(traits) -> dict[str, float]:
    """Derive the resistance multiplier dict for a set of traits.

    Only damage types some trait touches appear in the result; the pipeline's
    `get_resistance` defaults everything else to 1.0, so an empty trait list
    yields an empty dict (a fully neutral enemy)."""
    steps: dict[str, int] = {}
    immune: set[str] = set()
    for trait in traits:
        for damage_type, step in TRAIT_PROFILES.get(trait, {}).items():
            if step is IMMUNE:
                immune.add(damage_type)
            else:
                steps[damage_type] = steps.get(damage_type, 0) + step

    resistances: dict[str, float] = {}
    for damage_type, total in steps.items():
        if damage_type in immune:
            continue  # immunity is absolute; handled below
        clamped = max(_STEP_MIN, min(_STEP_MAX, total))
        resistances[damage_type] = STEP_TO_MULTIPLIER[clamped]
    for damage_type in immune:
        resistances[damage_type] = 0.0
    return resistances
