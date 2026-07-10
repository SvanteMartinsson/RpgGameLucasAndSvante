"""B93: enemy AI avoids recasting a DoT on an already-afflicted target.

Refreshing a running DoT wastes the round; the AI picks another action when
any exists, falls back to the old behaviour when nothing else is ready, and a
DIFFERENT DoT type on the same target stays allowed. Deterministic (seeded).
"""

import random
import unittest

from rpg_game.core import combat
from rpg_game.core.data_loader import load_content
from rpg_game.core.entities import ActiveStatus
from rpg_game.core.game import GameEngine


class AiAvoidsDotRecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = load_content()

    def _player(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        return engine.player

    def _poisoned(self, player):
        player.active_statuses.append(
            ActiveStatus(type="poison", magnitude=3, duration=3, tick_timing="round_end")
        )
        return player

    def test_spider_never_recasts_poison_on_a_poisoned_target(self):
        spider = self.content.enemies["giant_spider"].create_enemy()
        target = self._poisoned(self._player())
        for seed in range(30):
            action = combat.choose_enemy_action(
                spider, target, self.content.actions, random.Random(seed))
            self.assertIsNotNone(action)
            self.assertNotEqual(action.id, "poison_sting", f"seed {seed}")

    def test_spider_still_uses_poison_on_a_clean_target(self):
        spider = self.content.enemies["giant_spider"].create_enemy()
        target = self._player()
        chosen = {
            combat.choose_enemy_action(
                spider, target, self.content.actions, random.Random(seed)).id
            for seed in range(30)
        }
        self.assertIn("poison_sting", chosen)

    def test_redundant_dot_is_allowed_when_it_is_the_only_option(self):
        spider = self.content.enemies["giant_spider"].create_enemy()
        spider.action_ids = ["poison_sting"]
        spider.ai = []
        target = self._poisoned(self._player())
        action = combat.choose_enemy_action(
            spider, target, self.content.actions, random.Random(0))
        self.assertIsNotNone(action)
        self.assertEqual(action.id, "poison_sting")

    def test_a_different_dot_type_is_not_redundant(self):
        fire_dot = self.content.actions["ignite"]
        target = self._poisoned(self._player())
        self.assertFalse(combat.action_reapplies_active_dot(fire_dot, target))
        poison_dot = self.content.actions["poison_sting"]
        self.assertTrue(combat.action_reapplies_active_dot(poison_dot, target))


if __name__ == "__main__":
    unittest.main()
