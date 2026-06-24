"""Walls layer must hold only real, VISIBLE obstacles — no invisible collision.

The Verralda heath bug: sparse/transparent prop tiles (e.g. bush idx 98 = 0%
alpha, rock idx 240 = 8%) were placed in the walls (collision) layer, so the
player hit nothing visible ("phantom collision") and faint fragments read as
"clipped". Root: the obstacle index lists included near-empty ark tiles. Fix:
extend_verralda filters the pool to >= 25% opaque tiles.

These guards would have caught it: a walls cell may never hold a tile under 25%
opaque, nor a ground (grass/stone) tileset gid. Parses raw TMX gids (pytmx remaps
them) and measures each tile against its ark. Skips without pygame/pytmx.
"""

import os
import re
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import MAPS_DIR

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False

TMX = os.path.join(MAPS_DIR, "overworld.tmx") if DEPS_OK else ""
HEATH_Y0 = 20            # heath rows (the part this task generates)
MIN_ALPHA = 25.0
# Pre-existing phantom-collision cells in the CORE (rows 0-19), inherited from
# beautify_overworld.py's prop index lists. They predate this task and live in the
# byte-identical core, so fixing them needs a separate beautify-side change. Frozen
# here so a heath regression (count > this) fails, while the known core debt is
# tracked rather than silently ignored.
KNOWN_CORE_PHANTOM = 10


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class OverworldCollisionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        with open(TMX, encoding="utf-8") as handle:
            src = handle.read()
        cls.tilesets = sorted(
            (int(fg), name, src2)
            for fg, name, _c, src2 in re.findall(
                r'<tileset firstgid="(\d+)" name="([^"]+)"[^>]*tilecount="(\d+)"[^>]*>'
                r'\s*<image source="([^"]+)"', src, re.S))
        m = re.search(r'name="walls"[^>]*>\s*<data encoding="csv">\s*(.*?)\s*</data>', src, re.S)
        cls.walls = [[int(v) for v in r.rstrip(",").split(",")]
                     for r in m.group(1).strip().split("\n")]
        cls._alpha_cache = {}

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _tileset_of(self, gid):
        best = None
        for fg, name, src in self.tilesets:
            if gid >= fg:
                best = (fg, name, src)
            else:
                break
        return best

    def _alpha(self, gid):
        fg, name, src = self._tileset_of(gid)
        local = gid - fg
        key = (name, local)
        if key not in self._alpha_cache:
            surf = pygame.image.load(os.path.join(MAPS_DIR, src))
            cols = surf.get_width() // 32
            cx, cy = (local % cols) * 32, (local // cols) * 32
            opaque = sum(1 for y in range(cy, cy + 32) for x in range(cx, cx + 32)
                         if surf.get_at((x, y))[3] > 0)
            self._alpha_cache[key] = 100.0 * opaque / (32 * 32)
        return self._alpha_cache[key]

    def _walls_cells(self, y0, y1):
        for y in range(y0, min(y1, len(self.walls))):
            for x in range(len(self.walls[y])):
                gid = self.walls[y][x]
                if gid and self._tileset_of(gid)[1] != "placeholder":  # skip border
                    yield x, y, gid

    def test_heath_walls_have_no_invisible_collision(self):
        offenders = [(x, y, round(self._alpha(g)))
                     for x, y, g in self._walls_cells(HEATH_Y0, len(self.walls))
                     if self._alpha(g) < MIN_ALPHA]
        self.assertEqual(offenders, [], f"phantom collision in heath: {offenders}")

    def test_no_ground_tileset_gid_in_walls_anywhere(self):
        # Ground decor (grass/stone/cobble) must never sit in the collision layer.
        offenders = [(x, y, self._tileset_of(g)[1])
                     for x, y, g in self._walls_cells(0, len(self.walls))
                     if any(k in self._tileset_of(g)[1] for k in ("grass", "stone"))]
        self.assertEqual(offenders, [], f"ground tiles in walls: {offenders}")

    def test_whole_map_phantom_collision_is_only_known_core_debt(self):
        # Heath is clean (0); the only remaining sub-25% cells are the documented
        # pre-existing core ones. If the heath regresses, this exceeds the known
        # count and fails; if the core is later fixed, it drops below and reminds us.
        total = sum(1 for x, y, g in self._walls_cells(0, len(self.walls))
                    if self._alpha(g) < MIN_ALPHA)
        self.assertEqual(total, KNOWN_CORE_PHANTOM)


if __name__ == "__main__":
    unittest.main()
