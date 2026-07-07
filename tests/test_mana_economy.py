"""B15: mana items/stats + a tiered potion economy.

Distribution rule:
  * LESSER hp/mana potions are buyable in stores.
  * GREATER hp/mana potions are NEVER sold — only via reward/drop.
  * mana-stat items (gear with max_mana) exist, and mana potions restore mana.
Pure core/data.
"""

import random
import unittest

from rpg_game.core import store
from rpg_game.core.data_loader import load_content, DEFAULT_STORE_INVENTORY
from rpg_game.core.game import GameEngine

LESSER_POTS = {"lesser_hp_potion", "lesser_mana_potion"}
GREATER_POTS = {"greater_hp_potion", "greater_mana_potion"}


class ManaEconomyTests(unittest.TestCase):
    def setUp(self):
        self.content = load_content()
        self.store_ids = [pid for pid, place in self.content.places.items() if place.has_store]
        # Curated stores stock the lesser-pot basics; specialized towns on the
        # default fallback are a separate content pass (has_store now derives from
        # core_zone, so the store set is much larger than the authored inventories).
        self.curated_ids = [pid for pid in self.store_ids
                            if tuple(self.content.places[pid].store_inventory) != DEFAULT_STORE_INVENTORY]

    def test_tiered_potions_exist(self):
        for pot in LESSER_POTS | GREATER_POTS | {"hp_potion", "mana_potion"}:
            self.assertIn(pot, self.content.items, f"{pot} missing")
        # mana pots actually restore mana
        self.assertEqual(self.content.items["lesser_mana_potion"].mana_amount, 25)
        self.assertEqual(self.content.items["greater_mana_potion"].mana_amount, 100)

    def test_lesser_pots_are_sold_in_stores(self):
        # B8 2b: stores are category-split — the basics rule applies to every
        # store that sells consumables at all (generals + capital/cities);
        # weapons/armor towns carry no potions by design.
        for pid in self.curated_ids:
            stock = set(self.content.places[pid].store_inventory)
            if not any(i in self.content.items for i in stock):
                continue
            self.assertTrue(LESSER_POTS <= stock, f"{pid} missing lesser pots")

    def test_greater_pots_are_never_sold(self):
        for pid in self.store_ids:
            stock = set(self.content.places[pid].store_inventory)
            self.assertFalse(stock & GREATER_POTS, f"{pid} sells a greater pot")
            # and the store entry builder never surfaces one either
            entry_ids = {e.id for e in store.get_store_entries(self.content, pid)}
            self.assertFalse(entry_ids & GREATER_POTS)

    def test_greater_pots_are_reachable_via_drops(self):
        drop_items = set()
        for enemy in self.content.enemies.values():
            for table in (enemy.loot_table, enemy.unique_table):
                drop_items |= {entry["item_id"] for entry in table}
        self.assertTrue(GREATER_POTS <= drop_items, "a greater pot is unobtainable")

    def test_mana_stat_items_exist(self):
        mana_gear = [g for g in self.content.gear_items.values() if g.stat_modifiers.get("max_mana", 0) > 0]
        self.assertGreaterEqual(len(mana_gear), 3)

    def test_buying_a_greater_pot_is_rejected(self):
        engine = GameEngine(rng=random.Random(0))
        engine.start_new_game("Hero", "mage")  # at burg_5
        engine.player.gold = 9999
        result = engine.buy_item("greater_mana_potion")
        self.assertFalse(result.success)

    def test_lesser_mana_potion_restores_mana(self):
        engine = GameEngine(rng=random.Random(0))
        engine.start_new_game("Hero", "mage")
        engine.player.inventory.add_consumable("lesser_mana_potion")
        engine.player.mana = 0
        result = engine.use_consumable("lesser_mana_potion")
        self.assertTrue(result.success)
        self.assertEqual(engine.player.mana, 25)


if __name__ == "__main__":
    unittest.main()
