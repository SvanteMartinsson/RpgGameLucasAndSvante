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
    from rpg_game.presentation.pygame_overworld import OverworldApp, CLUSTER_TOWN_ID, CLUSTER_TOWN_IDS
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
        for bid, dx, dy, fw, fh, _facing, _flip in town_cluster.CLUSTER_TEMPLATE:
            cells = town_cluster.building_footprint((0, 0), dx, dy, fw, fh)
            overlap |= seen & cells
            seen |= cells
        self.assertEqual(overlap, set())

    def test_east_column_sprites_are_flipped_west(self):
        # The q1 (east) column mirrors its sprite so the door/sign reads west, in
        # toward the courtyard; the north fronts are not flipped.
        for _bid, _dx, _dy, _fw, _fh, facing, flip in town_cluster.CLUSTER_TEMPLATE:
            self.assertEqual(flip, facing == "q1")

    def test_each_facing_points_its_entrance_inward(self):
        anchor = (26, 18)
        foot = town_cluster.cluster_footprints(anchor)
        for bid, dx, dy, fw, fh, facing, _flip in town_cluster.CLUSTER_TEMPLATE:
            ent = town_cluster.entrance_tile(anchor, dx, dy, fw, fh, facing)
            cx, cy = anchor[0] + dx + (fw - 1) / 2, anchor[1] + dy + (fh - 1) / 2
            self.assertLess(math.dist(ent, anchor), math.dist((cx, cy), anchor),
                            f"{bid} ({facing}) entrance not inward")
            self.assertNotIn(ent, foot, f"{bid} entrance is inside a footprint")

    def test_cobble_reaches_every_entrance_avoids_footprints(self):
        anchor = (26, 18)
        net = town_cluster.cobble_network(anchor)
        self.assertEqual(net & town_cluster.cluster_footprints(anchor), set())
        self.assertIn(anchor, net)
        for bid, ent in town_cluster.cluster_entrances(anchor).items():
            self.assertIn(ent, net, f"cobble does not reach {bid}'s entrance")

    def test_each_entrance_is_a_spur_tip_one_cobble_neighbour(self):
        # Comb shape: a door is the tip of its own spur — exactly one adjacent cobble
        # tile — so the net reads as roads to each door, not a paved slab.
        anchor = (26, 18)
        net = town_cluster.cobble_network(anchor)
        for bid, (ex, ey) in town_cluster.cluster_entrances(anchor).items():
            neighbours = sum(((ex + dx, ey + dy) in net) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            self.assertEqual(neighbours, 1, f"{bid}'s entrance has {neighbours} cobble neighbours")


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
        # B8 Slice 2a: sprites are keyed by (building, facing) across all tiers.
        pairs = {(b[0], b[5]) for tmpl in self.app.cluster_templates.values() for b in tmpl}
        for bid, facing in pairs:
            self.assertIsNotNone(self.app._building_sprites.get((bid, facing)),
                                 f"{bid}/{facing} sprite missing")

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

    def _sprite_bbox_tiles(self, bid, facing, fx, fy, fw, fh):
        """The tile rectangle a building's scaled sprite covers, matching how
        _draw_town blits it (bottom-aligned, centred on the footprint)."""
        sprite = self.app._building_sprites[(bid, facing)]
        sw, sh = sprite.get_size()
        tw, th = self.app.world.tw, self.app.world.th
        cx = fx * tw + (fw * tw) // 2
        by = (fy + fh) * th
        left = (cx - sw // 2) // tw
        right = (cx - sw // 2 + sw - 1) // tw
        top = (by - sh) // th
        return left, right, top, fy + fh - 1

    def test_no_entrance_sits_under_another_buildings_sprite(self):
        # The core layout rule: a building's scaled sprite may overlap another's
        # ROOF (packed town), but never another building's entrance tile.
        tmpl = self.app.cluster_templates[CLUSTER_TOWN_ID]
        builds = town_cluster.cluster_buildings(self.anchor, tmpl)
        ents = town_cluster.cluster_entrances(self.anchor, tmpl)
        bboxes = {b[0]: self._sprite_bbox_tiles(b[0], b[5], b[1], b[2], b[3], b[4]) for b in builds}
        for bid, (ex, ey) in ents.items():
            for other, (l, r, t, bm) in bboxes.items():
                if other == bid:
                    continue
                self.assertFalse(l <= ex <= r and t <= ey <= bm,
                                 f"{bid}'s entrance {(ex, ey)} is under {other}'s sprite")

    def test_footprints_never_on_water(self):
        self.assertEqual(town_cluster.cluster_footprints(self.anchor) & self.app._water_tiles(), set())

    def test_no_cobble_tile_borders_water(self):
        # "No town in the water": no cobble cell sits on, or even next to, water — so
        # nothing points SW into the river.
        water = self.app._water_tiles()
        for (x, y) in self.app._cobble_net:
            self.assertNotIn((x, y), water)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                self.assertNotIn((x + dx, y + dy), water, f"cobble {(x, y)} borders water")

    def test_renders_without_crashing(self):
        self.app.display = pygame.Surface((960, 640))
        self.app.draw()


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class MultiHubPlacementTest(unittest.TestCase):
    """B28: the hub model is reused on more cities. Every town in CLUSTER_TOWN_IDS
    must pass the SAME placement properties the start town does — so a new hub can
    only be added (to the tuple) once it satisfies all of them. Each property is
    checked for every hub, not just burg_5."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.app = OverworldApp()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _anchors(self):
        return self.app.cluster_anchors

    def test_there_is_more_than_one_hub(self):
        # B28 is about MORE cities: the start town plus at least one more.
        self.assertGreaterEqual(len(self._anchors()), 2)
        self.assertIn(CLUSTER_TOWN_ID, self._anchors())

    def test_every_cluster_town_has_exactly_one_rest_door(self):
        # B8 Slice 2a: every town (all tiers) has exactly one bed — inn, or cottage
        # in a village. (Villages may be store-less; only the rest door is universal.)
        from rpg_game.presentation.pygame_overworld import BUILDING_FUNCTION
        for pid in self._anchors():
            tmpl = self.app.cluster_templates[pid]
            rests = [b[0] for b in tmpl if BUILDING_FUNCTION.get(b[0]) == "rest"]
            self.assertEqual(len(rests), 1, f"{pid} rest doors: {rests}")

    def test_every_hub_footprint_is_solid_and_clear_of_water(self):
        water = self.app._water_tiles()
        for pid, anchor in self._anchors().items():
            fp = town_cluster.cluster_footprints(anchor, self.app.cluster_templates[pid])
            self.assertTrue(fp <= self.app.world.blocked, f"{pid} footprints not solid")
            self.assertEqual(fp & water, set(), f"{pid} footprint on water")

    def test_every_hub_plaza_is_the_walkable_menu_trigger(self):
        for pid, anchor in self._anchors().items():
            self.assertNotIn(anchor, self.app.world.blocked, f"{pid} plaza blocked")
            self.app.world.set_tile(*anchor)
            self.assertEqual(self.app.world.town_place_id(), pid, f"{pid} plaza wrong trigger")

    def test_every_hub_cobble_reaches_every_door_and_shuns_water(self):
        water = self.app._water_tiles()
        for pid, anchor in self._anchors().items():
            tmpl = self.app.cluster_templates[pid]
            net = town_cluster.cobble_network(anchor, self.app.world.blocked, water, tmpl)
            self.assertEqual(net & town_cluster.cluster_footprints(anchor, tmpl), set(),
                             f"{pid} cobble under a footprint")
            for bid, ent in town_cluster.cluster_entrances(anchor, tmpl).items():
                self.assertIn(ent, net, f"{pid}: cobble does not reach {bid}")
            for (x, y) in net:
                self.assertNotIn((x, y), water, f"{pid} cobble on water {(x, y)}")
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    self.assertNotIn((x + dx, y + dy), water, f"{pid} cobble borders water")

    def test_hubs_do_not_overlap_each_other_or_any_town_tile(self):
        anchors = self._anchors()
        foots = {pid: town_cluster.cluster_footprints(a, self.app.cluster_templates[pid])
                 for pid, a in anchors.items()}
        ids = list(foots)
        for i, a in enumerate(ids):           # pairwise hub footprints disjoint
            for b in ids[i + 1:]:
                self.assertEqual(foots[a] & foots[b], set(), f"{a} overlaps {b}")
        # no hub footprint covers ANY town's tile (including non-hub neighbours)
        town_tiles = set(self.app.world.town_tiles)
        for pid, anchor in anchors.items():
            covered = foots[pid] & (town_tiles - {anchor})
            self.assertEqual(covered, set(), f"{pid} footprint covers town tile(s) {covered}")

    def test_all_towns_and_gates_reachable_with_every_hub_built(self):
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

    def test_hub_generation_is_idempotent(self):
        # Regenerating a hub's footprints and cobble yields byte-identical sets —
        # placement is pure (no RNG / order dependence), so a re-render is stable.
        water = self.app._water_tiles()
        for pid, anchor in self._anchors().items():
            tmpl = self.app.cluster_templates[pid]
            self.assertEqual(town_cluster.cluster_footprints(anchor, tmpl),
                             town_cluster.cluster_footprints(anchor, tmpl), f"{pid} footprints not idempotent")
            self.assertEqual(town_cluster.cobble_network(anchor, self.app.world.blocked, water, tmpl),
                             town_cluster.cobble_network(anchor, self.app.world.blocked, water, tmpl),
                             f"{pid} cobble not idempotent")


if __name__ == "__main__":
    unittest.main()
