"""Every class starts with one equipped starter skill (B7).

Previously only Cleric had a starting skill (smite); the others started with an
empty loadout. Each class now starts with its signature first-branch active skill
(the same pattern as Cleric's smite = cleric_light_l1_smite), and that skill must
be a real, equipped action.
"""

import unittest

from rpg_game.core.game import GameEngine

EXPECTED_STARTERS = {
    "fighter": "frenzy",
    "tank": "block",
    "cleric": "smite",
    "rogue": "backstab",
    "mage": "firebolt",
    "hunter": "aimed_shot",
}


class StarterSkillTest(unittest.TestCase):
    def test_every_class_starts_with_its_signature_skill_equipped(self):
        engine = GameEngine()
        for class_id, skill_id in EXPECTED_STARTERS.items():
            with self.subTest(class_id=class_id):
                engine.start_new_game("Hero", class_id)
                self.assertEqual(engine.player.equipped_skill_ids, (skill_id,))
                # the starter is a real action and resolves through equipped_skills()
                self.assertIn(skill_id, engine.content.actions)
                self.assertIn(skill_id, {s.id for s in engine.equipped_skills()})

    def test_no_class_starts_with_an_empty_loadout(self):
        engine = GameEngine()
        for class_id in EXPECTED_STARTERS:
            engine.start_new_game("Hero", class_id)
            self.assertTrue(engine.player.equipped_skill_ids,
                            f"{class_id} has no starter skill")

    def test_starter_skills_respect_the_four_skill_cap(self):
        engine = GameEngine()
        for player_class in engine.content.classes.values():
            self.assertLessEqual(len(player_class.starting_skill_ids), 4)


if __name__ == "__main__":
    unittest.main()
