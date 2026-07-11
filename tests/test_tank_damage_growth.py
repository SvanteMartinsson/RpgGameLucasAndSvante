"""Lever e (progression pass 2026-07-12): the tank's automatic base-damage
growth per level — applied on every level gain regardless of main-stat choice,
and ONLY for the tank."""

import unittest

from rpg_game.core import progression
from rpg_game.core.game import GameEngine


def _level_once(engine):
    engine.player.xp = 0
    progression.award_xp(engine.player, engine.player.xp_required)
    while engine.player.pending_stat_choices:
        engine.apply_stat_choice("hp")


class TankDamageGrowthTests(unittest.TestCase):
    def test_tank_gains_class_damage_on_level_even_maining_hp(self):
        engine = GameEngine()
        engine.start_new_game("T", "tank")
        before = engine.player.base_damage
        _level_once(engine)
        gained = engine.player.base_damage - before
        # class growth + the hp-main baseline (+1 damage)
        self.assertEqual(gained,
                         progression.CLASS_DAMAGE_PER_LEVEL["tank"]
                         + progression.LEVEL_STAT_BASELINE["damage"])

    def test_other_classes_get_no_class_damage_growth(self):
        for class_id in ("fighter", "mage", "rogue", "cleric", "hunter"):
            engine = GameEngine()
            engine.start_new_game("H", class_id)
            before = engine.player.base_damage
            _level_once(engine)
            self.assertEqual(engine.player.base_damage - before,
                             progression.LEVEL_STAT_BASELINE["damage"], class_id)

    def test_growth_applies_per_level_in_multi_level_awards(self):
        engine = GameEngine()
        engine.start_new_game("T", "tank")
        before = engine.player.base_damage
        levels = progression.award_xp(engine.player, 10 + 30 + 225)  # L1->L4
        self.assertEqual(levels, 3)
        self.assertEqual(engine.player.base_damage - before,
                         3 * progression.CLASS_DAMAGE_PER_LEVEL["tank"])


if __name__ == "__main__":
    unittest.main()
