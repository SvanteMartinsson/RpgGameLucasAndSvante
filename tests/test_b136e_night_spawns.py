"""B136e: phase-gated spawn tables via trait remix.

The load-bearing test in here is the FIRST one: with the default phase, the pool
function must be byte-identical to the pre-B136e implementation for every tile on
the map, and a seeded (species, level) sequence must reproduce exactly. That is
what keeps the day's delta curve where B102 tuned it — night changes WHICH
species roll and nothing else.
"""

import random
import unittest

from rpg_game.core import daynight, spawns
from rpg_game.core.data_loader import (MIN_SPECIES_PER_ZONE_PHASE, _read_json,
                                       _theme_for_tile, load_content)
from rpg_game.core.game import GameEngine
from rpg_game.core.world import roll_enemy_level

NIGHT_TAGS = {"undead", "spirit", "cursed"}
DAY_TAGS = {"beast", "plant"}


def _day_pool_pre_b136e(areas, fallbacks, tile, region_place_id):
    """The B48 implementation verbatim — the oracle for "the day is untouched"."""
    weights = {}
    for area in areas:
        if area.covers(tile):
            for enemy_id, weight in area.enemies:
                weights[enemy_id] = weights.get(enemy_id, 0) + weight
    if weights:
        return tuple(sorted(weights.items()))
    return fallbacks.get(region_place_id, ())


class SpawnPhaseBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = load_content()
        cls.themes = _read_json("maps/core_zone.json").get("ground_themes", ())

    def _pool(self, tile, phase=spawns.DAY, region=""):
        return spawns.pool_at(self.content.spawn_areas, self.content.spawn_fallbacks,
                              tile, region, phase=phase,
                              night_fallbacks=self.content.spawn_fallbacks_night)

    def _center(self, area_id):
        area = next(a for a in self.content.spawn_areas if a.id == area_id)
        x0, y0, x1, y1 = area.rect
        return ((x0 + x1) // 2, (y0 + y1) // 2)


class DayIsUntouchedTests(SpawnPhaseBase):
    def test_the_default_phase_is_byte_identical_to_pre_b136e(self):
        regions = sorted(self.content.spawn_fallbacks) + [""]
        checked = 0
        for area in self.content.spawn_areas:
            x0, y0, x1, y1 = area.rect
            for tile in {(x0, y0), (x1, y1), ((x0 + x1) // 2, (y0 + y1) // 2)}:
                for region in regions:
                    expected = _day_pool_pre_b136e(
                        self.content.spawn_areas, self.content.spawn_fallbacks, tile, region)
                    # no phase argument at all — the old call signature
                    self.assertEqual(
                        spawns.pool_at(self.content.spawn_areas,
                                       self.content.spawn_fallbacks, tile, region),
                        expected, (tile, region))
                    # and explicitly asking for day must agree
                    self.assertEqual(self._pool(tile, spawns.DAY, region), expected,
                                     (tile, region))
                    checked += 1
        self.assertGreater(checked, 100)

    def test_a_seeded_day_spawn_reproduces_species_and_level(self):
        for area in self.content.spawn_areas:
            tile = self._center(area.id)
            band = spawns.band_at(self.content.spawn_areas, tile)
            for seed in range(4):
                rolls = []
                for pool in (spawns.pool_at(self.content.spawn_areas,
                                            self.content.spawn_fallbacks, tile, ""),
                             self._pool(tile, spawns.DAY)):
                    rng = random.Random(seed)
                    picked = spawns.weighted_pick(pool, rng)
                    template = self.content.enemies[picked]
                    rolls.append((picked, roll_enemy_level(template, rng, band=band)))
                self.assertEqual(rolls[0], rolls[1], (area.id, seed))

    def test_band_at_never_sees_the_phase(self):
        # Structural guarantee that night cannot be a difficulty lever: the level
        # band function takes no phase argument at all.
        import inspect
        params = inspect.signature(spawns.band_at).parameters
        self.assertNotIn("phase", params)
        self.assertEqual(list(params), ["areas", "tile"])

    def test_the_level_band_is_the_same_in_both_phases(self):
        for area in self.content.spawn_areas:
            tile = self._center(area.id)
            band = spawns.band_at(self.content.spawn_areas, tile)
            if band is None:
                continue
            for phase in (spawns.DAY, spawns.NIGHT):
                pool = self._pool(tile, phase)
                rng = random.Random(5)
                levels = []
                for _ in range(60):
                    picked = spawns.weighted_pick(pool, rng)
                    template = self.content.enemies[picked]
                    levels.append(roll_enemy_level(template, rng, band=band))
                self.assertGreaterEqual(min(levels), band[0], (area.id, phase))
                self.assertLessEqual(max(levels), band[1], (area.id, phase))


class NightRosterTests(SpawnPhaseBase):
    def test_the_night_really_changes_the_roster(self):
        changed = [area.id for area in self.content.spawn_areas
                   if area.roster(spawns.NIGHT) != area.roster(spawns.DAY)]
        self.assertEqual(len(changed), len(self.content.spawn_areas))

    def test_every_zone_and_phase_can_roll_enough_species(self):
        per_zone = {}
        for area in self.content.spawn_areas:
            x0, y0, x1, y1 = area.rect
            zone = _theme_for_tile(self.themes, (x0 + x1) // 2, (y0 + y1) // 2)
            if not zone:
                continue
            buckets = per_zone.setdefault(zone, {spawns.DAY: set(), spawns.NIGHT: set()})
            for phase in (spawns.DAY, spawns.NIGHT):
                buckets[phase].update(eid for eid, _w in area.roster(phase))
        self.assertEqual(len(per_zone), 4)
        for zone, buckets in per_zone.items():
            for phase, species in buckets.items():
                self.assertGreaterEqual(len(species), MIN_SPECIES_PER_ZONE_PHASE,
                                        f"{zone} @ {phase}: {sorted(species)}")

    def test_no_area_pool_is_ever_empty_in_either_phase(self):
        for area in self.content.spawn_areas:
            for phase in (spawns.DAY, spawns.NIGHT):
                self.assertTrue(area.roster(phase), (area.id, phase))
                tile = self._center(area.id)
                self.assertTrue(self._pool(tile, phase), (area.id, phase))

    def test_night_species_corridors_reach_the_band_they_roll_in(self):
        for area in self.content.spawn_areas:
            if not area.night_enemies or not (area.level_min or area.level_max):
                continue
            low = area.level_min or area.level_max
            high = area.level_max or area.level_min
            for enemy_id, _weight in area.night_enemies:
                enemy = self.content.enemies[enemy_id]
                corridor_low = enemy.level_min or enemy.level
                corridor_high = enemy.level_max or enemy.level
                self.assertFalse(corridor_high < low or corridor_low > high,
                                 f"{area.id}: {enemy_id} {corridor_low}-{corridor_high} "
                                 f"cannot reach {low}-{high}")

    def test_the_trait_rule_holds_beast_and_plant_stand_down_at_night(self):
        # A purely day-affine species (beast/plant, no night tag) must not appear
        # in any night roster.
        for area in self.content.spawn_areas:
            for enemy_id, _weight in area.roster(spawns.NIGHT):
                tags = set(self.content.enemies[enemy_id].tags)
                if tags & DAY_TAGS and not tags & NIGHT_TAGS:
                    self.fail(f"{area.id} night roster keeps day-only {enemy_id} {sorted(tags)}")

    def test_no_boss_ever_enters_a_night_roster(self):
        for area in self.content.spawn_areas:
            for enemy_id, _weight in area.roster(spawns.NIGHT):
                self.assertFalse(self.content.enemies[enemy_id].boss, (area.id, enemy_id))
        for place_id, pool in self.content.spawn_fallbacks_night.items():
            for enemy_id, _weight in pool:
                self.assertFalse(self.content.enemies[enemy_id].boss, (place_id, enemy_id))

    def test_night_fallbacks_exist_for_every_day_fallback_region(self):
        self.assertEqual(set(self.content.spawn_fallbacks_night),
                         set(self.content.spawn_fallbacks))

    def test_an_uncovered_tile_uses_the_regions_night_fallback(self):
        region = sorted(self.content.spawn_fallbacks)[0]
        far = (0, self.content.spawn_areas[0].rect[3] + 10_000)   # covered by nothing
        day = self._pool(far, spawns.DAY, region)
        night = self._pool(far, spawns.NIGHT, region)
        self.assertEqual(day, self.content.spawn_fallbacks[region])
        self.assertEqual(night, self.content.spawn_fallbacks_night[region])
        self.assertNotEqual(day, night)

    def test_an_area_without_a_night_roster_rolls_the_day_one(self):
        bare = spawns.SpawnArea(id="x", rect=(0, 0, 1, 1), enemies=(("giant_rat", 10),))
        self.assertEqual(bare.roster(spawns.NIGHT), bare.enemies)
        self.assertEqual(bare.roster(spawns.DAY), bare.enemies)
        self.assertEqual(
            spawns.pool_at((bare,), {}, (0, 0), "", phase=spawns.NIGHT),
            (("giant_rat", 10),))


class PhaseWiringTests(SpawnPhaseBase):
    def test_dusk_already_rolls_the_night_roster(self):
        self.assertEqual(daynight.spawn_phase("dusk"), spawns.NIGHT)
        self.assertEqual(daynight.spawn_phase("night"), spawns.NIGHT)
        self.assertEqual(daynight.spawn_phase("dawn"), spawns.DAY)
        self.assertEqual(daynight.spawn_phase("day"), spawns.DAY)

    def test_the_phase_names_match_the_clocks_vocabulary(self):
        self.assertEqual({spawns.DAY, spawns.NIGHT},
                         {daynight.spawn_phase(p) for p in daynight.PHASE_ORDER})

    def test_seeded_night_spawns_are_deterministic(self):
        tile = self._center("heath_ghoul_west")
        pool = self._pool(tile, spawns.NIGHT)
        band = spawns.band_at(self.content.spawn_areas, tile)
        runs = []
        for _ in range(2):
            rng = random.Random(4242)
            sequence = []
            for _ in range(25):
                picked = spawns.weighted_pick(pool, rng)
                level = roll_enemy_level(self.content.enemies[picked], rng, band=band)
                sequence.append((picked, level))
            runs.append(sequence)
        self.assertEqual(runs[0], runs[1])
        self.assertGreater(len({species for species, _level in runs[0]}), 1)

    def test_the_engine_spawns_night_species_at_night(self):
        # End to end through create_encounter: the heath's day beast is gone and
        # the night's spirits are present, at the same level band.
        engine = GameEngine(content=self.content, rng=random.Random(11))
        engine.start_new_game("Hero", "fighter")
        tile = self._center("heath_ghoul_west")
        band = spawns.band_at(self.content.spawn_areas, tile)
        seen = {}
        for phase in (spawns.DAY, spawns.NIGHT):
            pool = self._pool(tile, phase)
            species, levels = set(), []
            for _ in range(120):
                enemy = engine.create_encounter(pool=pool, band=band, zone="grave_heath")
                species.add(enemy.id)
                levels.append(enemy.level)
            seen[phase] = species
            self.assertGreaterEqual(min(levels), band[0], phase)
            self.assertLessEqual(max(levels), band[1], phase)
        self.assertIn("grave_hound", seen[spawns.DAY])       # the beast walks by day
        self.assertNotIn("grave_hound", seen[spawns.NIGHT])  # and not after dark
        self.assertIn("shade", seen[spawns.NIGHT])

    def test_the_bounty_roster_is_unaffected(self):
        # B135e rolls bounties from zone_enemies, built from the DAY rosters. No
        # species is night-exclusive to a zone, so no bounty can name an enemy the
        # player cannot find in daylight.
        for area in self.content.spawn_areas:
            x0, y0, x1, y1 = area.rect
            zone = _theme_for_tile(self.themes, (x0 + x1) // 2, (y0 + y1) // 2)
            if not zone:
                continue
            for enemy_id, _weight in area.roster(spawns.NIGHT):
                self.assertIn(enemy_id, self.content.zone_enemies[zone],
                              f"{enemy_id} is night-only in {zone} — bounties cannot name it")


if __name__ == "__main__":
    unittest.main()
