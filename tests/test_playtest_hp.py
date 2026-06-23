"""Playtest log surfaces player & enemy HP so fights are debuggable.

encounter_start carries both sides' opening vitals; every attack event carries
the defender's post-event HP; death disambiguates its respawn vitals. Logging is
pure observation: a deterministic fight runs byte-for-byte the same with the
logger on or off (HP, outcome, RNG state). No combat/RNG changes.
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


def _fighter(seed):
    engine = GameEngine(rng=random.Random(seed))
    engine.start_new_game("Hero", "fighter")
    return engine


class PlaytestHpLoggingTest(unittest.TestCase):
    def test_encounter_start_logs_both_sides_vitals(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = _fighter(1)
            rat = engine.content.enemies["giant_rat"].create_enemy()
            logger = PlaytestLogger(folder)
            logger.encounter_start(rat, build_snapshot(engine), "burg_54")
            row = next(r for r in _rows(logger) if r["event"] == "encounter_start")

        for key in ("player_hp", "player_max_hp", "player_mana", "player_max_mana",
                    "enemy_hp", "enemy_max_hp"):
            self.assertIn(key, row)
        self.assertEqual(row["player_hp"], engine.player.hp)
        self.assertEqual(row["enemy_hp"], rat.hp)
        self.assertEqual(row["enemy_max_hp"], rat.max_hp)

    def test_every_attack_event_carries_target_hp_after(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = _fighter(1)
            rat = engine.content.enemies["giant_rat"].create_enemy()
            logger = PlaytestLogger(folder)
            result = engine.run_combat_turn(rat, "attack")
            logger.combat_result(result, rat, build_snapshot(engine), "burg_54")
            attacks = [r for r in _rows(logger) if r["event"] == "attack"]

        self.assertTrue(attacks)
        for row in attacks:
            self.assertIn("target_hp_after", row)
            self.assertIn("target_max_hp", row)
        # The player's swing targets the enemy -> enemy's end-of-turn HP.
        player_swing = next(r for r in attacks if r["source"] == "player")
        self.assertEqual(player_swing["target_hp_after"], result.enemy_hp)
        self.assertEqual(player_swing["target_max_hp"], rat.max_hp)
        # The enemy's swing targets the player -> player's end-of-turn HP.
        enemy_swing = next((r for r in attacks if r["source"] == "enemy"), None)
        if enemy_swing is not None:
            self.assertEqual(enemy_swing["target_hp_after"], result.player_hp)

    def test_death_event_disambiguates_respawn_vitals(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = _fighter(7)
            # Force a loss: a strong enemy and a near-dead player.
            boss = engine.content.enemies["cave_bear"].create_enemy()
            engine.player.hp = 1
            logger = PlaytestLogger(folder)
            result = engine.run_combat_turn(boss, "attack")
            self.assertIsNotNone(result.respawn)  # the turn killed the player
            logger.combat_result(result, boss, build_snapshot(engine), "burg_54")
            death = next(r for r in _rows(logger) if r["event"] == "death")

        self.assertEqual(death["respawn_hp"], result.respawn.hp)
        self.assertEqual(death["hp_after"], result.respawn.hp)  # back-compat label kept
        self.assertIn("respawn_place_id", death)
        self.assertEqual(death["respawn_place_id"], engine.player.current_place_id)

    def test_logging_is_side_effect_free(self):
        # Same seed, same script of turns: the engine state and RNG must be
        # byte-identical whether or not the logger observes the fight.
        def run(logger):
            engine = _fighter(20)
            enemy = engine.content.enemies["giant_rat"].create_enemy()
            if logger is not None:
                logger.encounter_start(enemy, build_snapshot(engine), "burg_54")
            for _ in range(3):
                result = engine.run_combat_turn(enemy, "attack")
                if logger is not None:
                    logger.combat_result(result, enemy, build_snapshot(engine), "burg_54")
                if result.outcome in ("victory", "defeat"):
                    break
            return (engine.player.hp, engine.player.mana, enemy.hp,
                    result.outcome, engine.rng.getstate())

        with tempfile.TemporaryDirectory() as folder:
            without = run(None)
            with_log = run(PlaytestLogger(folder))
        self.assertEqual(without, with_log)


if __name__ == "__main__":
    unittest.main()
