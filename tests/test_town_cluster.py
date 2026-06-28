"""B8 Slice 1 (refined): the start town (burg_5) renders as an anchored building
HUB — facings pointing inward, an autotiled cobble wayfinding net on the routes,
solid footprints, plaza menu-trigger.

Pure-template tests (anchor-relative placement, disjoint footprints, plaza clear,
entrances inward, cobble routes) plus runtime tests (footprints solid, plaza
walkable+triggers, no water/neighbour overlap, reachability). Runtime tests skip
without pygame/pytmx.
"""

import math
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
    def test_hub_has_the_service_suite_and_is_6_to_8_buildings(self):
        ids = [bid for bid, *_ in town_cluster.CLUSTER_TEMPLATE]
        self.assertTrue({"church", "inn", "shop", "blacksmith", "barracks", "town_hall"} <= set(ids))
        self.assertTrue(6 <= len(ids) <= 8)

    def test_plaza_anchor_is_never_built_on(self):
        for anchor in [(0, 0), (26, 18), (40, 30)]:
            self.assertNotIn(anchor, town_cluster.cluster_footprints(anchor))

    def test_footprints_and_cobble_are_anchor_relative(self):
        base_fp = town_cluster.cluster_footprints((0, 0))
        base_net = town_cluster.cobble_network((0, 0))
        self.assertEqual(town_cluster.cluster_footprints((100, 50)),
                         {(x + 100, y + 50) for (x, y) in base_fp})
        self.assertEqual(town_cluster.cobble_network((100, 50)),
                         {(x + 100, y + 50) for (x, y) in base_net})

    def test_buildings_do_not_overlap_each_other(self):
        seen, overlap = set(), set()
        for bid, dx, dy, fw, fh, _facing in town_cluster.CLUSTER_TEMPLATE:
            cells = town_cluster.building_footprint((0, 0), dx, dy, fw, fh)
            overlap |= seen & cells
            seen |= cells
        self.assertEqual(overlap, set())

    def test_each_facing_points_its_entrance_inward(self):
        # The chosen facing must put the door on the plaza side: the entrance tile is
        # closer to the anchor than the building's centre, and is walkable (not a
        # footprint). Covers the front/q1/q2 per-position rule.
        anchor = (26, 18)
        foot = town_cluster.cluster_footprints(anchor)
        for bid, dx, dy, fw, fh, facing in town_cluster.CLUSTER_TEMPLATE:
            ent = town_cluster.entrance_tile(anchor, dx, dy, fw, fh, facing)
            cx, cy = anchor[0] + dx + (fw - 1) / 2, anchor[1] + dy + (fh - 1) / 2
            d_ent = math.dist(ent, anchor)
            d_centre = math.dist((cx, cy), anchor)
            self.assertLess(d_ent, d_centre, f"{bid} ({facing}) entrance not inward")
            self.assertNotIn(ent, foot, f"{bid} entrance is inside a footprint")

    def test_cobble_routes_reach_every_entrance_and_avoid_footprints(self):
        anchor = (26, 18)
        net = town_cluster.cobble_network(anchor)
        foot = town_cluster.cluster_footprints(anchor)
        self.assertEqual(net & foot, set(), "cobble runs under a building")
        self.assertIn(anchor, net)
        for bid, dx, dy, fw, fh, facing in town_cluster.CLUSTER_TEMPLATE:
            ent = town_cluster.entrance_tile(anchor, dx, dy, fw, fh, facing)
            self.assertIn(ent, net, f"cobble does not reach {bid}'s entrance")


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
        self.assertTrue(fp <= self.app.world.blocked)

    def test_plaza_tile_walkable_and_triggers_town_menu(self):
        self.assertNotIn(self.anchor, self.app.world.blocked)
        self.app.world.set_tile(*self.anchor)
        self.assertEqual(self.app.world.town_place_id(), CLUSTER_TOWN_ID)

    def test_cobble_net_is_not_under_footprints_and_not_on_water(self):
        net = self.app._cobble_net
        fp = town_cluster.cluster_footprints(self.anchor)
        self.assertEqual(net & fp, set())
        walls = self.app.world.tmx.get_layer_by_name("walls")
        for (x, y) in net:
            gid = walls.data[y][x]
            ts = self.app.world.tmx.get_tileset_from_gid(gid) if gid else None
            self.assertFalse(ts is not None and ts.name == "water_autotile", f"cobble on water {(x, y)}")

    def test_buildings_loaded_for_every_template_entry(self):
        for bid, *_ in town_cluster.CLUSTER_TEMPLATE:
            self.assertIsNotNone(self.app._building_sprites.get(bid), f"{bid} sprite missing")

    def test_no_overlap_with_water_or_neighbour_towns(self):
        fp = town_cluster.cluster_footprints(self.anchor)
        other = {t for t in self.app.world.town_tiles if t != self.anchor}
        self.assertEqual(fp & other, set())

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
            self.assertIn(tile, seen)
        for gate in self.app.zone.gates:
            self.assertIn(gate, seen)

    def test_renders_without_crashing(self):
        self.app.display = pygame.Surface((960, 640))
        self.app.draw()


if __name__ == "__main__":
    unittest.main()
