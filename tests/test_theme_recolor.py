"""Tonal harmonisation of the dark overworld zones (art/asset only).

Locks the measurable outcome of recolor_themes.py: the dark themes' base-grass
luminance now sits in the same family as cainos (lifted, but still distinct and
below it), props/struct sheets are lifted so they stop drowning, and the cainos
sheets are byte-for-byte untouched. Skips without pygame.
"""

import hashlib
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    import recolor_themes as rt

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False

TILES = "rpg_game/assets/tiles/generated"
PROPS = "rpg_game/assets/props/generated"
CAINOS = {
    "rpg_game/assets/tiles/cainos/TX Tileset Grass.png": "3afee45fa3ab4f29",
    "rpg_game/assets/tiles/cainos/TX Tileset Stone Ground.png": "fc5b3817bc03b760",
    "rpg_game/assets/tiles/cainos/TX Tileset Wall.png": "9c32a07a940e2335",
    "rpg_game/assets/props/cainos/TX Plant with Shadow.png": "f9fbf5bb5d8518b6",
    "rpg_game/assets/props/cainos/TX Props with Shadow.png": "00fec4ada4c03cd1",
}
# Per-theme base-grass tile-0 luma window (and the metric matches cainos ~106).
GRASS_TARGET = {
    "mork_skog": (78, 88),
    "cursed_mire": (80, 90),
}


def _opaque_luma(surface, region=None):
    """Mean Rec.601 luma over opaque pixels (whole sheet, or a region rect)."""
    if region is None:
        region = surface.get_rect()
    total, count = 0.0, 0
    for y in range(region.top, region.bottom):
        for x in range(region.left, region.right):
            r, g, b, a = surface.get_at((x, y))
            if a == 0:
                continue
            count += 1
            total += 0.299 * r + 0.587 * g + 0.114 * b
    return total / (count or 1)


def _grass(theme):
    return pygame.image.load(os.path.join(TILES, f"01-TX-Tileset-Grass__{theme}.png"))


@unittest.skipUnless(DEPS_OK, "pygame not installed")
class ThemeRecolorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_grass_base_tile_luma_in_target_window(self):
        for theme, (lo, hi) in GRASS_TARGET.items():
            tile0 = pygame.Rect(0, 0, 32, 32)
            luma = _opaque_luma(_grass(theme), tile0)
            self.assertTrue(lo <= luma <= hi, f"{theme} grass luma {luma:.1f} not in [{lo},{hi}]")

    def test_zones_stay_distinct_and_below_cainos(self):
        tile0 = pygame.Rect(0, 0, 32, 32)
        mork = _opaque_luma(_grass("mork_skog"), tile0)
        mire = _opaque_luma(_grass("cursed_mire"), tile0)
        cainos = _opaque_luma(
            pygame.image.load("rpg_game/assets/tiles/cainos/TX Tileset Grass.png"), tile0)
        self.assertLess(mork, mire)        # mork_skog stays the darkest
        self.assertLess(mire, cainos)      # both remain below cainos -> zones read distinct

    def test_props_and_struct_sheets_are_lifted_not_drowning(self):
        # The likely-wrong guess was "only the grass needs lifting". Verify the
        # prop/struct sheets rose too (before-means were ~48-62; now well above).
        for theme in ("mork_skog", "cursed_mire"):
            for name in ("03-TX-Props-with-Shadow", "06-TX-Struct"):
                surf = pygame.image.load(os.path.join(PROPS if "Props" in name or "Struct" in name else TILES,
                                                       f"{name}__{theme}.png"))
                self.assertGreaterEqual(_opaque_luma(surf), 70.0,
                                        f"{name}__{theme} still too dark")

    def test_cainos_sheets_are_byte_identical(self):
        for path, expected in CAINOS.items():
            digest = hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
            self.assertEqual(digest, expected, f"cainos sheet changed: {path}")

    def test_recolor_targets_only_the_two_dark_themes(self):
        # Structural guard: the script can never touch cainos or other themes.
        self.assertEqual(set(rt.THEME_FACTORS), {"mork_skog", "cursed_mire"})
        for theme in rt.THEME_FACTORS:
            sheets = rt.theme_sheets(theme)
            self.assertTrue(sheets)  # found something to lift
            self.assertEqual(len(sheets), 9)  # 3 tiles + 6 props per theme
            for path in sheets:
                self.assertNotIn("cainos", path)
                self.assertIn(f"__{theme}.png", path)


if __name__ == "__main__":
    unittest.main()
