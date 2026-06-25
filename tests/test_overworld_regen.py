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
        seen = self._reachable()
        # both endpoints of each cross-seam edge are in the same reachable set,
        # and the seam itself is open on the crossing columns (not walled).
        for a, b in ZONE_EDGES:
            self.assertIn(TOWNS[a], seen)
            self.assertIn(TOWNS[b], seen)
        crossings = [TOWNS["burg_117"][0], TOWNS["burg_149"][0]]
        for x in crossings:
            self.assertTrue(any((x + dx, SEAM_Y) in seen for dx in (-1, 0, 1)),
                            f"seam not passable near x={x}")

    def test_heath_faction_grouping_preserved(self):
        for pid in BONDEMILIS + HARROW:
            self.assertGreaterEqual(TOWNS[pid][1], SEAM_Y, f"{pid} not in heath")
        # Bondemilis sits west of Harrow (clusters stay separated, not interleaved)
        bond_x = max(TOWNS[p][0] for p in BONDEMILIS)
        harrow_x = min(TOWNS[p][0] for p in HARROW)
        self.assertLess(bond_x, harrow_x)

    def test_open_wilderness_is_the_default(self):
        # foundation feel: the vast majority of tiles are walkable (open).
        walkable = sum(1 for y in range(H) for x in range(W)
                       if (x, y) not in self.world.blocked)
        self.assertGreater(walkable / (W * H), 0.80)

    # -- ground texture + broken path hints (under player, no collision) ----

    def _layer(self, name):
        return self.world.tmx.get_layer_by_name(name).data

    def _is_path(self, gid):
        # cobble path tiles are idx 32-63 of the grass tilesets (firstgid 3/387).
        return any(fg <= gid < fg + 64 and (gid - fg) >= 32 for fg in (3, 387))

    def test_ground_is_textured_not_monochrome(self):
        ground = self._layer("ground")
        from collections import Counter
        c = Counter(ground[y][x] for y in range(H) for x in range(W))
        self.assertGreater(len(c), 20, "ground barely varied (near-monochrome)")
        base = c[3] + c[387]  # the two base-grass gids
        self.assertLess(base / (W * H), 0.65, "ground dominated by base grass")

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

    def test_paths_and_detail_never_collide(self):
        # path + detail live in the ground layer only; the walls layer must hold
        # no grass-sheet (path/detail) gid -> walking over a path is never blocked.
        walls = self._layer("walls")
        offenders = [(x, y) for y in range(H) for x in range(W)
                     if walls[y][x] and self._is_path(walls[y][x])]
        self.assertEqual(offenders, [], f"path tiles in walls (collide): {offenders}")


if __name__ == "__main__":
    unittest.main()
