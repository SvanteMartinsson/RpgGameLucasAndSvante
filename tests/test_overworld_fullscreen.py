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

    def test_present_centers_at_native_size_when_display_is_larger(self):
        canvas = pygame.Surface((1024, 680))
        big = pygame.Surface((1280, 800))
        self.assertEqual(pygame_canvas.present(big, canvas, (0, 0, 0)), (128, 60, 1.0))
        same = pygame.Surface((1024, 680))
        self.assertEqual(pygame_canvas.present(same, canvas, (0, 0, 0)), (0, 0, 1.0))

    def test_present_scales_down_to_fit_a_smaller_display(self):
        canvas = pygame.Surface((1024, 680))
        small = pygame.Surface((800, 600))
        ox, oy, scale = pygame_canvas.present(small, canvas, (0, 0, 0))
        self.assertLess(scale, 1.0)
        # Scaled frame fits entirely on screen (nothing clipped).
        self.assertLessEqual(ox * 2 + int(1024 * scale), 800)
        self.assertLessEqual(oy * 2 + int(680 * scale), 600)

    def test_to_canvas_inverts_offset_and_scale(self):
        self.assertEqual(pygame_canvas.to_canvas((200, 150), (128, 60, 1.0)), (72, 90))
        self.assertEqual(pygame_canvas.to_canvas((200, 150), (0, 0, 0.5)), (400, 300))

    def test_fit_size_never_exceeds_desktop(self):
        dw, dh = pygame_canvas.desktop_size()
        fw, fh = pygame_canvas.fit_size((100000, 100000))
        self.assertLessEqual(fw, dw)
        self.assertLessEqual(fh, dh)


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

    def test_videoresize_updates_windowed_size_and_renders(self):
        self.assertFalse(self.app.fullscreen)
        pygame.event.post(pygame.event.Event(pygame.VIDEORESIZE, w=1100, h=720))
        self.app.handle_events()
        self.assertEqual(self.app.windowed_size, (1100, 720))
        self.app.draw()  # layout follows the new size without crashing

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
