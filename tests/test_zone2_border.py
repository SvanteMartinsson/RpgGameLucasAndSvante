"""ZONE2 step 1: the western border is open and walkable, western places are
reachable, and the west has its own wild region + respawn.

Skips when pygame/pytmx are not installed.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False

WESTERN_TOWNS = {
    (50, 16): "burg_235",  # Jinosa
    (57, 7): "burg_379",   # Condillosca
    (66, 12): "burg_146",  # Rotequero (hub, respawn)
    (60, 26): "burg_67",   # Fongorinos
    (73, 6): "burg_200",   # Estables
    (70, 31): "burg_320",  # Parguillas
    (74, 17): "burg_219",  # Tierva
}


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class Zone2BorderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()

    # -- border is open, not gated -----------------------------------------

    def test_old_east_gate_is_open_and_walkable(self):
        # The core's old eastern gate no longer blocks; the corridor west is open.
        self.assertNotIn((27, 10), self.app.world.gate_messages)
        self.assertNotIn((27, 10), self.app.world.blocked)

    def _west_is_reachable_from(self, start, goal_x=30):
        """True if some tile with x >= goal_x is reachable from `start` on the
        blocked-tile grid (4-neighbour). Models walking west while stepping
        around scattered decoration props, not a dead-straight corridor."""
        from collections import deque
        world = self.app.world
        cols = world.map_px_w // world.tw
        rows = world.map_px_h // world.th
        seen, queue = {start}, deque([start])
        while queue:
            tx, ty = queue.popleft()
            if tx >= goal_x:
                return True
            for nx, ny in ((tx + 1, ty), (tx - 1, ty), (tx, ty + 1), (tx, ty - 1)):
                if 0 <= nx < cols and 0 <= ny < rows and (nx, ny) not in seen \
                        and (nx, ny) not in world.blocked:
                    seen.add((nx, ny))
                    queue.append((nx, ny))
        return False

    def test_can_walk_from_core_into_the_west(self):
        # The border is open: from just east of Gaste you can reach the west,
        # detouring a tile up/down around any decoration prop in the corridor.
        self.assertTrue(self._west_is_reachable_from((22, 12)),
                        "cannot reach the west from the core side")

    def test_far_west_edge_is_still_gated(self):
        self.assertIn((79, 28), self.app.world.gate_messages)

    # -- western places reachable & playable -------------------------------

    def test_all_seven_western_towns_are_reachable(self):
        for (tx, ty), place_id in WESTERN_TOWNS.items():
            self.assertEqual(self.app.zone.towns.get((tx, ty)), place_id)
            self.assertNotIn((tx, ty), self.app.world.blocked)
            self.app.world.set_tile(tx, ty)
            self.app.sync_location()
            self.assertEqual(self.app.engine.player.current_place_id, place_id)

    # -- regions: east unchanged, west tier-2 + own respawn ----------------

    def test_core_wilderness_unchanged(self):
        self.app.world.set_tile(14, 8)  # core wilderness
        self.app.sync_location()
        self.assertEqual(self.app.engine.player.current_place_id, "burg_54")
        self.assertEqual(self.app.engine.player.respawn_place_id, "burg_5")

    def test_western_wilderness_uses_zone2_region_and_respawn(self):
        self.app.world.set_tile(50, 8)  # western wilderness (mid-west band)
        self.app.sync_location()
        self.assertEqual(self.app.engine.player.current_place_id, "burg_146")
        self.assertEqual(self.app.engine.player.respawn_place_id, "burg_146")

    def test_western_encounters_come_from_zone2_pool(self):
        self.app.world.set_tile(50, 8)
        self.app.sync_location()
        self.app.encounter_rate = 1.0
        seen = {self.app.maybe_encounter().id for _ in range(80)}
        self.assertTrue(seen <= {"undead", "cave_bear", "undead_priest", "dire_wolf", "wild_boar", "treant", "hollow_worg"})
        self.assertNotIn("giant_rat", seen)  # rat is a core-zone enemy

    def test_defeat_in_west_respawns_at_rotequero_tile(self):
        self.app.world.set_tile(50, 8)
        self.app.sync_location()
        self.app.engine.player.current_place_id = "burg_146"  # engine respawn already ran
        enemy = self.app.engine.create_encounter()
        self.app.resolve_battle_outcome("defeat", enemy)
        self.assertEqual(self.app.world.current_tile, (66, 12))  # Rotequero tile


if __name__ == "__main__":
    unittest.main()
