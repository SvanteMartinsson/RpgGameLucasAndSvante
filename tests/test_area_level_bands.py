"""Per-spawn-area level bands (nattbatch 2026-07-11): AREA > region > template.

The band is optional data on a spawn area; WITHOUT one, every seeded roll is
byte-identical to the pre-band behaviour (guard tests below). No area sets a
band in data yet — the geography pass proposes values separately.
"""

import dataclasses
import random
import unittest

from rpg_game.core import spawns, world
from rpg_game.core.data_loader import load_content

CONTENT = load_content()

# A real wild template with its own band, and a real region place to vary.
TEMPLATE = dataclasses.replace(
    next(t for t in CONTENT.enemies.values() if t.level_min or t.level_max),
    level_min=2, level_max=4, level=3)
REGION = next(p for p in CONTENT.places.values() if p.encounters and not p.locked)


def _region(level_min=0, level_max=0):
    return dataclasses.replace(REGION, level_min=level_min, level_max=level_max)


def _area(rect=(0, 0, 9, 9), level_min=0, level_max=0, area_id="a"):
    return spawns.SpawnArea(id=area_id, rect=rect,
                            enemies=((TEMPLATE.id, 1),),
                            level_min=level_min, level_max=level_max)


class RollPrecedenceTests(unittest.TestCase):
    def test_area_band_outranks_region_and_template(self):
        rng = random.Random(7)
        levels = {world.roll_enemy_level(TEMPLATE, rng, region=_region(5, 6),
                                         band=(11, 12)) for _ in range(40)}
        self.assertTrue(levels <= {11, 12} and levels)

    def test_region_band_still_wins_without_area_band(self):
        rng = random.Random(7)
        levels = {world.roll_enemy_level(TEMPLATE, rng, region=_region(5, 6),
                                         band=None) for _ in range(40)}
        self.assertTrue(levels <= {5, 6} and levels)

    def test_template_band_is_the_last_fallback(self):
        rng = random.Random(7)
        levels = {world.roll_enemy_level(TEMPLATE, rng, region=_region(),
                                         band=None) for _ in range(40)}
        self.assertTrue(levels <= {2, 3, 4} and levels)

    def test_fixed_band_rolls_exactly_that_level(self):
        rng = random.Random(7)
        self.assertEqual(world.roll_enemy_level(TEMPLATE, rng, band=(8, 8)), 8)


class GuardUnchangedRollsTests(unittest.TestCase):
    """No band => the seeded stream and result are EXACTLY the old behaviour."""

    def test_seeded_rolls_identical_without_band(self):
        for seed in range(20):
            old = random.Random(seed).randint(5, 6)          # pre-band region path
            new = world.roll_enemy_level(TEMPLATE, random.Random(seed),
                                         region=_region(5, 6))
            self.assertEqual(old, new, seed)
            old_t = random.Random(seed).randint(2, 4)        # pre-band template path
            new_t = world.roll_enemy_level(TEMPLATE, random.Random(seed))
            self.assertEqual(old_t, new_t, seed)

    def test_seeded_create_encounter_unchanged_without_band(self):
        from rpg_game.core.game import GameEngine
        for seed in (1, 2, 3):
            spawned = []
            for band in (None, None):   # band=None twice: identical seeded results
                engine = GameEngine(rng=random.Random(seed))
                engine.start_new_game("t", "fighter")
                engine.player.current_place_id = REGION.id
                spawned.append(engine.create_encounter(band=band))
            self.assertEqual((spawned[0].id, spawned[0].level, spawned[0].max_hp),
                             (spawned[1].id, spawned[1].level, spawned[1].max_hp))


class BandAtTests(unittest.TestCase):
    def test_no_covering_band_is_none(self):
        areas = (_area(level_min=0, level_max=0),
                 _area(rect=(50, 50, 60, 60), level_min=3, level_max=5, area_id="far"))
        self.assertIsNone(spawns.band_at(areas, (1, 1)))

    def test_single_area_band(self):
        areas = (_area(level_min=4, level_max=7),)
        self.assertEqual(spawns.band_at(areas, (5, 5)), (4, 7))

    def test_overlapping_bands_union(self):
        areas = (_area(level_min=3, level_max=5, area_id="a"),
                 _area(level_min=6, level_max=9, area_id="b"))
        self.assertEqual(spawns.band_at(areas, (2, 2)), (3, 9))

    def test_banded_and_unbanded_overlap_uses_the_banded(self):
        areas = (_area(area_id="plain"),
                 _area(level_min=6, level_max=8, area_id="banded"))
        self.assertEqual(spawns.band_at(areas, (0, 0)), (6, 8))

    def test_half_open_band_uses_the_set_bound(self):
        self.assertEqual(spawns.band_at((_area(level_min=5),), (0, 0)), (5, 5))
        self.assertEqual(spawns.band_at((_area(level_max=7),), (0, 0)), (7, 7))

    def test_loader_reads_the_authored_bands(self):
        # geo GO 2026-07-12: every area now carries a loaded int band
        self.assertTrue(CONTENT.spawn_areas)
        for area in CONTENT.spawn_areas:
            self.assertIsInstance(area.level_min, int)
            self.assertIsInstance(area.level_max, int)
            self.assertTrue(area.level_min and area.level_max, area.id)


if __name__ == "__main__":
    unittest.main()
