"""B5: stores sell varied simple/mid gear instead of one shared default list.
Every store town has its own inventory (no two identical, none empty), drawn
from the expanded item pool — weapons + consumables + gear, which are now
buyable. Pure core/data; no presentation needed.
"""

import random
import unittest

from rpg_game.core import store
from rpg_game.core.data_loader import load_content, DEFAULT_STORE_INVENTORY
from rpg_game.core.game import GameEngine


class StoreDiversityTests(unittest.TestCase):
    def setUp(self):
        self.content = load_content()
        self.store_ids = [pid for pid, place in self.content.places.items() if place.has_store]
        # B: has_store now derives from core_zone, so MANY more towns are stores —
        # but only the authored (non-default) ones are hand-curated. The
        # richness/diversity guarantees apply to those; specialized towns that fall
        # back to the default stock are a separate content pass.
        self.curated_ids = [pid for pid in self.store_ids
                            if tuple(self.content.places[pid].store_inventory) != DEFAULT_STORE_INVENTORY]

    def test_there_are_multiple_store_towns(self):
        self.assertGreaterEqual(len(self.store_ids), 2)

    def test_no_store_is_empty(self):
        for pid in self.store_ids:
            self.assertTrue(store.get_store_entries(self.content, pid), f"{pid} store is empty")

    def test_no_two_stores_have_identical_stock(self):
        stocks = {pid: tuple(self.content.places[pid].store_inventory) for pid in self.curated_ids}
        # every store differs from every other
        seen = {}
        for pid, stock in stocks.items():
            self.assertNotIn(stock, seen.values(), f"{pid} identical to {seen}")
            seen[pid] = stock
        # and the assortment genuinely varies (union >> any single store)
        union = set().union(*stocks.values())
        self.assertGreater(len(union), max(len(s) for s in stocks.values()))

    def test_every_store_carries_gear_weapons_and_consumables(self):
        for pid in self.curated_ids:
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


class StoreCategoryTests(unittest.TestCase):
    """Differentiated trade buildings: the town's single inventory is split by
    category — blacksmith=weapons, barracks=gear/armour, shop=consumables. The full
    (category=None) view is unchanged."""

    def setUp(self):
        self.content = load_content()
        # Both hub store towns must carry all three categories for the split to work.
        self.hub_store_ids = ["burg_5", "burg_67"]

    def test_category_filter_returns_only_that_kind(self):
        for pid in self.hub_store_ids:
            weapons = store.get_store_entries(self.content, pid, "weapons")
            armor = store.get_store_entries(self.content, pid, "armor")
            general = store.get_store_entries(self.content, pid, "general")
            self.assertTrue(weapons and all(e.kind == "weapon" for e in weapons), pid)
            self.assertTrue(armor and all(e.kind == "gear" for e in armor), pid)
            self.assertTrue(general and all(e.kind == "consumable" for e in general), pid)

    def test_categories_partition_the_full_inventory(self):
        # The three slices together equal the unsplit store (no item lost/duplicated).
        for pid in self.hub_store_ids:
            full = {e.id for e in store.get_store_entries(self.content, pid)}
            split = set()
            for cat in ("weapons", "armor", "general"):
                split |= {e.id for e in store.get_store_entries(self.content, pid, cat)}
            self.assertEqual(full, split, pid)

    def test_store_and_sell_entries_carry_stat_descriptions(self):
        # UI Slice A: every buy/sell row exposes its stats (skada/tier/mods/nivå)
        # via .description so the shop screen can render them.
        engine = GameEngine(rng=random.Random(0))
        engine.start_new_game("Hero", "fighter")  # at burg_5
        for entry in engine.store_entries("weapons"):
            self.assertIn("damage", entry.description)
            self.assertIn("tier", entry.description)
        for entry in engine.store_entries("armor"):
            self.assertTrue(entry.description.startswith("["))  # [rarity] mods...
        engine.player.owned_weapon_ids = (*engine.player.owned_weapon_ids, "axe")
        weapon_sell = next(e for e in engine.sellable_entries("weapons") if e.id == "axe")
        self.assertIn("damage", weapon_sell.description)
        self.assertIn("tier", weapon_sell.description)

    def test_sellables_filter_by_category(self):
        engine = GameEngine(rng=random.Random(0))
        engine.start_new_game("Hero", "fighter")  # at burg_5
        engine.player.owned_weapon_ids = (*engine.player.owned_weapon_ids, "axe")  # sword is equipped
        engine.player.owned_gear_ids = ("padded_vest",)
        engine.player.inventory.add_consumable("rat_pelt")  # miscellaneous

        self.assertEqual({e.kind for e in engine.sellable_entries("weapons")}, {"weapon"})
        self.assertEqual({e.kind for e in engine.sellable_entries("armor")}, {"gear"})
        self.assertEqual({e.kind for e in engine.sellable_entries("general")}, {"miscellaneous"})


if __name__ == "__main__":
    unittest.main()
