"""B121c: character-screen interaction — equip/unequip by click AND keyboard,
hover tooltips with the item details, keyboard focus between slots and inventory,
and the stat delta updating live on equip. Skips without pygame.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame

    from rpg_game.core.game import GameEngine
    from rpg_game.core.view import build_snapshot
    from rpg_game.presentation import ui
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


def _key(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="")


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class CharacterInteractionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        self.app = OverworldApp(engine=engine)
        self.app.display = pygame.Surface((980, 660))
        self.app.screen = pygame.Surface((980, 660))
        self.eng = self.app.engine
        self.app.overlay = "character"

    def _button(self, pred):
        return next((b for b in self.app.buttons if pred(b)), None)

    def _focus(self, section_name, pred):
        """Point keyboard focus at the button matching pred within a section."""
        for si, (name, items) in enumerate(self.app.focus._sections):
            if name != section_name:
                continue
            for ii, b in enumerate(items):
                if pred(b):
                    self.app.focus.section = si
                    self.app.focus.index = ii
                    return b
        return None

    # -- equip / unequip by CLICK -------------------------------------------

    def test_click_inventory_gear_equips_to_its_slot(self):
        self.eng.player.owned_gear_ids = ("padded_vest",)
        self.app.draw()
        self._button(lambda b: b.label == "Padded Vest").on_click()
        self.assertEqual(self.eng.player.equipped_gear.get("chest"), "padded_vest")

    def test_click_inventory_weapon_equips(self):
        self.eng.player.owned_weapon_ids = (*self.eng.player.owned_weapon_ids, "sword")
        self.app.draw()
        self._button(lambda b: b.label == "Sword").on_click()
        self.assertEqual(self.eng.player.equipped_weapon_id, "sword")

    def test_click_filled_slot_unequips(self):
        self.eng.player.owned_gear_ids = ("padded_vest",)
        self.eng.equip_gear("padded_vest", "chest")
        self.app.draw()
        slot = self._button(lambda b: b.custom and b.label == "chest")
        self.assertIsNotNone(slot)
        slot.on_click()
        self.assertNotIn("chest", self.eng.player.equipped_gear)

    # -- equip / unequip by KEYBOARD ----------------------------------------

    def test_keyboard_enter_on_inventory_gear_equips(self):
        self.eng.player.owned_gear_ids = ("padded_vest",)
        self.app.draw()
        self._focus("inventory", lambda b: b.label == "Padded Vest")
        self.app._handle_key(_key(pygame.K_RETURN))
        self.assertEqual(self.eng.player.equipped_gear.get("chest"), "padded_vest")

    def test_keyboard_enter_on_filled_slot_unequips(self):
        self.eng.player.owned_gear_ids = ("padded_vest",)
        self.eng.equip_gear("padded_vest", "chest")
        self.app.draw()
        self._focus("slots", lambda b: b.custom and b.label == "chest")
        self.app._handle_key(_key(pygame.K_RETURN))
        self.assertNotIn("chest", self.eng.player.equipped_gear)

    def test_keyboard_moves_focus_between_slots_and_inventory(self):
        self.eng.player.owned_gear_ids = ("padded_vest",)
        self.app.draw()
        # focus starts in the slots section
        start = self.app.focus._sections[self.app.focus.section][0]
        self.assertEqual(start, "slots")
        # Right/Tab jumps to the next section (the inventory)
        self.app._handle_key(_key(pygame.K_RIGHT))
        self.app.draw()
        self.assertEqual(self.app.focus._sections[self.app.focus.section][0], "inventory")

    def test_escape_backs_out_of_the_screen(self):
        self.app.draw()
        self.app._handle_key(_key(pygame.K_ESCAPE))
        self.assertEqual(self.app.overlay, "")

    # -- hover tooltips ------------------------------------------------------

    def _tooltip(self, title):
        self.app.draw()
        return next((p for _r, p in self.app.hover._zones
                     if isinstance(p, ui.Tooltip) and p.title == title), None)

    def test_worn_slot_tooltip_shows_item_details(self):
        self.eng.player.owned_gear_ids = ("padded_vest",)
        self.eng.equip_gear("padded_vest", "chest")
        tip = self._tooltip("Padded Vest")
        self.assertIsNotNone(tip, "worn slot registered no tooltip")
        text = " ".join(tip.lines)
        self.assertIn("tier", text)
        self.assertIn("Lv", text)                       # required level
        self.assertTrue(any("Armor" in line or "HP" in line for line in tip.lines))  # stat mods

    def test_inventory_item_tooltip_shows_type_and_tier(self):
        self.eng.player.owned_weapon_ids = (*self.eng.player.owned_weapon_ids, "sword")
        tip = self._tooltip("Sword")
        self.assertIsNotNone(tip)
        text = " ".join(tip.lines).lower()
        self.assertIn("tier", text)
        self.assertIn("melee", text)                    # the weapon type surfaces

    # -- live stat delta -----------------------------------------------------

    def test_stat_delta_updates_live_on_equip(self):
        self.eng.player.owned_gear_ids = ("padded_vest",)  # armor +2
        self.app.draw()
        armor_before = next(r for r in build_snapshot(self.eng).player.stats if r.stat == "armor")
        self.assertEqual(armor_before.from_gear, 0)
        # equip via the same inventory button the player would click
        self._button(lambda b: b.label == "Padded Vest").on_click()
        self.app.draw()                                    # screen rebuilds the snapshot
        armor_after = next(r for r in build_snapshot(self.eng).player.stats if r.stat == "armor")
        self.assertEqual(armor_after.from_gear, 2)
        self.assertEqual(armor_after.total, armor_before.total + 2)


if __name__ == "__main__":
    unittest.main()
