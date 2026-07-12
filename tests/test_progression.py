import unittest
import random

from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine
from rpg_game.core.progression import award_xp, level_scaled_xp, xp_required_for_level


class ProgressionTests(unittest.TestCase):
    def test_xp_thresholds_front_load_early_levels_then_use_half_up_curve(self):
        thresholds = [xp_required_for_level(level) for level in range(1, 6)]

        self.assertEqual(thresholds, [10, 30, 70, 338, 506])

    def test_level_three_and_later_thresholds_remain_on_existing_curve(self):
        thresholds = [xp_required_for_level(level) for level in range(3, 8)]

        self.assertEqual(thresholds, [70, 338, 506, 759, 1139])

    def test_xp_curve_is_strictly_monotonic(self):
        thresholds = [xp_required_for_level(level) for level in range(1, 13)]
        self.assertTrue(all(left < right for left, right in zip(thresholds, thresholds[1:])))

    def test_exponential_tail_from_level_four_is_unchanged(self):
        self.assertEqual([xp_required_for_level(level) for level in range(4, 8)],
                         [338, 506, 759, 1139])

    def test_enemy_levels_are_loaded_from_progression_table(self):
        enemies = load_content().enemies

        self.assertEqual(enemies["giant_rat"].level, 1)
        self.assertEqual(enemies["undead"].level, 2)
        self.assertEqual(enemies["cave_bear"].level, 3)
        self.assertEqual(enemies["undead_priest"].level, 3)
        self.assertEqual(enemies["plague_acolyte"].level, 4)

    def test_level_scaled_xp_uses_level_diff_multiplier_and_caps(self):
        self.assertEqual(level_scaled_xp(20, player_level=3, enemy_level=3), 20)
        self.assertEqual(level_scaled_xp(20, player_level=1, enemy_level=4), 35)
        self.assertEqual(level_scaled_xp(20, player_level=3, enemy_level=1), 10)
        self.assertEqual(level_scaled_xp(20, player_level=1, enemy_level=9), 40)
        self.assertEqual(level_scaled_xp(20, player_level=9, enemy_level=1), 5)

    def test_level_scaled_xp_is_never_zero(self):
        self.assertEqual(level_scaled_xp(1, player_level=99, enemy_level=1), 1)

    def test_xp_overflow_carries_through_front_loaded_thresholds(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")

        levels = award_xp(engine.player, 45)

        self.assertEqual(levels, 2)
        self.assertEqual(engine.player.level, 3)
        self.assertEqual(engine.player.xp, 5)
        self.assertEqual(engine.player.xp_required, 70)

    def test_two_giant_rat_wins_reach_level_two_with_talent_point(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Hero", "fighter")

        for _ in range(2):
            enemy = engine.content.enemies["giant_rat"].create_enemy()
            engine._handle_victory(enemy, [])

        self.assertEqual(engine.player.level, 2)
        self.assertEqual(engine.player.xp, 0)
        self.assertEqual(engine.player.talent_points, 1)
        self.assertGreater(len(engine.available_talents()), 0)

    def test_every_class_has_available_talent_at_level_two(self):
        content = load_content()

        for class_id in content.classes:
            with self.subTest(class_id=class_id):
                engine = GameEngine(content=content)
                engine.start_new_game("Hero", class_id)
                engine.player.level = 2
                engine.player.talent_points = 1

                self.assertGreater(len(engine.available_talents()), 0)


if __name__ == "__main__":
    unittest.main()
