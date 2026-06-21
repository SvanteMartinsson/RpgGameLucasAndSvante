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
    from rpg_game.presentation import terminal
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

    def test_skills_panel_toggle_skill_goes_through_engine(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "cleric")
        app = OverworldApp(engine=engine)

        app.toggle_skill("smite", equipped=True)
        self.assertNotIn("smite", app.engine.player.equipped_skill_ids)

        app.toggle_skill("smite", equipped=False)
        self.assertIn("smite", app.engine.player.equipped_skill_ids)

    def test_skills_panel_allocate_talent_goes_through_engine(self):
        self.app.engine.player.talent_points = 1
        node = self.app.engine.available_talents()[0]

        self.app.learn_talent(node.id)

        self.assertIn(node.id, self.app.engine.player.learned_talent_ids)
        self.assertEqual(self.app.engine.player.talent_points, 0)

    def test_skills_panel_draws_talent_lock_states(self):
        self.app.engine.player.talent_points = 1
        self.app.overlay = "skills_talents"

        self.app.draw()
        labels = [button.label for button in self.app.buttons]

        self.assertTrue(any("[CAN LEARN]" in label for label in labels))
        self.assertTrue(any("[LOCKED]" in label for label in labels))

    def test_overlay_from_town_menu_pauses_menu_and_restores_it_on_close(self):
        self.app.world.set_tile(14, 10)
        self.app.sync_location()
        self.app.mode = "townmenu"

        self.app.do_action("skills_talents")

        self.assertEqual(self.app.overlay, "skills_talents")
        self.assertEqual(self.app.mode, "walk")
        self.assertEqual(self.app.overlay_return_mode, "townmenu")

        self.app.draw()
        labels = [button.label for button in self.app.buttons]
        self.assertNotIn("Store", labels)
        self.assertNotIn("Rest", labels)

        self.app._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))

        self.assertEqual(self.app.overlay, "")
        self.assertEqual(self.app.mode, "townmenu")

    def test_overlay_input_from_town_menu_reaches_panel_not_menu_underneath(self):
        self.app.world.set_tile(14, 10)
        self.app.sync_location()
        self.app.mode = "townmenu"
        self.app.engine.player.inventory.add_consumable("hp_potion")
        self.app.engine.player.hp = 1

        self.app.do_action("inventory")
        self.app.draw()

        labels = [button.label for button in self.app.buttons]
        self.assertNotIn("Store", labels)
        potion = next(button for button in self.app.buttons if "HP Potion" in button.label)
        potion.on_click()

        self.assertGreater(self.app.engine.player.hp, 1)
        self.assertEqual(self.app.mode, "walk")
        self.assertEqual(self.app.overlay, "inventory")

        back = next(button for button in self.app.buttons if button.label == "Back (Esc)")
        back.on_click()
        self.assertEqual(self.app.mode, "townmenu")

    def test_talent_detail_lines_match_terminal_description(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "cleric")
        engine.player.talent_points = 1
        app = OverworldApp(engine=engine)
        node = engine.content.talents["cleric_light_l1_smite"]

        lines = app.talent_detail_lines(node)

        self.assertIn(node.name, lines)
        self.assertIn("[CAN LEARN]", lines)
        self.assertIn(f"Effect: {terminal.describe_talent(engine, node)}", lines)
        self.assertIn("Cost: 6 mana", lines)
        self.assertIn("Requires: none", lines)

    def test_talent_detail_shows_prerequisite_for_locked_node(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "cleric")
        app = OverworldApp(engine=engine)
        node = engine.content.talents["cleric_light_l2_mend"]

        lines = app.talent_detail_lines(node)

        self.assertIn("[LOCKED]", lines)
        self.assertIn("Requires: Smite", lines)

    def test_talent_selection_works_with_keyboard_and_node_buttons(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "cleric")
        app = OverworldApp(engine=engine)
        app.overlay = "skills_talents"

        first = app.selected_talent_node()
        app._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
        second = app.selected_talent_node()

        self.assertNotEqual(first.id, second.id)

        app.draw()
        smite_button = next(button for button in app.buttons if "[CAN LEARN] Smite" in button.label)
        smite_button.on_click()

        self.assertEqual(app.selected_talent_id, "cleric_light_l1_smite")


if __name__ == "__main__":
    unittest.main()
