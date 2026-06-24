"""Verralda skeleton: a walkable grave_heath field south of the core, reached via
the opened gate_south, with Alherralba as the respawn hub — and NO enemies yet.

Map/data only. Combat/RNG untouched. Skips without pygame/pytmx.
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

    def test_map_grew_southward(self):
        self.assertEqual((self.world.tmx.width, self.world.tmx.height), (48, 32))

    def test_gate_south_opened_frontier_moved_outward(self):
        gates = self.world.gate_messages
        self.assertNotIn((13, 19), gates)            # old gate_south removed...
        self.assertNotIn((13, 19), self.world.blocked)  # ...and now walkable
        self.assertIn((13, 31), gates)               # new frontier gate on the south edge
        self.assertIn((13, 31), self.world.blocked)

    def test_heath_reachable_from_core_through_the_seam(self):
        blocked = self.world.blocked
        seen, q = {(14, 10)}, deque([(14, 10)])
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < 48 and 0 <= ny < 32 and (nx, ny) not in blocked and (nx, ny) not in seen:
                    seen.add((nx, ny)); q.append((nx, ny))
        # Alherralba and every town tile remain reachable; nothing walled in.
        self.assertIn((14, 26), seen)  # Alherralba
        for tile in self.world.town_tiles:
            self.assertIn(tile, seen)
        self.assertIn((13, 20), seen)  # first heath row, through the seam

    def test_alherralba_is_a_store_respawn_town(self):
        alherralba = self.app.engine.content.places["burg_121"]
        self.assertTrue(alherralba.has_store)
        self.assertTrue(alherralba.respawn)
        self.assertEqual(self.zone.towns.get((14, 26)), "burg_121")

    def test_heath_is_enemy_free(self):
        # The heath maps to a region with no encounter pool, so stepping there
        # never spawns a fight (skeleton: no enemies yet).
        self.assertEqual(self.zone.wild_region_at((14, 25)), "burg_121")
        self.app.engine.enter_place("burg_121")
        self.app.engine.rng = random.Random(1)
        self.assertTrue(all(self.app.engine.create_encounter() is None for _ in range(60)))

    def test_region_at_respects_x_and_y(self):
        self.assertEqual(self.zone.wild_region_at((14, 10)), "burg_54")   # core
        self.assertEqual(self.zone.wild_region_at((39, 10)), "burg_146")  # west band
        self.assertEqual(self.zone.wild_region_at((44, 25)), "burg_121")  # south wins over west
        self.assertEqual(self.zone.wild_region_at((13, 25)), "burg_121")  # heath

    def test_dying_in_heath_respawns_at_alherralba(self):
        engine = self.app.engine
        engine.enter_place("burg_121")  # standing in the heath region
        self.assertEqual(engine.player.respawn_place_id, "burg_121")
        engine._respawn_player()
        self.assertEqual(engine.player.current_place_id, "burg_121")

    def test_crossing_into_heath_shows_a_soft_signal(self):
        self.assertEqual(T.region_flavor("burg_121"), T.REGION_FLAVOR["burg_121"])
        self.assertNotEqual(T.region_flavor("burg_121"), T.WEST_BORDER_FLAVOR)
        self.assertEqual(T.region_flavor("burg_146"), T.WEST_BORDER_FLAVOR)  # west unchanged

    # -- heath is populated with themed trees + props ----------------------

    def _tileset_of(self, gid):
        return self.world.tmx.get_tileset_from_gid(gid).name if gid else None

    def test_grave_heath_prop_tilesets_registered(self):
        names = {ts.name for ts in self.world.tmx.tilesets}
        self.assertIn("grave_heath_plant", names)
        self.assertIn("grave_heath_props", names)

    def test_heath_has_trees_and_props_drawn_and_blocking(self):
        tmx = self.world.tmx
        walls = tmx.get_layer_by_name("walls")
        decor = tmx.get_layer_by_name("decor_over")
        heath_walls = [self._tileset_of(walls.data[y][x])
                       for y in range(20, tmx.height) for x in range(tmx.width)]
        heath_decor = [self._tileset_of(decor.data[y][x])
                       for y in range(20, tmx.height) for x in range(tmx.width)]
        # Obstacles (trunks + rocks/bushes) in walls; canopies in decor_over.
        self.assertIn("grave_heath_plant", heath_walls)   # trunks / bushes
        self.assertIn("grave_heath_props", heath_walls)   # rocks / markers
        self.assertIn("grave_heath_plant", heath_decor)   # canopies

    def test_no_canopy_gids_collide_in_walls(self):
        tmx = self.world.tmx
        walls = tmx.get_layer_by_name("walls")
        decor = tmx.get_layer_by_name("decor_over")
        canopy = {decor.data[y][x] for y in range(tmx.height) for x in range(tmx.width) if decor.data[y][x]}
        wall_gids = {walls.data[y][x] for y in range(tmx.height) for x in range(tmx.width) if walls.data[y][x]}
        self.assertEqual(canopy & wall_gids, set())  # canopy never collides

    def test_heath_trees_are_sparser_than_the_core_forest(self):
        # Distinct open-farmland feel: fewer trunks per row in the heath than the
        # core forest. pytmx remaps gids internally, so count from the RAW TMX
        # CSV where gids are firstgid + tile-index. Trunks are plant idx 66/70/74
        # (cainos_plant firstgid 2691 in the core, grave_heath_plant 4227 south).
        import re
        from rpg_game.presentation.pygame_overworld import DEFAULT_MAP, MAPS_DIR
        import os
        src = open(os.path.join(MAPS_DIR, "overworld.tmx"), encoding="utf-8").read()
        m = re.search(r'name="walls"[^>]*>\s*<data encoding="csv">\s*(.*?)\s*</data>', src, re.S)
        rows = [[int(v) for v in r.rstrip(",").split(",")] for r in m.group(1).strip().split("\n")]
        core_trunks = {2691 + i for i in (66, 70, 74)}
        heath_trunks = {4227 + i for i in (66, 70, 74)}
        core = sum(1 for y in range(20) for x in range(48) if rows[y][x] in core_trunks)
        heath = sum(1 for y in range(20, len(rows)) for x in range(48) if rows[y][x] in heath_trunks)
        self.assertGreater(heath, 0)                         # the heath does have trees
        self.assertLess(heath / 12, core / 20)               # but sparser per row than the core

    # -- faction villages + connecting paths -------------------------------

    FACTION_VILLAGES = {
        "burg_54": "Guaredama", "burg_385": "Cantida", "burg_149": "Salles",   # Bondemilis
        "burg_293": "Urrequena",                                                # crossroads
        "burg_105": "Chuequeroma", "burg_53": "Barroncami",                     # Harrow
    }

    def test_faction_villages_are_town_tiles_in_the_heath(self):
        towns = self.zone.towns  # (tx, ty) -> place_id
        by_id = {pid: tile for tile, pid in towns.items()}
        for pid, label in self.FACTION_VILLAGES.items():
            self.assertIn(pid, by_id, f"{label} missing as a town tile")
            self.assertGreaterEqual(by_id[pid][1], 20, f"{label} not in the heath (y>=20)")
            self.assertEqual(self.zone.town_labels[by_id[pid]], label)

    def test_villages_are_landmarks_without_a_store(self):
        # Alherralba stays the only service hub; villages are named landmarks.
        for pid in self.FACTION_VILLAGES:
            self.assertFalse(self.app.engine.content.places[pid].has_store)

    def test_every_village_is_reachable_from_start(self):
        blocked = self.world.blocked
        seen, q = {(14, 10)}, deque([(14, 10)])
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < 48 and 0 <= ny < 32 and (nx, ny) not in blocked and (nx, ny) not in seen:
                    seen.add((nx, ny)); q.append((nx, ny))
        by_id = {pid: tile for tile, pid in self.zone.towns.items()}
        for pid in self.FACTION_VILLAGES:
            self.assertIn(by_id[pid], seen, f"{pid} walled in")

    def test_no_prop_or_path_covers_a_village(self):
        # Town tiles must be walkable (no obstacle GID sitting on them).
        walls = self.world.tmx.get_layer_by_name("walls")
        by_id = {pid: tile for tile, pid in self.zone.towns.items()}
        for pid in self.FACTION_VILLAGES:
            tx, ty = by_id[pid]
            self.assertEqual(walls.data[ty][tx], 0, f"{pid} has a wall/prop on it")

    def test_heath_has_cobble_paths(self):
        # The path net paints grave_heath cobble (firstgid 387 + 35/43/44/45) into
        # the ground layer; pytmx name check via raw CSV (pytmx remaps gids).
        import re
        import os
        from rpg_game.presentation.pygame_overworld import MAPS_DIR
        src = open(os.path.join(MAPS_DIR, "overworld.tmx"), encoding="utf-8").read()
        m = re.search(r'name="ground"[^>]*>\s*<data encoding="csv">\s*(.*?)\s*</data>', src, re.S)
        rows = [[int(v) for v in r.rstrip(",").split(",")] for r in m.group(1).strip().split("\n")]
        cobble = {387 + i for i in (35, 43, 44, 45)}
        n = sum(1 for y in range(20, len(rows)) for x in range(48) if rows[y][x] in cobble)
        self.assertGreater(n, 20)  # a connecting path net, not a stray tile

    def test_renders_without_crashing(self):
        self.app.draw()


if __name__ == "__main__":
    unittest.main()
