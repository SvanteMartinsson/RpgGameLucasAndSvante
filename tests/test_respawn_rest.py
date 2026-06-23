"""Respawn relocation is a PAID, zone-scaled action at rest towns.

Resting only heals now (it no longer moves your respawn — changed from commit
4a039e2). Buying the move in a zone-2 town costs 700 G and sets the respawn
there; zone 1 is free. The death penalty and rest heal are untouched — only how
the respawn point is chosen changed.
"""

import json
import tempfile
import unittest

from rpg_game.core import progression
from rpg_game.core.game import GameEngine
from rpg_game.core.view import build_snapshot
from rpg_game.presentation.playtest_logger import PlaytestLogger

# Rest towns by zone (derived from tile-x bands): burg_5 = zone 1 (core),
# burg_146 / burg_67 = zone 2 (western forest).


def _engine():
    engine = GameEngine()
    engine.start_new_game("Hero", "fighter")
    return engine


class RespawnRelocationTest(unittest.TestCase):
    # -- cost formula -------------------------------------------------------
    def test_cost_formula_per_zone(self):
        self.assertEqual(progression.respawn_relocation_cost(1), 0)
        self.assertEqual(progression.respawn_relocation_cost(2), 700)
        self.assertEqual(progression.respawn_relocation_cost(3), 1000)
        self.assertEqual(progression.respawn_relocation_cost(4), 1300)

    # -- buying the move ----------------------------------------------------
    def test_zone2_purchase_charges_700_and_moves_respawn(self):
        engine = _engine()
        engine.enter_place("burg_146")
        engine.player.gold = 1000
        result = engine.relocate_respawn(zone=2)
        self.assertTrue(result.success)
        self.assertEqual(result.cost, 700)
        self.assertEqual(engine.player.gold, 300)
        self.assertEqual(engine.player.last_rest_place_id, "burg_146")
        engine._respawn_player()
        self.assertEqual(engine.player.current_place_id, "burg_146")

    def test_zone1_relocation_is_free(self):
        engine = _engine()
        engine.enter_place("burg_5")
        engine.player.gold = 0
        result = engine.relocate_respawn(zone=1)
        self.assertTrue(result.success)
        self.assertEqual(result.cost, 0)
        self.assertEqual(engine.player.gold, 0)            # nothing charged
        self.assertEqual(engine.player.last_rest_place_id, "burg_5")

    def test_insufficient_gold_blocks_and_charges_nothing(self):
        engine = _engine()
        engine.enter_place("burg_146")
        engine.player.gold = 100
        result = engine.relocate_respawn(zone=2)
        self.assertFalse(result.success)
        self.assertEqual(engine.player.gold, 100)          # untouched
        self.assertEqual(engine.player.last_rest_place_id, "")  # respawn unchanged
        engine._respawn_player()                            # falls back to hub, no crash
        self.assertEqual(engine.player.current_place_id, engine.player.respawn_place_id)

    def test_already_your_respawn_is_free_and_no_double_charge(self):
        engine = _engine()
        engine.enter_place("burg_146")
        engine.player.gold = 1000
        self.assertTrue(engine.relocate_respawn(zone=2).success)
        again = engine.relocate_respawn(zone=2)             # already set
        self.assertFalse(again.success)
        self.assertTrue(again.already_set)
        self.assertEqual(engine.player.gold, 300)           # not charged twice

    def test_relocation_requires_a_store_town(self):
        engine = _engine()
        engine.enter_place("burg_54")  # wilderness region, no store
        engine.player.gold = 1000
        result = engine.relocate_respawn(zone=1)
        self.assertFalse(result.success)
        self.assertEqual(engine.player.gold, 1000)

    # -- rest no longer moves respawn (changed from 4a039e2) ----------------
    def test_rest_no_longer_sets_respawn(self):
        engine = _engine()
        engine.enter_place("burg_146")
        engine.rest()
        self.assertEqual(engine.player.last_rest_place_id, "")  # rest heals only now

    def test_rest_still_fully_heals(self):
        engine = _engine()
        engine.enter_place("burg_5")
        engine.player.hp, engine.player.mana = 1, 0
        result = engine.rest()
        self.assertEqual(result.outcome, "rested")
        self.assertEqual(engine.player.hp, engine.effective_stat("max_hp"))
        self.assertEqual(engine.player.mana, engine.effective_stat("max_mana"))

    # -- unchanged invariants ----------------------------------------------
    def test_respawn_without_purchase_uses_default_hub(self):
        engine = _engine()
        self.assertEqual(engine.player.last_rest_place_id, "")
        default = engine.player.respawn_place_id
        engine._respawn_player()
        self.assertTrue(engine.player.current_place_id)        # never None
        self.assertEqual(engine.player.current_place_id, default)

    def test_death_penalty_values_unchanged(self):
        engine = _engine()
        engine.enter_place("burg_146")
        engine.player.gold = 1000
        engine.relocate_respawn(zone=2)  # gold now 300
        p = engine.player
        p.level, p.gold, p.xp = 3, 200, 137
        result = engine._respawn_player()
        self.assertEqual(result.gold_lost, 3 * progression.GOLD_LOSS_PER_LEVEL)
        self.assertEqual(result.xp_lost, 137)
        self.assertEqual(result.hp, progression.round_half_up(p.max_hp / 2))
        self.assertEqual(engine.player.current_place_id, "burg_146")  # respawns at chosen town

    def test_relocation_survives_save_load(self):
        with tempfile.TemporaryDirectory() as folder:
            path = f"{folder}/save.json"
            engine = _engine()
            engine.enter_place("burg_146")
            engine.player.gold = 1000
            engine.relocate_respawn(zone=2)
            engine.save(path)

            reloaded = GameEngine()
            self.assertTrue(reloaded.load(path).success)
            self.assertEqual(reloaded.player.last_rest_place_id, "burg_146")
            reloaded._respawn_player()
            self.assertEqual(reloaded.player.current_place_id, "burg_146")

    def test_old_saves_without_field_default_to_empty(self):
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

    def test_death_log_reflects_chosen_respawn(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = _engine()
            engine.enter_place("burg_146")
            engine.player.gold = 1000
            engine.relocate_respawn(zone=2)
            enemy = next(iter(engine.content.enemies.values())).create_enemy()
            result = engine._defeat(enemy, [])  # respawn happens inside
            logger = PlaytestLogger(folder)
            logger.combat_result(result, enemy, build_snapshot(engine), "burg_54")
            death = next(json.loads(l) for l in logger.path.read_text().splitlines()
                         if l.strip() and json.loads(l)["event"] == "death")
        self.assertEqual(death["respawn_place_id"], "burg_146")


if __name__ == "__main__":
    unittest.main()
