"""First frame anchors correctly without waiting for a VIDEORESIZE.

Fixed-canvas screens (overworld, battle) used to read a stale window size at
construction and only "heal" their centering after the first alt-tab/resize.
_apply_display_mode / BattleApp.__post_init__ now pump one event cycle and
re-read the OS-confirmed surface, so the very first draw() produces a transform
computed against the real drawable. Pure presentation — no game logic, no layout
change, present()/to_canvas untouched. Skips without pygame/pytmx.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation.pygame_overworld import OverworldApp
    from rpg_game.presentation.pygame_battle import BattleApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


def _expected_transform(display_size, canvas_size):
    """Mirror present()'s math so the test pins behaviour, not a magic tuple."""
    dw, dh = display_size
    cw, ch = canvas_size
    scale = min(1.0, dw / cw, dh / ch) if cw and ch else 1.0
    fw = cw if scale >= 1.0 else max(1, int(cw * scale))
    fh = ch if scale >= 1.0 else max(1, int(ch * scale))
    return (max(0, (dw - fw) // 2), max(0, (dh - fh) // 2), scale)


def _isolate_settings(testcase):
    """B122c: keep prefs writes (toggle_fullscreen persists) off the real
    settings.json by pointing SETTINGS_PATH at a throwaway temp file."""
    import tempfile
    from unittest import mock

    from rpg_game.presentation import settings as user_settings
    handle = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    handle.close()
    testcase.addCleanup(lambda: os.path.exists(handle.name) and os.unlink(handle.name))
    patcher = mock.patch.object(user_settings, "SETTINGS_PATH", handle.name)
    patcher.start()
    testcase.addCleanup(patcher.stop)


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class FirstFrameResyncTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        _isolate_settings(self)

    def test_overworld_first_frame_matches_the_real_surface(self):
        app = OverworldApp()
        # The construction re-sync made self.display the live surface.
        self.assertIs(app.display, pygame.display.get_surface())
        app.draw()  # FIRST frame, no VIDEORESIZE pumped beforehand
        self.assertEqual(app._transform,
                         _expected_transform(app.display.get_size(), app.screen.get_size()))

    def test_battle_first_frame_matches_the_real_surface(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        for pid, place in engine.content.places.items():
            if place.encounters:
                engine.player.current_place_id = pid
                break
        battle = BattleApp(engine=engine, enemy=engine.create_encounter(), standalone=False)
        self.assertIs(battle.display, pygame.display.get_surface())
        battle.draw()
        self.assertEqual(battle._transform,
                         _expected_transform(battle.display.get_size(), battle.screen.get_size()))

    def test_first_frame_is_not_a_naive_origin_anchor_when_sizes_differ(self):
        # If the live surface differs from the canvas, the transform must reflect
        # present()'s centering/letterbox math (not a stale (0,0,1.0) top-left).
        app = OverworldApp()
        app.draw()
        if app.display.get_size() != app.screen.get_size():
            self.assertNotEqual(app._transform, (0, 0, 1.0))

    def test_fullscreen_path_still_yields_a_valid_surface(self):
        # F11 toggles fullscreen; the re-sync must keep self.display a real surface.
        app = OverworldApp()
        app.toggle_fullscreen()
        self.assertTrue(app.fullscreen)
        self.assertIsNotNone(app.display)
        self.assertIs(app.display, pygame.display.get_surface())
        app.draw()  # must not raise
        app.toggle_fullscreen()
        self.assertFalse(app.fullscreen)
        self.assertIsNotNone(app.display)


if __name__ == "__main__":
    unittest.main()
