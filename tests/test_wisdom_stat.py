"""Wisdom slice A: wisdom is a real stat that DERIVES max_mana (no stored base)
and is the level-up caster choice (replacing the old mana pick). Values are
placeholders (MANA_PER_WISDOM, the +1/level) tuned in Slice B.
"""

import unittest

from rpg_game.core import entities, equipment, progression
from rpg_game.core.game import GameEngine


class WisdomStatTests(unittest.TestCase):
    def test_each_class_starts_with_wisdom_derived_mana(self):
        expected = {"cleric": 30, "fighter": 20, "tank": 15, "rogue": 20, "mage": 40, "hunter": 25}
        for cls, mana in expected.items():
            eng = GameEngine(); eng.start_new_game("H", cls)
            self.assertEqual(eng.effective_stat("max_mana"), mana, cls)
            self.assertEqual(eng.player.mana, mana, f"{cls} should start full")
            self.assertEqual(eng.player.wisdom * entities.MANA_PER_WISDOM, mana, cls)

    def test_max_mana_is_derived_not_a_stored_base(self):
        eng = GameEngine(); eng.start_new_game("H", "mage")
        eng.player.max_mana = 999          # stored base is IGNORED
        self.assertEqual(eng.effective_stat("max_mana"), eng.player.wisdom * 5)
        eng.player.wisdom += 2
        self.assertEqual(eng.effective_stat("max_mana"), (eng.player.wisdom) * 5)

    def test_wisdom_gear_bonus_raises_mana(self):
        eng = GameEngine(); eng.start_new_game("H", "cleric")
        base = eng.effective_stat("max_mana")
        eng.player.gear_stat_modifiers = {"wisdom": 2}
        self.assertEqual(eng.effective_stat("max_mana"), base + 2 * entities.MANA_PER_WISDOM)
        self.assertIn("wisdom", equipment.ALLOWED_GEAR_STATS)

    def test_level_up_offers_wisdom_not_mana(self):
        self.assertIn("wisdom", progression.LEVEL_STAT_MAIN)
        self.assertNotIn("mana", progression.LEVEL_STAT_MAIN)
        self.assertNotIn("mana", progression.LEVEL_STAT_BASELINE)
        with self.assertRaises(ValueError):
            eng = GameEngine(); eng.start_new_game("H", "mage")
            eng.player.pending_stat_choices = 1
            eng.apply_stat_choice("mana")

    def test_choosing_wisdom_raises_max_mana_by_five(self):
        eng = GameEngine(); eng.start_new_game("H", "mage")
        before = eng.effective_stat("max_mana")
        eng.player.pending_stat_choices = 1
        eng.apply_stat_choice("wisdom")
        self.assertEqual(eng.player.wisdom * 5, before + entities.MANA_PER_WISDOM)
        self.assertEqual(eng.effective_stat("max_mana"), before + entities.MANA_PER_WISDOM)


if __name__ == "__main__":
    unittest.main()
