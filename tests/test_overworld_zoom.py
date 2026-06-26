"""Player-centered integer zoom in the overworld (Platinum-style view).

The world renders to a small surface (screen / zoom) and is nearest-neighbour
scaled up by an INTEGER factor -> crisp pixel art, ~10 tiles wide. The player
stays centered (camera clamps at map edges). HUD/overlays are drawn in unscaled
screen space. Pure presentation. Skips without pygame/pytmx.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp, ZOOM_TARGET_TILES_W

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class OverworldZoomTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _app(self, size=(960, 640)):
        app = OverworldApp()
        app.display = pygame.Surface(size)
        return app

    def test_zoom_is_an_integer_in_range(self):
        for size in [(960, 640), (1391, 903), (1920, 1080)]:
            app = self._app(size)
            app.draw()
            z = app._zoom_factor()
            self.assertEqual(z, int(z))
            self.assertTrue(2 <= z <= 5)

    def test_zoom_and_tiles_in_width_locked(self):
        # ZOOM_TARGET_TILES_W=12 with integer-stepped zoom -> these exact values.
        # (width -> expected integer zoom, tiles-in-width). Locks the ~12-wide view.
        expected = {1280: (3, 1280 / (3 * 32)),    # 13.33 tiles (was 10.0 @ zoom 4)
                    1600: (4, 1600 / (4 * 32))}     # 12.50 tiles (was 10.0 @ zoom 5)
        for w, (exp_z, exp_tiles) in expected.items():
            app = self._app((w, 720))
            app.draw()
            z = app._zoom_factor()
            self.assertEqual(z, exp_z, f"width {w}")
            visible_w = w / (z * app.world.tw)
            self.assertAlmostEqual(visible_w, exp_tiles, delta=0.01)
            self.assertGreater(visible_w, 11.5)             # ~2 tiles wider than the old 10
            self.assertLess(visible_w, app.world.tmx.width)  # still a slice, not the map

    def test_player_stays_centered_mid_map(self):
        app = self._app((960, 640))
        app.world.set_tile(24, 16)  # interior, away from edges
        app.draw()
        z = app._zoom_factor()
        ox, oy = app._cam_offset
        view_w, view_h = (960 // z), (640 // z)
        # Player's world center sits at the view center (within a tile).
        self.assertAlmostEqual(app.world.player.centerx - ox, view_w // 2, delta=app.world.tw)
        self.assertAlmostEqual(app.world.player.centery - oy, view_h // 2, delta=app.world.th)

    def test_camera_clamps_at_map_edge(self):
        app = self._app((960, 640))
        app.world.set_tile(0, 0)  # top-left corner
        app.draw()
        ox, oy = app._cam_offset
        self.assertEqual((ox, oy), (0, 0))  # never scrolls past the map edge

    def test_screen_to_tile_maps_through_zoom(self):
        app = self._app((960, 640))
        app.world.set_tile(24, 16)
        app.draw()
        z = app._zoom_factor()
        ox, oy = app._cam_offset
        # The player's drawn screen position maps back to its tile.
        sx = (app.world.player.centerx - ox) * z
        sy = (app.world.player.centery - oy) * z
        self.assertEqual(app.screen_to_tile((sx, sy)), (24, 16))

    def test_hud_canvas_is_unscaled_full_window(self):
        # _draw_map must not change the canvas size; HUD/overlays draw unscaled
        # over the full window after the zoomed world blit.
        app = self._app((1391, 903))
        app.draw()
        self.assertEqual(app.screen.get_size(), (1391, 903))
        self.assertEqual(app._transform, (0, 0, 1.0))  # fluid: identity present

    def test_target_constant_drives_zoom(self):
        self.assertEqual(ZOOM_TARGET_TILES_W, 12)


if __name__ == "__main__":
    unittest.main()
