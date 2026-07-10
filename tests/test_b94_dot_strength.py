"""B94: DoT ticks rebalanced to meaningful levels.

Principle (Lucas): a DoT's TOTAL over its duration ~1.3-1.6x a comparable
same-cost direct skill (the delay premium), and a single tick should be felt
(>= ~4-6% of an on-level standard enemy's HP) — symmetrically for enemy DoTs.
Spell-scaled player DoTs sat ABOVE the band (3.0x source total vs a ~1.45x
nuke) and were trimmed to 0.75x/tick; flat ones were raised. Locks the data
and the computed tick at cast time.
"""

import random
import unittest

from rpg_game.core import combat
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine
from rpg_game.core.progression import round_half_up


class DotDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actions = load_content().actions

    def _dot(self, action_id):
        return next(e for e in self.actions[action_id].effects
                    if e.type == "apply_status"
                    and (e.status_type in combat.DAMAGE_TYPES or e.tag in combat.DAMAGE_TYPES))

    def test_spell_scaled_player_dots_sit_in_the_band(self):
        # total = 3 ticks x 0.75 = 2.25x source vs a same-cost ~1.45x nuke -> ~1.55x
        for action_id in ("plague_bolt", "venom_trap", "plague_ooze", "immolate", "ignite"):
            effect = self._dot(action_id)
            self.assertEqual(effect.scale, "spell", action_id)
            self.assertEqual(effect.multiplier, 0.75, action_id)

    def test_flat_dot_magnitudes(self):
        self.assertEqual(self._dot("rupture").magnitude, 14)
        self.assertEqual(self._dot("poison_sting").magnitude, 6)
        self.assertEqual(self._dot("spider_venom").magnitude, 8)
        self.assertEqual(self._dot("rotting_grasp").magnitude, 8)
        self.assertEqual(self._dot("rat_king_plague_leap").magnitude, 6)
        self.assertEqual(self._dot("briar_lash").magnitude, 7)

    def test_cast_immolate_ticks_at_three_quarters_of_spell_source(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "mage")
        player = engine.player
        weapon = engine.content.weapons[player.equipped_weapon_id]
        enemy = engine.content.enemies["cave_bear"].create_enemy()
        combat.resolve_action(player, enemy, engine.content.actions["immolate"],
                              weapon=weapon, rng=random.Random(0))
        status = next(s for s in enemy.active_statuses if s.type == "fire")
        expected = round_half_up(combat.spell_source_value(player, weapon) * 0.75)
        self.assertEqual(status.magnitude, expected)


if __name__ == "__main__":
    unittest.main()
