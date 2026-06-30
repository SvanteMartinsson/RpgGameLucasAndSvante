"""Presentation slice: level-locked item buttons are CLICKABLE (visually
restricted, not dead), so a click explains why — a named line in the chatbox.
The chatbox is also drawn over overlays/menus (read-only there).
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


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class ClickableItemsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()
        self.app.display = pygame.Surface((1000, 720))

    def _weapon_buttons(self):
        # open the character overlay on the weapon slot and build buttons
        self.app.engine.player.owned_weapon_ids = (
            *self.app.engine.player.owned_weapon_ids, "rimebrand")  # 16 dmg -> needs Lv 5
        self.app.overlay = "character"
        self.app.selected_equipment_slot = "weapon"
        self.app.draw()
        return [b for b in self.app.buttons if "Rimebrand" in b.label]

    def test_level_locked_weapon_button_is_clickable_but_restricted(self):
        self.assertEqual(self.app.engine.player.level, 1)  # below Rimebrand's Lv 5
        buttons = self._weapon_buttons()
        self.assertEqual(len(buttons), 1)
        rimebrand = buttons[0]
        self.assertTrue(rimebrand.enabled, "level-locked weapon must still be clickable")
        self.assertTrue(rimebrand.restricted, "level-locked weapon must look restricted")

    def test_clicking_a_locked_weapon_logs_a_named_line(self):
        rimebrand = self._weapon_buttons()[0]
        before = len(self.app.event_log)
        rimebrand.on_click()
        self.assertGreater(len(self.app.event_log), before)
        self.assertEqual(self.app.event_log[-1][0], "Rimebrand needs level 5.")

    def test_disabled_buttons_still_fire_when_restricted_only(self):
        # The click gate is `enabled`; restricted buttons keep enabled=True, so the
        # MOUSEBUTTONDOWN handler (enabled-gated) will fire them.
        rimebrand = self._weapon_buttons()[0]
        self.assertTrue(rimebrand.enabled)

    def test_chatbox_is_drawn_over_an_overlay(self):
        # The log is drawn last (after the overlay), in every mode — not just walk.
        self.app.push_log("hello from the log", (200, 200, 200))
        for overlay in ("character", "inventory", "skills_talents", "system"):
            self.app.overlay = overlay
            self.app.draw()  # must render the chatbox without error
        # read-only under menus: scroll/resize is gated to free-walk
        self.app.overlay = "character"
        self.assertFalse(self.app._log_interactive())
        self.app.overlay = ""
        self.app.mode = "walk"
        self.assertTrue(self.app._log_interactive())


if __name__ == "__main__":
    unittest.main()
