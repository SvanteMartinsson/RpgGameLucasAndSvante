"""Headless tests for overworld overlay panels.

Skips when pygame/pytmx are not installed.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame

    from rpg_game.core.game import GameEngine
    from rpg_game.presentation.pygame_battle import BattleApp
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class OverworldOverlayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()

    def tearDown(self):
        if os.path.exists("savegame.json"):
            os.remove("savegame.json")

    def test_hotkeys_toggle_overworld_overlays_anywhere(self):
        self.app.world.set_tile(14, 8)  # wilderness
        self.app.sync_location()

        self.app._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_c))
        self.assertEqual(self.app.overlay, "character")
        self.app._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_c))
        self.assertEqual(self.app.overlay, "")

        self.app._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_i))
        self.assertEqual(self.app.overlay, "inventory")
        self.app._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertEqual(self.app.overlay, "")

    def test_escape_opens_system_overlay_and_save_writes(self):
        self.app._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertEqual(self.app.overlay, "system")

        self.app.save_game()

        self.assertTrue(os.path.exists("savegame.json"))
        self.assertIn("saved", self.app.toast.lower())

    def test_inventory_overlay_use_consumable_goes_through_engine(self):
        self.app.engine.player.inventory.add_consumable("hp_potion")
        self.app.engine.player.hp = 1

        self.app.use_inventory_item("hp_potion")

        self.assertGreater(self.app.engine.player.hp, 1)
        self.assertEqual(self.app.engine.player.inventory.count("hp_potion"), 0)

    def test_character_overlay_blocks_level_gated_weapon(self):
        self.app.engine.player.owned_weapon_ids = ("sword", "worldsplitter")
        self.app.engine.player.equipped_weapon_id = "sword"

        self.app.equip_weapon("worldsplitter")

        self.assertEqual(self.app.engine.player.equipped_weapon_id, "sword")
        self.assertIn("needs level", self.app.toast.lower())

    def test_panel_hotkeys_do_not_open_in_battle(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        battle = BattleApp(engine=engine, enemy=enemy, standalone=False)

        battle._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_c, unicode="c"))

        self.assertFalse(hasattr(battle, "overlay"))
        self.assertEqual(battle.mode, "combat")


if __name__ == "__main__":
    unittest.main()
