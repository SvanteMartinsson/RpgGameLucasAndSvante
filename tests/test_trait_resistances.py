"""Trait-driven resistances: `traits` are the source of truth and the combat
pipeline's `resistances` dict is derived from them at load. Locks the exact
derived matrix and the combination rules (sum -> clamp -> map, immune absolute).
"""

import unittest

from rpg_game.core import traits
from rpg_game.core.data_loader import load_content


def _r(enemy, damage_type):
    # Mirrors combat.get_resistance: missing type defaults to neutral 1.0.
    return enemy.resistances.get(damage_type, 1.0)


# (fire, frost, holy, poison, physical, lightning) the derivation must produce.
EXPECTED = {
    "cave_bear":      {"fire": 2.0, "frost": 0.65, "holy": 1.0, "poison": 1.25, "physical": 1.0, "lightning": 1.0},
    "dire_wolf":      {"fire": 2.0, "frost": 0.65, "holy": 1.0, "poison": 1.25, "physical": 1.0, "lightning": 1.0},
    "wild_boar":      {"fire": 2.0, "frost": 0.65, "holy": 1.0, "poison": 1.25, "physical": 1.0, "lightning": 1.0},
    "treant":         {"fire": 2.0, "frost": 0.65, "holy": 1.0, "poison": 1.0, "physical": 1.0, "lightning": 1.0},
    "tar_beast":      {"fire": 0.65, "frost": 2.0, "holy": 1.0, "poison": 0.65, "physical": 1.0, "lightning": 1.0},
    "mutated_mudcrab": {"fire": 1.5, "frost": 1.5, "holy": 1.0, "poison": 1.0, "physical": 1.0, "lightning": 1.0},
    "hollow_worg":    {"fire": 2.0, "frost": 0.65, "holy": 1.5, "poison": 1.25, "physical": 0.65, "lightning": 1.0},
    "undead":         {"fire": 1.0, "frost": 0.65, "holy": 2.0, "poison": 0.0, "physical": 1.0, "lightning": 1.0},
    "undead_priest":  {"fire": 1.0, "frost": 0.65, "holy": 2.0, "poison": 0.0, "physical": 1.0, "lightning": 1.0},
    "bog_wraith":     {"fire": 0.65, "frost": 1.5, "holy": 2.0, "poison": 0.0, "physical": 1.0, "lightning": 1.0},
    "plague_acolyte": {"fire": 1.0, "frost": 1.0, "holy": 1.5, "poison": 1.0, "physical": 0.65, "lightning": 1.0},
    "giant_rat":      {"fire": 1.0, "frost": 1.0, "holy": 1.0, "poison": 1.0, "physical": 1.0, "lightning": 1.0},
    "arena_ralla_quickstep": {"fire": 1.0, "frost": 1.0, "holy": 1.0, "poison": 1.0, "physical": 1.0, "lightning": 1.0},
    "arena_mira_candlewick": {"fire": 1.0, "frost": 1.0, "holy": 1.0, "poison": 1.0, "physical": 1.0, "lightning": 1.0},
}


class TraitMatrixTests(unittest.TestCase):
    def setUp(self):
        self.content = load_content()

    def test_derived_matrix_is_exact(self):
        for enemy_id, expected in EXPECTED.items():
            enemy = self.content.enemies[enemy_id]
            for damage_type, want in expected.items():
                self.assertAlmostEqual(
                    _r(enemy, damage_type), want, places=9,
                    msg=f"{enemy_id} / {damage_type}",
                )

    def test_lightning_is_always_neutral(self):
        # No trait touches lightning -> 1.0 for every enemy.
        for enemy in self.content.enemies.values():
            self.assertEqual(_r(enemy, "lightning"), 1.0, enemy.id)

    def test_every_enemy_has_at_most_two_traits(self):
        for enemy in self.content.enemies.values():
            self.assertLessEqual(len(enemy.traits), 2, enemy.id)


class TraitCombinationTests(unittest.TestCase):
    def test_beast_swamp_sums_then_maps(self):
        # fire: +3 (beast) -1 (swamp) = +2 -> 1.5 ; frost: -1 +3 = +2 -> 1.5
        r = traits.resistances_from_traits(["beast", "swamp"])
        self.assertEqual(r["fire"], 1.5)
        self.assertEqual(r["frost"], 1.5)
        self.assertEqual(r.get("poison", 1.0), 1.0)  # +1 -1 = 0 -> neutral

    def test_undead_swamp_frost(self):
        # frost: -1 (undead) +3 (swamp) = +2 -> 1.5
        r = traits.resistances_from_traits(["undead", "swamp"])
        self.assertEqual(r["frost"], 1.5)

    def test_immunity_is_absolute(self):
        # undead grants poison IMMUNE; swamp's -1 step cannot lift it off 0.0.
        r = traits.resistances_from_traits(["undead", "swamp"])
        self.assertEqual(r["poison"], 0.0)

    def test_steps_clamp_to_plus_three(self):
        # beast +3 and plant +3 on fire = +6, clamped to +3 -> 2.0 (not higher).
        r = traits.resistances_from_traits(["beast", "plant"])
        self.assertEqual(r["fire"], 2.0)

    def test_unknown_trait_contributes_nothing(self):
        self.assertEqual(traits.resistances_from_traits(["nonsense"]), {})

    def test_empty_traits_is_fully_neutral(self):
        self.assertEqual(traits.resistances_from_traits([]), {})


if __name__ == "__main__":
    unittest.main()
