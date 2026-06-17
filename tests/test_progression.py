import unittest

from rpg_game.core.data_loader import load_content
from rpg_game.core.progression import level_scaled_xp, xp_required_for_level


class ProgressionTests(unittest.TestCase):
    def test_xp_thresholds_use_half_up_curve(self):
        thresholds = [xp_required_for_level(level) for level in range(1, 6)]

        self.assertEqual(thresholds, [100, 150, 225, 338, 506])

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


if __name__ == "__main__":
    unittest.main()
