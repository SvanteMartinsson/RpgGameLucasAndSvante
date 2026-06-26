"""B20: rest costs gold (free first time via a Rest Voucher granted at new game),
and respawn restores full HP + mana. Pure core; no presentation needed."""

import os
import tempfile
import unittest

from rpg_game.core import progression
from rpg_game.core.game import GameEngine

VOUCHER = "rest_voucher"


def _engine():
    engine = GameEngine()
    engine.start_new_game("Hero", "fighter")  # starts at burg_5 (has_store)
    return engine


class RestEconomyTest(unittest.TestCase):
    def test_new_game_grants_one_rest_voucher(self):
        engine = _engine()
        self.assertEqual(engine.player.inventory.count(VOUCHER), 1)

    def test_voucher_rest_is_free_and_consumes_the_voucher(self):
        engine = _engine()
        p = engine.player
        p.gold, p.hp, p.mana = 500, 1, 0
        result = engine.rest(zone=1)
        self.assertEqual(result.outcome, "rested")
        self.assertEqual(p.gold, 500)                       # no gold spent
        self.assertEqual(p.inventory.count(VOUCHER), 0)     # voucher consumed
        self.assertEqual(p.hp, engine.effective_stat("max_hp"))
        self.assertEqual(p.mana, engine.effective_stat("max_mana"))

    def test_rest_costs_50_in_zone_1_and_100_later(self):
        engine = _engine()
        p = engine.player
        p.inventory.remove_consumable(VOUCHER)              # spend the free rest
        p.gold, p.hp = 500, 1
        engine.rest(zone=1)
        self.assertEqual(p.gold, 450)                       # -50
        p.hp = 1
        engine.rest(zone=3)
        self.assertEqual(p.gold, 350)                       # -100
        self.assertEqual(progression.rest_cost(1), 50)
        self.assertEqual(progression.rest_cost(2), 100)

    def test_rest_refused_when_too_poor_no_gold_drawn_no_heal(self):
        engine = _engine()
        p = engine.player
        p.inventory.remove_consumable(VOUCHER)
        p.gold, p.hp = 10, 5
        result = engine.rest(zone=1)
        self.assertEqual(result.outcome, "not_allowed")
        self.assertEqual(p.gold, 10)                        # untouched
        self.assertEqual(p.hp, 5)                           # no heal

    def test_respawn_restores_full_hp_and_mana(self):
        engine = _engine()
        p = engine.player
        p.hp, p.mana = 1, 0
        engine._respawn_player()
        self.assertEqual(p.hp, engine.effective_stat("max_hp"))
        self.assertEqual(p.mana, engine.effective_stat("max_mana"))

    def test_no_soft_lock_broke_and_dead_still_respawns_able_to_act(self):
        engine = _engine()
        p = engine.player
        p.inventory.remove_consumable(VOUCHER)
        p.gold, p.hp, p.mana = 0, 0, 0
        engine._respawn_player()
        self.assertEqual(p.gold, 0)
        self.assertEqual(p.hp, engine.effective_stat("max_hp"))  # full -> can go fight for gold
        self.assertGreater(p.hp, 0)

    def test_voucher_and_gold_persist_across_save_load(self):
        engine = _engine()
        engine.player.gold = 777
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "s.json")
            engine.save(path)
            loaded = GameEngine(content=engine.content)
            loaded.load(path)
        self.assertEqual(loaded.player.inventory.count(VOUCHER), 1)
        self.assertEqual(loaded.player.gold, 777)


if __name__ == "__main__":
    unittest.main()
