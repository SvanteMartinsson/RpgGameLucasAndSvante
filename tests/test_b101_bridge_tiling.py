"""B101: edge-aware bridge deck tiling.

The halfdeck tile carries one rail (dark stringer, columns 0..DECK_RAIL_W-1
after the B52 rotation). Wide crossings pick variants per column at render
time — left edge keeps the rail, mid columns erase it (plank continuation),
the right edge is flipped so its rail lands outside. Map data is untouched.
Skips without pygame/pytmx.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame

    from rpg_game.presentation import overworld_render
    from rpg_game.presentation.overworld_render import MapRenderMixin, DECK_RAIL_W

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class DeckVariantKeyTest(unittest.TestCase):
    GID = 4871

    def _row(self, cells):
        return [self.GID if c else 0 for c in cells]

    def test_three_wide_crossing(self):
        row = self._row([0, 1, 1, 1, 0])
        key = MapRenderMixin._deck_variant_key
        self.assertEqual(key(row, 1, self.GID), "left")
        self.assertEqual(key(row, 2, self.GID), "mid")
        self.assertEqual(key(row, 3, self.GID), "right")

    def test_single_column_is_solo(self):
        row = self._row([0, 1, 0])
        self.assertEqual(MapRenderMixin._deck_variant_key(row, 1, self.GID), "solo")

    def test_row_edges_do_not_wrap(self):
        row = self._row([1, 1])
        key = MapRenderMixin._deck_variant_key
        self.assertEqual(key(row, 0, self.GID), "left")
        self.assertEqual(key(row, 1, self.GID), "right")


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class DeckVariantImageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        sheet = pygame.image.load(
            "rpg_game/assets/tiles/generated/bridge_halfdeck_32x32.png").convert_alpha()
        cls.rotated = pygame.transform.rotate(sheet.subsurface((0, 0, 32, 32)).copy(), 90)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _column_avg(self, surface, x):
        return sum(sum(surface.get_at((x, y))[:3]) for y in range(surface.get_height())) / (
            3 * surface.get_height())

    def test_mid_variant_erases_the_rail(self):
        mid = MapRenderMixin._deck_variant(self.rotated, "mid")
        # The rail columns become as bright as the interior planks they copy.
        for x in range(DECK_RAIL_W):
            self.assertEqual(mid.get_at((x, 5)), self.rotated.get_at((x + DECK_RAIL_W, 5)))
        self.assertGreater(self._column_avg(mid, 2), self._column_avg(self.rotated, 2))

    def test_right_variant_moves_the_rail_to_the_outer_edge(self):
        right = MapRenderMixin._deck_variant(self.rotated, "right")
        width = right.get_width()
        # Darkest rail column mirrors from the left edge to the right edge.
        self.assertEqual(right.get_at((width - 3, 5)), self.rotated.get_at((2, 5)))

    def test_left_and_solo_pass_through_unchanged(self):
        self.assertIs(MapRenderMixin._deck_variant(self.rotated, "left"), self.rotated)
        self.assertIs(MapRenderMixin._deck_variant(self.rotated, "solo"), self.rotated)


if __name__ == "__main__":
    unittest.main()
