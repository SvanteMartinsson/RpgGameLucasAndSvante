"""B113: shared overflow scrolling for settings and mage-tower tomes."""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from rpg_game.presentation import ui
from rpg_game.presentation.pygame_overworld import OverworldApp


class ScrollAreaTest(unittest.TestCase):
    def test_clamps_and_counts_hidden_rows(self):
        scroll = ui.ScrollArea()
        scroll.configure(460, 230)
        self.assertTrue(scroll.scroll(10_000))
        self.assertEqual(scroll.offset, 230)
        self.assertEqual(scroll.hidden_rows(46), (5, 0))
        scroll.scroll(-46)
        self.assertEqual(scroll.hidden_rows(46), (4, 1))


class OverflowMenuTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()
        self.app.display = pygame.Surface((720, 480))
        self.app.screen = pygame.Surface((720, 480))

    def test_settings_wheel_and_arrow_scroll_overflow(self):
        self.app.overlay = "settings"
        self.app.draw()
        scroll = self.app._menu_scrolls["settings"]
        self.assertGreater(scroll.maximum, 0)
        self.app.handle_events()  # drain startup events
        pygame.event.post(pygame.event.Event(pygame.MOUSEWHEEL, y=-1))
        self.app.handle_events()
        self.assertGreater(scroll.offset, 0)
        scroll.offset = 0
        self.app.draw()
        self.app.focus.index = len(self.app.focus._sections[0][1]) - 1
        self.app._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN, mod=0))
        self.assertGreater(scroll.offset, 0)

    def test_tome_shop_scrolls_and_only_registers_visible_rows(self):
        self.app._open_tome_shop("tower")
        self.app.draw()
        scroll = self.app._menu_scrolls["tomes"]
        self.assertGreater(scroll.maximum, 0)
        first_labels = {button.label for button in self.app.buttons}
        scroll.scroll(10_000)
        self.app.draw()
        last_labels = {button.label for button in self.app.buttons}
        self.assertNotEqual(first_labels, last_labels)
        self.assertTrue(all(0 <= button.rect.centery <= self.app.screen.get_height()
                            for button in self.app.buttons))


if __name__ == "__main__":
    unittest.main()
