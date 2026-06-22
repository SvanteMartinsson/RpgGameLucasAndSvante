"""ZONE2 step 3: raised western loot — tier 3-5 weapons + gear from the zone-2
archetypes, with the Hollow Worg as the top-band jackpot. Data only.
"""

import collections
import json
import os
import random
import unittest

from rpg_game.core.game import GameEngine

ZONE2_LOOT_ENEMIES = (
    "dire_wolf", "wild_boar", "treant", "mutated_mudcrab", "bog_wraith", "tar_beast", "hollow_worg",
)
JUNK = {"bone_dust", "tattered_cloth"}


def _ids(path):
    with open(os.path.join("rpg_game/data", path), encoding="utf-8") as handle:
        return {x["id"] for x in json.load(handle)}


class Zone2LootTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gear_ids = _ids("gear.json")
        cls.weapon_ids = _ids("weapons.json")

    def setUp(self):
        self.engine = GameEngine()
        self.engine.start_new_game("Hero", "fighter")

    def _pool(self, enemy_id):
        enemy = self.engine.content.enemies[enemy_id].create_enemy()
        return self.engine.loot_pool(enemy)

    def _pool_ids(self, enemy_id):
        return [entry["item_id"] for entry in self._pool(enemy_id)]

    def _pool_tiers(self, enemy_id):
        return [int(entry.get("rarity_tier", 1)) for entry in self._pool(enemy_id)]

    # -- rare access + tier band -------------------------------------------

    def test_zone2_archetypes_have_rare_table_access(self):
        for enemy_id in ZONE2_LOOT_ENEMIES:
            self.assertTrue(self.engine.content.enemies[enemy_id].rare_table_access, enemy_id)

    def test_zone2_loot_reaches_tier_three_to_five_band(self):
        for enemy_id in ZONE2_LOOT_ENEMIES:
            tiers = self._pool_tiers(enemy_id)
            self.assertTrue(any(3 <= t <= 5 for t in tiers), enemy_id)

    def test_tier_gate_holds_no_entry_above_the_cap(self):
        # rare access -> cap 6; without -> cap 3. No pool entry exceeds its cap.
        for enemy_id in ZONE2_LOOT_ENEMIES:
            self.assertLessEqual(max(self._pool_tiers(enemy_id)), 6, enemy_id)
        grunt = self.engine.content.enemies["undead"]  # no rare access
        self.assertFalse(grunt.rare_table_access)
        self.assertLessEqual(max(int(e.get("rarity_tier", 1)) for e in self.engine.loot_pool(grunt.create_enemy())), 3)

    # -- gear, not just weapons + junk kept --------------------------------

    def test_gear_can_drop_in_the_west_not_just_weapons(self):
        for enemy_id in ZONE2_LOOT_ENEMIES:
            ids = set(self._pool_ids(enemy_id))
            self.assertTrue(ids & self.gear_ids, f"{enemy_id} drops no gear")

    def test_junk_is_kept_as_a_gold_source(self):
        for enemy_id in ZONE2_LOOT_ENEMIES:
            self.assertTrue(set(self._pool_ids(enemy_id)) & JUNK, enemy_id)

    # -- Hollow Worg jackpot -----------------------------------------------

    def test_hollow_worg_is_the_top_band_jackpot(self):
        worg = self.engine.content.enemies["hollow_worg"]
        self.assertGreaterEqual(worg.drop_chance, 0.9)  # almost always drops
        tiers = self._pool_tiers("hollow_worg")
        self.assertGreaterEqual(max(tiers), 5)
        self.assertIn(6, tiers)  # worldsplitter via the shared rare table

    def test_hollow_worg_drops_both_gear_and_weapons(self):
        worg = self.engine.content.enemies["hollow_worg"]
        self.engine.rng = random.Random(3)
        dropped = collections.Counter()
        for _ in range(3000):
            drop = self.engine.roll_loot(worg.create_enemy())
            if drop is not None:
                dropped[drop.item_id] += 1
        self.assertTrue(set(dropped) & self.gear_ids)
        self.assertTrue(set(dropped) & self.weapon_ids)

    # -- core unchanged -----------------------------------------------------

    def test_core_enemy_loot_unchanged(self):
        self.assertEqual(
            [e["item_id"] for e in self.engine.content.enemies["giant_rat"].loot_table],
            ["rat_pelt", "hp_potion", "training_cap", "novice_ring", "worn_shortsword", "steel_greatsword"],
        )
        # shared core enemies keep their pre-zone3 access flags
        self.assertFalse(self.engine.content.enemies["undead"].rare_table_access)

    def test_core_giant_rat_never_rolls_above_tier_three(self):
        rat = self.engine.content.enemies["giant_rat"]
        self.assertLessEqual(max(int(e.get("rarity_tier", 1)) for e in self.engine.loot_pool(rat.create_enemy())), 3)


if __name__ == "__main__":
    unittest.main()
