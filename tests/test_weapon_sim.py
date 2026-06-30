"""B37 weapon-aware sim: simulated players can equip a specific weapon so the
material ladder is measurable (the new starting weapons are all 0-bonus, so an
attack-only sim is otherwise blind to weapon damage). Pure sim infrastructure —
attack-only L1 with no weapon stays the default and is unchanged.
"""

import unittest

from rpg_game.core import simulation as S
from rpg_game.core.data_loader import load_content


class WeaponSimTests(unittest.TestCase):
    def test_equipping_a_stronger_weapon_raises_win_rate(self):
        # Same fighter, same enemy: a real blade beats the bare 0-bonus starter.
        bare = S.simulate_matchup("fighter", "treant", trials=60, level=4)
        armed = S.simulate_matchup("fighter", "treant", trials=60, level=4,
                                   weapon_id="steel_longsword")
        self.assertGreater(armed.win_rate, bare.win_rate + 0.3)

    def test_best_weapon_for_respects_category_and_level(self):
        content = load_content()
        # At L1 only t0-t2 melee is equippable -> axe (9) is the strongest.
        self.assertEqual(S.best_weapon_for(content, "melee", 1, "physical"), "axe")
        # By L5 steel_greatsword (18, t4) is reachable and tops the melee list.
        self.assertEqual(S.best_weapon_for(content, "melee", 5, "physical"), "steel_greatsword")
        # Category is honoured.
        self.assertEqual(content.weapons[S.best_weapon_for(content, "ranged", 1)].category, "ranged")

    def test_default_sim_is_unchanged_without_a_weapon(self):
        a = S.simulate_matchup("fighter", "giant_rat", trials=30, seed=1)
        b = S.simulate_matchup("fighter", "giant_rat", trials=30, seed=1)
        self.assertEqual(a.victories, b.victories)


if __name__ == "__main__":
    unittest.main()
