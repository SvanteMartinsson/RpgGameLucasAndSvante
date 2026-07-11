"""Lever f (progression pass 2026-07-12): the BUYABLE weapon ladder.

Every weapon category must offer shop-buyable commons stepping t1 -> t3 -> t4
-> t5 (equip gates L1/L3/L5/L8), so each ~2nd level has a purchasable damage
jump. Rares stay loot-only (B27); shops top out at t5 commons (B8-regeln).
"""

import unittest

from rpg_game.core import combat
from rpg_game.core.data_loader import load_content

CONTENT = load_content()


def _shop_ids():
    ids = set()
    for place in CONTENT.places.values():
        ids |= set(place.store_inventory)
    return {i for i in ids if i in CONTENT.weapons}


class WeaponLadderTests(unittest.TestCase):
    def test_every_category_has_a_buyable_t3_t4_t5_step(self):
        shop = _shop_ids()
        for category in ("melee", "magic", "ranged"):
            tiers = {CONTENT.weapons[i].tier for i in shop
                     if CONTENT.weapons[i].category == category}
            for tier in (3, 4, 5):
                self.assertIn(tier, tiers, (category, sorted(tiers)))

    def test_shop_weapons_are_commons_only(self):
        for item_id in _shop_ids():
            self.assertEqual(CONTENT.weapons[item_id].rarity, "common", item_id)

    def test_ladder_gates_step_l1_l3_l5_l8(self):
        shop = _shop_ids()
        for category in ("melee", "magic", "ranged"):
            gates = sorted({combat.weapon_required_level(CONTENT.weapons[i])
                            for i in shop
                            if CONTENT.weapons[i].category == category})
            self.assertEqual(gates, [1, 3, 5, 8], category)

    def test_new_melee_commons_slot_under_the_rare_alternatives(self):
        # the shop common of a tier stays weaker than that tier's loot rare
        self.assertLess(CONTENT.weapons["warsteel_blade"].damage_bonus,
                        CONTENT.weapons["steel_greatsword"].damage_bonus)
        self.assertLess(CONTENT.weapons["knight_greatsword"].damage_bonus,
                        CONTENT.weapons["worgfang"].damage_bonus)


if __name__ == "__main__":
    unittest.main()
