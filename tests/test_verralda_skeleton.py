"""Verralda heath: a walkable grave_heath field south of the seam (y>=36) on the
80x56 overworld, with Alherralba as the respawn hub and NO enemies yet, plus the
faction villages (Bondemilis / crossroads / Harrow) as named landmark town tiles.

Map/data only. Combat/RNG untouched. After the 80x56 wilderness-first regen the
heath has no cobble paths and no scattered props — open default + organic forest
masses (trunks + canopies) — so those old-design checks are gone. Skips without
pygame/pytmx.
"""

import os
import random
import unittest
from collections import deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp
    from rpg_game.presentation import ui_text as T

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False

W, H, SEAM_Y = 80, 56, 36


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class VerraldaSkeletonTest(unittest.TestCase):
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

    def _reachable_from_start(self):
        start = self.zone.start_tile
        blocked = self.world.blocked
        seen, q = {start}, deque([start])
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in blocked and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        return seen

    def test_map_is_80x56(self):
        self.assertEqual((self.world.tmx.width, self.world.tmx.height), (W, H))

    def test_gate_verralda_south_on_the_south_edge(self):
        gates = self.world.gate_messages
        self.assertNotIn((13, 31), gates)        # old frontier gate removed
        self.assertIn((24, 55), gates)           # new south frontier gate
        self.assertIn((24, 55), self.world.blocked)

    def test_heath_reachable_from_core_through_the_seam(self):
        seen = self._reachable_from_start()
        self.assertIn((24, 47), seen)            # Alherralba (heath hub)
        self.assertIn((24, 40), seen)            # open heath, through the seam
        for tile in self.world.town_tiles:       # nothing walled in
            self.assertIn(tile, seen)

    def test_alherralba_is_a_store_respawn_town(self):
        alherralba = self.app.engine.content.places["burg_121"]
        self.assertTrue(alherralba.has_store)
        self.assertTrue(alherralba.respawn)
        self.assertEqual(self.zone.towns.get((24, 47)), "burg_121")

    def test_heath_is_enemy_free(self):
        self.assertEqual(self.zone.wild_region_at((24, 40)), "burg_121")
        self.app.engine.enter_place("burg_121")
        self.app.engine.rng = random.Random(1)
        self.assertTrue(all(self.app.engine.create_encounter() is None for _ in range(60)))

    def test_region_at_respects_x_and_y(self):
        self.assertEqual(self.zone.wild_region_at((20, 8)), "burg_54")    # core
        self.assertEqual(self.zone.wild_region_at((50, 8)), "burg_146")   # mid-west band
        self.assertEqual(self.zone.wild_region_at((44, 40)), "burg_121")  # south wins over band
        self.assertEqual(self.zone.wild_region_at((13, 40)), "burg_121")  # heath

    def test_dying_in_heath_respawns_at_hordanita_unless_relocated(self):
        # Respawn no longer auto-moves: entering the heath leaves it at Hordanita.
        engine = self.app.engine
        engine.enter_place("burg_121")
        self.assertEqual(engine.player.respawn_place_id, "burg_5")
        engine._respawn_player()
        self.assertEqual(engine.player.current_place_id, "burg_5")
        # Only buying relocation at Alherralba moves it there.
        engine.enter_place("burg_121")
        engine.player.gold = 1000
        self.assertTrue(engine.relocate_respawn(zone=1).success)
        engine._respawn_player()
        self.assertEqual(engine.player.current_place_id, "burg_121")

    def test_crossing_into_heath_shows_a_soft_signal(self):
        self.assertEqual(T.region_flavor("burg_121"), T.REGION_FLAVOR["burg_121"])
        self.assertNotEqual(T.region_flavor("burg_121"), T.WEST_BORDER_FLAVOR)
        self.assertEqual(T.region_flavor("burg_146"), T.WEST_BORDER_FLAVOR)  # west unchanged

    # -- heath is populated with themed trees (trunks in walls, canopies over) --

    def _tileset_of(self, gid):
        return self.world.tmx.get_tileset_from_gid(gid).name if gid else None

    def test_grave_heath_tilesets_registered(self):
        names = {ts.name for ts in self.world.tmx.tilesets}
        self.assertIn("grave_heath_plant", names)
        self.assertIn("grave_heath_props", names)  # reserved for the edge phase

    def test_heath_has_trees_drawn_and_blocking(self):
        tmx = self.world.tmx
        walls = tmx.get_layer_by_name("walls")
        decor = tmx.get_layer_by_name("decor_over")
        heath_walls = [self._tileset_of(walls.data[y][x])
                       for y in range(SEAM_Y, tmx.height) for x in range(tmx.width)]
        heath_decor = [self._tileset_of(decor.data[y][x])
                       for y in range(SEAM_Y, tmx.height) for x in range(tmx.width)]
        self.assertIn("grave_heath_plant", heath_walls)   # trunks block
        self.assertIn("grave_heath_plant", heath_decor)   # canopies drawn over

    def test_only_dense_canopy_collides_never_wispy_edge_crowns(self):
        # Forest collision fill is the dense centre canopy (offset 34, fully opaque,
        # hidden under the crown). The wispy edge/corner crown tiles (transparent
        # outline) live ONLY in decor_over and must never end up in walls (they
        # would read as phantom collision). Raw CSV: plant gid = firstgid + offset.
        import os
        import re
        from rpg_game.presentation.pygame_overworld import MAPS_DIR
        src = open(os.path.join(MAPS_DIR, "overworld.tmx"), encoding="utf-8").read()

        def layer(name):
            m = re.search(r'name="%s"[^>]*>\s*<data encoding="csv">\s*(.*?)\s*</data>' % name, src, re.S)
            return [[int(v) for v in r.rstrip(",").split(",")] for r in m.group(1).strip().split("\n")]

        def plant_offset(gid):
            for fg in (2691, 4227):           # cainos_plant / grave_heath_plant
                if fg <= gid < fg + 256:
                    return gid - fg
            return None

        walls = layer("walls")
        wispy = {17, 18, 19, 33, 35, 49, 50, 51, 21, 22, 23, 37, 39, 53, 54, 55,
                 25, 26, 27, 41, 43, 57, 58, 59}   # all crown tiles except the dense centres
        wall_offsets = {plant_offset(walls[y][x]) for y in range(len(walls))
                        for x in range(len(walls[0])) if plant_offset(walls[y][x]) is not None}
        self.assertTrue(wall_offsets, "no forest fill in walls")
        self.assertEqual(wall_offsets & wispy, set(), "wispy crown tile used as collision")
        self.assertTrue(wall_offsets <= {34, 38, 42}, f"unexpected plant collision tiles: {wall_offsets}")

    # -- faction villages (grouping preserved on the larger heath) --------

    FACTION_VILLAGES = {
        "burg_54": "Guaredama", "burg_385": "Cantida", "burg_149": "Salles",   # Bondemilis
        "burg_293": "Urrequena",                                                # crossroads
        "burg_105": "Chuequeroma", "burg_53": "Barroncami",                     # Harrow
    }

    def test_faction_villages_are_town_tiles_in_the_heath(self):
        by_id = {pid: tile for tile, pid in self.zone.towns.items()}
        for pid, label in self.FACTION_VILLAGES.items():
            self.assertIn(pid, by_id, f"{label} missing as a town tile")
            self.assertGreaterEqual(by_id[pid][1], SEAM_Y, f"{label} not in the heath (y>={SEAM_Y})")
            self.assertEqual(self.zone.town_labels[by_id[pid]], label)

    def test_villages_are_landmarks_without_a_store(self):
        for pid in self.FACTION_VILLAGES:
            self.assertFalse(self.app.engine.content.places[pid].has_store)

    def test_every_village_is_reachable_from_start(self):
        seen = self._reachable_from_start()
        by_id = {pid: tile for tile, pid in self.zone.towns.items()}
        for pid in self.FACTION_VILLAGES:
            self.assertIn(by_id[pid], seen, f"{pid} walled in")

    def test_no_prop_covers_a_village(self):
        walls = self.world.tmx.get_layer_by_name("walls")
        by_id = {pid: tile for tile, pid in self.zone.towns.items()}
        for pid in self.FACTION_VILLAGES:
            tx, ty = by_id[pid]
            self.assertEqual(walls.data[ty][tx], 0, f"{pid} has a wall/prop on it")

    def test_renders_without_crashing(self):
        self.app.draw()


if __name__ == "__main__":
    unittest.main()
