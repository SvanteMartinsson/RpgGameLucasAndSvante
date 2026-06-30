"""Wisdom slice A: wisdom is a real stat that DERIVES max_mana (no stored base)
and is the level-up caster choice (replacing the old mana pick). The ratio
(MANA_PER_WISDOM) and the wisdom level-up step were sim-tuned in Slice B; these
tests lock the RELATIONS to the live constants, not the numbers.
"""

import unittest

from rpg_game.core import entities, equipment, progression
from rpg_game.core.game import GameEngine


class WisdomStatTests(unittest.TestCase):
    def test_each_class_starts_with_wisdom_derived_mana(self):
        for cls in ("cleric", "fighter", "tank", "rogue", "mage", "hunter"):
            eng = GameEngine(); eng.start_new_game("H", cls)
            mana = eng.player.wisdom * entities.MANA_PER_WISDOM
            self.assertEqual(eng.effective_stat("max_mana"), mana, cls)
            self.assertEqual(eng.player.mana, mana, f"{cls} should start full")

    def test_max_mana_is_derived_not_a_stored_base(self):
        eng = GameEngine(); eng.start_new_game("H", "mage")
        eng.player.max_mana = 999          # stored base is IGNORED
        self.assertEqual(eng.effective_stat("max_mana"), eng.player.wisdom * entities.MANA_PER_WISDOM)
        eng.player.wisdom += 2
        self.assertEqual(eng.effective_stat("max_mana"), eng.player.wisdom * entities.MANA_PER_WISDOM)

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

    def test_choosing_wisdom_raises_max_mana_by_the_wisdom_step(self):
        eng = GameEngine(); eng.start_new_game("H", "mage")
        before = eng.effective_stat("max_mana")
        before_wisdom = eng.player.wisdom
        eng.player.pending_stat_choices = 1
        eng.apply_stat_choice("wisdom")
        step = progression.LEVEL_STAT_MAIN["wisdom"]   # wisdom gained per level-up
        self.assertEqual(eng.player.wisdom, before_wisdom + step)
        self.assertEqual(eng.effective_stat("max_mana"), before + step * entities.MANA_PER_WISDOM)


if __name__ == "__main__":
    unittest.main()
