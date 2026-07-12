"""B35: at level-up the player picks a main stat (HP / Mana / Damage / Crit, no
Speed). Universal + flat bundle: every stat gets its baseline, the main stat gets
the bigger main value instead. The pick is applied to persistent player stats.
"""

import os
import tempfile
import unittest

from rpg_game.core import entities, progression
from rpg_game.core.game import GameEngine


class LevelUpStatTests(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine()
        self.engine.start_new_game("Hero", "fighter")

    def _baseline(self):
        p = self.engine.player
        return (p.max_hp, p.wisdom, p.base_damage, p.crit_chance)

    def _apply(self, stat):
        self.engine.player.pending_stat_choices += 1
        before = self._baseline()
        self.engine.apply_stat_choice(stat)
        after = self._baseline()
        return tuple(a - b for a, b in zip(after, before))  # (dhp, dwisdom, ddmg, dcrit)

    def test_each_main_choice_applies_baseline_plus_main(self):
        # (HP, Wisdom, Damage, Crit) deltas. Mana is gone (derived from wisdom);
        # wisdom has no baseline, so non-wisdom picks raise it by 0. The wisdom
        # main step is sim-tuned (Slice B) -> read it from the table, not a literal.
        # Class-identity pass 2026-07-12: fighter is a glass cannon -> HP
        # baseline +2 (only the cleric keeps +3).
        wis = progression.LEVEL_STAT_MAIN["wisdom"]
        self.assertEqual(self._apply("hp"), (8, 0, 1, 1))
        self.assertEqual(self._apply("wisdom"), (2, wis, 1, 1))
        self.assertEqual(self._apply("damage"), (2, 0, 4, 1))
        self.assertEqual(self._apply("crit"), (2, 0, 1, 4))

    def test_choosing_wisdom_raises_derived_max_mana(self):
        before = self.engine.effective_stat("max_mana")
        self.engine.player.pending_stat_choices = 1
        self.engine.apply_stat_choice("wisdom")
        gained = progression.LEVEL_STAT_MAIN["wisdom"] * entities.MANA_PER_WISDOM
        self.assertEqual(self.engine.effective_stat("max_mana"), before + gained)

    def test_no_level_scaling_and_only_the_cleric_hp_exception(self):
        # The bundle is identical at any level; the ONLY per-class difference is
        # the cleric's HP baseline staying at +3 (class-identity pass 2026-07-12,
        # its defensive sustain identity) — every other class is the frail +2.
        for class_id in ("fighter", "mage", "rogue", "tank", "cleric", "hunter"):
            eng = GameEngine(); eng.start_new_game("H", class_id)
            eng.player.level = 6
            eng.player.pending_stat_choices = 1
            base = (eng.player.max_hp, eng.player.wisdom, eng.player.base_damage, eng.player.crit_chance)
            eng.apply_stat_choice("damage")
            delta = (eng.player.max_hp - base[0], eng.player.wisdom - base[1],
                     eng.player.base_damage - base[2], eng.player.crit_chance - base[3])
            hp_baseline = 3 if class_id == "cleric" else 2
            self.assertEqual(delta, (hp_baseline, 0, 4, 1), class_id)

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
        snapshot = (self.engine.player.max_hp, self.engine.player.wisdom,
                    self.engine.player.base_damage, self.engine.player.crit_chance)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "save.json")
            self.engine.save(path)
            loaded = GameEngine(content=self.engine.content)
            loaded.load(path)
        self.assertEqual((loaded.player.max_hp, loaded.player.wisdom,
                          loaded.player.base_damage, loaded.player.crit_chance), snapshot)


if __name__ == "__main__":
    unittest.main()
