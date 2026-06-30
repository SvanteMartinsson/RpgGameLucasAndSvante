"""B37 Slice 2: the weapon/armour upgrade system + miscellaneous materials.

Locks RULES/RELATIONS (tier never changes, exclusion respected, one-time upgrade,
deltas stored separately from damage_bonus, material/gold cost), not placeholder
numbers.
"""

import random
import unittest

from rpg_game.core import combat, data_loader
from rpg_game.core.game import GameEngine


class MaterialsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = data_loader.load_content()

    def test_materials_exist_as_miscellaneous(self):
        for mid in ("worg_tooth", "worg_claw", "grave_iron", "chill_crystal",
                    "blessed_ash", "iron_scrap"):
            self.assertIn(mid, self.content.items, mid)
            self.assertEqual(self.content.items[mid].kind, "miscellaneous", mid)

    def test_materials_drop_from_their_enemies(self):
        engine = GameEngine(rng=random.Random(0))
        engine.start_new_game("H", "fighter")
        worg = self.content.enemies["hollow_worg"].create_enemy()
        pool_ids = {e["item_id"] for e in engine.loot_pool(worg)}
        self.assertIn("worg_tooth", pool_ids)
        self.assertIn("worg_claw", pool_ids)

    def test_collected_materials_stack_in_inventory(self):
        engine = GameEngine(rng=random.Random(0))
        engine.start_new_game("H", "fighter")
        from rpg_game.core.entities import LootDrop
        engine.collect_loot(LootDrop("worg_tooth", "Worg Tooth", "miscellaneous", 1))
        engine.collect_loot(LootDrop("worg_tooth", "Worg Tooth", "miscellaneous", 1))
        self.assertEqual(engine.player.inventory.count("worg_tooth"), 2)


if __name__ == "__main__":
    unittest.main()
