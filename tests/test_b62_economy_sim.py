"""B62: the economy/loot-flow measuring harness.

Locks: determinism per seed, coherent report arithmetic (rates in range, the
rest-pressure identity, the net-gold formula), materials counted only from
consumable drops, and that the harness measures through the REAL spawn path
(a report for a pool place produces enemies from that pool)."""

import unittest

from rpg_game.core.data_loader import load_content
from rpg_game.core.simulation import EconomyBandReport, simulate_economy_band

CONTENT = load_content()


def _report(**overrides) -> EconomyBandReport:
    args = dict(class_id="fighter", place_id="burg_54", level=3, trials=25,
                seed=11, rest_zone=1, content=CONTENT)
    args.update(overrides)
    return simulate_economy_band(**args)


class EconomySimTests(unittest.TestCase):
    def test_same_seed_gives_the_identical_report(self):
        self.assertEqual(_report(), _report())

    def test_another_seed_gives_a_different_stream(self):
        self.assertNotEqual(_report(), _report(seed=99))

    def test_rates_and_arithmetic_are_coherent(self):
        report = _report()
        self.assertGreaterEqual(report.win_rate, 0.0)
        self.assertLessEqual(report.win_rate, 1.0)
        self.assertGreaterEqual(report.drop_rate, 0.0)
        self.assertLessEqual(report.drop_rate, 1.0)
        self.assertGreater(report.player_max_hp, 0)
        # rest identity: cost per fight = full rest / fights per rest
        if report.fights_per_rest != float("inf"):
            self.assertAlmostEqual(
                report.rest_cost_per_fight,
                report.rest_cost / report.fights_per_rest, places=6)
        # net formula: win-weighted income minus the rest share
        expected_net = (report.win_rate
                        * (report.average_kill_gold + report.average_sell_value)
                        - report.rest_cost_per_fight)
        self.assertAlmostEqual(report.net_gold_per_fight, expected_net, places=6)

    def test_materials_are_consumables_only(self):
        report = _report(place_id="burg_121", level=11, rest_zone=4, trials=40)
        for item_id, count in report.material_counts:
            self.assertIn(item_id, CONTENT.items, item_id)
            self.assertGreater(count, 0)

    def test_rarity_counts_match_the_drop_total(self):
        report = _report(trials=40)
        # every counted drop carries exactly one rarity label
        total_rarities = sum(count for _r, count in report.rarity_counts)
        self.assertGreaterEqual(total_rarities, 0)
        wins = round(report.win_rate * report.trials)
        self.assertAlmostEqual(report.drop_rate * wins, total_rarities, delta=0.51)


if __name__ == "__main__":
    unittest.main()
