"""Flee chance scales with enemy difficulty (level delta), clamped to a floor/cap.
Failed flee costs the turn; attempts are logged for tuning.
"""

import json
import random
import tempfile
import unittest

from rpg_game.core import progression
from rpg_game.core.game import GameEngine
from rpg_game.core.progression import round_half_up
from rpg_game.presentation.playtest_logger import PlaytestLogger


def _engine(seed=0):
    engine = GameEngine(rng=random.Random(seed))
    engine.start_new_game("Hero", "fighter")  # level 1
    return engine


def _enemy_at_level(engine, level):
    enemy = engine.content.enemies["giant_rat"].create_enemy()
    enemy.level = level
    return enemy


class FleeChanceTest(unittest.TestCase):
    def test_chance_is_clamped_formula_of_level_delta(self):
        engine = _engine()
        engine.player.level = 10
        for enemy_level in range(1, 21):
            enemy = _enemy_at_level(engine, enemy_level)
            delta = enemy_level - engine.player.level
            expected = max(
                progression.FLEE_CHANCE_FLOOR,
                min(progression.FLEE_CHANCE_CAP,
                    progression.FLEE_BASE_CHANCE - progression.FLEE_CHANCE_PER_LEVEL * delta),
            )
            self.assertAlmostEqual(engine.flee_chance(enemy), expected)

    def test_trivial_enemy_hits_the_cap(self):
        engine = _engine()
        engine.player.level = 10
        self.assertAlmostEqual(engine.flee_chance(_enemy_at_level(engine, 1)), progression.FLEE_CHANCE_CAP)

    def test_dangerous_enemy_hits_the_floor(self):
        engine = _engine()
        engine.player.level = 1
        self.assertAlmostEqual(engine.flee_chance(_enemy_at_level(engine, 10)), progression.FLEE_CHANCE_FLOOR)

    def test_even_level_is_mid_band(self):
        engine = _engine()
        engine.player.level = 5
        chance = engine.flee_chance(_enemy_at_level(engine, 5))
        self.assertAlmostEqual(chance, progression.FLEE_BASE_CHANCE)
        self.assertTrue(0.55 <= chance <= 0.65)

    def test_seeded_rng_is_deterministic_success_then_failure(self):
        # Even level -> chance 0.60. Random(1): 0.134 (<0.60 success).
        engine = _engine(seed=1)
        enemy = engine.content.enemies["giant_rat"].create_enemy()  # level 1 == player level
        result = engine.attempt_flee(enemy)
        self.assertEqual(result.outcome, "fled")

        engine2 = _engine(seed=0)  # 0.844 >= 0.60 -> fail
        enemy2 = engine2.content.enemies["giant_rat"].create_enemy()
        before = engine2.player.hp
        result2 = engine2.attempt_flee(enemy2)
        self.assertEqual(result2.outcome, "ongoing")
        self.assertLess(engine2.player.hp, before)  # failed flee cost the turn (free hit)

    def test_failed_flee_gives_the_enemy_a_turn(self):
        engine = _engine(seed=0)
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        before = engine.player.hp
        result = engine.attempt_flee(enemy)
        self.assertEqual(result.outcome, "ongoing")
        self.assertTrue(any("failed to flee" in e for e in result.events))
        self.assertLess(engine.player.hp, before)

    def test_flee_attempt_is_logged_with_chance_and_outcome(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = _engine(seed=1)
            enemy = engine.content.enemies["giant_rat"].create_enemy()
            from rpg_game.core.view import build_snapshot

            logger = PlaytestLogger(folder)
            result = engine.attempt_flee(enemy)
            logger.combat_result(result, enemy, build_snapshot(engine), "burg_5")
            rows = [json.loads(line) for line in logger.path.read_text().splitlines() if line.strip()]

        flee = next(r for r in rows if r["event"] == "flee")
        self.assertTrue(flee["success"])
        self.assertEqual(flee["chance_pct"], round_half_up(progression.FLEE_BASE_CHANCE * 100))  # 60


if __name__ == "__main__":
    unittest.main()
