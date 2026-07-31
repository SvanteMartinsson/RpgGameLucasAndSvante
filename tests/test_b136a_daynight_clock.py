"""B136a: the day/night clock — phases, movement-time ticking, save migration."""

import random
import unittest

from rpg_game.core import daynight, persistence
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine


_CONTENT = None


def _engine(class_id="fighter", seed=0):
    global _CONTENT
    if _CONTENT is None:
        _CONTENT = load_content()
    engine = GameEngine(content=_CONTENT, rng=random.Random(seed))
    engine.start_new_game("Hero", class_id)
    return engine


class DayNightPhaseBoundaryTests(unittest.TestCase):
    def test_cycle_is_seven_minutes_of_light_and_seven_of_dark(self):
        self.assertAlmostEqual(daynight.CYCLE_SECONDS, 840.0)
        light = daynight.DAWN_SECONDS + daynight.DAY_SECONDS
        dark = daynight.DUSK_SECONDS + daynight.NIGHT_SECONDS
        self.assertAlmostEqual(light, 420.0)
        self.assertAlmostEqual(dark, 420.0)
        # dawn/dusk are the SHORT transitions carved out of those halves.
        for transition in (daynight.DAWN_SECONDS, daynight.DUSK_SECONDS):
            self.assertTrue(30.0 <= transition <= 60.0, transition)

    def test_phase_transitions_land_on_the_accumulated_boundaries(self):
        dawn_end = daynight.DAWN_SECONDS
        day_end = dawn_end + daynight.DAY_SECONDS
        dusk_end = day_end + daynight.DUSK_SECONDS
        cases = [
            (0.0, "dawn"),
            (dawn_end - 0.001, "dawn"),
            (dawn_end, "day"),
            (day_end - 0.001, "day"),
            (day_end, "dusk"),
            (dusk_end - 0.001, "dusk"),
            (dusk_end, "night"),
            (daynight.CYCLE_SECONDS - 0.001, "night"),
        ]
        for seconds, expected in cases:
            self.assertEqual(daynight.phase_at(seconds), expected, seconds)

    def test_morning_is_zero_and_the_cycle_wraps_back_to_it(self):
        self.assertEqual(daynight.phase_at(daynight.MORNING_SECONDS), daynight.MORNING_PHASE)
        self.assertEqual(daynight.phase_at(daynight.CYCLE_SECONDS), "dawn")
        self.assertAlmostEqual(daynight.normalize(daynight.CYCLE_SECONDS + 10.0), 10.0)

    def test_phase_progress_spans_zero_to_one_inside_each_phase(self):
        for phase in daynight.PHASE_ORDER:
            start = daynight.phase_start(phase)
            length = daynight.PHASE_SECONDS[phase]
            self.assertAlmostEqual(daynight.phase_progress(start), 0.0)
            self.assertAlmostEqual(daynight.phase_progress(start + length / 2), 0.5, places=6)
            self.assertLess(daynight.phase_progress(start + length - 0.001), 1.0)

    def test_phase_start_round_trips_every_phase(self):
        for phase in daynight.PHASE_ORDER:
            self.assertEqual(daynight.phase_at(daynight.phase_start(phase)), phase)
        self.assertEqual(daynight.phase_start("nonsense"), daynight.MORNING_SECONDS)

    def test_towns_close_only_at_night_dusk_is_the_warning(self):
        self.assertFalse(daynight.towns_closed("dawn"))
        self.assertFalse(daynight.towns_closed("day"))
        self.assertFalse(daynight.towns_closed("dusk"))
        self.assertTrue(daynight.towns_closed("night"))

    def test_spawn_phase_gives_the_night_roster_from_dusk(self):
        self.assertEqual(daynight.spawn_phase("dawn"), "day")
        self.assertEqual(daynight.spawn_phase("day"), "day")
        self.assertEqual(daynight.spawn_phase("dusk"), "night")
        self.assertEqual(daynight.spawn_phase("night"), "night")

    def test_advance_never_runs_backwards_and_ignores_garbage(self):
        self.assertAlmostEqual(daynight.advance(100.0, 5.0), 105.0)
        self.assertAlmostEqual(daynight.advance(100.0, -5.0), 100.0)
        self.assertAlmostEqual(daynight.advance(100.0, 0.0), 100.0)
        self.assertAlmostEqual(daynight.advance(100.0, float("nan")), 100.0)
        self.assertAlmostEqual(daynight.advance(100.0, float("inf")), 100.0)
        self.assertAlmostEqual(daynight.advance(100.0, "x"), 100.0)
        # wraps rather than growing without bound
        self.assertAlmostEqual(daynight.advance(daynight.CYCLE_SECONDS - 1.0, 2.0), 1.0)


