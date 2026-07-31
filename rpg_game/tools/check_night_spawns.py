"""B136e: verify the phase-gated spawn tables.

Three things need proving, and the first is the important one:

1. THE DAY IS UNTOUCHED. Not "close enough" — byte-identical. `pool_at` with the
   default phase must return exactly the pre-B136e pool for every tile on the
   map, and a seeded spawn sequence must reproduce the same species AND the same
   rolled levels. That is what leaves the delta curve where B102 tuned it: the
   day rolls the same enemies from the same bands with the same rng draws, and no
   stat, HP, damage or band value was edited at all.
2. Every zone x phase can roll enough species (the load-time rail, printed here
   as the actual table for review).
3. Every night species is rolled inside a band its own level corridor reaches.

Prints the zone x phase roster table and exits non-zero on any violation.
"""

from __future__ import annotations

import random
import sys

from rpg_game.core import spawns
from rpg_game.core.data_loader import _theme_for_tile, _read_json, load_content
from rpg_game.core.game import GameEngine
from rpg_game.core.world import roll_enemy_level

NIGHT_TAGS = {"undead", "spirit", "cursed"}
DAY_TAGS = {"beast", "plant"}

# --- accepted residuals (B138, Lucas 2026-07-31) -----------------------------
# A cell that FAILS a balance expectation on purpose. Declared here, printed on
# every run, and bound to the data by
# tests/test_b138_skog_worg.py::test_the_accepted_residual_still_describes_reality
# so the record cannot go stale in silence.
#
# The point of writing it down: a future sim/balance pass must not "fix" this
# cell believing it found a regression. It is a design choice — Lucas:
# "surprises over perfect balance". delta_curve.py's residual section
# cross-references this list.
ACCEPTED_RESIDUALS = (
    {
        "id": "b138-worg-deep-east-d3",
        "area": "skog_deep_east",
        "enemy": "hollow_worg",
        "measured": "3.3% player win at level 9 (d-3 for a level-6 player)",
        "compare": "the area's next-hardest is treant at 15.0%",
        "cause": "base level 8: level 9 triggers HP_GROWTH_PER_LEVEL 0.38 (+38% HP)",
        "why_accepted": "intentional — surprises over perfect balance (Lucas 2026-07-31)",
        "rests_on": "the worg stays RARE here and wild fights allow flee",
    },
)


def _day_pool_pre_b136e(areas, fallbacks, tile, region_place_id):
    """The B48 implementation, verbatim — the oracle for "the day is untouched"."""
    weights: dict[str, int] = {}
    for area in areas:
        if area.covers(tile):
            for enemy_id, weight in area.enemies:
                weights[enemy_id] = weights.get(enemy_id, 0) + weight
    if weights:
        return tuple(sorted(weights.items()))
    return fallbacks.get(region_place_id, ())


def _tag_group(enemy) -> str:
    tags = set(enemy.tags)
    if tags & NIGHT_TAGS:
        return "night"
    if tags & DAY_TAGS:
        return "day"
    return "both"


