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

    def test_s2_all_four_zone_presets_wired(self):
        # Lucas GO 2026-07-12: all four zones wired — mork_skog fireflies + the
        # three approved drafts (cainos/cursed_mire/grave_heath).
        self.assertEqual(set(ambience.PRESETS),
                         {"mork_skog", "cainos", "cursed_mire", "grave_heath"})
        skog = ambience.PRESETS["mork_skog"]
        self.assertEqual(skog["kind"], "firefly")
        self.assertEqual(skog["count"], ambience.FIREFLY_COUNT)

    def test_s2_wired_presets_render_particles(self):
        for zone, preset in ambience.PRESETS.items():
            layer = ambience.ParticleLayer((320, 200), seed=2, preset=preset)
            surface = pygame.Surface((320, 200), pygame.SRCALPHA)
            for _ in range(30):
                layer.update()
            layer.draw(surface)
            # low threshold: mist/pollen are deliberately faint (alpha < 127)
            self.assertGreater(pygame.mask.from_surface(surface, 8).count(), 0, zone)

    def test_drafts_stay_in_sync_with_wired_presets(self):
        # The historical draft dict re-derives from PRESETS so it can't drift.
        from rpg_game.presentation import ambience_drafts
        for zone, preset in ambience_drafts.DRAFT_PRESETS.items():
            self.assertEqual(preset, ambience.PRESETS[zone], zone)

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

    def test_app_swaps_the_preset_per_zone_theme(self):
        # Lucas GO 2026-07-12: every zone now has a preset; the layer is rebuilt
        # when the theme changes so cainos drift and mork_skog fireflies never
        # bleed into each other.
        app = OverworldApp()
        app.screen = pygame.Surface((640, 400))

        def _tile_for(theme):
            for y in (20, 40, 60):
                for x in range(0, app.world.tmx.width, 4):
                    if app.zone.theme_for_tile((x, y)) == theme:
                        return (x, y)
            return None

        cainos = _tile_for("cainos")
        skog = _tile_for("mork_skog")
        self.assertIsNotNone(cainos)
        self.assertIsNotNone(skog)

        app.world.set_tile(*cainos)
        app._draw_ambience()
        self.assertIsNotNone(app._ambience)               # cainos has a preset now
        self.assertEqual(app._ambience_theme, "cainos")
        self.assertEqual(app._ambience.preset["kind"], "drift")

        app.world.set_tile(*skog)
        app._draw_ambience()
        self.assertEqual(app._ambience_theme, "mork_skog")  # rebuilt for the new zone
        self.assertEqual(app._ambience.preset["kind"], "firefly")


if __name__ == "__main__":
    unittest.main()
