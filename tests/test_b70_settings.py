"""B70: the settings screen + settings.json persistence.

Locks: defaults on a missing/corrupt file, load-merge over defaults, the app
applying settings at startup, mutators persisting immediately, and the overlay
rendering its rows. File IO runs against temp paths.
"""

import json
import os
import tempfile
import unittest
from unittest import mock

from rpg_game.presentation import settings as user_settings

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


class SettingsFileTests(unittest.TestCase):
    def test_missing_file_yields_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            values = user_settings.load(os.path.join(folder, "nope.json"))
            self.assertEqual(values, user_settings.DEFAULTS)

    def test_corrupt_file_yields_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "settings.json")
            open(path, "w").write("{broken")
            self.assertEqual(user_settings.load(path), user_settings.DEFAULTS)

    def test_saved_values_merge_over_defaults_and_keep_unknown_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "settings.json")
            user_settings.save({"minimap": False, "future_key": 7}, path)
            values = user_settings.load(path)
            self.assertFalse(values["minimap"])
            self.assertEqual(values["future_key"], 7)
            self.assertIn("fullscreen", values)            # defaults still present


try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class SettingsAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        path = os.path.join(self._tmp.name, "settings.json")
        patcher = mock.patch.object(user_settings, "SETTINGS_PATH", path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def test_app_applies_saved_settings_at_startup(self):
        user_settings.save({"minimap": False, "log_visible": 14},
                           user_settings.SETTINGS_PATH)
        app = OverworldApp()
        self.assertFalse(app.show_minimap)
        self.assertEqual(app.log_visible, 14)

    def test_mutators_persist_immediately(self):
        app = OverworldApp()
        app.resize_log(1)
        on_disk = json.load(open(user_settings.SETTINGS_PATH))
        self.assertEqual(on_disk["log_visible"], app.log_visible)

    def test_settings_overlay_renders_its_rows(self):
        app = OverworldApp()
        app.screen = pygame.Surface((1024, 680))
        app.overlay = "settings"
        app.buttons = []
        app.hover.begin()
        app._draw_overlay_screen()
        labels = " | ".join(b.label for b in app.buttons)
        self.assertIn("Fullscreen", labels)
        self.assertIn("Log rows", labels)
        self.assertIn("Minimap", labels)

    def test_system_overlay_offers_settings(self):
        app = OverworldApp()
        app.screen = pygame.Surface((1024, 680))
        app.overlay = "system"
        app.buttons = []
        app.hover.begin()
        app._draw_overlay_screen()
        self.assertTrue(any(b.label == "Settings" for b in app.buttons))


if __name__ == "__main__":
    unittest.main()
