"""Playtest log records display-geometry events tagged with the triggering action
(window resize / fullscreen toggle / after battle / anchoring change), so the
recurring fullscreen bug is debuggable from the log. `fills` = surface==window.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from rpg_game.presentation.playtest_logger import PlaytestLogger

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp
    PYGAME_OK = True
except Exception:  # pragma: no cover
    PYGAME_OK = False


class DisplayLogEventTest(unittest.TestCase):
    def _rows(self, logger):
        return [json.loads(line) for line in logger.path.read_text().splitlines()]

    def test_display_event_records_geometry_and_fills(self):
        with tempfile.TemporaryDirectory() as d:
            logger = PlaytestLogger(log_dir=d)
            logger.display("resize", (2560, 1440), (2560, 1440),
                           transform=(0, 0, 1.0), mode="windowed",
                           desktops=[(1512, 982), (2560, 1440)])
            logger.display("after_battle", (960, 640), (2048, 1360),
                           transform=(0, 0, 1.0), mode="windowed")
            rows = [r for r in self._rows(logger) if r["event"] == "display"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["trigger"], "resize")
        self.assertEqual(rows[0]["surface"], [2560, 1440])
        self.assertTrue(rows[0]["fills"])           # surface == window
        self.assertEqual(rows[0]["desktops"], [[1512, 982], [2560, 1440]])
        # the bug signature: logical surface smaller than the window -> not filling
        self.assertEqual(rows[1]["trigger"], "after_battle")
        self.assertFalse(rows[1]["fills"])


@unittest.skipUnless(PYGAME_OK, "pygame/pytmx not installed")
class OverworldDisplayLogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_overworld_logs_init_display_event(self):
        app = OverworldApp()
        rows = [json.loads(line) for line in app.playtest_logger.path.read_text().splitlines()]
        display_rows = [r for r in rows if r["event"] == "display"]
        self.assertTrue(display_rows, "no display event logged on startup")
        self.assertEqual(display_rows[0]["trigger"], "init")
        self.assertIn("surface", display_rows[0])
        self.assertIn("fills", display_rows[0])


if __name__ == "__main__":
    unittest.main()
