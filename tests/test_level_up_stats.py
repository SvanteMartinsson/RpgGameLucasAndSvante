"""B35: at level-up the player picks a main stat (HP / Mana / Damage / Crit, no
Speed). Universal + flat bundle: every stat gets its baseline, the main stat gets
the bigger main value instead. The pick is applied to persistent player stats.
"""

import os
import tempfile
import unittest

from rpg_game.core import progression
from rpg_game.core.game import GameEngine


class LevelUpStatTests(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine()
        self.engine.start_new_game("Hero", "fighter")

    def _baseline(self):
        p = self.engine.player
        return (p.max_hp, p.max_mana, p.base_damage, p.crit_chance)

    def _apply(self, stat):
        self.engine.player.pending_stat_choices += 1
        before = self._baseline()
        self.engine.apply_stat_choice(stat)
        after = self._baseline()
        return tuple(a - b for a, b in zip(after, before))  # (dhp, dmana, ddmg, dcrit)

    def test_each_main_choice_applies_baseline_plus_main(self):
        # (HP, Mana, Damage, Crit) deltas — main +8/+8/+4/+4, others +2/+2/+1/+1.
        self.assertEqual(self._apply("hp"), (8, 2, 1, 1))
        self.assertEqual(self._apply("mana"), (2, 8, 1, 1))
        self.assertEqual(self._apply("damage"), (2, 2, 4, 1))
        self.assertEqual(self._apply("crit"), (2, 2, 1, 4))

    def test_no_level_scaling_or_per_class_difference(self):
        # The bundle is identical at any level and for any class.
        for class_id in ("fighter", "mage", "rogue", "tank", "cleric", "hunter"):
            eng = GameEngine(); eng.start_new_game("H", class_id)
            eng.player.level = 6
            eng.player.pending_stat_choices = 1
            base = (eng.player.max_hp, eng.player.max_mana, eng.player.base_damage, eng.player.crit_chance)
            eng.apply_stat_choice("damage")
            delta = (eng.player.max_hp - base[0], eng.player.max_mana - base[1],
                     eng.player.base_damage - base[2], eng.player.crit_chance - base[3])
            self.assertEqual(delta, (2, 2, 4, 1), class_id)

    def test_speed_is_not_a_choice(self):
        self.assertNotIn("speed", progression.LEVEL_STAT_MAIN)
        with self.assertRaises(ValueError):
            self.engine.player.pending_stat_choices = 1
            self.engine.apply_stat_choice("speed")

    def test_choice_consumes_one_pending_and_requires_one(self):
        with self.assertRaises(ValueError):
            self.engine.apply_stat_choice("hp")          # none pending
        self.engine.player.pending_stat_choices = 2
        self.engine.apply_stat_choice("hp")
        self.assertEqual(self.engine.player.pending_stat_choices, 1)

    def test_chosen_stats_persist_through_save_load(self):
        self.engine.player.pending_stat_choices = 1
        self.engine.apply_stat_choice("crit")
        snapshot = (self.engine.player.max_hp, self.engine.player.max_mana,
                    self.engine.player.base_damage, self.engine.player.crit_chance)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "save.json")
            self.engine.save(path)
            loaded = GameEngine(content=self.engine.content)
            loaded.load(path)
        self.assertEqual((loaded.player.max_hp, loaded.player.max_mana,
                          loaded.player.base_damage, loaded.player.crit_chance), snapshot)


if __name__ == "__main__":
    unittest.main()
