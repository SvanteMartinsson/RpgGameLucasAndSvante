"""The overworld foundation after the 80x56 regeneration: open wilderness with
spread-out towns. Locks the approved coordinates, the graph-adjacency invariants
(every town + gate reachable from spawn, the two zone-crossing edges passable),
spawn/respawn, and the heath faction grouping. No rivers/mountains/houses yet.
Skips without pygame/pytmx.
"""

import os
import unittest
from collections import deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False

W, H, SEAM_Y = 80, 56, 36

# Approved scattered coordinates (place_id -> tile).
TOWNS = {
    "burg_5": (26, 18), "burg_117": (10, 8), "burg_160": (38, 22),
    "burg_235": (50, 16), "burg_379": (57, 7), "burg_146": (66, 12),
    "burg_67": (60, 26), "burg_200": (73, 6), "burg_320": (70, 31),
    "burg_219": (74, 17), "burg_121": (24, 47), "burg_54": (14, 42),
    "burg_385": (17, 51), "burg_149": (33, 44), "burg_293": (50, 43),
    "burg_105": (63, 47), "burg_53": (73, 51),
}
# heath faction grouping (must stay clustered)
BONDEMILIS = ("burg_54", "burg_121", "burg_385", "burg_149")
HARROW = ("burg_293", "burg_105", "burg_53")
# the two zone-crossing edges that must stay passable across the seam
ZONE_EDGES = (("burg_117", "burg_54"), ("burg_149", "burg_67"))


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class OverworldRegenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()
        self.world = self.app.world
        self.zone = self.app.zone

    def _reachable(self):
        start = self.zone.start_tile
        # Gate tiles are walls-layer holes (walkable) that the presentation blocks
        # with a message; reachability = can you walk UP TO them, so exclude gates.
        blocked = self.world.blocked - set(self.world.gate_messages)
        seen, q = {start}, deque([start])
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in blocked and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        return seen

    def test_map_is_80x56_with_three_layers(self):
        self.assertEqual((self.world.tmx.width, self.world.tmx.height), (W, H))
        names = {l.name for l in self.world.tmx.layers if hasattr(l, "data")}
        self.assertEqual(names, {"ground", "walls", "decor_over"})

    def test_all_17_towns_at_approved_coords(self):
        self.assertEqual(len(TOWNS), 17)
        for pid, tile in TOWNS.items():
            self.assertEqual(self.zone.towns.get(tile), pid, f"{pid} not at {tile}")
            self.assertNotIn(tile, self.world.blocked, f"{pid} walled in")

    def test_spawn_and_respawn_intact(self):
        self.assertEqual(self.zone.start_tile, (26, 18))
        self.assertEqual(self.zone.respawn_place_id, "burg_5")
        for pid in ("burg_5", "burg_320", "burg_121"):
            self.assertTrue(self.app.engine.content.places[pid].respawn, f"{pid} not a respawn")

    def test_every_town_and_gate_reachable_from_spawn(self):
        seen = self._reachable()
        for pid, tile in TOWNS.items():
            self.assertIn(tile, seen, f"{pid} unreachable")
        for gate in self.world.gate_messages:
            self.assertIn(gate, seen, f"gate {gate} unreachable")

    def test_zone_crossing_edges_passable_over_the_seam(self):
        # core<->heath is gated by the seam flood; the only crossings are the two
        # seam bridges (x=12-13 west, x=57-58 east). Those bridge cells are walkable
        # and a core cell above each connects to a heath cell below it.
        blocked = self.world.blocked
        for bx in (12, 13, 57, 58):
            for by in (35, 36):
                self.assertNotIn((bx, by), blocked, f"seam bridge cell {(bx, by)} blocked")
        seen = self._reachable()
        for a, b in ZONE_EDGES:   # both endpoints reachable through the bridges
            self.assertIn(TOWNS[a], seen)
            self.assertIn(TOWNS[b], seen)

    def test_heath_faction_grouping_preserved(self):
        for pid in BONDEMILIS + HARROW:
            self.assertGreaterEqual(TOWNS[pid][1], SEAM_Y, f"{pid} not in heath")
        # Bondemilis sits west of Harrow (clusters stay separated, not interleaved)
        bond_x = max(TOWNS[p][0] for p in BONDEMILIS)
        harrow_x = min(TOWNS[p][0] for p in HARROW)
        self.assertLess(bond_x, harrow_x)

    def test_open_wilderness_is_the_default(self):
        # land stays mostly open; rivers + lake + the cliff/forest edge terrain are
        # intended obstacles (~30%), so the floor is lower than the bare foundation.
        walkable = sum(1 for y in range(H) for x in range(W)
                       if (x, y) not in self.world.blocked)
        self.assertGreater(walkable / (W * H), 0.65)

    # -- ground texture + broken path hints (under player, no collision) ----

    def _layer(self, name):
        # Parse the RAW TMX CSV (pytmx remaps gids internally, which would break
        # firstgid math); raw gids are firstgid + tile-index.
        import os
        import re
        from rpg_game.presentation.pygame_overworld import MAPS_DIR
        src = open(os.path.join(MAPS_DIR, "overworld.tmx"), encoding="utf-8").read()
        m = re.search(r'name="%s"[^>]*>\s*<data encoding="csv">\s*(.*?)\s*</data>' % name, src, re.S)
        return [[int(v) for v in r.rstrip(",").split(",")] for r in m.group(1).strip().split("\n")]

    def _is_path(self, gid):
        # cobble path tiles are idx 32-63 of the grass tilesets (firstgid 3/387).
        return any(fg <= gid < fg + 64 and (gid - fg) >= 32 for fg in (3, 387))

    # grass-sheet indices that carry a VISIBLE mark at zoom (stones + flowers);
    # the micro-tuft "variant" tiles are pixel-identical to base and don't count.
    VISIBLE_MARK = {6, 7, 12, 13, 21, 22, 28, 30, 31, 14, 20, 23, 29}

    def _mark_idx(self, gid):
        for fg in (3, 387):
            if fg <= gid < fg + 32:   # grass region (not cobble)
                return gid - fg
        return None

    def test_ground_has_lively_visible_detail(self):
        # Judged on visible marks, not gid count: enough scattered stone/flower
        # detail to read as living wilderness, but sparse enough to stay open
        # (not a meadow). The before/after zoom render is the real proof.
        ground = self._layer("ground")
        vis = sum(1 for y in range(H) for x in range(W)
                  if self._mark_idx(ground[y][x]) in self.VISIBLE_MARK)
        frac = vis / (W * H)
        self.assertGreater(frac, 0.12, f"too sparse to read as lively: {frac:.2f}")
        self.assertLess(frac, 0.30, f"too busy (meadow, not open wilderness): {frac:.2f}")

    def test_path_hints_exist_and_are_broken(self):
        ground = self._layer("ground")
        towns = {tuple(t): p for t, p in self.zone.towns.items()}
        town_pos = {p: t for t, p in self.zone.towns.items()}
        # path remnants are present at all
        n_path = sum(1 for y in range(H) for x in range(W) if self._is_path(ground[y][x]))
        self.assertGreater(n_path, 30, "no path hints painted")
        # every on-map connection edge has a GAP (no unbroken cobble line)
        for a, b in ZONE_EDGES + (("burg_5", "burg_117"), ("burg_5", "burg_160"),
                                  ("burg_105", "burg_53"), ("burg_121", "burg_385")):
            (ax, ay), (bx, by) = town_pos[a], town_pos[b]
            steps = max(abs(ax - bx), abs(ay - by)) or 1
            interior = []
            for i in range(steps + 1):
                x = round(ax + (bx - ax) * i / steps)
                y = round(ay + (by - ay) * i / steps)
                if (x, y) not in town_pos.values():
                    interior.append((x, y))
            self.assertTrue(any(not self._is_path(ground[y][x]) for x, y in interior),
                            f"edge {a}<->{b} has an unbroken path line")

    def _is_water(self, gid):
        return 4739 <= gid <= 4754   # water_autotile gids (firstgid 4739, 16 tiles)

    def test_v3_water_invariants(self):
        walls = self._layer("walls")
        decor = self._layer("decor_over")
        water = {(x, y) for y in range(H) for x in range(W) if self._is_water(walls[y][x])}
        bridges = {(x, y) for y in range(H) for x in range(W) if 4755 <= decor[y][x] <= 4778}
        self.assertGreater(len(water), 200, "no water placed")
        # gates are not drowned
        for g in self.world.gate_messages:
            self.assertNotIn(g, water, f"gate drowned: {g}")
        # all water connects to the lake (no dead river ends). Bridges carve gaps in
        # the walls water, so treat bridge cells as river connectors for the flood.
        river = water | bridges
        lake = {(x, y) for (x, y) in water
                if ((x - 72) / 12) ** 2 + ((y - 55) / 7) ** 2 <= 1.0}
        self.assertTrue(lake, "no lake cells")
        seen, dq = set(lake), deque(lake)
        while dq:
            x, y = dq.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) in river and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    dq.append((nx, ny))
        self.assertEqual(water - seen, set(), "water not all connected to the lake")
        # the five bridge crossings are walkable (not blocked)
        for bx, by in [(12, 35), (57, 35), (26, 27), (44, 43), (77, 28)]:
            self.assertNotIn((bx, by), self.world.blocked, f"bridge {(bx, by)} blocked")

    def _plant_offset(self, gid):
        for fg in (2691, 4227):       # cainos_plant / grave_heath_plant
            if fg <= gid < fg + 256:
                return fg, gid - fg
        return None, None

    def test_gradual_coherent_zone_transition(self):
        ground = self._layer("ground")

        def gtheme(gid):
            if 3 <= gid < 67:
                return "cainos"
            if 387 <= gid < 451:
                return "grave_heath"
            return None

        def heath_share(y):
            row = [t for t in (gtheme(ground[y][x]) for x in range(W)) if t]
            return row.count("grave_heath") / len(row) if row else 0.0

        # pure core north of the band, pure heath south of it
        self.assertEqual(heath_share(24), 0.0)
        self.assertEqual(heath_share(50), 1.0)
        # GRADUAL, no hard line: adjacent band rows change smoothly (no abrupt
        # jump from mostly-core to mostly-heath in one row)
        for y in range(28, 44):
            self.assertLess(abs(heath_share(y + 1) - heath_share(y)), 0.5,
                            f"hard jump at row {y}")
        # monotone trend north -> south, and the seam itself is clearly blended
        north = sum(heath_share(y) for y in range(29, 34)) / 5
        south = sum(heath_share(y) for y in range(39, 44)) / 5
        self.assertGreater(south, north + 0.2)
        self.assertTrue(0.2 < heath_share(36) < 0.8, "seam not blended")
        # COHERENT, not checkerboard: same-theme cells form runs > 2 on average
        runs, cur, ln = [], None, 0
        for y in range(30, 43):
            for x in range(W):
                t = gtheme(ground[y][x])
                if t is None:
                    if ln:
                        runs.append(ln)
                    cur, ln = None, 0
                elif t == cur:
                    ln += 1
                else:
                    if ln:
                        runs.append(ln)
                    cur, ln = t, 1
            if ln:
                runs.append(ln)
                cur, ln = None, 0
        self.assertGreater(sum(runs) / len(runs), 2.0, "transition is checkerboard, not clustered")

    GATES = ((26, 0), (79, 28), (24, 55))

    def _is_sea_or_river(self, gid):           # water_autotile gids 4739..4754
        return 4739 <= gid < 4755

    def _is_bridge(self, gid):                  # water_bridge gids 4755..4778
        return 4755 <= gid < 4779

    def test_no_forest_canopy_anywhere(self):
        # The forest edge-band + inner groves are gone: NO plant-sheet canopy/crown
        # tile survives in walls or decor anywhere on the map.
        walls, decor = self._layer("walls"), self._layer("decor_over")
        plant = [(x, y) for y in range(H) for x in range(W)
                 if self._plant_offset(walls[y][x])[1] is not None
                 or self._plant_offset(decor[y][x])[1] is not None]
        self.assertEqual(plant, [], f"forest canopy still present at {plant[:5]}")

    def test_sea_frames_and_seals_the_border(self):
        # The whole map perimeter is water (the sea) except the dry gate mouths:
        # no open non-gate edge cell remains.
        walls = self._layer("walls")

        def near_gate(x, y):
            return any(abs(x - gx) <= 6 and abs(y - gy) <= 6 for gx, gy in self.GATES)

        perim = ([(x, 0) for x in range(W)] + [(x, H - 1) for x in range(W)]
                 + [(0, y) for y in range(H)] + [(W - 1, y) for y in range(H)])
        open_cells = [(x, y) for (x, y) in perim
                      if not self._is_sea_or_river(walls[y][x]) and not near_gate(x, y)]
        self.assertEqual(open_cells, [], f"unsealed non-gate border cells: {open_cells[:5]}")
        # the sea is substantial (it frames the map, not a thin ring)
        sea = sum(1 for y in range(H) for x in range(W) if self._is_sea_or_river(walls[y][x]))
        self.assertGreater(sea, 900, "sea too small to frame the map")

    def test_all_water_is_one_connected_body(self):
        # sea + rivers + lake + (bridge-covered) cells flood-connect to the lake.
        walls, decor = self._layer("walls"), self._layer("decor_over")
        body = {(x, y) for y in range(H) for x in range(W)
                if self._is_sea_or_river(walls[y][x]) or self._is_bridge(decor[y][x])}
        lake = {(x, y) for (x, y) in body
                if ((x - 72) / 12) ** 2 + ((y - 55) / 7) ** 2 <= 1.0}
        seen, q = set(lake), deque(lake)
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) in body and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        self.assertEqual(body - seen, set(), "water not all one body connected to the lake")

    def test_no_town_or_gate_sits_in_water(self):
        walls = self._layer("walls")
        for (x, y) in list(TOWNS.values()) + list(self.GATES):
            self.assertFalse(self._is_sea_or_river(walls[y][x]), f"{(x, y)} drowned")

    def test_paths_and_detail_never_collide(self):
        # path + detail live in the ground layer only; the walls layer must hold
        # no grass-sheet (path/detail) gid -> walking over a path is never blocked.
        walls = self._layer("walls")
        offenders = [(x, y) for y in range(H) for x in range(W)
                     if walls[y][x] and self._is_path(walls[y][x])]
        self.assertEqual(offenders, [], f"path tiles in walls (collide): {offenders}")


if __name__ == "__main__":
    unittest.main()
