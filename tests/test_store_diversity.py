"""B5: stores sell varied simple/mid gear instead of one shared default list.
Every store town has its own inventory (no two identical, none empty), drawn
from the expanded item pool — weapons + consumables + gear, which are now
buyable. Pure core/data; no presentation needed.
"""

import random
import unittest

from rpg_game.core import store
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine


class StoreDiversityTests(unittest.TestCase):
    def setUp(self):
        self.content = load_content()
        self.store_ids = [pid for pid, place in self.content.places.items() if place.has_store]

    def test_there_are_multiple_store_towns(self):
        self.assertGreaterEqual(len(self.store_ids), 2)

    def test_no_store_is_empty(self):
        for pid in self.store_ids:
            self.assertTrue(store.get_store_entries(self.content, pid), f"{pid} store is empty")

    def test_no_two_stores_have_identical_stock(self):
        stocks = {pid: tuple(self.content.places[pid].store_inventory) for pid in self.store_ids}
        # every store differs from every other
        seen = {}
        for pid, stock in stocks.items():
            self.assertNotIn(stock, seen.values(), f"{pid} identical to {seen}")
            seen[pid] = stock
        # and the assortment genuinely varies (union >> any single store)
        union = set().union(*stocks.values())
        self.assertGreater(len(union), max(len(s) for s in stocks.values()))

    def test_every_store_carries_gear_weapons_and_consumables(self):
        for pid in self.store_ids:
            kinds = {entry.kind for entry in store.get_store_entries(self.content, pid)}
            self.assertIn("gear", kinds, f"{pid} sells no gear")
            self.assertIn("weapon", kinds, f"{pid} sells no weapon")
            self.assertIn("consumable", kinds, f"{pid} sells no consumable")

    def test_gear_is_buyable_into_inventory(self):
        engine = GameEngine(rng=random.Random(0))
        engine.start_new_game("Hero", "fighter")  # starts at burg_5
        entry = next(e for e in engine.store_entries() if e.kind == "gear")
        engine.player.gold = entry.price + 5

        result = engine.buy_item(entry.id)

        self.assertTrue(result.success, result.message)
        self.assertIn(entry.id, engine.player.owned_gear_ids)
        self.assertEqual(engine.player.gold, 5)

    def test_cannot_buy_item_not_in_this_store(self):
        engine = GameEngine(rng=random.Random(0))
        engine.start_new_game("Hero", "fighter")
        sold_here = set(engine.content.places[engine.player.current_place_id].store_inventory)
        absent = next(g for g in engine.content.gear_items if g not in sold_here)
        engine.player.gold = 9999

        result = engine.buy_item(absent)

        self.assertFalse(result.success)
        self.assertNotIn(absent, engine.player.owned_gear_ids)


if __name__ == "__main__":
    unittest.main()
