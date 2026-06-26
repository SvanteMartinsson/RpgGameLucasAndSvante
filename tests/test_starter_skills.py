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

    def _starter_node(self, engine, class_id, skill_id):
        return next(n for n in engine.content.talents.values()
                    if n.class_id == class_id and n.node_type == "active"
                    and n.action_id == skill_id)

    def test_starter_skill_node_reads_learned_not_can_learn(self):
        # B7.1: the starter skill's talent node is LEARNED from class selection — not
        # offered again as "Can learn", and no talent point was spent on it.
        from rpg_game.presentation.talent_text import talent_status
        engine = GameEngine()
        for class_id, skill_id in EXPECTED_STARTERS.items():
            with self.subTest(class_id=class_id):
                engine.start_new_game("Hero", class_id)
                node = self._starter_node(engine, class_id, skill_id)
                self.assertIn(node.id, engine.player.learned_talent_ids)
                self.assertEqual(talent_status(engine, node), "[LEARNED]")
                self.assertNotIn(node.id, {t.id for t in engine.available_talents()})
                self.assertEqual(engine.player.talent_points, 0)  # starter was free

    def test_starter_branch_continues_without_double_paying(self):
        # The node after the starter is available immediately (its prerequisite, the
        # starter root, is already learned) and costs exactly ONE point — not two.
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        starter = self._starter_node(engine, "fighter", "frenzy")
        nxt = next(n for n in engine.content.talents.values()
                   if n.class_id == "fighter" and n.branch == starter.branch
                   and n.order == starter.order + 1)
        self.assertIn(nxt.id, {t.id for t in engine.available_talents()})
        engine.player.talent_points = 1
        engine.allocate_talent(nxt.id)
        self.assertEqual(engine.player.talent_points, 0)
        self.assertIn(nxt.id, engine.player.learned_talent_ids)


if __name__ == "__main__":
    unittest.main()
