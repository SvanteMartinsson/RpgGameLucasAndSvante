"""B73 S1: the ambience particle layer — mork_skog fireflies only.

Screen-space layer drawn over the map and under the HUD; its RNG is its own
stream (never the engine's). Locks: theme gating, particle pool size/wrapping,
and that drawing leaves pixels on the surface. Skips without pygame/pytmx.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation import ambience
    from rpg_game.presentation.pygame_overworld import OverworldApp

    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class AmbienceLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_layer_draws_fireflies_and_wraps_horizontally(self):
        layer = ambience.ParticleLayer((320, 200), seed=1)
        self.assertEqual(len(layer.particles), ambience.FIREFLY_COUNT)
        surface = pygame.Surface((320, 200), pygame.SRCALPHA)
        for _ in range(30):
            layer.update()
        layer.draw(surface)
        self.assertGreater(pygame.mask.from_surface(surface).count(), 0)
        for p in layer.particles:
            self.assertTrue(0 <= p.x < 320)

    def test_app_only_draws_ambience_in_mork_skog(self):
        app = OverworldApp()
        app.screen = pygame.Surface((640, 400))
        # a cainos tile: no layer instantiated
        cainos = next(t for t in [(10, 40), (12, 40), (20, 40)]
                      if app.zone.theme_for_tile(t) != "mork_skog")
        app.world.set_tile(*cainos)
        app._draw_ambience()
        self.assertIsNone(app._ambience)
        # a mork_skog tile: the layer appears
        skog = None
        for x in range(0, app.world.tmx.width, 4):
            if app.zone.theme_for_tile((x, 20)) == "mork_skog":
                skog = (x, 20)
                break
        self.assertIsNotNone(skog)
        app.world.set_tile(*skog)
        app._draw_ambience()
        self.assertIsNotNone(app._ambience)


if __name__ == "__main__":
    unittest.main()
