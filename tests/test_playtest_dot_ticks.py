"""Playtest logger surfaces DoT/status ticks as their own JSONL rows.

Reads the tick strings already present in result.events; no combat logic changes.
"""

import json
import random
import tempfile
import unittest

from rpg_game.core.game import GameEngine
from rpg_game.core.view import build_snapshot
from rpg_game.presentation.playtest_logger import PlaytestLogger


def _rows(logger):
    return [json.loads(line) for line in logger.path.read_text().splitlines() if line.strip()]


class DotTickLoggingTest(unittest.TestCase):
    def _tank_vs_mira(self, seed=4):
        engine = GameEngine(rng=random.Random(seed))
        engine.start_new_game("Tank", "tank")
        engine.player.equipped_skill_ids = ("iron_stance",)
        engine.player.hp = engine.player.max_hp - 30  # so regen actually heals
        mira = engine.content.enemies["arena_mira_candlewick"].create_enemy()  # casts ignite
        return engine, mira

    def test_burn_dot_tick_is_logged_with_type_and_amount(self):
        with tempfile.TemporaryDirectory() as folder:
            engine, mira = self._tank_vs_mira()
            logger = PlaytestLogger(folder)
            result = engine.run_combat_turn(mira, "attack")
            logger.combat_result(result, mira, build_snapshot(engine), "arena")
            rows = _rows(logger)

        burn = [r for r in rows if r["event"] == "dot_tick" and r["kind"] == "damage"]
        self.assertTrue(burn)
        self.assertEqual(burn[0]["damage_type"], "fire")
        self.assertEqual(burn[0]["amount"], 5)   # B94: ignite spell-scaled; enemy source = damage (7) x 0.75
        self.assertEqual(burn[0]["target"], "Tank")
        self.assertEqual(burn[0]["status"], "fire")

    def test_regen_tick_is_logged_as_a_heal(self):
        with tempfile.TemporaryDirectory() as folder:
            engine, mira = self._tank_vs_mira()
            logger = PlaytestLogger(folder)
            result = engine.run_combat_turn(mira, "iron_stance")
            logger.combat_result(result, mira, build_snapshot(engine), "arena")
            rows = _rows(logger)

        regen = [r for r in rows if r["event"] == "dot_tick" and r["status"] == "regen"]
        self.assertTrue(regen)
        self.assertEqual(regen[0]["kind"], "heal")
        self.assertEqual(regen[0]["amount"], 6)
        self.assertNotIn("damage_type", regen[0])

    def test_attack_rows_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            engine, mira = self._tank_vs_mira()
            logger = PlaytestLogger(folder)
            result = engine.run_combat_turn(mira, "attack")
            logger.combat_result(result, mira, build_snapshot(engine), "arena")
            rows = _rows(logger)

        attacks = [r for r in rows if r["event"] == "attack"]
        self.assertTrue(attacks)
        for row in attacks:  # attack rows keep their existing shape
            self.assertIn("source", row)
            self.assertIn("damage", row)
            self.assertIn("rolled_style", row)

    def test_no_tick_rows_when_no_status_ticks(self):
        # A plain hit with no DoT/regen in play produces no dot_tick rows.
        with tempfile.TemporaryDirectory() as folder:
            engine = GameEngine(rng=random.Random(1))
            engine.start_new_game("Hero", "fighter")
            rat = engine.content.enemies["giant_rat"].create_enemy()
            logger = PlaytestLogger(folder)
            result = engine.run_combat_turn(rat, "attack")
            logger.combat_result(result, rat, build_snapshot(engine), "burg_54")
            rows = _rows(logger)

        self.assertFalse([r for r in rows if r["event"] == "dot_tick"])

    def test_parser_handles_each_known_tick_shape(self):
        with tempfile.TemporaryDirectory() as folder:
            logger = PlaytestLogger(folder)
            logger._maybe_log_tick("Undead took 7 physical damage from bleed.")
            logger._maybe_log_tick("Hero regenerated 5 HP.")
            logger._maybe_log_tick("Hero used Rupture.")  # not a tick -> ignored
            rows = [r for r in _rows(logger) if r["event"] == "dot_tick"]

        self.assertEqual(len(rows), 2)
        bleed = next(r for r in rows if r["status"] == "bleed")
        self.assertEqual((bleed["kind"], bleed["damage_type"], bleed["amount"], bleed["target"]),
                         ("damage", "physical", 7, "Undead"))
        regen = next(r for r in rows if r["status"] == "regen")
        self.assertEqual((regen["kind"], regen["amount"]), ("heal", 5))


if __name__ == "__main__":
    unittest.main()
