"""Display mode: SCALED for crisp HiDPI scaling, and NEVER exclusive fullscreen
(which on macOS hid the window controls and blocked app-switching).

ROOT (measured, 3024x1964 Retina Mac): fullscreen gave a LOGICAL 1512x982 surface;
present() centered fine, but without SCALED macOS copied it 1:1 into the top-left
of the 2x physical framebuffer -> top-left + half-size. SCALED makes SDL upscale
(integer 2x) to fill the screen. Exclusive FULLSCREEN also trapped the user, so
"fullscreen" is now a large bordered RESIZABLE+SCALED window; the OS green button
gives true native fullscreen with Cmd+Tab and a way out.

NON-CIRCULAR: this asserts the actual display MODE REQUEST (flags + size), which a
headless driver can't render but can still record — so dropping SCALED, or going
back to exclusive FULLSCREEN, fails the test. On-screen scaling is confirmed
manually on the Mac (headless has no GPU renderer).
"""

import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp
    from rpg_game.presentation.pygame_canvas import desktop_size, fit_size

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


def _isolate_settings(testcase):
    """B122c: keep prefs writes (toggle_fullscreen persists) off the real
    settings.json by pointing SETTINGS_PATH at a throwaway temp file."""
    import tempfile

    from rpg_game.presentation import settings as user_settings
    handle = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    handle.close()
    testcase.addCleanup(lambda: os.path.exists(handle.name) and os.unlink(handle.name))
    patcher = mock.patch.object(user_settings, "SETTINGS_PATH", handle.name)
    patcher.start()
    testcase.addCleanup(patcher.stop)


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class DisplayModeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        _isolate_settings(self)

    def _spy_apply(self, fullscreen):
        app = OverworldApp()
        real = pygame.display.set_mode
        calls = []

        def spy(size, flags=0, *a, **k):
            calls.append((tuple(size), flags))
            return real(size, flags, *a, **k)

        with mock.patch.object(pygame.display, "set_mode", side_effect=spy):
            app.fullscreen = fullscreen
            app._apply_display_mode()
        return calls

    def test_big_mode_requests_scaled_bordered_not_exclusive_fullscreen(self):
        calls = self._spy_apply(fullscreen=True)
        self.assertTrue(calls)
        # The first attempt (before any headless fallback) is the real request.
        size, flags = calls[0]
        self.assertTrue(flags & pygame.SCALED, "must request SCALED for crisp HiDPI scaling")
        self.assertTrue(flags & pygame.RESIZABLE, "must stay a normal resizable window")
        self.assertFalse(flags & pygame.FULLSCREEN, "must NOT use exclusive fullscreen (traps the user)")
        self.assertEqual(size, tuple(fit_size(desktop_size())))  # large bordered window

    def test_windowed_mode_also_scaled_and_bordered(self):
        calls = self._spy_apply(fullscreen=False)
        self.assertTrue(calls)
        size, flags = calls[0]
        self.assertTrue(flags & pygame.SCALED)
        self.assertTrue(flags & pygame.RESIZABLE)
        self.assertFalse(flags & pygame.FULLSCREEN)

    def test_headless_fallback_drops_scaled_only_when_needed(self):
        # set_display_mode retries without SCALED if the renderer can't init. Verify
        # the helper itself doesn't raise headless and yields a surface.
        from rpg_game.presentation.pygame_canvas import set_display_mode
        surf = set_display_mode((800, 600))
        self.assertIsNotNone(surf)

    def test_toggle_yields_valid_surface_both_ways(self):
        app = OverworldApp()
        app.toggle_fullscreen()
        self.assertTrue(app.fullscreen)
        self.assertIsNotNone(app.display)
        app.draw()
        app.toggle_fullscreen()
        self.assertFalse(app.fullscreen)
        self.assertIsNotNone(app.display)
        app.draw()


if __name__ == "__main__":
    unittest.main()
