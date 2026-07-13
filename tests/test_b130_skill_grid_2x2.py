"""B130: the battle skill menu is a 2x2 square block (4 skills) with the
Esc/Back cell BESIDE the block (its own column to the right), NOT on a third
row. The 4 skill cells occupy exactly two rows and two columns. Skips without
pygame.

The equal-square + wide-item-rows invariants stay locked by test_b128; the 2D
focus nav is locked by test_b126.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame

    from rpg_game.core.game import GameEngine
    from rpg_game.presentation.pygame_battle import BattleApp, ACTIONS

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class SkillGrid2x2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _battle(self, skills):
        engine = GameEngine()
        engine.start_new_game("Hero", "rogue")
        engine.player.learned_skill_ids = ("evasion", "riposte")
        engine.player.equipped_skill_ids = skills
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        return BattleApp(engine=engine, enemy=enemy, standalone=False)

    def test_four_skills_form_two_rows_and_two_columns(self):
        battle = self._battle(("rupture", "deadly_precision", "evasion", "riposte"))
        battle.open_submenu("skill")
        battle.draw()
        # skill cells are the custom squares that are NOT the Esc/Back cell
        skill_cells = [b for b in battle.buttons if b.custom and b.label != "Back"]
        self.assertEqual(len(skill_cells), 4)
        rows = {b.rect.centery for b in skill_cells}
        cols = {b.rect.centerx for b in skill_cells}
        self.assertEqual(len(rows), 2, "skills should span exactly two rows")
        self.assertEqual(len(cols), 2, "skills should span exactly two columns")

    def test_esc_cell_sits_beside_the_block_not_on_a_third_row(self):
        battle = self._battle(("rupture", "deadly_precision", "evasion", "riposte"))
        battle.open_submenu("skill")
        battle.draw()
        skill_cells = [b for b in battle.buttons if b.custom and b.label != "Back"]
        back = next(b for b in battle.buttons if b.custom and b.label == "Back")
        # Esc is to the RIGHT of every skill cell...
        self.assertGreater(back.rect.centerx, max(b.rect.centerx for b in skill_cells))
        # ...and shares vertical space with the block (no extra third row below).
        block_bottom = max(b.rect.bottom for b in skill_cells)
        self.assertLessEqual(back.rect.bottom, block_bottom + 1)

    def test_grid_stays_inside_the_actions_band(self):
        battle = self._battle(("rupture", "deadly_precision", "evasion", "riposte"))
        battle.open_submenu("skill")
        battle.draw()
        for b in (b for b in battle.buttons if b.custom):
            self.assertTrue(ACTIONS.contains(b.rect), f"{b.label} escapes ACTIONS")


if __name__ == "__main__":
    unittest.main()
