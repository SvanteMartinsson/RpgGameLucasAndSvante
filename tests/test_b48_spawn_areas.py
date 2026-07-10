"""B48: drawn spawn areas — union-of-overlaps pools + weighted spawning.

Locks: the authored data loads (22 areas, 4 fallbacks), pool_at unions
overlapping areas (weights sum) and falls back per wild region, weighted picks
honour the pool through the real engine path (with the region level band still
applied), the validator rejects bad data (unknown enemy, boss in pool,
non-positive weight, malformed rect, duplicates), the tile-less path is
untouched, and the design intents (worg rare, hag confined, holy compensation,
Rotfang's moved lair). The pygame shell test locks maybe_encounter feeding the
tile pool. Pygame parts skip without pygame.
"""

import os
import random
import unittest

from rpg_game.core import data_loader, spawns
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine
from rpg_game.core.spawns import SpawnArea

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

CONTENT = load_content()


def _pool(tile, region):
    return spawns.pool_at(CONTENT.spawn_areas, CONTENT.spawn_fallbacks, tile, region)


class SpawnDataTests(unittest.TestCase):
    def test_all_areas_and_fallbacks_load(self):
        self.assertEqual(len(CONTENT.spawn_areas), 22)
        self.assertEqual(set(CONTENT.spawn_fallbacks),
                         {"burg_54", "burg_146", "burg_320", "burg_121"})

    def test_pure_area_gives_only_its_roster(self):
        self.assertEqual(_pool((10, 10), "burg_54"), (("wild_stag", 60),))

    def test_overlap_unions_and_sums_weights(self):
        pool = dict(_pool((20, 50), "burg_54"))     # stag_west ∩ generalists
        self.assertEqual(pool["wild_stag"], 60)
        self.assertEqual(pool["wild_dog"], 25)
        self.assertEqual(len(pool), 5)
        # the same enemy in two areas sums: cave_bear in beast_north ∩ goblin_west
        pool = dict(_pool((100, 30), "burg_146"))
        self.assertEqual(pool["cave_bear"], 60)     # 30 + 30

    def test_gap_falls_back_to_the_wild_region_pool(self):
        pool = _pool((110, 175), "burg_121")        # heath mid-strip: no area
        self.assertEqual(dict(pool), {"ghoul": 35, "grave_hound": 35})
        self.assertEqual(_pool((110, 175), "no_such_region"), ())

    def test_weighted_pick_is_deterministic_and_covers_the_pool(self):
        pool = (("a", 1), ("b", 3))
        rng = random.Random(0)
        picks = {spawns.weighted_pick(pool, random.Random(seed)) for seed in range(40)}
        self.assertEqual(picks, {"a", "b"})
        self.assertEqual(spawns.weighted_pick(pool, random.Random(7)),
                         spawns.weighted_pick(pool, random.Random(7)))

    def test_design_intents_hold(self):
        # hollow worg: rare — strictly the lightest weight wherever it appears
        worg_areas = [a for a in CONTENT.spawn_areas
                      if any(e == "hollow_worg" for e, _w in a.enemies)]
        self.assertEqual(len(worg_areas), 2)        # worg_column + palegate
        for area in worg_areas:
            weights = dict(area.enemies)
            self.assertLess(weights["hollow_worg"], min(w for e, w in area.enemies
                                                        if e != "hollow_worg"))
        # bog hag: confined to her one pocket
        hag_areas = [a.id for a in CONTENT.spawn_areas
                     if any(e == "bog_hag" for e, _w in a.enemies)]
        self.assertEqual(hag_areas, ["mire_hag_bog"])
        # holy compensation: gravewarden on the wight AND in the tier-5 chest
        wight = CONTENT.enemies["cursed_wight"]
        self.assertTrue(any(r["item_id"] == "gravewarden_blade" for r in wight.loot_table))
        chest = CONTENT.chests["chest_heath_4"]
        self.assertTrue(any(r["item_id"] == "gravewarden_blade" for r in chest.loot_table))

    def test_rotfang_lair_moved_to_the_southwest(self):
        self.assertEqual(tuple(CONTENT.bosses["rotfang"].lair_tile), (14, 88))


