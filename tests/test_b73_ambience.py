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

    def test_s2_preset_table_wires_only_mork_skog(self):
        # S2: the zone->preset table carries the S1 fireflies unchanged; the
        # proposal presets stay in the draft file until Lucas approves them.
        from rpg_game.presentation import ambience_drafts
        self.assertEqual(set(ambience.PRESETS), {"mork_skog"})
        preset = ambience.PRESETS["mork_skog"]
        self.assertEqual(preset["kind"], "firefly")
        self.assertEqual(preset["count"], ambience.FIREFLY_COUNT)
        for zone in ambience_drafts.DRAFT_PRESETS:
            self.assertNotIn(zone, ambience.PRESETS, zone)

    def test_s2_draft_presets_render_particles(self):
        from rpg_game.presentation import ambience_drafts
        for zone, preset in ambience_drafts.DRAFT_PRESETS.items():
            layer = ambience.ParticleLayer((320, 200), seed=2, preset=preset)
            surface = pygame.Surface((320, 200), pygame.SRCALPHA)
            for _ in range(30):
                layer.update()
            layer.draw(surface)
            # low threshold: mist/pollen drafts are deliberately faint (alpha < 127)
            self.assertGreater(pygame.mask.from_surface(surface, 8).count(), 0, zone)

    def test_s2_settings_toggle_gates_the_layer(self):
        from rpg_game.presentation import settings as user_settings
        self.assertIn("ambience", user_settings.DEFAULTS)
        self.assertIn("ambience", [o["key"] for o in user_settings.OPTIONS])
        app = OverworldApp()
        app.screen = pygame.Surface((640, 400))
        skog = next((x, 20) for x in range(0, app.world.tmx.width, 4)
                    if app.zone.theme_for_tile((x, 20)) == "mork_skog")
        app.world.set_tile(*skog)
        app._settings["ambience"] = False
        app._draw_ambience()
        self.assertIsNone(app._ambience)      # off: never instantiated
        app._settings["ambience"] = True
        app._draw_ambience()
        self.assertIsNotNone(app._ambience)   # on: the skog preset appears

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
