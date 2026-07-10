"""B89: tome tooltips explain what the taught skill DOES on every surface.

The shared wording comes from talent_text.skill_effect_lines (the B78
formatter) so the tome shop, the inventory consumables tab and the skill rows
never diverge. Locks the shared builder + the tome tooltip content + that the
skills screen attaches a tooltip per skill row. Skips render parts without
pygame/pytmx.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from rpg_game.core.data_loader import load_content
from rpg_game.presentation import item_text
from rpg_game.presentation.talent_text import skill_effect_lines

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp

    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


class SkillEffectLinesTests(unittest.TestCase):
    def setUp(self):
        self.content = load_content()

    def test_dot_skill_lines_show_effect_cost(self):
        lines = skill_effect_lines(self.content.actions["immolate"])
        self.assertTrue(any("fire/round" in line for line in lines), lines)
        self.assertTrue(any("8 mana" in line for line in lines), lines)

    def test_weapon_gated_skill_names_the_gate(self):
        lines = skill_effect_lines(self.content.actions["holy_strike"])
        self.assertIn("Requires a magic weapon", lines)

    def test_tome_tooltip_includes_the_taught_skill_effect(self):
        tome = self.content.items["tome_immolate"]
        tip = item_text.consumable_tooltip(tome, self.content)
        self.assertTrue(any("Teaches: Immolate" in line for line in tip.lines))
        self.assertTrue(any("fire/round" in line for line in tip.lines), tip.lines)
        self.assertTrue(any("mana" in line for line in tip.lines), tip.lines)


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class SkillRowTooltipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_skill_rows_carry_effect_tooltips(self):
        app = OverworldApp()
        app.screen = pygame.Surface((1024, 680))
        app.overlay = "skills_talents"
        app.buttons = []
        app.hover.begin()
        app._draw_overlay_screen()
        skills = app.engine.equippable_skills()
        self.assertTrue(skills)
        tipped = [b for b in app.buttons if getattr(b, "tooltip", None) is not None]
        titles = {b.tooltip.title for b in tipped}
        for skill in skills:
            self.assertIn(skill.name, titles)


if __name__ == "__main__":
    unittest.main()
