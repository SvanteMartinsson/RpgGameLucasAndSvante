import unittest

from rpg_game.core import simulation


class CombatSimulationTests(unittest.TestCase):
    def test_single_fight_is_seed_deterministic(self):
        first = simulation.simulate_fight("fighter", "giant_rat", seed=12)
        second = simulation.simulate_fight("fighter", "giant_rat", seed=12)

        self.assertEqual(first, second)
        self.assertIn(first.outcome, {"victory", "defeat", "timeout"})
        self.assertGreater(first.turns, 0)

    def test_matchup_reports_bounded_rates_and_counts(self):
        result = simulation.simulate_matchup("fighter", "giant_rat", trials=10, seed=1)

        self.assertEqual(result.trials, 10)
        self.assertEqual(result.victories + result.defeats + result.timeouts, 10)
        self.assertGreaterEqual(result.win_rate, 0.0)
        self.assertLessEqual(result.win_rate, 1.0)
        self.assertGreater(result.average_turns, 0.0)

    def test_matrix_uses_requested_classes_and_enemies(self):
        results = simulation.simulate_matrix(["fighter", "rogue"], ["giant_rat"], trials=2)

        self.assertEqual([(row.class_id, row.enemy_id, row.trials) for row in results], [
            ("fighter", "giant_rat", 2),
            ("rogue", "giant_rat", 2),
        ])


if __name__ == "__main__":
    unittest.main()
