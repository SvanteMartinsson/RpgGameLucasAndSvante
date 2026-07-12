"""Headless tests for overworld overlay panels.

Skips when pygame/pytmx are not installed.
"""

import json
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame

    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import terminal
    from rpg_game.presentation.pygame_battle import BattleApp
    from rpg_game.presentation.pygame_overworld import SAVE_PATH, OverworldApp
    from rpg_game.presentation.playtest_logger import PlaytestLogger

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
        if os.path.exists(SAVE_PATH):
            os.remove(SAVE_PATH)

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

        # B71: manual saves land in the app's slot (saves/slotN.json), not the
        # legacy root savegame.json.
        self.assertTrue(os.path.exists(self.app.save_path))
        self.addCleanup(lambda: os.path.exists(self.app.save_path) and os.remove(self.app.save_path))
        self.assertIn("saved", self.app.event_log[-1][0].lower())

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
        self.assertIn("needs level", self.app.event_log[-1][0].lower())

    def test_character_panel_equip_and_unequip_gear_updates_effective_stats(self):
        self.app.engine.player.owned_gear_ids = ("padded_vest",)
        self.app.selected_equipment_slot = "chest"

        self.app.equip_gear_to_slot("padded_vest")

        self.assertEqual(self.app.engine.player.equipped_gear["chest"], "padded_vest")
        self.assertEqual(self.app.engine.effective_stat("armor"), self.app.engine.player.armor + 2)

        self.app.unequip_gear_from_slot("chest")

        self.assertNotIn("chest", self.app.engine.player.equipped_gear)
        self.assertEqual(self.app.engine.effective_stat("armor"), self.app.engine.player.armor)

    def test_panel_equip_unequip_emit_playtest_events(self):
        with tempfile.TemporaryDirectory() as folder:
            self.app.playtest_logger = PlaytestLogger(folder)
            self.app.engine.player.owned_gear_ids = ("padded_vest",)
            self.app.selected_equipment_slot = "chest"

            self.app.equip_gear_to_slot("padded_vest")
            self.app.unequip_gear_from_slot("chest")

            rows = [json.loads(line) for line in self.app.playtest_logger.path.read_text().splitlines() if line.strip()]

        equip = next(r for r in rows if r["event"] == "equip")
        self.assertEqual((equip["slot"], equip["item_id"]), ("chest", "padded_vest"))
        unequip = next(r for r in rows if r["event"] == "unequip")
        self.assertEqual((unequip["slot"], unequip["item_id"]), ("chest", "padded_vest"))

    def test_weapon_equip_emits_playtest_event_with_damage_type(self):
        with tempfile.TemporaryDirectory() as folder:
            self.app.playtest_logger = PlaytestLogger(folder)
            self.app.engine.player.owned_weapon_ids = ("knife", "sword")
            self.app.engine.player.equipped_weapon_id = "knife"

            self.app.equip_weapon("sword")

            rows = [json.loads(line) for line in self.app.playtest_logger.path.read_text().splitlines() if line.strip()]

        equip = next(r for r in rows if r["event"] == "equip" and r["slot"] == "weapon")
        self.assertEqual(equip["item_id"], "sword")
        self.assertEqual(equip["damage_type"], "physical")

    def test_character_panel_blocks_wrong_slot_and_level_gated_gear(self):
        self.app.engine.player.owned_gear_ids = ("training_cap", "veteran_ring")

        self.app.equip_gear_to_slot("training_cap", "chest")
        self.assertNotIn("chest", self.app.engine.player.equipped_gear)
        self.assertIn("cannot be equipped", self.app.event_log[-1][0].lower())

        self.app.equip_gear_to_slot("veteran_ring", "ring_1")
        self.assertNotIn("ring_1", self.app.engine.player.equipped_gear)
        self.assertIn("requires level", self.app.event_log[-1][0].lower())

    def test_character_panel_draws_slots_and_inventory(self):
        # B121: the character screen draws ten anatomical equip slots (custom
        # icon buttons) plus the full inventory listing owned items by name.
        self.app.engine.player.owned_gear_ids = ("padded_vest",)
        self.app.overlay = "character"

        self.app.draw()

        slot_buttons = [b for b in self.app.buttons if b.custom]
        self.assertEqual(len(slot_buttons), 10)             # one per equipment slot
        labels = [button.label for button in self.app.buttons]
        self.assertTrue(any("Padded Vest" in label for label in labels))  # inventory row

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

        # B106: lock states render as compact markers, not bracket prefixes.
        self.assertTrue(any("+ " in label for label in labels))   # can learn
        self.assertTrue(any("\u25cb " in label for label in labels))  # locked

    def test_skills_panel_regions_do_not_overlap_on_compact_panel(self):
        panel = pygame.Rect(16, 16, 608, 560)

        skills, talents, detail = self.app._skills_talents_regions(panel)

        self.assertFalse(skills.colliderect(talents))
        self.assertFalse(skills.colliderect(detail))
        self.assertFalse(talents.colliderect(detail))
        self.assertGreaterEqual(detail.width, talents.width)

    def test_talent_detail_wraps_to_available_pixel_width(self):
        panel = pygame.Rect(16, 16, 608, 560)
        _skills, _talents, detail = self.app._skills_talents_regions(panel)
        long_line = (
            "Effect: apply a very long named status modifier with several conditions "
            "and enough descriptive text to require multiple wrapped rows"
        )

        lines = self.app._wrapped_lines_pixels(long_line, detail.width - 20, self.app.font_sm)

        self.assertGreater(len(lines), 1)
        self.assertTrue(all(self.app.font_sm.size(line)[0] <= detail.width - 20 for line in lines))

    def test_overlay_panels_render_headless_without_crashing(self):
        self.app.engine.player.inventory.add_consumable("hp_potion")
        self.app.engine.player.owned_gear_ids = ("padded_vest",)
        self.app.engine.player.talent_points = 1

        for overlay in ("character", "inventory", "skills_talents", "system"):
            with self.subTest(overlay=overlay):
                self.app.overlay = overlay
                self.app.draw()
                self.assertTrue(self.app.buttons)

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

        back = next(button for button in self.app.buttons if button.label == "Back")
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
        self.assertIn("Learned", lines)  # smite is the pre-learned starter node (B7.1); B106: plain word
        self.assertIn(f"Effect: {terminal.describe_talent(engine, node)}", lines)
        self.assertIn("Cost: 6 mana", lines)
        self.assertIn("Requires: none", lines)

    def test_talent_detail_shows_prerequisite_for_locked_node(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "cleric")
        app = OverworldApp(engine=engine)
        # mend is now CAN LEARN (its prereq smite is the pre-learned starter), so use a
        # deeper node still locked behind an unlearned prerequisite.
        node = engine.content.talents["cleric_light_l3_devotion"]

        lines = app.talent_detail_lines(node)

        self.assertIn("Locked", lines)   # B106: plain word in the detail panel
        self.assertTrue(any(l.startswith("Requires: ") and l != "Requires: none" for l in lines),
                        f"no prerequisite shown: {lines}")

    def test_talent_selection_works_with_keyboard_and_node_buttons(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "cleric")
        app = OverworldApp(engine=engine)
        app.overlay = "skills_talents"

        # B99: arrows drive the shared focus model — jump to the talents
        # section, step down one row and activate it with Enter.
        first = app.selected_talent_node()
        app.draw()   # registers this frame's focus sections
        app._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
        app._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
        app._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0))
        second = app.selected_talent_node()

        self.assertNotEqual(first.id, second.id)

        app.draw()
        smite_button = next(button for button in app.buttons if "Smite" in button.label and "\u2713" in button.label)
        smite_button.on_click()

        self.assertEqual(app.selected_talent_id, "cleric_light_l1_smite")


if __name__ == "__main__":
    unittest.main()
