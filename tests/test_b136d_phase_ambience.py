"""B136d: ambience presets per zone × phase; the fireflies moved to NIGHT.

Skips the render tests without pygame; the preset table is checked either way.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from rpg_game.core import daynight

try:
    import pygame

    from rpg_game.presentation import ambience
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False

ZONES = ("cainos", "mork_skog", "cursed_mire", "grave_heath")


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class PhasePresetTableTests(unittest.TestCase):
    def test_every_zone_has_both_a_day_and_a_night_preset(self):
        for theme in ZONES:
            for group in ("day", "night"):
                self.assertIn((theme, group), ambience.PHASE_PRESETS, (theme, group))

    def test_no_firefly_layer_survives_in_daylight(self):
        # The whole point of the slice: a pulsing glow in full sun reads as a
        # rendering artefact, not as an insect.
        for phase in ("dawn", "day"):
            for theme in ZONES:
                preset = ambience.preset_for(theme, phase)
                self.assertNotEqual(preset.get("kind", "firefly"), "firefly",
                                    f"{theme} @ {phase}")

    def test_every_zone_lights_up_after_dark(self):
        for phase in ("dusk", "night"):
            for theme in ZONES:
                preset = ambience.preset_for(theme, phase)
                self.assertEqual(preset.get("kind"), "firefly", f"{theme} @ {phase}")

    def test_dusk_already_shows_the_night_layer(self):
        # Same rule as the night spawn roster: the lights come out AS it darkens.
        for theme in ZONES:
            self.assertEqual(ambience.preset_for(theme, "dusk"),
                             ambience.preset_for(theme, "night"), theme)
            self.assertEqual(ambience.preset_for(theme, "dawn"),
                             ambience.preset_for(theme, "day"), theme)

    def test_mork_skogs_night_preset_is_the_original_s1_fireflies(self):
        self.assertIs(ambience.PHASE_PRESETS[("mork_skog", "night")],
                      ambience.PRESETS["mork_skog"])

    def test_the_approved_day_presets_are_reused_not_reinvented(self):
        # The B73 S2 renders Lucas approved stay pixel-identical by day.
        for theme in ("cainos", "cursed_mire", "grave_heath"):
            self.assertIs(ambience.PHASE_PRESETS[(theme, "day")], ambience.PRESETS[theme])

    def test_a_theme_without_a_phase_variant_falls_back_to_today(self):
        self.assertEqual(ambience.preset_for("mork_skog", "day"),
                         ambience.PHASE_PRESETS[("mork_skog", "day")])
        # An unwired theme keeps drawing nothing rather than inventing a layer.
        self.assertIsNone(ambience.preset_for("no_such_theme", "night"))
        self.assertIsNone(ambience.preset_for("no_such_theme", "day"))

    def test_every_preset_declares_a_kind_the_engine_supports(self):
        supported = {"firefly", "drift", "mist", "fall"}
        for key, preset in ambience.PHASE_PRESETS.items():
            self.assertIn(preset.get("kind", "firefly"), supported, key)
            self.assertGreater(preset.get("count", 0), 0, key)

    def test_night_glows_are_recoloured_per_zone(self):
        colors = {theme: ambience.preset_for(theme, "night").get("color") for theme in ZONES}
        for theme, color in colors.items():
            self.assertIsNotNone(color, theme)
            self.assertEqual(len(color), 3, theme)
        # The mire and the heath do NOT reuse the warm forest glow.
        self.assertNotEqual(colors["cursed_mire"], colors["mork_skog"])
        self.assertNotEqual(colors["grave_heath"], colors["mork_skog"])


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class PhaseAmbienceRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.app = OverworldApp()
        cls.app.screen = pygame.Surface((320, 200))
        cls.skog = cls._tile_for(cls.app, "mork_skog")

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    @staticmethod
    def _tile_for(app, theme):
        for y in (20, 40, 60):
            for x in range(0, app.world.tmx.width, 4):
                if app.zone.theme_for_tile((x, y)) == theme:
                    return (x, y)
        return None

    def test_crossing_into_night_rebuilds_the_layer(self):
        app = self.app
        app._settings["ambience"] = True
        app.world.set_tile(*self.skog)
        app.engine.set_world_phase("day")
        app._ambience = None
        app._draw_ambience()
        self.assertEqual(app._ambience_theme, ("mork_skog", "day"))
        day_layer = app._ambience
        self.assertNotEqual(day_layer.preset.get("kind"), "firefly")

        app.engine.set_world_phase("night")
        app._draw_ambience()
        self.assertEqual(app._ambience_theme, ("mork_skog", "night"))
        self.assertIsNot(app._ambience, day_layer)      # rebuilt, not reused
        self.assertEqual(app._ambience.preset["kind"], "firefly")

    def test_the_ambience_toggle_still_governs_every_phase(self):
        app = self.app
        app.world.set_tile(*self.skog)
        for phase in daynight.PHASE_ORDER:
            app.engine.set_world_phase(phase)
            app._settings["ambience"] = False
            app._ambience = None
            app._draw_ambience()
            self.assertIsNone(app._ambience, phase)     # off: never instantiated
            app._settings["ambience"] = True
            app._draw_ambience()
            self.assertIsNotNone(app._ambience, phase)

    def test_all_four_phases_draw_ambience_without_raising(self):
        app = self.app
        app._settings["ambience"] = True
        for theme in ZONES:
            tile = self._tile_for(app, theme)
            if tile is None:
                continue
            app.world.set_tile(*tile)
            for phase in daynight.PHASE_ORDER:
                app.engine.set_world_phase(phase)
                app._ambience = None
                app.screen.fill((0, 0, 0))
                app._draw_ambience()
                self.assertIsNotNone(app._ambience, (theme, phase))

    def test_night_fireflies_actually_put_light_on_the_screen(self):
        # _draw_map is what publishes _cam_offset, which the world-space particle
        # layer blits through — so the baseline is a map-only frame.
        app = self.app
        app._settings["ambience"] = True
        app.world.set_tile(*self.skog)
        app.engine.set_world_phase("night")
        app.screen.fill((0, 0, 0))
        app._draw_map()
        baseline = pygame.image.tostring(app.screen, "RGB")

        app._ambience = None
        differed = False
        for _ in range(40):        # let the pulse phase around
            app.screen.fill((0, 0, 0))
            app._draw_map()
            app._draw_ambience()
            if pygame.image.tostring(app.screen, "RGB") != baseline:
                differed = True
                break
        self.assertTrue(differed, "the night layer drew nothing at all")


if __name__ == "__main__":
    unittest.main()
