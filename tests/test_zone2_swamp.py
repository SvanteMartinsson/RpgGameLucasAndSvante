"""ZONE2 step 2b: the swamp (deep west) — a distinct deep-x region pocket with
two new enemies. Data only, reusing the bruiser/caster archetypes.
"""

import os
import random
import unittest

from rpg_game.core import combat, world
from rpg_game.core.entities import EffectSpec
from rpg_game.core.game import GameEngine

SWAMP_ENEMIES = ("mutated_mudcrab", "bog_wraith", "tar_beast")
SWAMP = "burg_320"   # deep-west swamp region (Parguillas)
FOREST = "burg_146"  # mid-west forest region (Rotequero)
CORE = "burg_54"     # core wild region


class Zone2SwampTest(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine()
        self.engine.start_new_game("Hero", "fighter")

    def test_swamp_enemies_load(self):
        for enemy in SWAMP_ENEMIES:
            self.assertIn(enemy, self.engine.content.enemies)

    def test_swamp_pool_is_distinct_from_forest_and_core(self):
        swamp = set(self.engine.content.places[SWAMP].encounters)
        self.assertEqual(swamp, set(SWAMP_ENEMIES))
        self.assertFalse(set(SWAMP_ENEMIES) & set(self.engine.content.places[FOREST].encounters))
        self.assertFalse(set(SWAMP_ENEMIES) & set(self.engine.content.places[CORE].encounters))

    def test_forest_and_core_pools_unchanged(self):
        forest = set(self.engine.content.places[FOREST].encounters)
        self.assertEqual(forest, {"undead", "cave_bear", "undead_priest", "dire_wolf", "wild_boar", "treant"})
        self.assertEqual(set(self.engine.content.places[CORE].encounters),
                         {"giant_rat", "undead", "cave_bear", "undead_priest"})

    def test_swamp_spawns_only_swamp_enemies_in_the_regional_band(self):
        self.engine.rng = random.Random(5)
        self.engine.player.current_place_id = SWAMP
        ids, levels = set(), set()
        for _ in range(400):
            enemy = self.engine.create_encounter()
            ids.add(enemy.id)
            levels.add(enemy.level)
        self.assertEqual(ids, set(SWAMP_ENEMIES))
        self.assertGreaterEqual(min(levels), 5)
        self.assertLessEqual(max(levels), 10)

    def test_mudcrab_is_weak_to_both_fire_and_frost(self):
        # beast+swamp flips the mudcrab: beast's fire-bane and swamp's frost-bane
        # partly cancel to a +2 step each, leaving it doubly soft (x1.5/x1.5).
        crab = self.engine.content.enemies["mutated_mudcrab"].create_enemy()
        fire = EffectSpec(type="damage", scale="flat", magnitude=10, damage_type="fire")
        frost = EffectSpec(type="damage", scale="flat", magnitude=10, damage_type="frost")
        self.assertEqual(combat.calculate_effect_damage(self.engine.player, crab, None, fire), 15)   # x1.5
        self.assertEqual(combat.calculate_effect_damage(self.engine.player, crab, None, frost), 15)  # x1.5

    def test_bog_wraith_is_weak_to_frost(self):
        # undead's frost-resist (-1) + swamp's frost-bane (+3) = +2 -> x1.5.
        wraith = self.engine.content.enemies["bog_wraith"].create_enemy()
        frost = EffectSpec(type="damage", scale="flat", magnitude=10, damage_type="frost")
        self.assertEqual(combat.calculate_effect_damage(self.engine.player, wraith, None, frost), 15)  # x1.5

    def test_bog_wraith_telegraphs_its_nuke_then_releases(self):
        wraith = self.engine.content.enemies["bog_wraith"].create_enemy()
        rng = random.Random(1)
        before = self.engine.player.hp
        combat.enemy_take_turn(wraith, self.engine.player, self.engine.content.actions, rng)
        self.assertEqual(wraith.charging_action_id, "wraith_hex")
        self.assertEqual(self.engine.player.hp, before)  # telegraph: no damage yet
        combat.enemy_take_turn(wraith, self.engine.player, self.engine.content.actions, rng)
        self.assertEqual(wraith.charging_action_id, "")
        self.assertLess(self.engine.player.hp, before)


class SwampRegionRoutingTest(unittest.TestCase):
    """The deep-west pocket routes to the swamp; mid-west stays forest."""

    def test_region_lookup_picks_swamp_only_in_the_deep_west(self):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        try:
            import pygame  # noqa: F401
            from rpg_game.presentation.pygame_overworld import ZoneConfig
        except Exception:  # pragma: no cover - import guard
            self.skipTest("pygame/pytmx not installed")
        zone = ZoneConfig.load()
        self.assertEqual(zone.wild_region_at((170, 17)), SWAMP)   # cursed_mire east (x>=159)
        self.assertEqual(zone.wild_region_at((100, 8)), FOREST)   # mork_skog band (83<=x<=158)
        self.assertEqual(zone.wild_region_at((14, 8)), CORE)      # cainos core


if __name__ == "__main__":
    unittest.main()
