"""B73/B110: world-space ambience drawn over the map and under the HUD.

Its RNG is its own stream (never the engine's). Locks: theme gating, pool size,
world anchoring, culling,
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

    def test_layer_draws_fireflies_and_recycles_far_outliers(self):
        layer = ambience.ParticleLayer((320, 200), seed=1, world_center=(500, 400))
        self.assertEqual(len(layer.particles), ambience.FIREFLY_COUNT)
        surface = pygame.Surface((320, 200), pygame.SRCALPHA)
        for _ in range(30):
            layer.update()
        layer.draw(surface, (340, 300))
        self.assertGreater(pygame.mask.from_surface(surface).count(), 0)
        for p in layer.particles:
            self.assertTrue(260 <= p.x <= 740)

    def test_particle_stays_in_world_when_camera_moves(self):
        layer = ambience.ParticleLayer((320, 200), seed=4, world_center=(500, 400))
        particle = layer.particles[0]
        particle.x, particle.y, particle.vx = 500, 400, 0
        before = (particle.x, particle.y)
        layer.update((530, 400))
        self.assertEqual((particle.x, particle.y), before)
        self.assertEqual(particle.x - 340, 160)  # first camera position
        self.assertEqual(particle.x - 370, 130)  # camera moved: particle moved on screen

    def test_offscreen_particles_are_culled_before_blit(self):
        layer = ambience.ParticleLayer((320, 200), seed=2, world_center=(500, 400))
        for particle in layer.particles:
            particle.x, particle.y = 10_000, 10_000
        surface = pygame.Surface((320, 200), pygame.SRCALPHA)
        layer.draw(surface, (340, 300))
        self.assertEqual(pygame.mask.from_surface(surface).count(), 0)

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
