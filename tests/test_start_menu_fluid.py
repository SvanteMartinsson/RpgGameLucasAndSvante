"""Fluid-layout pilot: the start menu draws at the live display resolution.

Instead of authoring onto a fixed 1024x680 canvas that present() centers as a
small island, the start menu sizes its canvas to the real display, lays the
title + buttons out from that live size, and lets present() be the identity
transform. Pure presentation — no game logic. Skips without pygame/pytmx.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation import pygame_overworld as ow
    from rpg_game.presentation.pygame_canvas import present, to_canvas

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False

BG = (18, 20, 28)
OPTIONS = [("new", "New game"), ("load", "Load game"), ("quit", "Quit")]


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class StartMenuFluidLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_layout_centers_on_the_live_surface_size(self):
        for size in [(1024, 680), (2560, 1440), (1366, 768)]:
            buttons, title_pos, _msg = ow.start_menu_layout(size, OPTIONS)
            w, h = size
            self.assertEqual(title_pos[0], w // 2)            # title horizontally centered
            for b in buttons:
                self.assertEqual(b.rect.centerx, w // 2)      # each button centered to live width
                self.assertTrue(0 <= b.rect.top and b.rect.bottom <= h)
            # The button stack is vertically centered on the live height.
            stack_mid = (buttons[0].rect.top + buttons[-1].rect.bottom) // 2
            self.assertAlmostEqual(stack_mid, h // 2, delta=b.rect.height)

    def test_layout_fills_a_large_screen_not_a_fixed_island(self):
        # On a 2560-wide display the content spreads across it: a fixed 1024
        # canvas would have clustered everything left of x=1024.
        buttons, title_pos, _msg = ow.start_menu_layout((2560, 1440), OPTIONS)
        self.assertEqual(title_pos[0], 1280)
        self.assertEqual(buttons[0].rect.centerx, 1280)
        self.assertGreater(buttons[0].rect.centerx, 1024)     # not stuck in the old canvas

    def test_present_is_identity_when_canvas_matches_display(self):
        # The converted screen makes canvas == display, so present() centers
        # nothing: transform is (0, 0, 1.0).
        display = pygame.Surface((2560, 1440))
        canvas = pygame.Surface(display.get_size())
        transform = present(display, canvas, BG)
        self.assertEqual(transform, (0, 0, 1.0))

    def test_click_hits_the_right_button_at_fluid_size(self):
        size = (1920, 1080)
        buttons, _title, _msg = ow.start_menu_layout(size, OPTIONS)
        # With identity transform, a display click maps straight to canvas space.
        transform = (0, 0, 1.0)
        for expected in buttons:
            display_point = expected.rect.center
            canvas_point = to_canvas(display_point, transform)
            hit = [b for b in buttons if b.rect.collidepoint(canvas_point)]
            self.assertEqual([b.on_click for b in hit], [expected.on_click])

    def test_two_or_three_options_both_stay_centered(self):
        for options in (OPTIONS, OPTIONS[:2]):
            buttons, _t, _m = ow.start_menu_layout((1280, 720), options)
            self.assertEqual(len(buttons), len(options))
            for b in buttons:
                self.assertEqual(b.rect.centerx, 640)


if __name__ == "__main__":
    unittest.main()
