"""Per-enemy level ranges with stat scaling — wild enemies only."""

import random
import unittest
from unittest.mock import patch

from rpg_game.core import combat, world
from rpg_game.core.game import GameEngine
from rpg_game.core.progression import round_half_up


class EnemyLevelScalingTest(unittest.TestCase):
    def setUp(self):
        # Isolate level-scaling math from the global HP multiplier (tested
        # separately); 1.0 reproduces the pre-multiplier scaling values.
        multiplier = patch("rpg_game.core.progression.ENEMY_HP_MULTIPLIER", 1.0)
        multiplier.start()
        self.addCleanup(multiplier.stop)
        self.engine = GameEngine()
        self.engine.start_new_game("Hero", "fighter")

    # -- roll + scale helpers ----------------------------------------------

    def test_roll_stays_within_template_range(self):
        rat = self.engine.content.enemies["giant_rat"]  # 1..5
        rng = random.Random(7)
        rolls = {world.roll_enemy_level(rat, rng) for _ in range(500)}
        self.assertEqual(min(rolls), 1)
        self.assertEqual(max(rolls), 5)
        self.assertTrue(rolls <= {1, 2, 3, 4, 5})

    def test_no_range_rolls_the_fixed_level(self):
        arena = self.engine.content.enemies["arena_ser_kaela_voss"]  # level 5, no range
        rng = random.Random(3)
        self.assertEqual({world.roll_enemy_level(arena, rng) for _ in range(50)}, {5})

    def test_scaling_grows_hp_and_power_with_round_half_up(self):
        enemy = self.engine.content.enemies["giant_rat"].create_enemy()  # base L1: hp20 dmg6
        world.scale_enemy_to_level(enemy, base_level=1, target_level=5)
        self.assertEqual(enemy.level, 5)
        self.assertEqual(enemy.max_hp, round_half_up(20 * (1 + world.HP_GROWTH_PER_LEVEL * 4)))  # 36
        self.assertEqual(enemy.hp, enemy.max_hp)
        self.assertEqual(enemy.damage, round_half_up(6 * (1 + world.DAMAGE_GROWTH_PER_LEVEL * 4)))  # 9

    def test_scaling_is_a_noop_at_base_level(self):
        enemy = self.engine.content.enemies["giant_rat"].create_enemy()
        world.scale_enemy_to_level(enemy, base_level=1, target_level=1)
        self.assertEqual((enemy.level, enemy.max_hp, enemy.damage), (1, 20, 6))

    # -- wild spawn path ----------------------------------------------------

    def test_wild_encounter_rolls_and_scales(self):
        self.engine.player.current_place_id = "burg_54"  # wild region: giant_rat/undead
        self.engine.rng = random.Random(7)
        seen_levels = set()
        for _ in range(400):
            enemy = self.engine.create_encounter()
            seen_levels.add((enemy.id, enemy.level))
            if enemy.id == "giant_rat":
                self.assertIn(enemy.level, range(1, 6))
                if enemy.level == 1:
                    self.assertEqual((enemy.max_hp, enemy.damage), (20, 6))
                if enemy.level == 5:
                    self.assertEqual((enemy.max_hp, enemy.damage), (36, 9))
        # the range actually varied
        rat_levels = {lvl for eid, lvl in seen_levels if eid == "giant_rat"}
        self.assertGreater(len(rat_levels), 1)

    def test_identify_reports_rolled_level_and_scaled_stats(self):
        self.engine.player.current_place_id = "burg_54"
        self.engine.rng = random.Random(7)
        enemy = None
        while enemy is None or enemy.id != "giant_rat" or enemy.level == 1:
            enemy = self.engine.create_encounter()
        reveal = combat.identify_enemy(enemy, self.engine.content.actions)
        self.assertEqual(reveal.level, enemy.level)
        self.assertEqual(reveal.power, enemy.damage)
        self.assertGreater(enemy.max_hp, 20)  # scaled above base

    # -- tournament opponents stay fixed -----------------------------------

    def test_tournament_opponents_never_roll_or_scale(self):
        # Tournament opponents keep a FIXED level (no wild level-roll) and are fully
        # deterministic across calls. The B13 per-instance buff adjusts hp/armour/
        # crit/damage, but the level is never rolled/scaled.
        self.engine.rng = random.Random(1)
        tournament = self.engine.content.tournaments["fongorinos_iron_ring"]
        for index, enemy_id in enumerate(tournament.opponent_ids):
            template = self.engine.content.enemies[enemy_id]
            results = {(o.level, o.max_hp, o.damage, o.armor, o.crit_chance)
                       for o in (self.engine.create_tournament_opponent(tournament, index)
                                 for _ in range(20))}
            self.assertEqual(len(results), 1)                       # deterministic, no roll
            self.assertEqual(next(iter(results))[0], template.level)  # level never scaled


if __name__ == "__main__":
    unittest.main()
