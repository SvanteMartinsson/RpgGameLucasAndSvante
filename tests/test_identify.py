import unittest

from rpg_game.core.game import GameEngine
from rpg_game.presentation import terminal


class IdentifyTests(unittest.TestCase):
    def test_identify_consumes_player_turn_enemy_acts_and_returns_reveal(self):
        engine = GameEngine(rng=ChoiceRng([0.0]))
        engine.start_new_game("Fighter", "fighter")
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        hp_before = engine.player.hp

        result = engine.run_combat_turn(enemy, "identify")

        self.assertEqual(result.outcome, "ongoing")
        self.assertLess(engine.player.hp, hp_before)
        self.assertEqual(enemy.hp, enemy.max_hp)
        self.assertTrue(enemy.identified)
        self.assertIsNotNone(result.enemy_reveal)
        self.assertEqual(result.enemy_reveal.level, enemy.level)
        self.assertEqual(result.enemy_reveal.power, enemy.damage)
        self.assertEqual(result.enemy_reveal.armor, enemy.armor)
        self.assertEqual(result.enemy_reveal.speed, enemy.speed)
        self.assertEqual(result.enemy_reveal.tags, ("beast",))
        self.assertEqual(result.enemy_reveal.skill_ids, ("power", "normal", "quick"))
        self.assertEqual(result.enemy_reveal.skills, ("Power attack", "Normal attack", "Quick attack"))
        self.assertTrue(any("dealt" in event for event in result.events))

    def test_enemy_details_are_hidden_until_identified_in_ui_status_lines(self):
        engine = GameEngine(rng=ChoiceRng([0.0]))
        engine.start_new_game("Fighter", "fighter")
        enemy = engine.content.enemies["giant_rat"].create_enemy()

        before = "\n".join(terminal.enemy_status_lines(engine, enemy))

        self.assertIn("Giant Rat: HP", before)
        self.assertNotIn("Level", before)
        self.assertNotIn("Power", before)
        self.assertNotIn("Tags", before)
        self.assertNotIn("Skills", before)

        result = engine.run_combat_turn(enemy, "identify")
        after = "\n".join(terminal.enemy_status_lines(engine, enemy))

        self.assertIsNotNone(result.enemy_reveal)
        self.assertIn("Level 1", after)
        self.assertIn("Power 6", after)
        self.assertIn("Tags: beast", after)
        self.assertIn("Skills: Power attack, Normal attack, Quick attack", after)


class ChoiceRng:
    def __init__(self, values):
        self.values = list(values)

    def random(self):
        if self.values:
            return self.values.pop(0)
        return 0.0

    def randint(self, minimum, _maximum):
        return minimum

    def choice(self, values):
        return values[-1]


if __name__ == "__main__":
    unittest.main()
