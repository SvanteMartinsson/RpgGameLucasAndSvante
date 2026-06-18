"""Headless tests for overworld towns, location sync, town menu and gates.

Skips when pygame/pytmx are not installed (system interpreter / core run).
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp, ZoneConfig

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class OverworldTownsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()
        self.zone = self.app.zone

    # -- location sync ------------------------------------------------------

    def test_starts_in_hub_town(self):
        self.assertEqual(self.app.engine.player.current_place_id, "burg_5")

    def test_stepping_onto_town_sets_location(self):
        self.app.world.set_tile(6, 6)  # Yeblegali
        self.app.sync_location()
        self.assertEqual(self.app.engine.player.current_place_id, "burg_117")

    def test_wilderness_uses_wild_region(self):
        self.app.world.set_tile(14, 8)  # off any town tile
        self.app.sync_location()
        self.assertIsNone(self.app.world.town_place_id())
        self.assertEqual(self.app.engine.player.current_place_id, self.zone.wild_region_place_id)

    # -- town menu actions go through the engine ----------------------------

    def test_rest_in_hub_heals_via_engine(self):
        self.app.world.set_tile(14, 10)
        self.app.sync_location()
        self.app.engine.player.hp = 1
        self.app.do_action("rest")
        self.assertEqual(self.app.engine.player.hp, self.app.engine.player.max_hp)

    def test_save_action_writes_via_engine(self):
        self.app.do_action("save")
        self.assertIn("saved", self.app.toast.lower())
        self.addCleanup(lambda: os.path.exists("savegame.json") and os.remove("savegame.json"))

    def test_store_gated_when_town_has_no_store(self):
        self.app.world.set_tile(6, 6)  # Yeblegali has no store
        self.app.sync_location()
        self.app.mode = "townmenu"
        self.app.do_action("store")
        self.assertNotEqual(self.app.mode, "store")

    # -- no town menu in the wild -------------------------------------------

    def test_enter_in_wilderness_opens_no_menu(self):
        self.app.world.set_tile(14, 8)
        self.app.sync_location()
        self.app.mode = "walk"
        self.app._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        self.assertEqual(self.app.mode, "walk")

    def test_enter_on_town_opens_menu(self):
        self.app.world.set_tile(14, 10)
        self.app.sync_location()
        self.app.mode = "walk"
        self.app._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        self.assertEqual(self.app.mode, "townmenu")

    # -- gates --------------------------------------------------------------

    def test_gate_blocks_and_shows_its_message(self):
        self.app.world.set_tile(14, 2)  # below the north gate at (14, 0)
        message = ""
        for _ in range(40):
            hit = self.app.world.try_move(0, -3)
            if hit:
                message = hit
        self.assertTrue(message)
        self.assertGreaterEqual(self.app.world.player.top, self.app.world.th)  # never entered row 0

    def test_plain_wall_gives_no_gate_message(self):
        self.app.world.set_tile(2, 2)  # corner wall, not a gate
        message = ""
        for _ in range(40):
            hit = self.app.world.try_move(0, -3)
            if hit:
                message = hit
        self.assertEqual(message, "")


if __name__ == "__main__":
    unittest.main()
