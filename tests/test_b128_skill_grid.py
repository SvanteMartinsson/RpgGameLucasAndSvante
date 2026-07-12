"""B128: the battle skill menu is a grid of equal SQUARE cells, with the
Esc/Back button as its own cell. Item/swap submenus keep their wide rows.
Skips without pygame.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame

    from rpg_game.core.game import GameEngine
    from rpg_game.presentation.pygame_battle import BattleApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class SkillGridTest(unittest.TestCase):
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

    def test_skill_cells_are_equal_squares_plus_an_esc_cell(self):
        battle = self._battle(("rupture", "deadly_precision", "evasion", "riposte"))
        battle.open_submenu("skill")
        battle.draw()
        cells = [b for b in battle.buttons if b.custom]
        self.assertEqual(len(cells), 5)                 # 4 skills + Esc/Back
        for b in cells:
            self.assertEqual(b.rect.width, b.rect.height, f"{b.label} not square")
        sides = {b.rect.width for b in cells}
        self.assertEqual(len(sides), 1, f"cells differ in size: {sides}")
        # the last cell is the Esc/Back one
        back = next(b for b in cells if b.label == "Back")
        self.assertEqual(back.hotkey, "\x1b")

    def test_skill_cells_are_keyboard_focusable(self):
        battle = self._battle(("rupture", "evasion"))
        battle.open_submenu("skill")
        battle.draw()
        sections = {name for name, _items in battle.focus._sections}
        self.assertIn("skill", sections)
        self.assertIsNotNone(battle.focus.focused())

    def test_item_submenu_keeps_wide_rows_not_squares(self):
        battle = self._battle(("rupture",))
        battle.engine.player.inventory.add_consumable("hp_potion")
        battle.open_submenu("item")
        battle.draw()
        # item rows are the regular wide buttons, not square grid cells
        self.assertFalse(any(b.custom for b in battle.buttons))
        row = next(b for b in battle.buttons if "Potion" in b.label)
        self.assertGreater(row.rect.width, row.rect.height)


if __name__ == "__main__":
    unittest.main()
