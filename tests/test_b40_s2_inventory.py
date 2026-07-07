"""B40 S2: the inventory follows the menu spec.

Locks: no redundant header strings (the playtest text collision is gone with
them), category rows carry no "(N)" counters and empty categories are dimmed
(restricted) but still selectable, item rows are bare names with the
action-relevant figure as a right-aligned value, rarity rides as the name's
colour, and stats/prices live in hover tooltips built by item_text. Also locks
the S2 plumbing: buttons render through the shared draw_menu_row and register
their tooltip rects with the hover tracker. Skips without pygame.
"""

import os
import re
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation import chatlog, item_text, ui
    from rpg_game.presentation import ui_text as T
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class InventoryMenuSpecTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()
        self.eng = self.app.engine

    def _draw_inventory(self, category="consumables"):
        self.app.overlay = "inventory"
        self.app.inventory_category = category
        self.app.draw()
        return self.app.buttons

    # -- spec point 5: no redundant subheaders (and no text collision) ------

    def test_the_inventory_hint_strings_are_gone(self):
        self.assertFalse(hasattr(T, "INVENTORY_HINT"))
        self.assertFalse(hasattr(T, "INV_EQUIP_HINT"))

    # -- spec point 4: no counters, empty categories dimmed -----------------

    def test_category_rows_have_no_counters(self):
        buttons = self._draw_inventory()
        category_labels = [b.label for b in buttons
                           if any(name in b.label for name in T.INV_CATEGORY_LABELS.values())]
        self.assertTrue(category_labels)
        for label in category_labels:
            self.assertIsNone(re.search(r"\(\d+\)", label), label)

    def test_empty_category_is_restricted_but_selectable(self):
        buttons = self._draw_inventory()
        amulet = next(b for b in buttons if "Amulet" in b.label)
        weapons = next(b for b in buttons if "Weapons" in b.label)
        self.assertTrue(amulet.restricted)        # fresh fighter owns no amulet
        self.assertFalse(weapons.restricted)      # but owns the starting weapon
        self.assertTrue(amulet.enabled)           # dimmed, not dead
        amulet.on_click()
        self.assertEqual(self.app.inventory_category, "amulet")

    # -- spec points 1/2/7: bare names, value figure, rarity colour, hover --

    def test_weapon_row_has_value_color_and_tooltip(self):
        buttons = self._draw_inventory("weapon")
        weapon_id = self.eng.player.equipped_weapon_id
        weapon = self.eng.content.weapons[weapon_id]
        row = next(b for b in buttons if b.label == weapon.name)
        self.assertEqual(row.value, "equipped")
        self.assertEqual(row.label_color, chatlog.rarity_color(weapon.rarity))
        self.assertIsInstance(row.tooltip, ui.Tooltip)
        self.assertTrue(any("Damage bonus" in line for line in row.tooltip.lines))
        self.assertTrue(any("needs Lv" in line for line in row.tooltip.lines))

    def test_consumable_row_shows_count_as_value_and_effect_on_hover(self):
        self.eng.player.inventory.consumables.clear()
        self.eng.player.inventory.add_consumable("hp_potion")
        self.eng.player.inventory.add_consumable("hp_potion")
        buttons = self._draw_inventory("consumables")
        row = next(b for b in buttons if b.label == "HP Potion")
        self.assertEqual(row.value, "x2")
        self.assertTrue(any("Restores" in line for line in row.tooltip.lines))
        self.assertIsNone(re.search(r"x\d", row.label))   # count is not in the name

    def test_misc_row_is_inert_but_still_explains_itself(self):
        self.eng.player.inventory.add_consumable("bone_dust")
        buttons = self._draw_inventory("miscellaneous")
        row = next(b for b in buttons if b.label == "Bone Dust")
        self.assertFalse(row.enabled)                     # inert junk
        self.assertIsInstance(row.tooltip, ui.Tooltip)
        self.assertTrue(any("Sells for" in line for line in row.tooltip.lines))

    def test_gear_row_uses_rarity_colour_not_bracket_text(self):
        self.eng.player.owned_gear_ids = ("tin_amulet",)
        buttons = self._draw_inventory("amulet")
        row = next(b for b in buttons if "Tin Amulet" in b.label)
        self.assertNotIn("[", row.label)                  # no "[common]" suffix
        gear = self.eng.content.gear_items["tin_amulet"]
        self.assertEqual(row.label_color, chatlog.rarity_color(gear.rarity))
        self.assertTrue(any("·" in line for line in row.tooltip.lines))

    # -- plumbing: tooltips register with the hover tracker on draw ---------

    def test_drawing_registers_tooltip_zones(self):
        self._draw_inventory("weapon")
        self.app.hover.begin()
        self.app._draw_buttons()
        self.assertTrue(self.app.hover._zones)

    def test_hover_dwell_pops_the_tooltip_payload(self):
        buttons = self._draw_inventory("weapon")
        row = next(b for b in buttons if b.tooltip is not None)
        tracker = ui.HoverTracker(delay_ms=0)
        tracker.begin()
        tracker.add(row.rect, row.tooltip)
        tracker.update(row.rect.center, now_ms=1)
        tracker.update(row.rect.center, now_ms=2)
        self.assertIs(tracker.active, row.tooltip)

    # -- geometry: both columns share the same top (collision fix) ----------

    def test_columns_are_top_aligned(self):
        buttons = self._draw_inventory("weapon")
        weapon = self.eng.content.weapons[self.eng.player.equipped_weapon_id]
        category_top = min(b.rect.y for b in buttons if "Consumables" in b.label)
        item_top = next(b.rect.y for b in buttons if b.label == weapon.name)
        self.assertEqual(category_top, item_top)


class ItemTextTest(unittest.TestCase):
    """item_text builders are pure — exercised without an app."""

    @unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
    def test_on_hit_lines_spell_out_procs(self):
        from rpg_game.core.data_loader import load_content
        content = load_content()
        ember = content.weapons["emberwand"]
        lines = item_text.on_hit_lines(ember)
        self.assertEqual(len(lines), len(ember.on_hit))
        self.assertIn("30%", lines[0])
        self.assertIn("burning", lines[0])

    @unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
    def test_tome_tooltip_names_the_taught_skill(self):
        from rpg_game.core.data_loader import load_content
        content = load_content()
        tome = content.items["tome_zap"]
        tip = item_text.consumable_tooltip(tome, content)
        self.assertTrue(any("Teaches" in line for line in tip.lines))
        self.assertTrue(any("Zap" in line for line in tip.lines))


if __name__ == "__main__":
    unittest.main()
