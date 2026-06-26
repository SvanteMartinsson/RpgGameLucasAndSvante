"""Respawn point: persistent player field, default Hordanita (burg_5), changed
ONLY by a purchased relocation.

The bug this locks: respawn used to be auto-set by movement (enter_place/travel
wrote it from the place's data), so it drifted to whatever region you walked
through — burg_146 in the core, burg_5 in the heath — without the player choosing
it. Now nothing but relocate_respawn changes it. Resting only heals. Buying the
move in a zone-2 town costs 700 G (zone 1 free). Death penalty + rest heal are
untouched — only how the respawn point is chosen changed.
"""

import json
import tempfile
import unittest

from rpg_game.core import progression
from rpg_game.core.game import GameEngine
from rpg_game.core.view import build_snapshot
from rpg_game.presentation.playtest_logger import PlaytestLogger

HORDANITA = "burg_5"   # default respawn (start place)


def _engine():
    engine = GameEngine()
    engine.start_new_game("Hero", "fighter")
    return engine


class RespawnDefaultAndAutoChangeTest(unittest.TestCase):
    def test_new_player_respawns_at_hordanita(self):
        engine = _engine()
        self.assertEqual(engine.player.respawn_place_id, HORDANITA)

    def test_movement_and_zone_never_change_respawn(self):
        # Re-creates the playtest: walking through the core's burg_146 region and
        # the heath's burg_54 region must NOT move the respawn point. Dying in
        # either place respawns at Hordanita, because no relocation was bought.
        engine = _engine()
        engine.enter_place("burg_146")            # core region (a respawn-town in data)
        self.assertEqual(engine.player.respawn_place_id, HORDANITA)
        engine._respawn_player()
        self.assertEqual(engine.player.current_place_id, HORDANITA)

        engine.enter_place("burg_54")             # heath region (crossing the seam)
        self.assertEqual(engine.player.respawn_place_id, HORDANITA)
        engine._respawn_player()
        self.assertEqual(engine.player.current_place_id, HORDANITA)

    def test_rest_does_not_change_respawn(self):
        engine = _engine()
        engine.enter_place("burg_146")
        engine.rest()
        self.assertEqual(engine.player.respawn_place_id, HORDANITA)  # rest heals only

    def test_rest_still_fully_heals(self):
        engine = _engine()
        engine.enter_place(HORDANITA)
        engine.player.hp, engine.player.mana = 1, 0
        result = engine.rest()
        self.assertEqual(result.outcome, "rested")
        self.assertEqual(engine.player.hp, engine.effective_stat("max_hp"))
        self.assertEqual(engine.player.mana, engine.effective_stat("max_mana"))


class RespawnRelocationTest(unittest.TestCase):
    def test_cost_formula_per_zone(self):
        self.assertEqual(progression.respawn_relocation_cost(1), 0)
        self.assertEqual(progression.respawn_relocation_cost(2), 700)
        self.assertEqual(progression.respawn_relocation_cost(3), 1000)
        self.assertEqual(progression.respawn_relocation_cost(4), 1300)

    def test_zone2_purchase_charges_700_and_moves_respawn(self):
        engine = _engine()
        engine.enter_place("burg_146")
        engine.player.gold = 1000
        result = engine.relocate_respawn(zone=2)
        self.assertTrue(result.success)
        self.assertEqual(result.cost, 700)
        self.assertEqual(engine.player.gold, 300)
        self.assertEqual(engine.player.respawn_place_id, "burg_146")
        engine._respawn_player()
        self.assertEqual(engine.player.current_place_id, "burg_146")

    def test_zone1_relocation_is_free(self):
        # Relocate to a different zone-1 store town (Alherralba); Hordanita is
        # already the default, so it would report already-set.
        engine = _engine()
        engine.enter_place("burg_121")  # Alherralba: zone-1 store town
        engine.player.gold = 0
        result = engine.relocate_respawn(zone=1)
        self.assertTrue(result.success)
        self.assertEqual(result.cost, 0)
        self.assertEqual(engine.player.gold, 0)            # nothing charged
        self.assertEqual(engine.player.respawn_place_id, "burg_121")

    def test_insufficient_gold_blocks_and_charges_nothing(self):
        engine = _engine()
        engine.enter_place("burg_146")
        engine.player.gold = 100
        result = engine.relocate_respawn(zone=2)
        self.assertFalse(result.success)
        self.assertEqual(engine.player.gold, 100)
        self.assertEqual(engine.player.respawn_place_id, HORDANITA)  # unchanged

    def test_already_your_respawn_is_free_and_no_double_charge(self):
        engine = _engine()
        engine.enter_place("burg_146")
        engine.player.gold = 1000
        self.assertTrue(engine.relocate_respawn(zone=2).success)
        again = engine.relocate_respawn(zone=2)
        self.assertFalse(again.success)
        self.assertTrue(again.already_set)
        self.assertEqual(engine.player.gold, 300)

    def test_relocation_requires_a_store_town(self):
        engine = _engine()
        engine.enter_place("burg_54")  # wilderness region, no store
        engine.player.gold = 1000
        result = engine.relocate_respawn(zone=1)
        self.assertFalse(result.success)
        self.assertEqual(engine.player.gold, 1000)
        self.assertEqual(engine.player.respawn_place_id, HORDANITA)

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
        self.assertEqual(result.hp, p.max_hp)   # respawn now full-heals (B20)
        self.assertEqual(engine.player.current_place_id, "burg_146")


