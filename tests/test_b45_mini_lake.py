"""B45: the mini lake — a landmark pond in the cainos meadow.

Locks: the pond's 2x2 CORE is real blocking water in the LOADED map (a
skinnier pond rendered but let you walk through — majority-water collision
keeps shore tiles walkable by design), the ring just outside the rendered
water is fully walkable (you can round the pond, no bridge through it), and
the map stays globally reachable from the start. The pond is an intentional
second water body (worldgen's one-water-body pass seeds from it). Skips
without pygame.
"""

import os
import unittest
from collections import deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp
    from rpg_game.tools.worldgen import overworld_layout as L

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False

CORE = {(43, 75), (44, 75), (43, 76), (44, 76)}   # "full" water: must block
POND_BBOX = (42, 45, 74, 77)                       # all 16 rendered water cells


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class MiniLakeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.app = OverworldApp()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_the_constant_matches_the_probed_spot(self):
        self.assertEqual(L.MINI_LAKE, (44, 76, 1.5, 1.5))

    def test_pond_core_is_blocking_water(self):
        for tile in CORE:
            self.assertIn(tile, self.app.world.blocked, tile)

    def test_walk_around_ring_is_fully_walkable(self):
        x0, x1, y0, y1 = POND_BBOX
        ring = set()
        for x in range(x0 - 1, x1 + 2):
            ring.add((x, y0 - 1))
            ring.add((x, y1 + 1))
        for y in range(y0 - 1, y1 + 2):
            ring.add((x0 - 1, y))
            ring.add((x1 + 1, y))
        for tile in sorted(ring):
            self.assertNotIn(tile, self.app.world.blocked, f"ring tile {tile} blocked")

    def test_map_still_reachable_from_start(self):
        world, zone = self.app.world, self.app.zone
        W, H = world.tmx.width, world.tmx.height
        blocked = world.blocked - set(world.gate_messages)
        seen, q = {zone.start_tile}, deque([zone.start_tile])
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in blocked and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        for tile in zone.towns:
            self.assertIn(tile, seen)
        self.assertIn((44, 74), seen)     # the pond's north shore is visitable
        self.assertIn((44, 77), seen)     # ...and the south shore


if __name__ == "__main__":
    unittest.main()
