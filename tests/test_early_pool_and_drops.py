"""Broader early enemy pool + low-tier weapon drops in the playable zone."""

import random
import unittest

from rpg_game.core.game import GameEngine


class EarlyPoolAndDropsTest(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine()
        self.engine.start_new_game("Hero", "fighter")

    def _loot_ids(self, enemy_id):
        return [entry["item_id"] for entry in self.engine.content.enemies[enemy_id].loot_table]

    # -- broader pool -------------------------------------------------------

    def test_core_zone_pool_has_more_than_two_types(self):
        pool = set(self.engine.content.places["burg_54"].encounters)
        self.assertEqual(pool, {"giant_rat", "undead", "cave_bear", "undead_priest"})
        self.assertGreater(len(pool), 2)  # no longer just rat + undead on repeat

    # -- low-tier weapons exist --------------------------------------------

    def test_low_tier_weapons_added(self):
        weapons = self.engine.content.weapons
        for wid, bonus, tier in [("worn_shortsword", 2, 1), ("hunting_bow", 3, 1), ("iron_hatchet", 4, 2)]:
            self.assertIn(wid, weapons)
            self.assertEqual(weapons[wid].damage_bonus, bonus)
            self.assertEqual(weapons[wid].tier, tier)
            self.assertLessEqual(weapons[wid].tier, 2)  # genuinely low tier

    # -- drops from early enemies ------------------------------------------

    def test_early_enemies_can_drop_low_tier_weapons(self):
        self.assertIn("worn_shortsword", self._loot_ids("giant_rat"))
        self.assertIn("hunting_bow", self._loot_ids("undead"))
        self.assertIn("iron_hatchet", self._loot_ids("cave_bear"))

    def test_low_tier_weapon_actually_drops(self):
        rat = self.engine.content.enemies["giant_rat"]
        self.engine.rng = random.Random(0)
        dropped = set()
        for _ in range(3000):
            drop = self.engine.roll_loot(rat)
            if drop is not None:
                dropped.add(drop.item_id)
        self.assertIn("worn_shortsword", dropped)

    def test_existing_drops_unchanged(self):
        # Appending new weapons must not remove the original entries.
        self.assertTrue(
            {"rat_pelt", "hp_potion", "training_cap", "novice_ring", "steel_greatsword"}
            <= set(self._loot_ids("giant_rat"))
        )
        self.assertTrue(
            {"bone_dust", "hp_potion", "padded_vest", "focus_band", "rimebrand"}
            <= set(self._loot_ids("undead"))
        )


if __name__ == "__main__":
    unittest.main()
