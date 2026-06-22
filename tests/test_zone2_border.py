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
    (30, 12): "burg_235",  # Jinosa (border)
    (34, 6): "burg_379",   # Condillosca
    (39, 10): "burg_146",  # Rotequero (hub, respawn)
    (38, 16): "burg_67",   # Fongorinos
    (44, 6): "burg_200",   # Estables
    (42, 17): "burg_320",  # Parguillas
    (45, 13): "burg_219",  # Tierva
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

    def test_can_walk_from_core_into_the_west(self):
        self.app.world.set_tile(22, 12)  # just east of Gaste, core side
        for _ in range(150):
            self.app.world.try_move(3, 0)
        self.assertGreaterEqual(self.app.world.current_tile[0], 30)  # crossed into the west

    def test_far_west_edge_is_still_gated(self):
        self.assertIn((47, 10), self.app.world.gate_messages)

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
        self.app.world.set_tile(40, 8)  # western wilderness
        self.app.sync_location()
        self.assertEqual(self.app.engine.player.current_place_id, "burg_146")
        self.assertEqual(self.app.engine.player.respawn_place_id, "burg_146")

    def test_western_encounters_come_from_zone2_pool(self):
        self.app.world.set_tile(40, 8)
        self.app.sync_location()
        self.app.encounter_rate = 1.0
        seen = {self.app.maybe_encounter().id for _ in range(80)}
        self.assertTrue(seen <= {"undead", "cave_bear", "undead_priest", "dire_wolf", "wild_boar", "treant"})
        self.assertNotIn("giant_rat", seen)  # rat is a core-zone enemy

    def test_defeat_in_west_respawns_at_rotequero_tile(self):
        self.app.world.set_tile(40, 8)
        self.app.sync_location()
        self.app.engine.player.current_place_id = "burg_146"  # engine respawn already ran
        enemy = self.app.engine.create_encounter()
        self.app.resolve_battle_outcome("defeat", enemy)
        self.assertEqual(self.app.world.current_tile, (39, 10))  # Rotequero tile


if __name__ == "__main__":
    unittest.main()
