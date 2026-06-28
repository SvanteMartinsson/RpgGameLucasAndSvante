"""B8 Slice 1: the start town (burg_5) renders as an anchored building cluster.

Pure-template tests (anchor-relative placement, disjoint footprints, plaza clear)
plus runtime tests (footprints become solid collision, the plaza tile stays
walkable and triggers the town menu, reachability holds, no water/neighbour
overlap). Runtime tests skip without pygame/pytmx.
"""

import os
import unittest
from collections import deque

from rpg_game.presentation import town_cluster

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp, CLUSTER_TOWN_ID

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


class TownClusterTemplateTest(unittest.TestCase):
    def test_uses_the_service_buildings_plus_flavor(self):
        ids = {bid for bid, *_ in town_cluster.CLUSTER_TEMPLATE}
        self.assertTrue({"church", "inn", "shop"} <= ids)   # respawn / Rest / Store
        self.assertGreaterEqual(len(ids), 4)

    def test_plaza_anchor_is_never_built_on(self):
        for anchor in [(0, 0), (26, 18), (40, 30)]:
            self.assertNotIn(anchor, town_cluster.cluster_footprints(anchor))

    def test_footprints_are_anchor_relative(self):
        base = town_cluster.cluster_footprints((0, 0))
        moved = town_cluster.cluster_footprints((100, 50))
        self.assertEqual(moved, {(x + 100, y + 50) for (x, y) in base})

    def test_buildings_do_not_overlap_each_other(self):
        seen, overlap = set(), set()
        for bid, dx, dy, fw, fh in town_cluster.CLUSTER_TEMPLATE:
            cells = town_cluster.building_footprint((0, 0), dx, dy, fw, fh)
            overlap |= seen & cells
            seen |= cells
        self.assertEqual(overlap, set())


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class TownClusterRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()
        self.anchor = self.app.cluster_anchor

    def test_footprints_are_solid_collision(self):
        fp = town_cluster.cluster_footprints(self.anchor)
        self.assertTrue(fp)
        self.assertTrue(fp <= self.app.world.blocked, "building footprints not blocked")

    def test_plaza_tile_is_walkable_and_triggers_the_town_menu(self):
        self.assertNotIn(self.anchor, self.app.world.blocked)     # plaza walkable
        self.app.world.set_tile(*self.anchor)
        self.assertNotIn(self.anchor, self.app.world.blocked)
        self.assertEqual(self.app.world.town_place_id(), CLUSTER_TOWN_ID)  # menu trigger

    def test_cluster_does_not_overlap_water_or_neighbour_towns(self):
        fp = town_cluster.cluster_footprints(self.anchor)
        walls = self.app.world.tmx.get_layer_by_name("walls")
        for (x, y) in fp:
            gid = walls.data[y][x]
            ts = self.app.world.tmx.get_tileset_from_gid(gid) if gid else None
            self.assertFalse(ts is not None and ts.name == "water_autotile", f"{(x, y)} on water")
        other_towns = {t for t in self.app.world.town_tiles if t != self.anchor}
        self.assertEqual(fp & other_towns, set())

    def test_all_towns_and_gates_still_reachable(self):
        blocked = self.app.world.blocked - set(self.app.world.gate_messages)
        W, H = self.app.world.tmx.width, self.app.world.tmx.height
        start = self.app.zone.start_tile
        seen, q = {start}, deque([start])
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in blocked and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        for tile in self.app.world.town_tiles:
            self.assertIn(tile, seen, f"town {tile} unreachable")
        for gate in self.app.zone.gates:
            self.assertIn(gate, seen, f"gate {gate} unreachable")

    def test_renders_without_crashing(self):
        self.app.display = pygame.Surface((960, 640))
        self.app.draw()


if __name__ == "__main__":
    unittest.main()