class SpawnValidatorTests(unittest.TestCase):
    def _validate(self, areas, fallbacks=None):
        data_loader._validate_spawns(tuple(areas), fallbacks or {},
                                     CONTENT.enemies, CONTENT.places)

    def test_unknown_enemy_fails(self):
        with self.assertRaises(ValueError):
            self._validate([SpawnArea("x", (0, 0, 1, 1), (("nope", 5),))])

    def test_boss_in_pool_fails(self):
        with self.assertRaises(ValueError):
            self._validate([SpawnArea("x", (0, 0, 1, 1), (("boss_rotfang", 5),))])

    def test_non_positive_weight_fails(self):
        with self.assertRaises(ValueError):
            self._validate([SpawnArea("x", (0, 0, 1, 1), (("wild_dog", 0),))])

    def test_malformed_rect_and_duplicates_fail(self):
        with self.assertRaises(ValueError):
            self._validate([SpawnArea("x", (5, 0, 1, 1), (("wild_dog", 5),))])
        area = SpawnArea("x", (0, 0, 1, 1), (("wild_dog", 5),))
        with self.assertRaises(ValueError):
            self._validate([area, area])

    def test_bad_fallback_fails(self):
        with self.assertRaises(ValueError):
            self._validate([], {"no_place": (("wild_dog", 5),)})
        with self.assertRaises(ValueError):
            self._validate([], {"burg_54": ()})


class SpawnEngineTests(unittest.TestCase):
    def _engine(self, place_id, seed=0):
        engine = GameEngine(content=CONTENT, rng=random.Random(seed))
        engine.start_new_game("Hero", "fighter")
        engine.player.current_place_id = place_id
        return engine

    def test_pooled_encounter_spawns_from_the_pool_with_the_region_band(self):
        engine = self._engine("burg_121")
        for seed in range(12):
            engine.rng = random.Random(seed)
            enemy = engine.create_encounter(pool=(("undead", 1),))
            self.assertEqual(enemy.id, "undead")
            self.assertTrue(6 <= enemy.level <= 12)   # zonbandet styr nivån

    def test_tile_less_path_is_unchanged(self):
        engine = self._engine("burg_121", seed=3)
        enemy = engine.create_encounter()             # classic place pool + rare slot
        place = CONTENT.places["burg_121"]
        self.assertIn(enemy.id, set(place.encounters) | {place.rare_encounter})


try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class SpawnOverworldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.app = OverworldApp()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_maybe_encounter_spawns_from_the_tile_area(self):
        self.app.encounter_rate_at = lambda tile: 1.0   # force the roll
        self.app.world.set_tile(10, 10)                 # pure stag-väst
        self.app.sync_location()
        enemy = None
        for seed in range(10):                          # B67: skip event slots
            self.app.engine.rng = random.Random(seed)
            enemy = self.app.maybe_encounter()
            if enemy is not None:
                break
            self.app.active_event = None
            self.app.mode = "walk"
        self.assertEqual(enemy.id, "wild_stag")

    def test_maybe_encounter_mixes_in_overlaps(self):
        self.app.encounter_rate_at = lambda tile: 1.0
        self.app.world.set_tile(20, 50)                 # stag ∩ generalisterna
        self.app.sync_location()
        seen = set()
        for seed in range(40):
            self.app.engine.rng = random.Random(seed)
            enemy = self.app.maybe_encounter()
            if enemy is None:            # B67: ~10% of fired slots become events
                self.app.active_event = None
                self.app.mode = "walk"
                continue
            seen.add(enemy.id)
        self.assertIn("wild_stag", seen)
        self.assertTrue(seen & {"wild_dog", "giant_rat", "giant_spider", "goblin_scrapper"})
        self.assertLessEqual(seen, {"wild_stag", "wild_dog", "giant_rat",
                                    "giant_spider", "goblin_scrapper"})


if __name__ == "__main__":
    unittest.main()
