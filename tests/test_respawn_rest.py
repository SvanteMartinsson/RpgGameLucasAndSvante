"""Respawn returns you to the town you last RESTED in, not a fixed regional hub.

Before any rest, respawn falls back to the regional hub (unchanged early-game
behaviour). Resting sets the respawn point; it survives save/load. The rest heal
and the death penalty (lost XP/gold, half-HP) are untouched — only WHERE you
respawn changes.
"""

import json
import random
import tempfile
import unittest

from rpg_game.core import progression
from rpg_game.core.game import GameEngine
from rpg_game.core.view import build_snapshot
from rpg_game.presentation.playtest_logger import PlaytestLogger

REST_TOWNS = ("burg_5", "burg_67", "burg_146")  # has_store towns (rest-enabled)


def _engine():
    engine = GameEngine()
    engine.start_new_game("Hero", "fighter")
    return engine


class RespawnAtRestTest(unittest.TestCase):
    def test_respawn_at_each_town_you_last_rested_in(self):
        engine = _engine()
        for town in ("burg_5", "burg_146"):
            engine.enter_place(town)
            engine.rest()
            engine._respawn_player()
            self.assertEqual(engine.player.current_place_id, town)

    def test_last_rest_overrides_the_regional_hub(self):
        # Rest in Fongorinos (hub = burg_5), then walk into Rotequero's region
        # (which would set respawn_place_id = burg_146). Respawn must still return
        # to the rested town, not the region hub.
        engine = _engine()
        engine.enter_place("burg_67")
        engine.rest()
        engine.enter_place("burg_146")
        self.assertEqual(engine.player.respawn_place_id, "burg_146")  # region hub tracked
        engine._respawn_player()
        self.assertEqual(engine.player.current_place_id, "burg_67")   # but rested town wins

    def test_respawn_without_resting_uses_default_hub(self):
        engine = _engine()
        self.assertEqual(engine.player.last_rest_place_id, "")  # never rested
        default = engine.player.respawn_place_id
        engine._respawn_player()
        self.assertTrue(engine.player.current_place_id)            # never None/empty
        self.assertEqual(engine.player.current_place_id, default)  # unchanged behaviour

    def test_rest_still_fully_heals(self):
        engine = _engine()
        engine.enter_place("burg_5")
        engine.player.hp = 1
        engine.player.mana = 0
        result = engine.rest()
        self.assertEqual(result.outcome, "rested")
        self.assertEqual(engine.player.hp, engine.effective_stat("max_hp"))
        self.assertEqual(engine.player.mana, engine.effective_stat("max_mana"))

    def test_death_penalty_values_unchanged(self):
        engine = _engine()
        engine.enter_place("burg_146")
        engine.rest()
        p = engine.player
        p.level, p.gold, p.xp = 3, 200, 137
        result = engine._respawn_player()
        # Same penalty as before the respawn-point change.
        self.assertEqual(result.gold_lost, 3 * progression.GOLD_LOSS_PER_LEVEL)
        self.assertEqual(result.xp_lost, 137)
        self.assertEqual(result.hp, progression.round_half_up(p.max_hp / 2))
        self.assertEqual(engine.player.current_place_id, "burg_146")  # and respawns at rest

    def test_rest_point_survives_save_load(self):
        with tempfile.TemporaryDirectory() as folder:
            path = f"{folder}/save.json"
            engine = _engine()
            engine.enter_place("burg_146")
            engine.rest()
            engine.save(path)

            reloaded = GameEngine()
            self.assertTrue(reloaded.load(path).success)
            self.assertEqual(reloaded.player.last_rest_place_id, "burg_146")
            reloaded._respawn_player()
            self.assertEqual(reloaded.player.current_place_id, "burg_146")

    def test_old_saves_without_field_default_to_empty(self):
        # Backward compat: a save predating the field loads with "" (hub fallback).
        with tempfile.TemporaryDirectory() as folder:
            path = f"{folder}/save.json"
            engine = _engine()
            engine.save(path)
            with open(path) as handle:
                data = json.load(handle)
            data["player"].pop("last_rest_place_id", None)
            with open(path, "w") as handle:
                json.dump(data, handle)
            reloaded = GameEngine()
            self.assertTrue(reloaded.load(path).success)
            self.assertEqual(reloaded.player.last_rest_place_id, "")

    def test_death_log_reflects_last_rested_town(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = _engine()
            engine.enter_place("burg_146")
            engine.rest()
            enemy = next(iter(engine.content.enemies.values())).create_enemy()
            result = engine._defeat(enemy, [])  # respawn happens inside
            logger = PlaytestLogger(folder)
            logger.combat_result(result, enemy, build_snapshot(engine), "burg_54")
            death = next(json.loads(l) for l in logger.path.read_text().splitlines()
                         if l.strip() and json.loads(l)["event"] == "death")
        self.assertEqual(death["respawn_place_id"], "burg_146")


if __name__ == "__main__":
    unittest.main()
