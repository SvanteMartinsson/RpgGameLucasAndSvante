"""B99 S2: keyboard focus navigation across ALL menu surfaces.

Every _add_button registers into the FocusList (section "main" unless the
surface names its own sections), the focus keys dispatch on every menu
overlay/mode (bestiary keeps its B66 arrow model), focus resets when the
surface changes, and the settings music slider adjusts with left/right when
focused. Skips without pygame/pytmx.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import ui
    from rpg_game.presentation.pygame_overworld import FOCUS_MODES, OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


def _key(key, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod, unicode="")


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class FocusAllMenusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1280, 800))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        self.app = OverworldApp(engine=engine)

    def _focused_after_draw(self):
        self.app.draw()
        return self.app.focus.focused()

    def _assert_focus_moves_and_activates(self, surface_name):
        """The shared per-surface assertion: something is focused, DOWN moves
        the focus, and Enter fires the focused button's callback."""
        first = self._focused_after_draw()
        self.assertIsNotNone(first, f"{surface_name}: nothing focusable")
        self.app._handle_key(_key(pygame.K_DOWN))
        second = self._focused_after_draw()
        self.assertIsNot(second, first, f"{surface_name}: DOWN did not move focus")
        fired = []
        second.on_click = lambda: fired.append(True)
        self.app._handle_key(_key(pygame.K_RETURN))
        self.assertTrue(fired, f"{surface_name}: Enter did not activate")

    # -- overlays -----------------------------------------------------------

    def test_system_overlay(self):
        self.app.open_overlay("system")
        self._assert_focus_moves_and_activates("system")

    def test_settings_overlay(self):
        self.app.open_overlay("settings")
        self._assert_focus_moves_and_activates("settings")

    def test_character_overlay(self):
        self.app.open_overlay("character")
        self._assert_focus_moves_and_activates("character")

    def test_settings_slider_adjusts_with_left_right(self):
        import tempfile
        from unittest import mock
        from rpg_game.presentation import settings as user_settings
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self.addCleanup(os.unlink, tmp.name)
        patcher = mock.patch.object(user_settings, "SETTINGS_PATH", tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app.open_overlay("settings")
        self.app._settings["sound_music"] = 0.50
        self.app.draw()
        # Walk the focus down until the slider row is focused.
        for _ in range(40):
            if isinstance(self.app.focus.focused(), ui.FocusSlider):
                break
            self.app._handle_key(_key(pygame.K_DOWN))
            self.app.draw()
        self.assertIsInstance(self.app.focus.focused(), ui.FocusSlider,
                              "slider row never received focus")
        self.app._handle_key(_key(pygame.K_RIGHT))
        self.assertAlmostEqual(self.app._settings["sound_music"], 0.55)
        self.app._handle_key(_key(pygame.K_LEFT))
        self.app._handle_key(_key(pygame.K_LEFT))
        self.assertAlmostEqual(self.app._settings["sound_music"], 0.45)

    # -- mode-based screens --------------------------------------------------

    def test_death_screen(self):
        self.app.mode = "death"
        self._assert_focus_moves_and_activates("death")

    def test_victory_screen(self):
        enemy = self.app.engine.create_encounter()
        self.app.victory_enemy_name = getattr(enemy, "name", "Enemy")
        self.app.mode = "victory"
        self.app.draw()
        focused = self.app.focus.focused()
        self.assertIsNotNone(focused, "victory: nothing focusable")
        fired = []
        focused.on_click = lambda: fired.append(True)
        self.app._handle_key(_key(pygame.K_RETURN))
        self.assertTrue(fired, "victory: Enter did not activate")

    def test_travel_event_screen(self):
        events = list(self.app.engine.content.travel_events)
        if not events:
            self.skipTest("no travel events in content")
        self.app.active_event = events[0]
        self.app.mode = "travel_event"
        self.app.draw()
        self.assertIsNotNone(self.app.focus.focused(), "event: nothing focusable")

    def test_all_menu_modes_are_focus_dispatched(self):
        for mode in ("building", "store", "tome_shop", "apothecary", "fast_travel",
                     "upgrade_station", "tournaments", "tournament_confirm",
                     "tournament_intermission", "death", "victory", "travel_event"):
            self.assertIn(mode, FOCUS_MODES)

    # -- surface change resets ------------------------------------------------

    def test_focus_resets_when_surface_changes(self):
        self.app.open_overlay("system")
        self.app.draw()
        self.app._handle_key(_key(pygame.K_DOWN))
        self.app._handle_key(_key(pygame.K_DOWN))
        self.app.draw()
        moved = (self.app.focus.section, self.app.focus.index)
        self.assertNotEqual(moved, (0, 0))
        self.app.overlay = ""          # a mode-based screen opens without
        self.app.mode = "death"        # open_overlay -> draw() detects it
        self.app.draw()
        self.assertEqual((self.app.focus.section, self.app.focus.index), (0, 0))

    def test_bestiary_keeps_its_own_arrow_model(self):
        self.app.open_overlay("bestiary")
        self.app.draw()
        before = self.app.bestiary_index
        self.app._handle_key(_key(pygame.K_DOWN))
        self.assertEqual(self.app.bestiary_index, (before + 1) % max(
            1, len(__import__("rpg_game.core.bestiary", fromlist=["x"]).codex_enemy_ids(
                self.app.engine.content))))


if __name__ == "__main__":
    unittest.main()
