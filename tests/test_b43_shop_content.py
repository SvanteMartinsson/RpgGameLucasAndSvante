"""B43: curated shop inventories for the newly-activated store towns.

Locks Lucas's shop philosophy — shops fill gaps + small upgrades, you PERFORM
for your gear: every store carries at most ONE rare item, none is left on the
thin default four, and every listed id is a real item. Also checks the B46
wisdom pieces are reachable via a shop.
"""

import unittest

from rpg_game.core.data_loader import load_content

DEFAULT_FOUR = {"hp_potion", "sword", "axe", "longsword"}


class ShopContentTests(unittest.TestCase):
    def setUp(self):
        self.content = load_content()

    def _rarity(self, item_id):
        if item_id in self.content.weapons:
            return getattr(self.content.weapons[item_id], "rarity", "common") or "common"
        if item_id in self.content.gear_items:
            return self.content.gear_items[item_id].rarity
        return "common"  # consumables/materials

    def _stores(self):
        return [p for p in self.content.places.values() if p.has_store]

    def test_no_store_is_left_on_the_default_four(self):
        for place in self._stores():
            self.assertNotEqual(set(place.store_inventory), DEFAULT_FOUR,
                                f"{place.id} still carries only the default four")

    def test_every_store_has_at_most_one_rare(self):
        for place in self._stores():
            rares = [i for i in place.store_inventory if self._rarity(i) == "rare"]
            self.assertLessEqual(len(rares), 1, f"{place.id} has {len(rares)} rares: {rares}")

    def test_every_store_item_is_a_real_item(self):
        valid = set(self.content.weapons) | set(self.content.gear_items) | set(self.content.items)
        for place in self._stores():
            for item_id in place.store_inventory:
                self.assertIn(item_id, valid, f"{place.id}: unknown item {item_id}")

    def test_wisdom_gear_is_reachable_in_a_shop(self):
        # B46 reachability: casters can buy an early wisdom piece somewhere.
        stocked = set()
        for place in self._stores():
            stocked |= set(place.store_inventory)
        self.assertTrue({"acolyte_charm", "seer_pendant", "oracle_loop"} & stocked,
                        "no wisdom gear stocked in any shop")


if __name__ == "__main__":
    unittest.main()
