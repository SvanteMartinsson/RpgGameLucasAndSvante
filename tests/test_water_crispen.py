"""Water/bridge tilesheet is crispened: the AI's soft ~4px alpha shoreline is
thresholded to hard 0/255 edges (crisp pixel art when zoomed), RGB preserved, raw
sheet kept. Deep water self-tiles seamlessly. Asset prep only — no TMX/placement.
Skips without pygame.
"""

import os
import unittest
from collections import Counter

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.tools.worldgen import crispen_water as cw

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame not installed")
class WaterCrispenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.raw = pygame.image.load(cw.RAW)
        cls.crisp = pygame.image.load(cw.OUT)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _alpha_hist(self, surf):
        return Counter(surf.get_at((x, y))[3]
                       for y in range(surf.get_height()) for x in range(surf.get_width()))

    def test_dimensions_preserved_8x3_grid(self):
        self.assertEqual(self.crisp.get_size(), self.raw.get_size())
        w, h = self.crisp.get_size()
        self.assertEqual((w % 32, h % 32), (0, 0))         # 32px grid intact
        self.assertEqual((w // 32, h // 32), (8, 3))

    def test_crisp_edges_only_0_or_255_alpha(self):
        # The whole point: no soft fringe left. Pure hard edges.
        self.assertEqual(set(self._alpha_hist(self.crisp)), {0, 255})

    def test_raw_is_preserved_with_soft_gradient(self):
        # Raw must keep its soft AI gradient (intermediate alphas) so we can re-run.
        soft = [a for a in self._alpha_hist(self.raw) if a not in (0, 255)]
        self.assertTrue(soft, "raw should still have its soft alpha gradient")

    def test_rgb_unchanged_where_opaque(self):
        # Thresholding only touches alpha; opaque RGB is preserved.
        for (x, y) in [(0, 0), (16, 16), (40, 8)]:
            if self.raw.get_at((x, y))[3] >= cw.THRESHOLD:
                self.assertEqual(self.crisp.get_at((x, y))[:3], self.raw.get_at((x, y))[:3])

    def test_deep_water_self_tiles_seamlessly(self):
        # Tile (0,0) is the deep-water fill; opposite edges must match closely so
        # repeating it shows no seam. (Texture, so allow a tiny ripple delta.)
        dw = self.crisp.subsurface((0, 0, 32, 32))

        def edge_delta(a, b):
            return sum(sum(abs(p[i] - q[i]) for i in range(3)) / 3 for p, q in zip(a, b)) / len(a)

        right = [dw.get_at((31, y)) for y in range(32)]
        left = [dw.get_at((0, y)) for y in range(32)]
        bottom = [dw.get_at((x, 31)) for x in range(32)]
        top = [dw.get_at((x, 0)) for x in range(32)]
        self.assertLess(edge_delta(right, left), 12)
        self.assertLess(edge_delta(bottom, top), 12)
        # And deep water is fully opaque (no shoreline holes in the fill tile).
        self.assertTrue(all(dw.get_at((x, y))[3] == 255 for y in range(32) for x in range(32)))

    def test_crispen_is_idempotent(self):
        # Re-crispening the already-crisp output changes nothing (0/255 in -> same).
        again = cw.crispen(self.crisp)
        for (x, y) in [(0, 0), (33, 5), (200, 40), (16, 70)]:
            self.assertEqual(again.get_at((x, y)), self.crisp.get_at((x, y)))


if __name__ == "__main__":
    unittest.main()
