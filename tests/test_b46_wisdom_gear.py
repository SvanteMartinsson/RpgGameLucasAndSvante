"""B46: wisdom-bearing gear.

Casters can now scale spell-power + mana through equipment, not only level-ups.
Locks that the new pieces are valid gear, that equipping wisdom raises effective
wisdom, the DERIVED max_mana (wisdom * MANA_PER_WISDOM + any max_mana bonus), and
the spell source value the caster pipeline reads.
"""

import random
import unittest

from rpg_game.core import combat
from rpg_game.core.data_loader import load_content
from rpg_game.core.entities import MANA_PER_WISDOM
from rpg_game.core.equipment import ALLOWED_GEAR_STATS
from rpg_game.core.game import GameEngine

WISDOM_GEAR = ["acolyte_charm", "seer_pendant", "runed_circlet", "oracle_loop",
               "mystic_robe", "archon_signet"]


class WisdomGearDataTests(unittest.TestCase):
    def setUp(self):
        self.content = load_content()

    def test_wisdom_is_an_allowed_gear_stat(self):
        self.assertIn("wisdom", ALLOWED_GEAR_STATS)

    def test_all_pieces_load_and_carry_wisdom(self):
        for gid in WISDOM_GEAR:
            self.assertIn(gid, self.content.gear_items, gid)
            gear = self.content.gear_items[gid]
            self.assertGreater(gear.stat_modifiers.get("wisdom", 0), 0, gid)
            self.assertIn(gear.slot_type, {"amulet", "ring", "head", "chest"}, gid)


class WisdomGearEffectTests(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(rng=random.Random(0))
        self.engine.start_new_game("Mage", "mage")
        self.player = self.engine.player

    def _own_and_equip(self, gid, slot):
        self.player.owned_gear_ids = (*self.player.owned_gear_ids, gid)
        return self.engine.equip_gear(gid, slot)

    def test_equipping_wisdom_raises_effective_wisdom_and_derived_mana(self):
        w0 = combat.effective_stat(self.player, "wisdom")
        m0 = combat.effective_stat(self.player, "max_mana")
        self.assertTrue(self._own_and_equip("acolyte_charm", "amulet").success)
        self.assertEqual(combat.effective_stat(self.player, "wisdom"), w0 + 1)
        self.assertEqual(combat.effective_stat(self.player, "max_mana"), m0 + 1 * MANA_PER_WISDOM)

    def test_mixed_wisdom_and_flat_mana_piece_sums_both(self):
        self.player.level = 3  # seer_pendant requires L3
        w0 = combat.effective_stat(self.player, "wisdom")
        m0 = combat.effective_stat(self.player, "max_mana")
        self.assertTrue(self._own_and_equip("seer_pendant", "amulet").success)
        self.assertEqual(combat.effective_stat(self.player, "wisdom"), w0 + 2)
        # +2 wisdom -> +2*MANA_PER_WISDOM derived, plus the piece's flat max_mana +4
        self.assertEqual(combat.effective_stat(self.player, "max_mana"), m0 + 2 * MANA_PER_WISDOM + 4)

    def test_spell_source_value_rises_with_wisdom_gear(self):
        self.player.level = 8  # archon_signet requires L8
        before = combat.spell_source_value(self.player, None)
        self.assertTrue(self._own_and_equip("archon_signet", "ring_1").success)
        after = combat.spell_source_value(self.player, None)
        # +4 wisdom * SPELL_WISDOM_WEIGHT (0.6) = +2.4 -> at least +2 after rounding
        self.assertGreaterEqual(after, before + 2)


if __name__ == "__main__":
    unittest.main()
