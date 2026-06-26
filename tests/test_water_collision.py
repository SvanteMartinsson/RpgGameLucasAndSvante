"""B19: majority-water collision. A water autotile cell blocks only if >= 60% of
it is water, so shore/edge + outer-corner tiles (mostly land) are walkable and the
player can reach the water's edge; deep water (full / inner corner / channel) still
blocks. Tiles are still rendered — only the blocked set changes. Skips without pygame.
"""

import os
import unittest
from collections import deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import (
        Overworld, ZoneConfig, WATER_TILESET, WATER_BLOCK_THRESHOLD)

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class WaterCollisionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.zone = ZoneConfig.load()
        cls.world = Overworld(cls.zone.map_path, dict(cls.zone.gates), dict(cls.zone.towns))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _reach(self, blocked):
        start = self.zone.start_tile
        W, H = self.world.tmx.width, self.world.tmx.height
        seen, q = {start}, deque([start])
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in blocked and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        return seen

    def test_threshold_is_point_six(self):
        self.assertEqual(WATER_BLOCK_THRESHOLD, 0.6)

    def test_majority_water_blocks_shore_walkable(self):
        # Every water tile: blocked iff its water fraction >= threshold. (Gate cells
        # are blocked-but-walkable-up-to via gate_messages, so exclude them.)
        layer = self.world.tmx.get_layer_by_name("walls")
        gates = set(self.world.gate_messages)
        blocked = self.world.blocked
        shore = deep = 0
        for x, y, img in layer.tiles():
            if (x, y) in gates:
                continue
            gid = layer.data[y][x]
            ts = self.world.tmx.get_tileset_from_gid(gid) if gid else None
            if ts is None or ts.name != WATER_TILESET:
                continue
            f = self.world._water_fraction(img)
            if f < WATER_BLOCK_THRESHOLD:
                self.assertNotIn((x, y), blocked, f"shore {f:.2f} at {(x, y)} should be walkable")
                shore += 1
            else:
                self.assertIn((x, y), blocked, f"deep water {f:.2f} at {(x, y)} should block")
                deep += 1
        self.assertGreater(shore, 100, "no shore became walkable")
        self.assertGreater(deep, 100, "deep water no longer blocks")

    def test_towns_and_gates_still_reachable(self):
        blocked = self.world.blocked - set(self.world.gate_messages)
        seen = self._reach(blocked)
        for tile in self.zone.towns:
            self.assertIn(tile, seen, f"town {tile} unreachable")
        for gate in self.zone.gates:
            self.assertIn(gate, seen, f"gate {gate} unreachable")

    def test_bridges_are_still_required(self):
        # Walking the shore must NOT let you ford a river: removing the bridges
        # (blocking them) leaves some town unreachable -> deep water still separates.
        decor = self.world.tmx.get_layer_by_name("decor_over")
        bridges = set()
        for x, y, _img in decor.tiles():
            gid = decor.data[y][x]
            ts = self.world.tmx.get_tileset_from_gid(gid) if gid else None
            if ts is not None and ts.name == "water_bridge":
                bridges.add((x, y))
        self.assertTrue(bridges)
        seen = self._reach((self.world.blocked - set(self.world.gate_messages)) | bridges)
        unreachable = [t for t in self.zone.towns if t not in seen]
        self.assertTrue(unreachable, "rivers fordable without bridges — shore rule too loose")


if __name__ == "__main__":
    unittest.main()
