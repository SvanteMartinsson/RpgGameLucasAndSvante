import unittest

from rpg_game.core.progression import xp_required_for_level


class ProgressionTests(unittest.TestCase):
    def test_xp_thresholds_use_half_up_curve(self):
        thresholds = [xp_required_for_level(level) for level in range(1, 6)]

        self.assertEqual(thresholds, [100, 150, 225, 338, 506])


if __name__ == "__main__":
    unittest.main()
