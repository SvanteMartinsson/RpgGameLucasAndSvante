"""ZONE2 step 2a: western forest beasts + a regional (higher) level band.

Data-driven, reusing the bruiser/telegraph archetypes. Core pools and bands are
unchanged.
"""

import random
import unittest

from rpg_game.core import combat, world
from rpg_game.core.entities import EffectSpec
from rpg_game.core.game import GameEngine

NEW_BEASTS = ("dire_wolf", "wild_boar", "treant")
WEST = "burg_146"   # western wild region (Rotequero)
CORE = "burg_54"    # core wild region (Guaredama)


class Zone2ForestTest(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine()
        self.engine.start_new_game("Hero", "fighter")

    # -- the beasts exist and load -----------------------------------------

    def test_new_beasts_load(self):
        for beast in NEW_BEASTS:
            self.assertIn(beast, self.engine.content.enemies)

    # -- they spawn in the west, not the core ------------------------------

    def test_beasts_are_in_western_pool_only(self):
        west = set(self.engine.content.places[WEST].encounters)
        core = set(self.engine.content.places[CORE].encounters)
        self.assertTrue(set(NEW_BEASTS) <= west)
        self.assertFalse(set(NEW_BEASTS) & core)

    def test_beasts_spawn_when_in_the_west(self):
        self.engine.rng = random.Random(3)
        self.engine.player.current_place_id = WEST
        spawned = {self.engine.create_encounter().id for _ in range(800)}
        self.assertTrue(set(NEW_BEASTS) <= spawned)

    # -- regional level band, core unchanged -------------------------------

    def test_western_spawns_roll_the_higher_regional_band(self):
        self.engine.rng = random.Random(3)
        self.engine.player.current_place_id = WEST
        levels = {self.engine.create_encounter().level for _ in range(800)}
        self.assertGreaterEqual(min(levels), 5)
        self.assertLessEqual(max(levels), 10)

    def test_core_shared_enemy_bands_unchanged(self):
        core = self.engine.content.places[CORE]
        undead = self.engine.content.enemies["undead"]
        bear = self.engine.content.enemies["cave_bear"]
        u = {world.roll_enemy_level(undead, random.Random(i), region=core) for i in range(300)}
        c = {world.roll_enemy_level(bear, random.Random(i), region=core) for i in range(300)}
        self.assertEqual((min(u), max(u)), (2, 6))
        self.assertEqual((min(c), max(c)), (3, 7))

    def test_no_regional_band_falls_back_to_type_band(self):
        # A core place carries no band, so the enemy type's band applies.
        rat = self.engine.content.enemies["giant_rat"]
        rolls = {world.roll_enemy_level(rat, random.Random(i), region=self.engine.content.places[CORE])
                 for i in range(300)}
        self.assertEqual((min(rolls), max(rolls)), (1, 5))

    # -- treant resistances -------------------------------------------------

    def test_treant_is_weak_to_fire_and_resists_frost(self):
        treant = self.engine.content.enemies["treant"].create_enemy()
        fire = EffectSpec(type="damage", scale="flat", magnitude=10, damage_type="fire")
        frost = EffectSpec(type="damage", scale="flat", magnitude=10, damage_type="frost")
        self.assertEqual(combat.calculate_effect_damage(self.engine.player, treant, None, fire), 20)   # plant: fire +3 -> x2.0
        self.assertEqual(combat.calculate_effect_damage(self.engine.player, treant, None, frost), 7)   # plant: frost -1 -> x0.65

    # -- archetype AI (bruiser + telegraph) --------------------------------

    def test_dire_wolf_acts_before_cave_bear_and_mauls(self):
        wolf = self.engine.content.enemies["dire_wolf"].create_enemy()
        bear = self.engine.content.enemies["cave_bear"].create_enemy()
        self.assertGreater(wolf.speed, bear.speed)
        first, _second = combat.ordered_by_speed(wolf, bear)
        self.assertIs(first, wolf)

    def test_wild_boar_telegraphs_its_charge_then_releases(self):
        boar = self.engine.content.enemies["wild_boar"].create_enemy()
        rng = random.Random(1)
        before = self.engine.player.hp
        # Round 1: telegraph — charges, deals no damage yet.
        combat.enemy_take_turn(boar, self.engine.player, self.engine.content.actions, rng)
        self.assertEqual(boar.charging_action_id, "boar_charge")
        self.assertEqual(self.engine.player.hp, before)
        # Round 2: releases the charged hit.
        combat.enemy_take_turn(boar, self.engine.player, self.engine.content.actions, rng)
        self.assertEqual(boar.charging_action_id, "")
        self.assertLess(self.engine.player.hp, before)


if __name__ == "__main__":
    unittest.main()
