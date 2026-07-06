"""B58: apply_effect dispatches through EFFECT_HANDLERS — one handler per effect
type. Locks table totality (every effect type authored in content has a handler),
the unknown-type error, and that dispatch reaches the right handler (spot checks
through the public apply_effect entry point; behaviour itself is locked by the
existing combat suite)."""

import random
import unittest

from rpg_game.core import combat
from rpg_game.core.data_loader import load_content
from rpg_game.core.entities import EffectSpec
from rpg_game.core.game import GameEngine


class DispatchTableTests(unittest.TestCase):
    def test_every_authored_effect_type_has_a_handler(self):
        content = load_content()
        authored = set()
        for action in content.actions.values():
            authored |= {effect.type for effect in action.effects}
        for talent in content.talents.values():
            authored |= {effect.type for effect in talent.effects}
        missing = authored - set(combat.EFFECT_HANDLERS)
        self.assertFalse(missing, f"authored effect types without a handler: {missing}")

    def test_damage_aliases_share_one_handler(self):
        self.assertIs(combat.EFFECT_HANDLERS["damage"], combat.EFFECT_HANDLERS["instant_damage"])

    def test_unknown_effect_type_raises(self):
        engine = GameEngine(rng=random.Random(0))
        engine.start_new_game("Hero", "fighter")
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        bogus = EffectSpec(type="no_such_effect", target="enemy")
        with self.assertRaisesRegex(ValueError, "unknown effect type: no_such_effect"):
            combat.apply_effect(engine.player, enemy, bogus,
                                combat.ActionResolution("x", "X", "Hero", "Rat"), weapon=None)


class DispatchSpotChecks(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(rng=random.Random(0))
        self.engine.start_new_game("Hero", "fighter")
        self.enemy = self.engine.content.enemies["giant_rat"].create_enemy()
        self.result = combat.ActionResolution("x", "X", "Hero", "Rat")

    def _apply(self, **spec):
        effect = EffectSpec(**spec)
        combat.apply_effect(self.engine.player, self.enemy, effect, self.result,
                            weapon=None, rng=self.engine.rng)

    def test_heal_reaches_the_heal_handler(self):
        self.engine.player.hp -= 10
        before = self.engine.player.hp
        self._apply(type="heal", magnitude=6, target="self")
        self.assertEqual(self.engine.player.hp, before + 6)
        self.assertEqual(self.result.total_healing, 6)

    def test_damage_reaches_the_damage_handler(self):
        before = self.enemy.hp
        self._apply(type="instant_damage", scale="flat", magnitude=8,
                    damage_type="physical", target="enemy")
        self.assertLess(self.enemy.hp, before)
        self.assertTrue(self.result.damage_components)

    def test_immunity_reaches_the_immunity_handler(self):
        self._apply(type="immunity", tag="burn", target="self")
        self.assertIn("burn", self.engine.player.immunity_tags)

    def test_apply_status_reaches_the_status_handler(self):
        self._apply(type="apply_status", status_type="poison", tag="poison",
                    magnitude=3, duration=2, tick_timing="round_end",
                    damage_type="poison", target="enemy")
        self.assertTrue(any(s.tag == "poison" for s in self.enemy.active_statuses))


if __name__ == "__main__":
    unittest.main()
