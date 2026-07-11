"""B105: talent lists group per branch; cross-passives attach to their parent.

The grouping rule is shared (talent_text.grouped_class_talents): main branches
as sections with nodes in order-sequence, single-node cross-passive branches
(flametongue/rimeblade pattern) appended under the branch their prerequisite
lives in. Presentation only — the tree data is untouched. The overlay test
skips without pygame/pytmx.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from rpg_game.core.data_loader import load_content
from rpg_game.presentation.talent_text import (
    class_tree_columns,
    cross_passive_parent_branch,
    grouped_class_talents,
)

try:
    import pygame
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


class GroupingRuleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = load_content()

    def _sections(self, class_id):
        return dict(grouped_class_talents(self.content, class_id))

    def test_mage_has_two_sections_with_cross_passives_attached(self):
        sections = self._sections("mage")
        self.assertEqual(sorted(sections), ["cryomancer", "pyromancer"])
        names = {b: [n.name for n in nodes] for b, nodes in sections.items()}
        self.assertIn("Flametongue", names["pyromancer"])
        self.assertIn("Rimeblade", names["cryomancer"])
        # Cross-passives come after the branch's own nodes.
        self.assertEqual(names["pyromancer"][-1], "Flametongue")
        self.assertEqual(names["cryomancer"][-1], "Rimeblade")

    def test_cleric_sanctified_attaches_under_light(self):
        sections = self._sections("cleric")
        self.assertEqual(sorted(sections), ["light", "pest"])
        self.assertIn("Sanctified Strikes", [n.name for n in sections["light"]])

    def test_class_without_cross_passives_is_unchanged(self):
        for branch, nodes in grouped_class_talents(self.content, "fighter"):
            for node in nodes:
                self.assertEqual(node.branch, branch)

    def test_main_branch_nodes_stay_in_order_sequence(self):
        for class_id in ("mage", "cleric", "fighter"):
            for branch, nodes in grouped_class_talents(self.content, class_id):
                own = [n.order for n in nodes if n.branch == branch]
                self.assertEqual(own, sorted(own), f"{class_id}/{branch}")

    def test_cross_passive_detection(self):
        flametongue = next(n for n in self.content.talents.values()
                           if n.name == "Flametongue")
        firebolt_node = next(n for n in self.content.talents.values()
                             if n.name == "Firebolt rank-up"
                             or n.id == flametongue.requires)
        self.assertEqual(cross_passive_parent_branch(self.content, flametongue),
                         firebolt_node.branch)

    def test_creation_columns_have_no_cross_columns(self):
        self.assertEqual(len(class_tree_columns(self.content, "mage")), 2)
        self.assertEqual(len(class_tree_columns(self.content, "cleric")), 2)


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class OverlayGroupingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1280, 800))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _app(self, class_id):
        engine = GameEngine()
        engine.start_new_game("Hero", class_id)
        app = OverworldApp(engine=engine)
        app.open_overlay("skills_talents")
        app.draw()
        return app

    def test_selection_order_follows_grouped_display(self):
        app = self._app("mage")
        nodes = app.class_talent_nodes()
        branches = [n.name for n in nodes]
        # Rimeblade right after the cryomancer nodes, before any pyromancer node.
        self.assertLess(branches.index("Rimeblade"), branches.index("Firebolt rank-up")
                        if "Firebolt rank-up" in branches else len(branches))

    def test_cross_passive_row_carries_requires_marker(self):
        app = self._app("mage")
        labels = [b.label for b in app.buttons]
        self.assertTrue(any("Rimeblade" in l and "requires" in l for l in labels),
                        labels)
        # No row shows the old raw "(branch tN)" suffix.
        self.assertFalse(any("(pyromancer" in l or "(cryomancer" in l for l in labels))


if __name__ == "__main__":
    unittest.main()
