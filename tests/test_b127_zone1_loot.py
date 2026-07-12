"""B127: every zone-1 (cainos) enemy can drop a wearable, and the common
wearable slots are all obtainable there — so early play isn't gated on buying
gear. Low weights keep it rare-but-recurring (the shop stays the upgrade source).
"""

import unittest

from rpg_game.core.data_loader import load_content

# The cainos spawn-area roster (core_zone.json spawn_areas with the cainos_* ids).
CAINOS_ENEMIES = ("giant_rat", "wild_dog", "giant_spider", "goblin_scrapper",
                  "wild_stag", "undead")
WEARABLE_SLOTS = {"head", "chest", "hands", "legs", "feet", "amulet", "ring"}


class Zone1WearableLootTests(unittest.TestCase):
    def setUp(self):
        self.content = load_content()

    def _wearables_in(self, enemy_id):
        enemy = self.content.enemies[enemy_id]
        return [row["item_id"] for row in enemy.loot_table
                if row["item_id"] in self.content.gear_items
                and self.content.gear_items[row["item_id"]].slot_type in WEARABLE_SLOTS]

    def test_every_cainos_enemy_drops_at_least_one_wearable(self):
        for enemy_id in CAINOS_ENEMIES:
            self.assertTrue(self._wearables_in(enemy_id),
                            f"{enemy_id} drops no wearable")

    def test_previously_barren_enemies_got_their_common_wearable(self):
        # The four cainos enemies that dropped nothing wearable before B127.
        added = {"wild_dog": "worn_boots", "giant_spider": "threadbare_gloves",
                 "goblin_scrapper": "patched_trousers", "wild_stag": "tin_amulet"}
        for enemy_id, item_id in added.items():
            self.assertIn(item_id, self._wearables_in(enemy_id))

    def test_all_wearable_slots_are_obtainable_in_zone_1(self):
        slots = set()
        for enemy_id in CAINOS_ENEMIES:
            for item_id in self._wearables_in(enemy_id):
                slots.add(self.content.gear_items[item_id].slot_type)
        self.assertEqual(slots, WEARABLE_SLOTS,
                         f"missing slots in zone 1: {WEARABLE_SLOTS - slots}")

    def test_added_wearables_stay_low_weight_bonuses(self):
        # Rare-but-recurring: the added commons sit at a low weight so the shop
        # stays the source of real upgrades (B62 economy: drops are a bonus).
        for enemy_id in ("wild_dog", "giant_spider", "goblin_scrapper", "wild_stag"):
            enemy = self.content.enemies[enemy_id]
            for row in enemy.loot_table:
                if (row["item_id"] in self.content.gear_items
                        and self.content.gear_items[row["item_id"]].rarity == "common"):
                    self.assertLessEqual(row["weight"], 12, f"{enemy_id}/{row['item_id']}")


if __name__ == "__main__":
    unittest.main()
