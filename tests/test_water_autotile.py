"""Seamless water autotile set generated deterministically from the crisp
deep-water surface. The set is a complete minimal blob (full + 4 edges + 4 outer
+ 4 inner corners + 2 channels). Seamlessness is proven by CORNER-based tiling:
adjacent tiles share two corners, so a shared border is identical by
construction. We autotile a straight river, a meandering wide river and a lake
with coves and assert zero seam mismatches. Asset prep only — no TMX/placement.
Skips without pygame.
"""

import hashlib
import math
import os
import unittest
from collections import Counter

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.tools.worldgen import generate_water_autotiles as gw

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False

TS = 32

# (nw, ne, se, sw) water-corner pattern -> tile name. Maps a corner-sampled water
# field to the blob set; saddles (1,0,1,0)/(0,1,0,1) are intentionally absent.
CORNER_MAP = {
    (1, 1, 1, 1): "full",
    (0, 0, 1, 1): "edge_N", (1, 1, 0, 0): "edge_S",
    (1, 0, 0, 1): "edge_E", (0, 1, 1, 0): "edge_W",
    (0, 0, 1, 0): "out_NW", (0, 0, 0, 1): "out_NE",
    (0, 1, 0, 0): "out_SW", (1, 0, 0, 0): "out_SE",
    (0, 1, 1, 1): "in_NW", (1, 0, 1, 1): "in_NE",
    (1, 1, 1, 0): "in_SW", (1, 1, 0, 1): "in_SE",
}


@unittest.skipUnless(DEPS_OK, "pygame not installed")
class WaterAutotileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        gw.build  # ensure module loaded
        cls.sheet = gw.build()                       # freshly generated, in memory
        cls.src = pygame.image.load(gw.SRC).convert_alpha()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    # --- tile access helpers ---
    def _tile(self, name):
        cx, cy = gw.ATLAS[name]
        return self.sheet.subsurface(pygame.Rect(cx * TS, cy * TS, TS, TS))

    def _profile(self, name, side):
        t = self._tile(name)
        if side == "N":
            return tuple(1 if t.get_at((i, 0))[3] else 0 for i in range(TS))
        if side == "S":
            return tuple(1 if t.get_at((i, TS - 1))[3] else 0 for i in range(TS))
        if side == "W":
            return tuple(1 if t.get_at((0, i))[3] else 0 for i in range(TS))
        return tuple(1 if t.get_at((TS - 1, i))[3] else 0 for i in range(TS))

    # --- structure ---
    def test_atlas_has_15_tiles_in_4x4(self):
        self.assertEqual(len(gw.ATLAS), 15)
        self.assertEqual(self.sheet.get_size(), (gw.COLS * TS, gw.ROWS * TS))

    def test_alpha_is_crisp_only_0_or_255(self):
        hist = Counter(self.sheet.get_at((x, y))[3]
                       for y in range(self.sheet.get_height())
                       for x in range(self.sheet.get_width()))
        self.assertEqual(set(hist) - {0, 255}, set(), f"non-crisp alpha: {dict(hist)}")

    def test_full_water_matches_source_deep_water_exactly(self):
        # zero palette drift: every water texel is the crisp tile (0,0) pixel.
        full = self._tile("full")
        for y in range(TS):
            for x in range(TS):
                self.assertEqual(full.get_at((x, y))[:3], self.src.get_at((x, y))[:3])

    def test_full_water_self_tiles(self):
        for side in "NSEW":
            self.assertEqual(self._profile("full", side), tuple([1] * TS))

    def test_only_five_distinct_border_profiles(self):
        # the invariant that makes the set seamless: every border is one of a few
        # canonical profiles, so matching profiles connect exactly.
        profs = {self._profile(n, s) for n in gw.ATLAS for s in "NSEW"}
        self.assertLessEqual(len(profs), 5)

    # --- seam proof on real scenes ---
    def _autotile(self, corner):
        H, W = len(corner) - 1, len(corner[0]) - 1
        placed, saddles = {}, []
        for y in range(H):
            for x in range(W):
                pat = (int(corner[y][x]), int(corner[y][x + 1]),
                       int(corner[y + 1][x + 1]), int(corner[y + 1][x]))
                if sum(pat) == 0:
                    continue
                name = CORNER_MAP.get(pat)
                if name is None:
                    saddles.append((x, y))
                else:
                    placed[(x, y)] = name
        return placed, saddles

    def _seam_fails(self, placed):
        fails = []
        for (x, y), name in placed.items():
            for dx, dy, a, b in [(1, 0, "E", "W"), (0, 1, "S", "N")]:
                nb = placed.get((x + dx, y + dy))
                if nb and self._profile(name, a) != self._profile(nb, b):
                    fails.append(((x, y), name, nb, a))
        return fails

    def _grid(self, W, H, field):
        return [[field(gx, gy) for gx in range(W + 1)] for gy in range(H + 1)]

    def test_straight_river_seamless(self):
        cg = self._grid(7, 9, lambda gx, gy: 2 <= gx <= 5)
        placed, saddles = self._autotile(cg)
        self.assertEqual(saddles, [])
        self.assertEqual(self._seam_fails(placed), [])

    def test_meander_river_seamless_uses_all_corners(self):
        cg = self._grid(11, 12,
                         lambda gx, gy: abs(gx - (4.5 + 2.4 * math.sin(gy * 0.55))) <= 2.0)
        placed, saddles = self._autotile(cg)
        self.assertEqual(saddles, [])
        self.assertEqual(self._seam_fails(placed), [])
        # a real meander should exercise every edge + corner kind
        for kind in ("edge_N", "edge_S", "edge_E", "edge_W",
                     "out_NW", "out_NE", "out_SE", "out_SW"):
            self.assertIn(kind, set(placed.values()))

    def test_lake_with_cove_seamless_uses_inner_corners(self):
        def field(gx, gy):
            inside = ((gx - 5.5) ** 2) / 18 + ((gy - 4.5) ** 2) / 10 <= 1.0
            cove = ((gx - 8.5) ** 2 + (gy - 4.5) ** 2) <= 4.0
            return inside and not cove
        cg = self._grid(12, 9, field)
        placed, saddles = self._autotile(cg)
        self.assertEqual(saddles, [])
        self.assertEqual(self._seam_fails(placed), [])
        self.assertTrue(any(k.startswith("in_") for k in placed.values()))

    def test_channels_self_tile(self):
        chV = {(0, i): "chan_V" for i in range(6)}
        chH = {(i, 0): "chan_H" for i in range(6)}
        self.assertEqual(self._seam_fails(chV), [])
        self.assertEqual(self._seam_fails(chH), [])

    # --- determinism / asset safety ---
    def test_generation_is_idempotent(self):
        def digest(surf):
            return hashlib.md5(pygame.image.tostring(surf, "RGBA")).hexdigest()
        self.assertEqual(digest(gw.build()), digest(self.sheet))

    def test_writes_separate_sheet_not_source(self):
        # bridges + raw/crisp sheets are preserved: we only ever write OUT.
        self.assertNotEqual(os.path.abspath(gw.OUT), os.path.abspath(gw.SRC))


if __name__ == "__main__":
    unittest.main()
