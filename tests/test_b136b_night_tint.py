"""B136b: the darkness tint and the HUD phase indicator.

The colour rule is a pure function and is tested as one. The render half only
has to prove three things: every phase draws without blowing up, full daylight
draws NOTHING at all, and the night frame really does keep the readability the
alpha cap promises (the analytic (1 - a/255) contrast scaling).

Skips without pygame.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from rpg_game.core import daynight
from rpg_game.presentation import daylight

try:
    import pygame

    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


class TintColourRuleTests(unittest.TestCase):
    def test_full_daylight_draws_nothing(self):
        for progress in (0.0, 0.5, 0.99):
            self.assertEqual(daylight.tint_for("day", progress), daylight.CLEAR)
            self.assertEqual(daylight.tint_for("day", progress)[3], 0)

    def test_night_holds_the_deep_blue_at_the_capped_alpha(self):
        for progress in (0.0, 0.5, 0.99):
            self.assertEqual(daylight.tint_for("night", progress), daylight.NIGHT_TINT)
        self.assertEqual(daylight.NIGHT_TINT[3], daylight.NIGHT_ALPHA)

    def test_dusk_slides_from_clear_through_warm_to_night(self):
        self.assertEqual(daylight.tint_for("dusk", 0.0), daylight.CLEAR)
        self.assertEqual(daylight.tint_for("dusk", 1.0), daylight.NIGHT_TINT)
        middle = daylight.tint_for("dusk", 0.6)
        self.assertEqual(middle, daylight.DUSK_GLOW)
        # Warm: red dominates blue on the way down.
        self.assertGreater(middle[0], middle[2])

    def test_dawn_slides_from_night_through_rose_to_clear(self):
        self.assertEqual(daylight.tint_for("dawn", 0.0), daylight.NIGHT_TINT)
        self.assertEqual(daylight.tint_for("dawn", 1.0), daylight.CLEAR)
        self.assertEqual(daylight.tint_for("dawn", 0.5), daylight.DAWN_GLOW)

    def test_alpha_moves_monotonically_across_a_transition(self):
        # Dusk darkens without ever brightening; dawn lightens without dimming.
        dusk = [daylight.tint_for("dusk", i / 20)[3] for i in range(21)]
        dawn = [daylight.tint_for("dawn", i / 20)[3] for i in range(21)]
        self.assertEqual(dusk, sorted(dusk))
        self.assertEqual(dawn, sorted(dawn, reverse=True))

    def test_the_transitions_agree_with_their_neighbours_at_the_boundary(self):
        # No snap: each phase's end colour is the next phase's start colour.
        order = daynight.PHASE_ORDER
        for index, phase in enumerate(order):
            following = order[(index + 1) % len(order)]
            self.assertEqual(daylight.tint_for(phase, 1.0),
                             daylight.tint_for(following, 0.0),
                             f"{phase} -> {following}")

    def test_the_alpha_cap_honours_the_readability_rail(self):
        retained = daylight.contrast_retained(daylight.NIGHT_ALPHA)
        self.assertGreaterEqual(retained, daylight.MIN_CONTRAST_RETAINED)
        # And no keyframe anywhere is darker than the cap.
        for phase, frames in daylight.KEYFRAMES.items():
            for _at, (_r, _g, _b, alpha) in frames:
                self.assertLessEqual(alpha, daylight.NIGHT_ALPHA, phase)

    def test_contrast_retained_is_the_blend_maths(self):
        self.assertAlmostEqual(daylight.contrast_retained(0), 1.0)
        self.assertAlmostEqual(daylight.contrast_retained(255), 0.0)
        self.assertAlmostEqual(daylight.contrast_retained(128), 1 - 128 / 255)
        # clamps rather than going out of range
        self.assertAlmostEqual(daylight.contrast_retained(-5), 1.0)
        self.assertAlmostEqual(daylight.contrast_retained(999), 0.0)

    def test_a_broken_phase_string_never_blacks_the_screen_out(self):
        self.assertEqual(daylight.tint_for("", 0.5), daylight.CLEAR)
        self.assertEqual(daylight.tint_for("midnight-ish", 0.5), daylight.CLEAR)

    def test_every_phase_has_a_keyframe_set_and_an_indicator_colour(self):
        for phase in daynight.PHASE_ORDER:
            self.assertIn(phase, daylight.KEYFRAMES)
            self.assertIn(phase, daylight.PHASE_COLORS)
            self.assertIn(phase, daynight.PHASE_LABELS)


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class TintRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.app = OverworldApp()
        cls.app.screen = pygame.Surface((320, 200))
        tile = next(iter(cls.app.zone.towns))
        cls.app.world.set_tile(tile[0] + 3, tile[1] + 2)
        cls.app.sync_location()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _frame(self, phase, progress=0.25):
        app = self.app
        app.engine.set_world_phase(phase)
        app.engine.player.world_time_seconds += daynight.PHASE_SECONDS[phase] * progress
        app.screen.fill((0, 0, 0))
        app._draw_map()
        app._draw_daylight_tint()
        return pygame.image.tostring(app.screen, "RGB")

    def _contrast(self, raw):
        # Luminance std-dev over the frame (Rec.601-ish, integer weights).
        values = [(raw[i] * 299 + raw[i + 1] * 587 + raw[i + 2] * 114) // 1000
                  for i in range(0, len(raw), 3)]
        mean = sum(values) / len(values)
        return (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5

    def test_all_four_phases_render(self):
        for phase in daynight.PHASE_ORDER:
            self.assertTrue(self._frame(phase))

    def test_daylight_leaves_the_map_pixel_identical(self):
        app = self.app
        app.engine.set_world_phase("day")
        app.screen.fill((0, 0, 0))
        app._draw_map()
        untinted = pygame.image.tostring(app.screen, "RGB")
        app._draw_daylight_tint()          # must be a no-op at full daylight
        self.assertEqual(pygame.image.tostring(app.screen, "RGB"), untinted)

    def test_night_darkens_the_frame_but_keeps_it_readable(self):
        day = self._frame("day")
        night = self._frame("night")
        self.assertNotEqual(day, night)
        # Darker on average...
        self.assertLess(sum(night) / len(night), sum(day) / len(day))
        # ...but the contrast retained matches the analytic rail (the HUD is not
        # drawn here, so this is the pure map-vs-tint number).
        ratio = self._contrast(night) / self._contrast(day)
        self.assertGreaterEqual(ratio, daylight.MIN_CONTRAST_RETAINED)
        self.assertAlmostEqual(ratio, daylight.contrast_retained(daylight.NIGHT_ALPHA),
                               delta=0.03)

    def test_the_night_frame_is_blue_not_merely_dark(self):
        raw = self._frame("night")
        reds = sum(raw[0::3]) / (len(raw) / 3)
        blues = sum(raw[2::3]) / (len(raw) / 3)
        day = self._frame("day")
        day_reds = sum(day[0::3]) / (len(day) / 3)
        day_blues = sum(day[2::3]) / (len(day) / 3)
        # Blue survives the night better than red does.
        self.assertGreater(blues / day_blues, reds / day_reds)

    def test_dusk_is_warmer_than_night(self):
        dusk = self._frame("dusk", progress=0.6)
        night = self._frame("night")
        dusk_warmth = (sum(dusk[0::3]) + 1) / (sum(dusk[2::3]) + 1)
        night_warmth = (sum(night[0::3]) + 1) / (sum(night[2::3]) + 1)
        self.assertGreater(dusk_warmth, night_warmth)

    def test_the_hud_draws_a_phase_indicator_in_every_phase(self):
        for phase in daynight.PHASE_ORDER:
            self.app.engine.set_world_phase(phase)
            self.app.screen.fill((0, 0, 0))
            self.app._draw_hud()          # must not raise; chip is drawn inside
            self.assertTrue(pygame.image.tostring(self.app.screen, "RGB"))

    def test_the_tint_is_drawn_under_the_particles_so_fireflies_glow(self):
        # Order contract: _draw_map -> tint -> ambience -> HUD. A firefly drawn
        # BEFORE the veil would be dimmed by it; drawn after, it glows.
        import inspect
        source = inspect.getsource(OverworldApp.draw)
        self.assertLess(source.index("_draw_daylight_tint"), source.index("_draw_ambience"))
        self.assertLess(source.index("_draw_ambience"), source.index("_draw_hud"))


if __name__ == "__main__":
    unittest.main()
