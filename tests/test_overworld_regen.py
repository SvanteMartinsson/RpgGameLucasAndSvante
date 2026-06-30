"""The overworld foundation after the #3 expansion (240x208, option A: parametric
terrain). Locks the approved coordinates, reachability (every town + gate reachable
from spawn), spawn/respawn, the four route-derived seam crossings, the derived
water body (sea frame + seam channel + the one north-born river -> central lake),
ground zone bands, path hints and "no canopy". Skips without pygame/pytmx.
"""

import os
import re
import unittest
from collections import deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp, MAPS_DIR

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False

W, H, SEAM_Y = 240, 208, 100

# Approved expanded coordinates (place_id -> tile).
TOWNS = {
    "burg_5": (51, 52), "burg_117": (24, 24), "burg_160": (72, 88),
    "burg_235": (106, 44), "burg_379": (126, 18), "burg_146": (152, 36),
    "burg_67": (136, 84), "burg_200": (198, 22), "burg_320": (186, 92),
    "burg_219": (218, 60), "burg_121": (72, 180), "burg_54": (38, 132),
    "burg_385": (27, 192), "burg_149": (99, 140), "burg_293": (162, 118),
    "burg_105": (181, 164), "burg_53": (216, 194),
}
GATES = ((51, 0), (239, 60), (51, 207))
LAKE = (135, 164, 11, 6)
# heath faction grouping (must stay clustered, all south of the seam)
BONDEMILIS = ("burg_54", "burg_121", "burg_385", "burg_149")
HARROW = ("burg_293", "burg_105", "burg_53")
# the four N<->S routes that must stay passable across the seam (incl. the two
# eastern crossings added so the SE is not a long westerly detour)
ZONE_EDGES = (("burg_117", "burg_54"), ("burg_149", "burg_67"),
              ("burg_320", "burg_105"), ("burg_219", "burg_53"))


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
        blocked = self.world.blocked - set(self.world.gate_messages)
        seen, q = {start}, deque([start])
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in blocked and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        return seen

    def _layer(self, name):
        src = open(os.path.join(MAPS_DIR, "overworld.tmx"), encoding="utf-8").read()
        m = re.search(r'name="%s"[^>]*>\s*<data encoding="csv">\s*(.*?)\s*</data>' % name, src, re.S)
        return [[int(v) for v in r.rstrip(",").split(",")] for r in m.group(1).strip().split("\n")]

    # -- dims / coords / spawn ----------------------------------------------

    def test_map_is_240x208_with_three_layers(self):
        self.assertEqual((self.world.tmx.width, self.world.tmx.height), (W, H))
        names = {l.name for l in self.world.tmx.layers if hasattr(l, "data")}
        self.assertEqual(names, {"ground", "walls", "decor_over"})

    def test_all_17_towns_at_approved_coords(self):
        self.assertEqual(len(TOWNS), 17)
        for pid, tile in TOWNS.items():
            self.assertEqual(self.zone.towns.get(tile), pid, f"{pid} not at {tile}")
            self.assertNotIn(tile, self.world.blocked, f"{pid} walled in")

    def test_spawn_and_respawn_intact(self):
        self.assertEqual(self.zone.start_tile, (51, 52))
        self.assertEqual(self.zone.respawn_place_id, "burg_5")
        for pid in ("burg_5", "burg_320", "burg_121"):
            self.assertTrue(self.app.engine.content.places[pid].respawn, f"{pid} not a respawn")

    def test_every_town_and_gate_reachable_from_spawn(self):
        seen = self._reachable()
        for pid, tile in TOWNS.items():
            self.assertIn(tile, seen, f"{pid} unreachable")
        for gate in self.world.gate_messages:
            self.assertIn(gate, seen, f"gate {gate} unreachable")

    def test_four_seam_crossings_are_passable(self):
        # each N<->S route's endpoints are reachable -> the seam channel is bridged
        # at four spread-out crossings, not one chokepoint.
        seen = self._reachable()
        for a, b in ZONE_EDGES:
            self.assertIn(TOWNS[a], seen, a)
            self.assertIn(TOWNS[b], seen, b)

    def test_heath_faction_grouping_preserved(self):
        for pid in BONDEMILIS + HARROW:
            self.assertGreaterEqual(TOWNS[pid][1], SEAM_Y, f"{pid} not in heath")
        bond_x = max(TOWNS[p][0] for p in BONDEMILIS)
        harrow_x = min(TOWNS[p][0] for p in HARROW)
        self.assertLess(bond_x, harrow_x)

    def test_open_wilderness_is_the_default(self):
        walkable = sum(1 for y in range(H) for x in range(W)
                       if (x, y) not in self.world.blocked)
        self.assertGreater(walkable / (W * H), 0.65)

    # -- water (derived) -----------------------------------------------------

    def _is_water(self, gid):
        return 4739 <= gid < 4755            # water_autotile

    def _is_bridge(self, gid):
        return 4755 <= gid < 4779 or 4871 <= gid < 4875   # water_bridge / half-deck

    GATESET = set(GATES)

    def test_sea_frames_and_seals_the_border(self):
        walls = self._layer("walls")

        def near_gate(x, y):
            return any(abs(x - gx) <= 7 and abs(y - gy) <= 7 for gx, gy in GATES)

        perim = ([(x, 0) for x in range(W)] + [(x, H - 1) for x in range(W)]
                 + [(0, y) for y in range(H)] + [(W - 1, y) for y in range(H)])
        open_cells = [(x, y) for (x, y) in perim
                      if not self._is_water(walls[y][x]) and not near_gate(x, y)]
        self.assertEqual(open_cells, [], f"unsealed non-gate border cells: {open_cells[:5]}")

    def test_no_isolated_interior_water_puddles(self):
        # Every water cell flood-connects to the lake OR the sealed border sea (gate
        # dry mouths legitimately split the coastal ring into arcs). No free-floating
        # interior puddle survives.
        walls, decor = self._layer("walls"), self._layer("decor_over")
        body = {(x, y) for y in range(H) for x in range(W)
                if self._is_water(walls[y][x]) or self._is_bridge(decor[y][x])}
        cx, cy, rx, ry = LAKE
        seed = {(x, y) for (x, y) in body if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0}
        seed |= {(x, y) for (x, y) in body if x in (0, W - 1) or y in (0, H - 1)}
        self.assertTrue(seed, "no lake/border water found")
        seen, q = set(seed), deque(seed)
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) in body and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        self.assertEqual(body - seen, set(), "isolated interior water puddle(s) present")

    def test_no_town_or_gate_sits_in_water(self):
        walls = self._layer("walls")
        for (x, y) in list(TOWNS.values()) + list(GATES):
            self.assertFalse(self._is_water(walls[y][x]), f"{(x, y)} drowned")

    def test_bridges_are_walkable_water_decks(self):
        decor = self._layer("decor_over")
        bridges = [(x, y) for y in range(H) for x in range(W) if self._is_bridge(decor[y][x])]
        self.assertGreater(len(bridges), 0, "no bridge decks placed")
        for (x, y) in bridges:
            self.assertNotIn((x, y), self.world.blocked, f"bridge {(x, y)} blocked")

    # -- ground (zone bands + detail + paths) --------------------------------

    def _grass_idx(self, gid):
        for fg in (3, 1923, 771, 387):     # cainos / mork_skog / cursed_mire / grave_heath grass
            if fg <= gid < fg + 64:
                return fg, gid - fg
        return None, None

    def test_ground_uses_the_four_zone_bands(self):
        ground = self._layer("ground")
        # sample a clearly-land cell per zone (away from coast/seam/river)
        samples = {(51, 52): 3, (120, 50): 1923, (200, 50): 771, (99, 150): 387}
        for (x, y), fg in samples.items():
            base, _ = self._grass_idx(ground[y][x])
            self.assertEqual(base, fg, f"zone band wrong at {(x, y)}")

    def test_ground_detail_is_clustered_not_uniform(self):
        # Pocket model: visible ground detail concentrates in feature pockets
        # (blomäng/sten) with open ground between — so the densest blocks stand far
        # above the map average (landmarks), unlike the old uniform speckle.
        ground = self._layer("ground")
        VIS = {6, 7, 12, 13, 21, 22, 28, 30, 31, 14, 20, 23, 29}
        total = sum(1 for y in range(H) for x in range(W) if self._grass_idx(ground[y][x])[1] in VIS)
        overall = total / (W * H)
        self.assertGreater(total, 200, "no ground detail at all")
        # densest 16x16 block fraction
        B = 16
        best = 0.0
        for by in range(0, H - B, B):
            for bx in range(0, W - B, B):
                d = sum(1 for y in range(by, by + B) for x in range(bx, bx + B)
                        if self._grass_idx(ground[y][x])[1] in VIS)
                best = max(best, d / (B * B))
        self.assertGreater(best, 0.30, f"no dense detail pocket (best block {best:.2f})")
        self.assertGreater(best, overall * 3, f"detail not clustered (best {best:.2f} vs avg {overall:.2f})")

    def _is_path(self, gid):
        fg, idx = self._grass_idx(gid)
        return idx is not None and idx >= 32

    def test_path_hints_exist(self):
        ground = self._layer("ground")
        n_path = sum(1 for y in range(H) for x in range(W) if self._is_path(ground[y][x]))
        self.assertGreater(n_path, 30, "no path hints painted")

    def test_paths_and_detail_never_collide(self):
        walls = self._layer("walls")
        offenders = [(x, y) for y in range(H) for x in range(W)
                     if walls[y][x] and self._is_path(walls[y][x])]
        self.assertEqual(offenders, [], f"path tiles in walls (collide): {offenders}")

    def _plant_offset(self, gid):
        for fg in (2691, 3203, 3715, 4227):   # *_plant sheets
            if fg <= gid < fg + 256:
                return gid - fg
        return None

    # Single-tile shrubs that may live in decor (walkable); multi-tile tree canopy
    # stays forbidden everywhere, and NO plant tile may sit in walls (collision).
    BUSHES = {97, 98, 99, 101, 103, 105, 107}

    def test_no_tree_canopy_only_single_tile_bushes(self):
        walls, decor = self._layer("walls"), self._layer("decor_over")
        # no plant-sheet tile in the collision layer at all
        wall_plant = [(x, y) for y in range(H) for x in range(W)
                      if self._plant_offset(walls[y][x]) is not None]
        self.assertEqual(wall_plant, [], f"plant tile in walls (collision) at {wall_plant[:5]}")
        # decor plant tiles are ONLY the allowed single-tile bushes (no tree canopy)
        bad = [(x, y) for y in range(H) for x in range(W)
               if (off := self._plant_offset(decor[y][x])) is not None and off not in self.BUSHES]
        self.assertEqual(bad, [], f"non-bush plant (tree canopy?) in decor at {bad[:5]}")


if __name__ == "__main__":
    unittest.main()