class RespawnPersistenceTest(unittest.TestCase):
    def test_respawn_survives_save_load(self):
        with tempfile.TemporaryDirectory() as folder:
            path = f"{folder}/save.json"
            engine = _engine()
            engine.enter_place("burg_146")
            engine.player.gold = 1000
            engine.relocate_respawn(zone=2)
            engine.save(path)

            reloaded = GameEngine()
            self.assertTrue(reloaded.load(path).success)
            self.assertEqual(reloaded.player.respawn_place_id, "burg_146")
            reloaded._respawn_player()
            self.assertEqual(reloaded.player.current_place_id, "burg_146")

    def test_legacy_save_keeps_purchased_respawn(self):
        # Old format: purchased respawn lived in last_rest_place_id.
        with tempfile.TemporaryDirectory() as folder:
            path = f"{folder}/save.json"
            engine = _engine()
            engine.save(path)
            data = json.load(open(path))
            data["player"]["last_rest_place_id"] = "burg_146"
            data["player"]["respawn_place_id"] = "burg_146"  # whatever movement left
            json.dump(data, open(path, "w"))
            reloaded = GameEngine()
            self.assertTrue(reloaded.load(path).success)
            self.assertEqual(reloaded.player.respawn_place_id, "burg_146")

    def test_legacy_save_without_purchase_defaults_to_hordanita(self):
        # Old format, no purchase (last_rest empty) but movement auto-set
        # respawn_place_id to garbage — migration must ignore it and default.
        with tempfile.TemporaryDirectory() as folder:
            path = f"{folder}/save.json"
            engine = _engine()
            engine.save(path)
            data = json.load(open(path))
            data["player"]["last_rest_place_id"] = ""        # never purchased
            data["player"]["respawn_place_id"] = "burg_146"  # auto-set garbage
            json.dump(data, open(path, "w"))
            reloaded = GameEngine()
            self.assertTrue(reloaded.load(path).success)
            self.assertEqual(reloaded.player.respawn_place_id, HORDANITA)


class RespawnLogTest(unittest.TestCase):
    def test_death_log_reflects_chosen_respawn(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = _engine()
            engine.enter_place("burg_146")
            engine.player.gold = 1000
            engine.relocate_respawn(zone=2)
            enemy = next(iter(engine.content.enemies.values())).create_enemy()
            result = engine._defeat(enemy, [])
            logger = PlaytestLogger(folder)
            logger.combat_result(result, enemy, build_snapshot(engine), "burg_54")
            death = next(json.loads(l) for l in logger.path.read_text().splitlines()
                         if l.strip() and json.loads(l)["event"] == "death")
        self.assertEqual(death["respawn_place_id"], "burg_146")


if __name__ == "__main__":
    unittest.main()
