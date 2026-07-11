"""B99 S1: keyboard focus navigation in the inventory + skills screens.

The shared ui.FocusList: up/down move within a section, left/right (or Tab)
jump between sections, Enter activates the focused button through the same
callback a click uses. Focus position persists across frames, clamps when a
list shrinks, and resets when a menu opens. Skips without pygame/pytmx.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame

    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import ui
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


class FocusListTest(unittest.TestCase):
    """Pure widget logic — no display needed."""

    def _focus(self):
        focus = ui.FocusList()
        focus.begin()
        focus.add("a", "a0")
        focus.add("a", "a1")
        focus.add("b", "b0")
        return focus

    def test_starts_on_first_item(self):
        self.assertEqual(self._focus().focused(), "a0")

    def test_move_within_section_clamps(self):
        focus = self._focus()
        focus.move(1)
        self.assertEqual(focus.focused(), "a1")
        focus.move(1)   # clamped at the section's last row
        self.assertEqual(focus.focused(), "a1")
        focus.move(-5)  # clamped at the first row
        self.assertEqual(focus.focused(), "a0")

    def test_move_section_jumps_and_clamps(self):
        focus = self._focus()
        focus.move_section(1)
        self.assertEqual(focus.focused(), "b0")
        focus.move_section(1)   # only two sections
        self.assertEqual(focus.focused(), "b0")
        focus.move_section(-1)
        self.assertEqual(focus.focused(), "a0")

    def test_index_clamps_when_list_shrinks(self):
        focus = self._focus()
        focus.move(1)   # a1
        focus.begin()
        focus.add("a", "only")
        self.assertEqual(focus.focused(), "only")

    def test_empty_focus_is_none(self):
        focus = ui.FocusList()
        focus.begin()
        self.assertIsNone(focus.focused())
        focus.move(1)           # no-ops, no crash
        focus.move_section(1)
        self.assertIsNone(focus.focused())

    def test_reset_returns_to_first_section(self):
        focus = self._focus()
        focus.move_section(1)
        focus.reset()
        self.assertEqual(focus.focused(), "a0")


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class FocusNavIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _key(self, app, key, mod=0):
        app._handle_key(pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod))

    def _app(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        return OverworldApp(engine=engine)

    def test_inventory_arrow_down_moves_focus(self):
        app = self._app()
        app.open_overlay("inventory")
        app.draw()
        first = app.focus.focused()
        self._key(app, pygame.K_DOWN)
        self.assertIsNot(app.focus.focused(), first)

    def test_inventory_enter_activates_category(self):
        app = self._app()
        app.open_overlay("inventory")
        app.draw()
        # Focus starts on the first category row; step to another category and
        # Enter must switch the open category exactly like a click would.
        start = app.inventory_category
        self._key(app, pygame.K_DOWN)
        self._key(app, pygame.K_RETURN)
        self.assertNotEqual(app.inventory_category, start)

    def test_tab_jumps_between_sections(self):
        app = self._app()
        app.open_overlay("skills_talents")
        app.draw()
        app.focus.move_section(0)   # normalise clamped read
        section_before = app.focus._position()[0]
        self._key(app, pygame.K_TAB)
        self.assertEqual(app.focus._position()[0], section_before + 1)
        self._key(app, pygame.K_TAB, mod=pygame.KMOD_SHIFT)
        self.assertEqual(app.focus._position()[0], section_before)

    def test_skills_enter_activates_talent_row(self):
        app = self._app()
        app.open_overlay("skills_talents")
        app.draw()
        first = app.selected_talent_node()
        self._key(app, pygame.K_RIGHT)   # skills -> talents section
        self._key(app, pygame.K_DOWN)
        self._key(app, pygame.K_RETURN)
        self.assertNotEqual(app.selected_talent_node().id, first.id)

    def test_focus_resets_on_menu_open(self):
        app = self._app()
        app.open_overlay("inventory")
        app.draw()
        self._key(app, pygame.K_DOWN)
        app.close_overlay()
        app.open_overlay("inventory")
        self.assertEqual((app.focus.section, app.focus.index), (0, 0))

    def test_mouse_clicks_still_work_alongside_focus(self):
        app = self._app()
        app.open_overlay("inventory")
        app.draw()
        # Every focusable button is still a normal button in app.buttons.
        self.assertTrue(any(b.enabled for b in app.buttons))


if __name__ == "__main__":
    unittest.main()