def main() -> int:
    content = load_content()
    core_zone = _read_json("maps/core_zone.json")
    themes = core_zone.get("ground_themes", ())
    failures: list[str] = []

    # --- 1. the day is byte-identical -------------------------------------
    regions = sorted(content.spawn_fallbacks) or [""]
    checked = 0
    for area in content.spawn_areas:
        x0, y0, x1, y1 = area.rect
        corners = {(x0, y0), (x1, y1), ((x0 + x1) // 2, (y0 + y1) // 2)}
        for tile in corners:
            for region in regions:
                before = _day_pool_pre_b136e(content.spawn_areas,
                                             content.spawn_fallbacks, tile, region)
                after = spawns.pool_at(content.spawn_areas, content.spawn_fallbacks,
                                       tile, region)
                explicit = spawns.pool_at(content.spawn_areas, content.spawn_fallbacks,
                                          tile, region, phase=spawns.DAY,
                                          night_fallbacks=content.spawn_fallbacks_night)
                checked += 1
                if before != after or before != explicit:
                    failures.append(f"DAY POOL CHANGED at {tile}/{region}: "
                                    f"{before} -> {after} / {explicit}")
    print(f"1. day pools byte-identical to pre-B136e: {checked} tile/region pools checked, "
          f"{len(failures)} differences")

    # A seeded spawn sequence must reproduce species AND rolled level.
    sequence_failures = 0
    for area in content.spawn_areas:
        x0, y0, x1, y1 = area.rect
        tile = ((x0 + x1) // 2, (y0 + y1) // 2)
        band = spawns.band_at(content.spawn_areas, tile)
        pool = spawns.pool_at(content.spawn_areas, content.spawn_fallbacks, tile, "")
        for seed in range(6):
            rolls = []
            for phase_arg in (None, spawns.DAY):
                rng = random.Random(seed)
                use = (pool if phase_arg is None else
                       spawns.pool_at(content.spawn_areas, content.spawn_fallbacks,
                                      tile, "", phase=phase_arg))
                picked = spawns.weighted_pick(use, rng)
                template = content.enemies[picked]
                rolls.append((picked, roll_enemy_level(template, rng, band=band)))
            if rolls[0] != rolls[1]:
                sequence_failures += 1
                failures.append(f"DAY SEQUENCE CHANGED in {area.id} seed {seed}: {rolls}")
    print(f"   seeded species+level sequences identical: "
          f"{'yes' if not sequence_failures else f'NO ({sequence_failures})'}")

    # The night pool must actually differ somewhere, or the slice did nothing.
    differing = sum(
        1 for area in content.spawn_areas
        if area.roster(spawns.NIGHT) != area.roster(spawns.DAY)
    )
    print(f"   areas whose roster changes after dark: {differing}/{len(content.spawn_areas)}")
    if not differing:
        failures.append("NO area changes roster at night — the slice is a no-op")

    # --- 2 + 3. per zone x phase ------------------------------------------
    per_zone: dict[str, dict[str, dict[str, int]]] = {}
    for area in content.spawn_areas:
        x0, y0, x1, y1 = area.rect
        zone = _theme_for_tile(themes, (x0 + x1) // 2, (y0 + y1) // 2)
        if not zone:
            continue
        buckets = per_zone.setdefault(zone, {spawns.DAY: {}, spawns.NIGHT: {}})
        for phase in (spawns.DAY, spawns.NIGHT):
            for enemy_id, weight in area.roster(phase):
                buckets[phase][enemy_id] = buckets[phase].get(enemy_id, 0) + weight

    print("\n2. zone x phase rosters (tag group in brackets):")
    for zone in sorted(per_zone):
        for phase in (spawns.DAY, spawns.NIGHT):
            species = per_zone[zone][phase]
            listing = ", ".join(
                f"{eid}[{_tag_group(content.enemies[eid])[0]}]" for eid in sorted(species))
            print(f"   {zone:13} {phase:5} {len(species):2d} species  {listing}")
            if len(species) < 2:
                failures.append(f"{zone} @ {phase} has only {len(species)} species")
        night_only = set(per_zone[zone][spawns.NIGHT]) - set(per_zone[zone][spawns.DAY])
        day_only = set(per_zone[zone][spawns.DAY]) - set(per_zone[zone][spawns.NIGHT])
        print(f"   {zone:13} ->    night-only {sorted(night_only) or '-'} · "
              f"day-only {sorted(day_only) or '-'}")

    print("\n3. night species inside a band their corridor reaches:")
    corridor_bad = 0
    for area in content.spawn_areas:
        if not area.night_enemies or not (area.level_min or area.level_max):
            continue
        low = area.level_min or area.level_max
        high = area.level_max or area.level_min
        for enemy_id, _weight in area.night_enemies:
            enemy = content.enemies[enemy_id]
            c_low = enemy.level_min or enemy.level
            c_high = enemy.level_max or enemy.level
            if c_high < low or c_low > high:
                corridor_bad += 1
                failures.append(f"{area.id}: {enemy_id} corridor {c_low}-{c_high} "
                                f"cannot reach band {low}-{high}")
    print(f"   violations: {corridor_bad}")

    # For contrast: how many pre-existing DAY pools already break rule 3.
    day_bad = []
    for area in content.spawn_areas:
        if not (area.level_min or area.level_max):
            continue
        low = area.level_min or area.level_max
        high = area.level_max or area.level_min
        for enemy_id, _weight in area.enemies:
            enemy = content.enemies[enemy_id]
            c_low = enemy.level_min or enemy.level
            c_high = enemy.level_max or enemy.level
            if c_high < low or c_low > high:
                day_bad.append(f"{area.id}/{enemy_id} ({c_low}-{c_high} in {low}-{high})")
    print(f"   (pre-existing DAY pools that break the same rule, untouched: "
          f"{len(day_bad)})")
    for entry in day_bad:
        print(f"     - {entry}")

    # --- the engine really rolls different species at night ----------------
    engine = GameEngine(content=content, rng=random.Random(7))
    engine.start_new_game("Hero", "fighter")
    heath = next(a for a in content.spawn_areas if a.id == "heath_ghoul_west")
    tile = ((heath.rect[0] + heath.rect[2]) // 2, (heath.rect[1] + heath.rect[3]) // 2)
    band = spawns.band_at(content.spawn_areas, tile)
    for phase in (spawns.DAY, spawns.NIGHT):
        pool = spawns.pool_at(content.spawn_areas, content.spawn_fallbacks, tile, "",
                              phase=phase, night_fallbacks=content.spawn_fallbacks_night)
        rng = random.Random(99)
        rolled = []
        for _ in range(200):
            picked = spawns.weighted_pick(pool, rng)
            template = content.enemies[picked]
            rolled.append((picked, roll_enemy_level(template, rng, band=band)))
        levels = [level for _e, level in rolled]
        species = sorted({e for e, _l in rolled})
        print(f"\n   heath_ghoul_west @ {phase}: levels {min(levels)}-{max(levels)} "
              f"(band {band[0]}-{band[1]}) species {species}")
        if (min(levels), max(levels)) != band:
            failures.append(f"{phase} rolled levels outside the area band {band}")

    print("\nACCEPTED RESIDUALS (deliberate — do NOT 'fix' these in a balance pass):")
    for residual in ACCEPTED_RESIDUALS:
        print(f"   [{residual['id']}] {residual['enemy']} in {residual['area']}")
        print(f"      measured : {residual['measured']}")
        print(f"      compare  : {residual['compare']}")
        print(f"      cause    : {residual['cause']}")
        print(f"      accepted : {residual['why_accepted']}")
        print(f"      rests on : {residual['rests_on']}")
        # Bound to reality: if the data moved, say so loudly rather than let the
        # record rot into a comment nobody trusts.
        area = next((a for a in content.spawn_areas if a.id == residual["area"]), None)
        present = area is not None and any(
            e == residual["enemy"] for e, _w in area.roster(spawns.DAY) + area.roster(spawns.NIGHT))
        print(f"      still in the data: {'yes' if present else 'NO — STALE RECORD'}")
        if not present:
            failures.append(f"accepted residual {residual['id']} no longer matches the data")

    print()
    if failures:
        print(f"FAILED ({len(failures)}):")
        for entry in failures:
            print(f"  - {entry}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
