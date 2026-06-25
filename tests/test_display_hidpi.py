"""macOS-HiDPI anchoring fix for the recurring fullscreen bug: when SCALED yields
a logical display surface smaller than the physical window (e.g. 1024 surface in a
2048 Retina window), the content sits 1:1 in the top-left. set_display_mode must
detect surface != window and recreate at the real window size (no SCALED) so they
match — which is the invariant of every correctly-filled frame. Skips without pygame.
"""

import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation import pygame_canvas as pc

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame not installed")
class DisplayHiDpiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_recreates_at_window_size_when_scaled_surface_is_smaller(self):
        # Simulate the measured Retina bug: SCALED returns a 1024x680 logical
        # surface while the physical window is 2048x1360.
        calls = []

        def fake_set_mode(size, flags=0):
            calls.append((tuple(size), flags))
            return pygame.Surface(size)  # surface == requested logical size

        windows = iter([(2048, 1360), (2048, 1360)])  # window stays physical
        with mock.patch.object(pygame.display, "set_mode", side_effect=fake_set_mode), \
             mock.patch.object(pygame.display, "get_window_size", side_effect=lambda: next(windows)):
            surface = pc.set_display_mode((1024, 680))

        # recreated once at the real window size, the second time without SCALED
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0], (1024, 680))
        self.assertEqual(calls[1][0], (2048, 1360))
        self.assertFalse(calls[1][1] & pygame.SCALED, "recreate must drop SCALED")
        self.assertEqual(surface.get_size(), (2048, 1360))  # surface now == window

    def test_no_recreate_when_surface_matches_window(self):
        # The working case (surface == window): set_mode is called exactly once.
        calls = []

        def fake_set_mode(size, flags=0):
            calls.append((tuple(size), flags))
            return pygame.Surface(size)

        with mock.patch.object(pygame.display, "set_mode", side_effect=fake_set_mode), \
             mock.patch.object(pygame.display, "get_window_size", side_effect=lambda: (960, 640)):
            surface = pc.set_display_mode((960, 640))

        self.assertEqual(len(calls), 1, "no needless recreate when surface fills window")
        self.assertEqual(surface.get_size(), (960, 640))


if __name__ == "__main__":
    unittest.main()
