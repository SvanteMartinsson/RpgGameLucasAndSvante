"""B78: skill/talent texts read as player language — raw internal stat names
(damage_dealt_mod & friends) must never surface in a menu string."""

import random
import unittest

from rpg_game.core.game import GameEngine
from rpg_game.presentation.talent_text import describe_effect, describe_talent

RAW_TOKENS = ("damage_dealt_mod", "damage_taken_mod", "crit_chance",
              "evasion_chance", "accuracy_mod", "max_hp", "max_mana",
              "skip_turn", "status_type", "_")


class ReadableTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = GameEngine(rng=random.Random(0))
        cls.engine.start_new_game("Hero", "fighter")

    def test_no_talent_description_leaks_raw_stat_names(self):
        for node in self.engine.content.talents.values():
            text = describe_talent(self.engine, node)
            for token in ("damage_dealt_mod", "damage_taken_mod", "evasion_chance",
                          "crit_chance", "accuracy_mod", "skip_turn"):
                self.assertNotIn(token, text, f"{node.id}: {text}")

    def test_no_action_effect_leaks_raw_stat_names(self):
        for action in self.engine.content.actions.values():
            for effect in action.effects:
                text = describe_effect(effect)
                for token in ("damage_dealt_mod", "damage_taken_mod", "evasion_chance",
                              "accuracy_mod", "skip_turn"):
                    self.assertNotIn(token, text, f"{action.id}: {text}")

    def test_percent_stats_phrase_with_percent(self):
        for node in self.engine.content.talents.values():
            if "reckless" in node.id:
                text = describe_talent(self.engine, node)
                self.assertIn("+50% damage dealt", text)
                self.assertIn("+25% damage taken", text)
                return
        self.fail("no reckless node found")


if __name__ == "__main__":
    unittest.main()
