"""B40 S5: character creation follows the menu spec.

Locks: every class offers exactly two tier-1 ACTIVE starter talents in a
stable order that includes the classic default, start_new_game's
starter_talent_id REPLACES the default (still exactly one free rank-1 talent,
its skill equipped) and rejects wrong class/order/passive picks, the class
stat preview carries no '(Mana X)' parenthesis, tree-preview tooltips build
from content alone, and engine_from_start_choice feeds the pick through
(older 2-tuple creation fns keep the class default). Skips without pygame.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.core import talents
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import talent_text
    from rpg_game.presentation.pygame_battle import _class_stat_rows
    from rpg_game.presentation.pygame_overworld import engine_from_start_choice

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class StarterChoiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.engine = GameEngine()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_every_class_offers_two_tier1_actives_including_the_default(self):
        for class_id, cls in self.engine.content.classes.items():
            picks = talent_text.starter_choices(self.engine.content, class_id)
            self.assertEqual(len(picks), 2, class_id)
            actions = {node.action_id for node in picks}
            for node in picks:
                self.assertEqual((node.order, node.node_type, node.class_id),
                                 (1, "active", class_id))
            for default in cls.starting_skill_ids:
                self.assertIn(default, actions, class_id)

    def test_starter_pick_replaces_the_default(self):
        engine = GameEngine()
        picks = talent_text.starter_choices(engine.content, "tank")
        other = next(n for n in picks
                     if n.action_id not in engine.content.classes["tank"].starting_skill_ids)
        engine.start_new_game("Hero", "tank", starter_talent_id=other.id)
        self.assertEqual(engine.player.equipped_skill_ids, (other.action_id,))
        self.assertEqual(engine.player.learned_talent_ids, {other.id})
        self.assertEqual(talents.talent_rank(engine.player, other.id), 1)
        self.assertEqual(engine.player.talent_points, 0)   # free, no leftovers
        self.assertIn(other.action_id,
                      talents.unlocked_skill_ids(engine.player, engine.content))

    def test_omitted_pick_keeps_the_class_default(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "tank")
        self.assertEqual(engine.player.equipped_skill_ids, ("block",))
        self.assertEqual(engine.player.learned_talent_ids, {"tank_guardian_g1_block"})

    def test_start_rejects_wrong_class_order_and_passives(self):
        engine = GameEngine()
        with self.assertRaises(ValueError):
            engine.start_new_game("H", "fighter",
                                  starter_talent_id="mage_pyromancer_y1_firebolt")
        deep = next(n.id for n in engine.content.talents.values()
                    if n.class_id == "fighter" and n.order > 1)
        with self.assertRaises(ValueError):
            engine.start_new_game("H", "fighter", starter_talent_id=deep)
        passive = next(n.id for n in engine.content.talents.values()
                       if n.class_id == "mage" and n.order == 1 and n.node_type == "passive")
        with self.assertRaises(ValueError):
            engine.start_new_game("H", "mage", starter_talent_id=passive)

    def test_stat_preview_has_no_parenthetical_mana(self):
        cls = self.engine.content.classes["mage"]
        rows = _class_stat_rows(self.engine, cls)
        for _stat, line in rows:
            self.assertNotIn("(", line, line)
        self.assertTrue(any(line.startswith("Wisdom") for _s, line in rows))

    def test_node_preview_lines_from_content_alone(self):
        pick = talent_text.starter_choices(self.engine.content, "fighter")[0]
        lines = talent_text.node_preview_lines(self.engine.content, pick)
        self.assertTrue(any("Unlocks skill" in line for line in lines))
        passive = next(n for n in self.engine.content.talents.values()
                       if n.node_type == "passive")
        self.assertIn("Passive", talent_text.node_preview_lines(self.engine.content, passive))

    def test_tree_columns_cover_the_whole_class(self):
        columns = talent_text.class_tree_columns(self.engine.content, "fighter")
        node_count = sum(len(nodes) for _b, nodes in columns)
        expected = sum(1 for n in self.engine.content.talents.values()
                       if n.class_id == "fighter")
        self.assertEqual(node_count, expected)
        for _branch, nodes in columns:
            self.assertEqual([n.order for n in nodes], sorted(n.order for n in nodes))

    def test_start_choice_feeds_the_pick_through(self):
        picks = talent_text.starter_choices(GameEngine().content, "hunter")
        other = next(n for n in picks if n.action_id != "aimed_shot")
        engine = engine_from_start_choice(
            "new", creation_fn=lambda e: ("Newbie", "hunter", other.id))
        self.assertEqual(engine.player.learned_talent_ids, {other.id})
        self.assertEqual(engine.player.equipped_skill_ids, (other.action_id,))

    def test_two_tuple_creation_fn_keeps_the_default(self):
        engine = engine_from_start_choice(
            "new", creation_fn=lambda e: ("Oldie", "tank"))
        self.assertEqual(engine.player.name, "Oldie")
        self.assertEqual(engine.player.equipped_skill_ids, ("block",))


if __name__ == "__main__":
    unittest.main()
