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


if __name__ == "__main__":
    unittest.main()
