"""Wisdom slice A: player magic effects use scale "spell" =
round(0.4 * (damage + magic weapon bonus) + 0.6 * wisdom), times the per-spell
multiplier. Enemies have no wisdom, so for them spell degrades to the power-
equivalent (their actions are unchanged). Multipliers/split are placeholders.
"""

import random
import unittest

from rpg_game.core import combat
from rpg_game.core.game import GameEngine
from rpg_game.core.progression import round_half_up

SPELL = 0.4, 0.6  # damage weight, wisdom weight


class SpellScalingTests(unittest.TestCase):
    def _cleric(self):
        e = GameEngine(rng=random.Random(1)); e.start_new_game("Cleric", "cleric")
        return e

    def test_spell_source_blends_damage_and_wisdom(self):
        e = self._cleric()
        mace = e.content.weapons["holy_mace"]
        expected = round_half_up(0.4 * (e.player.base_damage + mace.damage_bonus)
                                 + 0.6 * e.player.wisdom)
        self.assertEqual(combat.spell_source_value(e.player, mace), expected)

    def test_smite_uses_spell_scale(self):
        # cleric (dmg 10, wisdom 6), holy_mace +0 -> source 8; smite x1.5 -> 12 vs a
        # neutral target (giant_rat: holy 1.0, armor 0).
        e = self._cleric()
        rat = e.content.enemies["giant_rat"].create_enemy(); rat.hp = 999
        result = combat.resolve_action(e.player, rat, e.content.actions["smite"], e.rng,
                                       weapon=e.content.weapons["holy_mace"])
        src = combat.spell_source_value(e.player, e.content.weapons["holy_mace"])
        self.assertEqual(result.total_damage, round_half_up(src * 1.5))

    def test_smite_scales_with_wisdom(self):
        e = self._cleric()
        rat = e.content.enemies["giant_rat"].create_enemy(); rat.hp = 999
        low = combat.resolve_action(e.player, rat, e.content.actions["smite"], e.rng,
                                    weapon=e.content.weapons["holy_mace"]).total_damage
        e.player.wisdom += 50
        rat2 = e.content.enemies["giant_rat"].create_enemy(); rat2.hp = 999
        high = combat.resolve_action(e.player, rat2, e.content.actions["smite"], e.rng,
                                     weapon=e.content.weapons["holy_mace"]).total_damage
        self.assertGreater(high, low)

    def test_player_dot_magnitude_scales_with_wisdom(self):
        e = self._cleric()
        t1 = e.content.enemies["giant_rat"].create_enemy()
        combat.resolve_action(e.player, t1, e.content.actions["plague_bolt"], e.rng)
        base = t1.active_statuses[0].magnitude
        e.player.wisdom += 50
        t2 = e.content.enemies["giant_rat"].create_enemy()
        combat.resolve_action(e.player, t2, e.content.actions["plague_bolt"], e.rng)
        self.assertGreater(t2.active_statuses[0].magnitude, base)

    def test_enemy_spell_is_power_equivalent_not_wisdom(self):
        # An enemy has no wisdom: spell_source == its damage (so a shared damage
        # spell like firebolt keeps its old enemy value).
        e = self._cleric()
        mira = e.content.enemies["arena_mira_candlewick"].create_enemy()
        self.assertEqual(combat.spell_source_value(mira, None), mira.damage)


if __name__ == "__main__":
    unittest.main()
