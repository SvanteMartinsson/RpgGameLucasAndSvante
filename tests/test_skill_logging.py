"""Combat log names the skill the actor used, not just its effects.

The engine result (events) is shared by every presentation layer (terminal and
pygame both render result.events), so locking it here covers both surfaces.
"""

import random
import unittest

from rpg_game.core import combat
from rpg_game.core.game import GameEngine


class SkillLoggingTest(unittest.TestCase):
    def _engine(self, class_id="rogue"):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Hero", class_id)
        return engine

    def test_non_damage_skill_logs_action_line_before_effect(self):
        engine = self._engine()
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        result = combat.resolve_action(engine.player, enemy, engine.content.actions["rupture"], engine.rng)

        self.assertEqual(result.events[0], "Hero used Rupture.")
        # Effect line still present, and it comes after the action line.
        bleed_idx = next(i for i, e in enumerate(result.events) if "bleed" in e)
        self.assertGreater(bleed_idx, 0)

    def test_damage_skill_is_named_without_a_redundant_use_line(self):
        engine = self._engine()
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        # Find a skill that deals direct damage.
        damage_skill = next(
            a for a in engine.content.actions.values()
            if a.kind == "skill" and combat.action_can_be_evaded(a)
        )
        result = combat.resolve_action(engine.player, enemy, damage_skill, engine.rng)

        # Named via its damage/miss/evade line, like a basic attack — no "used X." line.
        self.assertNotIn(f"Hero used {damage_skill.name}.", result.events)
        self.assertTrue(any(damage_skill.name in event for event in result.events))


if __name__ == "__main__":
    unittest.main()
