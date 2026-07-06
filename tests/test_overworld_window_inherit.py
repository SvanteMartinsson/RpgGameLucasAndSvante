"""Entering the overworld must inherit the previous screen's window size (menu /
character creation / battle) instead of resetting to a tiny default — the
"jumps to a small screen after battle" bug. Skips without pygame/pytmx.
"""

import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp
    from rpg_game.presentation.pygame_canvas import set_display_mode

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class OverworldWindowInheritTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_overworld_inherits_a_larger_prior_window(self):
        # previous screen left a big window (e.g. maximized / external monitor)
        prior = set_display_mode((1391, 903))
        self.assertEqual(prior.get_size(), (1391, 903))
        app = OverworldApp()
        # the overworld matches it, does NOT shrink to the 960x640 default
        self.assertEqual(app.windowed_size, (1391, 903))
        self.assertEqual(app.display.get_size(), (1391, 903))
        self.assertNotEqual(app.display.get_size(), (960, 640))
