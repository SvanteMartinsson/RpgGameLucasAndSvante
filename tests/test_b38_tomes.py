"""B38: skill tomes — the acquisition path for the B27 elemental skill pool.

Locks the core mechanic (data + engine API): tomes are sold only at mage towers,
bought with gold into the inventory, and CONSUMED on use to learn the taught
skill into the non-talent pool — gated by level, deduped, and then equippable
within the max-4 limit. (The pygame mage-tower tome menu is a render-review
follow-up; this exercises the whole engine flow.)
"""

import random
import unittest

from rpg_game.core import talents
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine

B27_POOL = {"zap", "thunder_strike", "incineration", "holy_strike",
            "frost_shard", "earthen_smash", "plague_ooze", "immolate",
            "stone_ward", "venom_lash", "sun_flare", "power_slash"}


def _mage(level=8, gold=2000, seed=0):
    engine = GameEngine(rng=random.Random(seed))
    engine.start_new_game("Mage", "mage")
    engine.player.level = level
    engine.player.gold = gold
    return engine


class TomeDataTests(unittest.TestCase):
    def setUp(self):
        self.content = load_content()

    def test_tomes_cover_the_b27_pool_and_teach_real_actions(self):
        taught = {}
        for item in self.content.items.values():
            if item.kind == "tome":
                self.assertIn(item.teaches, self.content.actions, item.id)
                self.assertGreaterEqual(item.level_req, 1)
                taught[item.teaches] = item
        self.assertEqual(set(taught), B27_POOL)


class TomeShopTests(unittest.TestCase):
    def test_only_mage_towers_sell_tomes(self):
        engine = _mage()
        self.assertEqual(len(engine.tomes_for_sale("tower")), 11)
        self.assertEqual(len(engine.tomes_for_sale("mage_tower")), 11)
        self.assertEqual(engine.tomes_for_sale("blacksmith"), [])
        self.assertEqual(engine.tomes_for_sale("barracks"), [])

    def test_buy_requires_a_mage_tower_and_gold(self):
        engine = _mage(gold=90)
        self.assertFalse(engine.buy_tome("blacksmith", "tome_zap").success)   # wrong building
        self.assertFalse(engine.buy_tome("tower", "tome_incineration").success)  # 90 < 500
        ok = engine.buy_tome("tower", "tome_zap")                              # 100 gold, has 90? no
        # zap costs 100, gold 90 -> still fails; top up and retry
        engine.player.gold = 100
        ok = engine.buy_tome("tower", "tome_zap")
        self.assertTrue(ok.success, ok.message)
        self.assertEqual(engine.player.inventory.count("tome_zap"), 1)
        self.assertEqual(engine.player.gold, 0)


class TomeLearnTests(unittest.TestCase):
    def test_using_a_tome_learns_and_consumes_it(self):
        engine = _mage()
        engine.buy_tome("tower", "tome_incineration")
        result = engine.use_consumable("tome_incineration")
        self.assertTrue(result.success, result.message)
        self.assertIn("incineration", talents.unlocked_skill_ids(engine.player, engine.content))
        self.assertEqual(engine.player.inventory.count("tome_incineration"), 0)  # consumed

    def test_level_gate_blocks_and_does_not_consume(self):
        engine = _mage(level=3)
        engine.buy_tome("tower", "tome_thunder_strike")   # requires L6
        result = engine.use_consumable("tome_thunder_strike")
        self.assertFalse(result.success)
        self.assertIn("level 6", result.message)
        self.assertEqual(engine.player.inventory.count("tome_thunder_strike"), 1)  # NOT consumed
        self.assertNotIn("thunder_strike", talents.unlocked_skill_ids(engine.player, engine.content))

    def test_already_known_blocks_and_does_not_consume(self):
        engine = _mage()
        engine.buy_tome("tower", "tome_zap")
        self.assertTrue(engine.use_consumable("tome_zap").success)
        engine.buy_tome("tower", "tome_zap")               # a second copy
        again = engine.use_consumable("tome_zap")
        self.assertFalse(again.success)
        self.assertIn("already know", again.message)
        self.assertEqual(engine.player.inventory.count("tome_zap"), 1)  # NOT consumed

    def test_learned_skill_is_equippable_within_the_cap(self):
        engine = _mage()
        engine.buy_tome("tower", "tome_holy_strike")
        engine.use_consumable("tome_holy_strike")
        msg = talents.equip_skill(engine.player, engine.content, "holy_strike")
        self.assertIn("Equipped", msg)
        self.assertIn("holy_strike", engine.player.equipped_skill_ids)

    def test_learned_skills_survive_save_load(self):
        from rpg_game.core import persistence
        engine = _mage()
        engine.buy_tome("tower", "tome_frost_shard")
        engine.use_consumable("tome_frost_shard")
        restored = persistence.deserialize_player(persistence.serialize_player(engine.player))
        self.assertIn("frost_shard", restored.learned_skill_ids)


if __name__ == "__main__":
    unittest.main()
