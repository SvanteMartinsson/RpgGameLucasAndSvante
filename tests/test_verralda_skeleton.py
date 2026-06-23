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

    def test_renders_without_crashing(self):
        self.app.draw()


if __name__ == "__main__":
    unittest.main()
