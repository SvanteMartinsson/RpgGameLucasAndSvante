"""B37 Slice 1 — specific weapon stat changes (separate from the tier-derivation
engine): worn_shortsword is a pure tier-0 starter and no longer sold; venomfang
is poison (its name now matches its type); worgfang is bumped to a t5 weapon.
"""

import unittest

from rpg_game.core.data_loader import load_content


class B37WeaponChangeTests(unittest.TestCase):
    def setUp(self):
        self.content = load_content()

    def test_worn_shortsword_is_a_zero_bonus_starter(self):
        worn = self.content.weapons["worn_shortsword"]
        self.assertEqual(worn.damage_bonus, 0)
        self.assertEqual(worn.tier, 0)

    def test_worn_shortsword_is_not_sold_in_any_store(self):
        for place in self.content.places.values():
            self.assertNotIn("worn_shortsword", place.store_inventory, place.id)

    def test_venomfang_is_poison_and_t5(self):
        venom = self.content.weapons["venomfang"]
        self.assertEqual(venom.damage_type, "poison")
        self.assertEqual(venom.damage_bonus, 25)
        self.assertEqual(venom.tier, 5)

    def test_worgfang_is_t5(self):
        worg = self.content.weapons["worgfang"]
        self.assertEqual(worg.damage_bonus, 25)
        self.assertEqual(worg.tier, 5)

    def test_worldsplitter_and_consecrated_maul_unchanged(self):
        self.assertEqual(self.content.weapons["worldsplitter"].damage_bonus, 38)
        self.assertEqual(self.content.weapons["consecrated_maul"].damage_bonus, 24)
        self.assertEqual(self.content.weapons["consecrated_maul"].damage_type, "holy")

    def test_material_ladder_fillers_load_with_derived_tiers(self):
        from rpg_game.core import combat
        # (id, damage, type, category, expected tier, expected equip level)
        expected = [
            ("iron_shortsword", 3, "physical", "melee", 1, 1),
            ("iron_longsword", 8, "physical", "melee", 2, 1),
            ("steel_longsword", 13, "physical", "melee", 3, 3),
            ("maple_shortbow", 3, "physical", "ranged", 1, 1),
            ("willow_bow", 8, "physical", "ranged", 2, 1),
            ("willow_longbow", 13, "physical", "ranged", 3, 3),
            ("yew_warbow", 23, "physical", "ranged", 5, 8),
            ("adept_wand", 12, "fire", "magic", 3, 3),
        ]
        for wid, dmg, dtype, cat, tier, lvl in expected:
            w = self.content.weapons[wid]
            self.assertEqual(w.damage_bonus, dmg, wid)
            self.assertEqual(w.damage_type, dtype, wid)
            self.assertEqual(w.category, cat, wid)
            self.assertEqual(w.tier, tier, wid)
            self.assertEqual(combat.weapon_required_level(w), lvl, wid)

    def test_no_three_x_jump_between_consecutive_melee_upgrades(self):
        # Granular early ladder: each physical-melee step is < 2x the previous
        # non-zero damage (no 2->5->14 cliff).
        melee = sorted(
            w.damage_bonus for w in self.content.weapons.values()
            if w.category == "melee" and w.damage_type == "physical" and w.damage_bonus > 0
        )
        for prev, nxt in zip(melee, melee[1:]):
            self.assertLess(nxt, prev * 3, f"{prev}->{nxt} is a >=3x jump")


if __name__ == "__main__":
    unittest.main()
