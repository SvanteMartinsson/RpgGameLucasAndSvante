"""Viewport culling in the overworld draw: _draw_map blits only the tiles inside
the camera window (+1 margin) instead of the whole map. Must be render-identical
to a full sweep (off-window tiles contribute no pixels) and bounded by the view
(O(view), not O(map)). Presentation only — camera, zoom and click mapping
unchanged. Skips without pygame/pytmx.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False

POSITIONS = [(24, 16), (2, 2), (46, 30), (10, 25), (40, 5)]


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class OverworldCullingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _app(self):
        app = OverworldApp()
        app.screen = pygame.Surface((960, 640))  # fixed view for determinism
        return app

    def test_render_identical_to_full_sweep(self):
        culled = self._app()
        full = self._app()
        # Force the reference app to sweep the WHOLE map (no culling) via the same
        # production draw path -> any culled-out on-surface tile would differ.
        full._visible_tile_bounds = lambda vw, vh, ox, oy: (
            0, full.world.tmx.width, 0, full.world.tmx.height)
        for tx, ty in POSITIONS:
            for app in (culled, full):
                app.world.set_tile(tx, ty)
                app.screen.fill((0, 0, 0))
                app._draw_map()
            a = pygame.image.tostring(culled.screen, "RGBA")
            b = pygame.image.tostring(full.screen, "RGBA")
            self.assertEqual(a, b, f"culled != full sweep at camera {tx,ty}")

    def test_bounds_cover_the_whole_view(self):
        app = self._app()
        tw, th = app.world.tw, app.world.th
        view_w, view_h = 320, 240
        for ox, oy in [(0, 0), (500, 400), (100, 50)]:
            left, right, top, bottom = app._visible_tile_bounds(view_w, view_h, ox, oy)
            # the visible strip [ox, ox+view] is fully inside [left,right)*tw etc.
            self.assertLessEqual(left * tw, ox)
            self.assertGreaterEqual(right * tw, ox + view_w)
            self.assertLessEqual(top * th, oy)
            self.assertGreaterEqual(bottom * th, oy + view_h)

    def test_blit_count_is_O_view_not_O_map(self):
        app = self._app()
        view_w, view_h = 320, 240
        ox, oy = 200, 160  # away from edges so the clamp does not shrink the window
        small = app._visible_tile_bounds(view_w, view_h, ox, oy)
        # pretend the map is huge: the visible window must not grow with map size.
        orig_w, orig_h = app.world.tmx.width, app.world.tmx.height
        try:
            app.world.tmx.width, app.world.tmx.height = 800, 800
            big = app._visible_tile_bounds(view_w, view_h, ox, oy)
        finally:
            app.world.tmx.width, app.world.tmx.height = orig_w, orig_h
        cells = lambda b: (b[1] - b[0]) * (b[3] - b[2])
        self.assertEqual(cells(small), cells(big))
        # and it is a small constant ~ (view/tile + margin)^2, not the map area
        self.assertLess(cells(big), 400)

    def test_click_to_tile_unchanged_through_zoom(self):
        app = self._app()
        app.world.set_tile(24, 16)
        app._draw_map()  # sets _cam_offset
        zoom = app._zoom_factor()
        ox, oy = app._cam_offset
        tw, th = app.world.tw, app.world.th
        # a tile near the view centre should round-trip screen->tile exactly
        tx, ty = 24, 16
        sx = (tx * tw - ox + tw // 2) * zoom
        sy = (ty * th - oy + th // 2) * zoom
        self.assertEqual(app.screen_to_tile((sx, sy)), (tx, ty))


if __name__ == "__main__":
    unittest.main()