class EngineClockTests(unittest.TestCase):
    def setUp(self):
        self.engine = _engine("fighter")

    def test_a_fresh_game_starts_in_the_morning(self):
        self.assertEqual(self.engine.world_time(), 0.0)
        self.assertEqual(self.engine.world_phase(), "dawn")
        self.assertFalse(self.engine.towns_closed())

    def test_accumulated_movement_time_walks_through_all_four_phases(self):
        seen = [self.engine.world_phase()]
        # 840 s of movement in 1 s steps = exactly one full day.
        for _ in range(int(daynight.CYCLE_SECONDS)):
            phase = self.engine.advance_world_time(1.0)
            if phase != seen[-1]:
                seen.append(phase)
        self.assertEqual(seen, ["dawn", "day", "dusk", "night", "dawn"])

    def test_standing_still_freezes_the_clock(self):
        self.engine.advance_world_time(100.0)
        before = self.engine.world_time()
        for _ in range(1000):        # 1000 frames of NOT moving = no dt fed
            pass
        self.assertEqual(self.engine.world_time(), before)
        self.assertEqual(self.engine.world_phase(), "day")

    def test_the_clock_is_deterministic_and_spends_no_rng(self):
        self.engine.rng = random.Random(1234)
        probe = random.Random(1234)
        for _ in range(500):
            self.engine.advance_world_time(1.7)
        # The engine's stream is untouched: the next draw is still the first draw.
        self.assertEqual(self.engine.rng.random(), probe.random())
        # And the same dt sequence lands on the same time in a second engine.
        other = _engine("fighter")
        for _ in range(500):
            other.advance_world_time(1.7)
        self.assertEqual(other.world_time(), self.engine.world_time())

    def test_set_world_phase_snaps_to_the_phase_start(self):
        self.engine.advance_world_time(600.0)       # deep in the night
        self.assertEqual(self.engine.world_phase(), "night")
        self.assertEqual(self.engine.set_world_phase(), "dawn")   # default = morning
        self.assertEqual(self.engine.world_time(), daynight.MORNING_SECONDS)
        self.assertEqual(self.engine.set_world_phase("dusk"), "dusk")
        self.assertAlmostEqual(self.engine.world_phase_progress(), 0.0)
        self.assertEqual(self.engine.set_world_phase("garbage"), "dawn")

    def test_towns_closed_follows_the_phase(self):
        self.engine.set_world_phase("dusk")
        self.assertFalse(self.engine.towns_closed())
        self.engine.set_world_phase("night")
        self.assertTrue(self.engine.towns_closed())


class ClockPersistenceTests(unittest.TestCase):
    def test_the_time_round_trips_through_a_save(self):
        engine = _engine("mage")
        engine.advance_world_time(430.0)        # inside dusk (420-465)
        data = persistence.serialize_player(engine.player)
        self.assertAlmostEqual(data["world_time_seconds"], 430.0)
        restored = persistence.deserialize_player(data, default_place_id="hordanita")
        self.assertAlmostEqual(restored.world_time_seconds, 430.0)
        self.assertEqual(daynight.phase_at(restored.world_time_seconds), "dusk")

    def test_a_pre_b136_save_loads_as_morning_without_a_version_bump(self):
        engine = _engine("rogue")
        data = persistence.serialize_player(engine.player)
        data.pop("world_time_seconds")          # exactly what an old save looks like
        restored = persistence.deserialize_player(data, default_place_id="hordanita")
        self.assertEqual(restored.world_time_seconds, daynight.MORNING_SECONDS)
        self.assertEqual(daynight.phase_at(restored.world_time_seconds), "dawn")
        # The schema version is deliberately unchanged (from_json owns the default).
        self.assertEqual(persistence.SAVE_VERSION, 2)

    def test_an_out_of_range_saved_time_is_normalized_on_load(self):
        engine = _engine("tank")
        data = persistence.serialize_player(engine.player)
        data["world_time_seconds"] = daynight.CYCLE_SECONDS * 3 + 100.0
        restored = persistence.deserialize_player(data, default_place_id="hordanita")
        self.assertAlmostEqual(restored.world_time_seconds, 100.0)

    def test_the_field_is_covered_by_the_save_schema(self):
        self.assertIn("world_time_seconds", persistence.persisted_field_names())
        self.assertIn("world_time_seconds", persistence.PLAYER_FIELDS)


if __name__ == "__main__":
    unittest.main()
