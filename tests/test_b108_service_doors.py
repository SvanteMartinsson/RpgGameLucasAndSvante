"""B108 (2026-07-12): apothecary/stable get physical doors.

B8 2b wired their BUILDING_FUNCTION (brew / fast_travel) but left them in
COSMETIC_BUILDINGS, so no door tile reached them and the menus were unreachable
by walking — only via do_action (tests/debug). Same fix as the shrine (36e20bc):
out of the cosmetic set, physical door tiles via the template, menus opened by
standing on the door like every other building.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp
    from rpg_game.presentation import town_cluster
    from rpg_game.presentation.overworld_buildings import BUILDING_FUNCTION, BUILDING_TITLES
    DEPS_OK = True
except Exception:  # pragma: no cover
    DEPS_OK = False


class CosmeticSetTests(unittest.TestCase):
    def test_functional_props_left_the_cosmetic_set(self):
        self.assertNotIn("apothecary", town_cluster.COSMETIC_BUILDINGS)
        self.assertNotIn("stable", town_cluster.COSMETIC_BUILDINGS)
        # purely decorative props stay cosmetic
        self.assertIn("warehouse", town_cluster.COSMETIC_BUILDINGS)
        self.assertIn("gatehouse", town_cluster.COSMETIC_BUILDINGS)

    def test_both_still_map_their_service(self):
        self.assertEqual(BUILDING_FUNCTION["apothecary"], "brew")
        self.assertEqual(BUILDING_FUNCTION["stable"], "fast_travel")
        self.assertEqual(BUILDING_TITLES["apothecary"], "Apothecary")
        self.assertEqual(BUILDING_TITLES["stable"], "Stable")


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class DoorReachabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()

    def _door_for(self, building_id):
        return {tile: v for tile, v in self.app.door_index.items()
                if v[1] == building_id}

    def test_apothecary_and_stable_have_door_tiles(self):
        self.assertTrue(self._door_for("apothecary"))
        self.assertTrue(self._door_for("stable"))

    def test_walking_to_the_apothecary_door_opens_brewing(self):
        doors = self._door_for("apothecary")
        (tile, (pid, bid)) = next(iter(doors.items()))
        self.app.world.set_tile(*tile)
        self.app.sync_location()
        self.app._interact_door(pid, bid)
        # the door opens the titled building menu; picking the service enters brew
        self.assertEqual(self.app.mode, "building")
        self.assertEqual(self.app.building_menu, (pid, bid))

    def test_walking_to_the_stable_door_opens_fast_travel_menu(self):
        doors = self._door_for("stable")
        (tile, (pid, bid)) = next(iter(doors.items()))
        self.app.world.set_tile(*tile)
        self.app.sync_location()
        self.app._interact_door(pid, bid)
        self.assertEqual(self.app.mode, "building")
        self.assertEqual(self.app.building_menu, (pid, bid))

    def test_service_props_get_a_cobble_spur(self):
        # like every doored building, the door tile joins the cobble net
        for bid in ("apothecary", "stable"):
            doors = self._door_for(bid)
            for tile in doors:
                self.assertIn(tile, self.app._cobble_net, (bid, tile))


if __name__ == "__main__":
    unittest.main()
