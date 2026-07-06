"""B55: encounter pacing as core logic.

Locks the exact B12 heatmap the shell used to compute inline: 0 on safe tiles
and next to a town anchor, a (dist-1)/3 ramp to the zone base, x0.6 on roads —
plus the rng-stream contract (no draw in town, exactly one per wild step) and
the journey measures the simulator uses.
"""

import random
import unittest

from rpg_game.core import encounters
from rpg_game.core.encounters import EncounterMap


def _map(**kwargs):
    base = dict(town_tiles=frozenset({(10, 10)}), safe_tiles=frozenset(),
                path_tiles=frozenset())
    base.update({k: frozenset(v) for k, v in kwargs.items()})
    return EncounterMap(**base)


class RateCurveTests(unittest.TestCase):
    BASE = 0.06

    def rate(self, emap, tile):
        return encounters.encounter_rate_at(emap, tile, self.BASE)

    def test_zero_on_town_and_adjacent(self):
        emap = _map()
        self.assertEqual(self.rate(emap, (10, 10)), 0.0)   # the anchor itself
        self.assertEqual(self.rate(emap, (11, 11)), 0.0)   # dist 1 (Chebyshev)

    def test_ramps_to_full_over_three_tiles(self):
        emap = _map()
        self.assertAlmostEqual(self.rate(emap, (12, 10)), self.BASE * (1 / 3))
        self.assertAlmostEqual(self.rate(emap, (13, 10)), self.BASE * (2 / 3))
        self.assertAlmostEqual(self.rate(emap, (14, 10)), self.BASE)          # full
        self.assertAlmostEqual(self.rate(emap, (30, 30)), self.BASE)          # stays full

    def test_safe_tiles_override_everything(self):
        emap = _map(safe_tiles={(30, 30)})
        self.assertEqual(self.rate(emap, (30, 30)), 0.0)

    def test_road_tiles_reduce_by_the_path_factor(self):
        emap = _map(path_tiles={(14, 10)})
        self.assertAlmostEqual(self.rate(emap, (14, 10)), self.BASE * encounters.PATH_FACTOR)

    def test_no_towns_means_full_rate(self):
        emap = EncounterMap(town_tiles=frozenset())
        self.assertAlmostEqual(self.rate(emap, (0, 0)), self.BASE)


class RngStreamTests(unittest.TestCase):
    class CountingRng(random.Random):
        draws = 0

        def random(self):
            self.draws += 1
            return super().random()

    def test_in_town_consumes_no_draw(self):
        rng = self.CountingRng(1)
        hit = encounters.should_encounter(_map(), (10, 10), 1.0, rng, in_town=True)
        self.assertFalse(hit)
        self.assertEqual(rng.draws, 0)     # stream-identical to the pre-B55 shell

    def test_wild_step_consumes_exactly_one_draw(self):
        rng = self.CountingRng(1)
        encounters.should_encounter(_map(), (30, 30), 1.0, rng)
        self.assertEqual(rng.draws, 1)

    def test_rate_one_always_fires_far_from_town(self):
        self.assertTrue(encounters.should_encounter(_map(), (30, 30), 1.0, random.Random(3)))


class JourneyTests(unittest.TestCase):
    def test_encounter_load_is_the_sum_of_step_rates(self):
        emap = _map()
        route = [(14, 10), (15, 10), (11, 10)]   # full + full + safe-adjacent(0)
        self.assertAlmostEqual(encounters.journey_encounter_load(emap, route, 0.06), 0.12)

    def test_simulated_journey_is_seed_deterministic(self):
        emap = _map()
        route = [(x, 30) for x in range(60)]
        a = encounters.simulate_journey(emap, route, 0.5, random.Random(7))
        b = encounters.simulate_journey(emap, route, 0.5, random.Random(7))
        self.assertEqual(a, b)
        self.assertGreater(a, 0)


if __name__ == "__main__":
    unittest.main()
