"""Borderless fullscreen toggle + size-aware layout.

Skips when pygame/pytmx are not installed. The dummy SDL driver mangles
get_size() across fullscreen toggles, so these assert on the toggle state, the
canvas-centering math, and that layout helpers compute against the *current*
surface size — not on exact pixel dimensions.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp
    from rpg_game.presentation import pygame_canvas

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class CanvasMathTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))  # present() flips the display

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_present_centers_and_clamps(self):
        canvas = pygame.Surface((1024, 680))
        # Larger display -> centered, positive offset.
        big = pygame.Surface((1280, 800))
        self.assertEqual(pygame_canvas.present(big, canvas, (0, 0, 0)), (128, 60))
        # Equal display -> zero offset.
        same = pygame.Surface((1024, 680))
        self.assertEqual(pygame_canvas.present(same, canvas, (0, 0, 0)), (0, 0))
        # Smaller display -> clamped to non-negative (top-left stays visible).
        small = pygame.Surface((800, 600))
        self.assertEqual(pygame_canvas.present(small, canvas, (0, 0, 0)), (0, 0))

    def test_to_canvas_inverts_offset(self):
        self.assertEqual(pygame_canvas.to_canvas((200, 150), (128, 60)), (72, 90))


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class FullscreenToggleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()

    def test_toggle_flips_state_and_rebuilds_surface_without_crashing(self):
        self.assertFalse(self.app.fullscreen)
        self.app.toggle_fullscreen()
        self.assertTrue(self.app.fullscreen)
        self.app.draw()  # render once in fullscreen
        self.app.toggle_fullscreen()
        self.assertFalse(self.app.fullscreen)
        self.app.draw()  # render once back in windowed

    def test_f11_key_toggles(self):
        before = self.app.fullscreen
        self.app._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11, unicode=""))
        self.assertNotEqual(self.app.fullscreen, before)

    def test_overlays_render_within_bounds_at_several_sizes(self):
        for size in [(896, 640), (1280, 800), (1920, 1080)]:
            self.app.screen = pygame.display.set_mode(size)
            actual = self.app.screen.get_size()
            for overlay in ("character", "inventory", "skills_talents", "system"):
                self.app.overlay = overlay
                self.app.draw()
                panel = self.app._overlay_panel("x")  # size-aware panel rect
                self.assertGreaterEqual(panel.left, 0)
                self.assertGreaterEqual(panel.top, 0)
                self.assertLessEqual(panel.right, actual[0])
                self.assertLessEqual(panel.bottom, actual[1])
            self.app.overlay = ""


if __name__ == "__main__":
    unittest.main()
