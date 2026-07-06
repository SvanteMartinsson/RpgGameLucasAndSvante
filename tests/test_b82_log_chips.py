"""B82: the log tab chips must never sit above the panel (they occluded the
XP bar). Locks: every chip rect starts at/below the panel's top edge and stays
inside it. Skips without pygame."""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class LogChipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.app = OverworldApp()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_chips_stay_inside_the_log_panel(self):
        self.app.screen = pygame.Surface((1024, 680))
        self.app.buttons = []
        self.app.hover.begin()
        self.app._draw_log()
        panel = self.app._log_rect()
        chips = self.app.buttons[-2:]
        self.assertEqual(len(chips), 2)
        for chip in chips:
            self.assertGreaterEqual(chip.rect.top, panel.top)   # never above the panel
            self.assertLessEqual(chip.rect.bottom, panel.bottom)


if __name__ == "__main__":
    unittest.main()
