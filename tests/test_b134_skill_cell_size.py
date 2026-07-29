"""B134: the battle skill cells are WIDE RECTANGLES that fill the ACTIONS band.

B130's squares were bounded by the band's SHORT axis (138px / 2 rows = 57px) and
left ~330px of the 516px width unused, so the cells looked shrunken. The 2x2
shape and the Esc-beside-the-block placement are kept; only the cell geometry
changed: ~192x65 per cell, the Esc column narrowed to just what it needs, and
every skill name now reads on ONE line.

Skips without pygame.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame

    from rpg_game.core.data_loader import load_content
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import ui
    from rpg_game.presentation import pygame_battle as pb

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False

FULL_LOADOUT = ("rupture", "deadly_precision", "evasion", "riposte")


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class SkillCellSizeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _battle(self, skills=FULL_LOADOUT):
        engine = GameEngine()
        engine.start_new_game("Hero", "rogue")
        engine.player.learned_skill_ids = ("evasion", "riposte")
        engine.player.equipped_skill_ids = skills
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        battle = pb.BattleApp(engine=engine, enemy=enemy, standalone=False)
        battle.open_submenu("skill")
        battle.draw()
        return battle

    def _cells(self, battle):
        skills = [b for b in battle.buttons if b.custom and b.label != "Back"]
        back = next(b for b in battle.buttons if b.custom and b.label == "Back")
        return skills, back

    def test_cells_are_wider_than_tall(self):
        skills, _back = self._cells(self._battle())
        for b in skills:
            self.assertGreater(b.rect.width, b.rect.height,
                               f"{b.label} is not a wide rectangle")
            # decisively wide, not a near-square: at least 2x
            self.assertGreaterEqual(b.rect.width, 2 * b.rect.height)

    def test_grid_fills_the_band_width_and_height(self):
        skills, back = self._cells(self._battle())
        cells = skills + [back]
        # nothing escapes the band ...
        for b in cells:
            self.assertTrue(pb.ACTIONS.contains(b.rect), f"{b.label} escapes ACTIONS")
        # ... and almost none of the width is wasted (only the outer margins).
        used_left = min(b.rect.left for b in cells)
        used_right = max(b.rect.right for b in cells)
        self.assertLessEqual(used_left - pb.ACTIONS.left, pb.SKILL_CELL_GAP)
        self.assertLessEqual(pb.ACTIONS.right - used_right, pb.SKILL_CELL_GAP)
        # the two rows fill the band's height edge to edge
        self.assertEqual(min(b.rect.top for b in skills), pb.ACTIONS.top)
        self.assertEqual(max(b.rect.bottom for b in skills), pb.ACTIONS.bottom)

    def test_esc_column_is_narrow_not_a_third_of_the_band(self):
        skills, back = self._cells(self._battle())
        self.assertLessEqual(back.rect.width, 110)
        self.assertGreaterEqual(back.rect.width, 90)
        # and it is narrower than a skill cell, i.e. it stopped eating the width
        self.assertLess(back.rect.width, min(b.rect.width for b in skills))

    def test_two_by_two_shape_and_esc_placement_are_unchanged(self):
        # B130's layout decisions survive B134: 2 rows x 2 columns, Esc beside.
        skills, back = self._cells(self._battle())
        self.assertEqual(len({b.rect.centery for b in skills}), 2)
        self.assertEqual(len({b.rect.centerx for b in skills}), 2)
        self.assertGreater(back.rect.centerx, max(b.rect.centerx for b in skills))
        self.assertLessEqual(back.rect.bottom, max(b.rect.bottom for b in skills) + 1)

    def test_cell_size_is_stable_across_loadout_sizes(self):
        # The canonical 2-row height means equipping fewer skills does NOT
        # balloon the cells (a 1-skill loadout kept the same 65px height).
        heights = set()
        for skills in (FULL_LOADOUT, FULL_LOADOUT[:3], FULL_LOADOUT[:2], FULL_LOADOUT[:1]):
            cells, _back = self._cells(self._battle(skills))
            heights.update(b.rect.height for b in cells)
        self.assertEqual(len(heights), 1, f"cell height varies by loadout: {heights}")

    def test_every_skill_name_in_the_game_fits_one_line(self):
        # The point of the extra width: no more "Ruptur/e" or "Deadly/Precis".
        battle = self._battle()
        skills, _back = self._cells(battle)
        inner = battle._skill_cell_inner(skills[0])
        content = load_content()
        for action in content.actions.values():
            self.assertEqual(len(ui.wrap(action.name, battle.font_sm, inner)), 1,
                             f"{action.name!r} would wrap at {inner}px")

    def test_names_render_unwrapped_in_the_real_cells(self):
        battle = self._battle()
        skills, _back = self._cells(battle)
        for b in skills:
            inner = battle._skill_cell_inner(b)
            self.assertEqual(ui.wrap(b.label, battle.font_sm, inner), [b.label])
            self.assertEqual(ui.fit(b.label, battle.font_sm, inner), b.label)


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class SkillGridNavStillWorksTest(unittest.TestCase):
    """B130's geometric 2D nav must keep working on the new rectangles."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _key(self, battle, key):
        battle._handle_key(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=""))

    def test_arrows_step_the_grid_and_reach_the_esc_cell(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "rogue")
        engine.player.learned_skill_ids = ("evasion", "riposte")
        engine.player.equipped_skill_ids = FULL_LOADOUT
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        battle = pb.BattleApp(engine=engine, enemy=enemy, standalone=False)
        battle.open_submenu("skill")
        battle.draw()

        top_left = battle.focus.focused()
        self._key(battle, pygame.K_DOWN)
        self.assertEqual(battle.focus.focused().rect.centerx, top_left.rect.centerx)
        self._key(battle, pygame.K_UP)
        self.assertIs(battle.focus.focused(), top_left)
        self._key(battle, pygame.K_RIGHT)
        second = battle.focus.focused()
        self.assertEqual(second.rect.centery, top_left.rect.centery)
        # one more RIGHT reaches the Esc/Back column
        self._key(battle, pygame.K_RIGHT)
        self.assertEqual(battle.focus.focused().label, "Back")


if __name__ == "__main__":
    unittest.main()
