"""B92: the start-menu Settings and the in-game overlay render THE same options.

Both surfaces iterate user_settings.OPTIONS, so adding a setting in one place
shows it in both. Locks the shared definition's coverage, the cycle semantics,
and that the in-game overlay renders one row per option. Skips render parts
without pygame/pytmx.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from rpg_game.presentation import settings as user_settings

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp

    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


class SharedOptionsTests(unittest.TestCase):
    def test_options_cover_all_user_facing_settings(self):
        keys = [option["key"] for option in user_settings.OPTIONS]
        self.assertEqual(keys, ["fullscreen", "log_visible", "minimap",
                                "combat_fx", "combat_skip", "sound_music"])
        for option in user_settings.OPTIONS:
            self.assertIn(option["key"], user_settings.DEFAULTS)

    def test_cycle_semantics(self):
        toggle = {"key": "combat_fx", "label": "Combat FX", "kind": "toggle"}
        self.assertIs(user_settings.cycle_value(toggle, True), False)
        steps = {"key": "log_visible", "label": "Log rows", "kind": "steps",
                 "steps": (5, 8, 10)}
        self.assertEqual(user_settings.cycle_value(steps, 8), 10)
        self.assertEqual(user_settings.cycle_value(steps, 10), 5)   # wraps
        slider = {"key": "sound_music", "label": "Music volume", "kind": "slider"}
        self.assertAlmostEqual(user_settings.cycle_value(slider, 0.5), 0.6)
        self.assertEqual(user_settings.cycle_value(slider, 1.0), 0.0)  # wraps

    def test_option_labels_show_values(self):
        option = user_settings.OPTIONS[0]
        self.assertEqual(user_settings.option_label(option, True), "Fullscreen: On")
        slider = user_settings.OPTIONS[-1]
        self.assertEqual(user_settings.option_label(slider, 0.48), "Music volume: 48")


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class OverlayParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_overlay_renders_every_shared_option(self):
        app = OverworldApp()
        app.screen = pygame.Surface((1024, 680))
        app.overlay = "settings"
        app.buttons = []
        app.hover.begin()
        app._draw_overlay_screen()
        labels = " | ".join(b.label for b in app.buttons)
        for option in user_settings.OPTIONS:
            if option["kind"] == "slider":
                self.assertIsNotNone(app._music_slider_rect)   # slider row drawn
            else:
                self.assertIn(option["label"], labels)


if __name__ == "__main__":
    unittest.main()
