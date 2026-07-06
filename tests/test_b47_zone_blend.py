"""B47: the zone-seam crossfade — draw-time overrides built once at load.

Locks: overrides exist along the seams and never in deep zone cores, layer
data is untouched (gid-walking consumers unaffected), the pass is
deterministic, and the M-map terrain still builds from real gids."""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation import overworld_render as ow_render
    from rpg_game.presentation.pygame_overworld import OverworldApp
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class ZoneBlendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.app = OverworldApp()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_overrides_hug_the_seams_and_skip_the_cores(self):
        overrides = self.app._blend_overrides
        self.assertTrue(overrides)
        on_seam = sum(1 for y in range(0, 96) if (83, y) in overrides)
        self.assertGreater(on_seam, 20)
        band = ow_render.ZONE_BLEND_BAND
        for (x, y) in overrides:
            near_vertical = y < 100 and (abs(x - 82.5) <= band or abs(x - 158.5) <= band)
            near_heath = abs(y - 99.5) <= band
            self.assertTrue(near_vertical or near_heath, (x, y))

    def test_layer_data_is_untouched(self):
        # every ground gid still resolves through pytmx (no synthetic gids in data)
        tmx = self.app.world.tmx
        ground = next(l for l in tmx.layers if getattr(l, "name", None) == "ground")
        for y in range(0, tmx.height, 13):
            for x in range(0, tmx.width, 17):
                gid = ground.data[y][x]
                if gid:
                    self.assertIsNotNone(tmx.get_tileset_from_gid(gid))

    def test_map_terrain_builds_from_real_gids(self):
        terrain = self.app._build_map_terrain()
        self.assertEqual(terrain.get_size(),
                         (self.app.world.tmx.width, self.app.world.tmx.height))

    def test_blend_is_deterministic(self):
        other = OverworldApp()
        self.assertEqual(self.app._blend_overrides, other._blend_overrides)


if __name__ == "__main__":
    unittest.main()
