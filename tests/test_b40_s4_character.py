"""B40 S4: the character screen follows the menu spec.

Locks: the header block and the stats label can no longer collide (regions
start below the 3-line header), no parenthetical derived values anywhere (the
weapon bonus moved off the Damage row into its hover tooltip), stat rows
register hover explanations, slot rows carry the owned count as a value (no
"(N)" counter) plus the worn piece's tooltip, and option rows are uniform menu
rows with the equip-decision figure as the value. Skips without pygame.
"""

import os
import re
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation import chatlog, ui
    from rpg_game.presentation import ui_text as T
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class CharacterMenuSpecTest(unittest.TestCase):
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

    def _draw_character(self, slot="weapon"):
        self.app.overlay = "character"
        self.app.selected_equipment_slot = slot
        self.app.draw()
        return self.app.buttons

    # -- geometry: the playtest collision is structurally impossible --------

    def test_columns_start_below_the_header_block(self):
        panel = pygame.Rect(40, 40, 920, 580)
        content = self.app._content_rect(panel)
        stats, slots, items = self.app._character_regions(panel)
        header_bottom = content.y + self.app._CHAR_HEADER_H
        # the section labels sit at region.y - 22 and must clear the header
        for region in (stats, slots):
            self.assertGreaterEqual(region.y - 22, header_bottom, region)

    # -- spec point 3: no parenthetical derived values -----------------------

    def test_no_parenthetical_values_on_any_character_row(self):
        self.eng.player.owned_gear_ids = ("tin_amulet", "padded_vest")
        for slot in ("weapon", "chest", "amulet"):
            for b in self._draw_character(slot):
                self.assertIsNone(re.search(r"\(\d", b.label), b.label)
                self.assertIsNone(re.search(r"\(", b.value or ""), b.value)
                self.assertNotIn("[", b.label, b.label)

    def test_weapon_bonus_lives_in_the_damage_tooltip(self):
        # The starter weapon has bonus 0 (no "+0" noise) — equip a real one.
        self.eng.player.owned_weapon_ids = (*self.eng.player.owned_weapon_ids, "sword")
        self.eng.player.equipped_weapon_id = "sword"
        self._draw_character()
        zones = [payload for _r, payload in self.app.hover._zones
                 if isinstance(payload, ui.Tooltip)]
        damage = next(t for t in zones if t.title == "Damage")
        bonus = self.eng.content.weapons["sword"].damage_bonus
        self.assertTrue(any(f"+{bonus}" in line for line in damage.lines), damage.lines)
        self.assertIn("weapon", damage.body)

    def test_every_stat_row_has_a_hover_explanation(self):
        self._draw_character()
        titles = {payload.title for _r, payload in self.app.hover._zones
                  if isinstance(payload, ui.Tooltip)}
        for label in ("HP", "Wisdom", "Damage", "Armor", "Speed", "Crit"):
            self.assertIn(label, titles)

    def test_wisdom_help_names_the_mana_rule(self):
        from rpg_game.core.entities import MANA_PER_WISDOM
        self.assertIn(str(MANA_PER_WISDOM), T.stat_help("wisdom"))

    # -- slot rows: owned count as value, worn piece on hover ---------------

    def test_empty_slot_row_marks_waiting_candidates(self):
        self.eng.player.owned_gear_ids = ("tin_amulet", "sage_amulet")
        buttons = self._draw_character("amulet")
        row = next(b for b in buttons if "Amulet:" in b.label)
        self.assertEqual(row.value, "x2")              # empty slot, 2 candidates

    def test_worn_slot_gives_the_row_to_the_name(self):
        # A worn slot drops the count value so the item name fits un-cut; the
        # playtest-era truncation ("> Weapon...") must not return.
        buttons = self._draw_character("weapon")
        row = next(b for b in buttons if "Weapon" in b.label and ":" in b.label)
        self.assertEqual(row.value, "")                # worn slot: no count
        self.assertIn("Worn Shortsword", row.label)
        label_w = self.app.font.size(row.label)[0]
        self.assertLessEqual(label_w + 24, row.rect.width,
                             f"'{row.label}' overflows {row.rect.width}px")

    def test_worn_slot_offers_its_tooltip(self):
        self.eng.player.owned_gear_ids = ("padded_vest",)
        self.eng.equip_gear("padded_vest", "chest")
        buttons = self._draw_character("chest")
        row = next(b for b in buttons if "Chest: Padded Vest" in b.label)
        self.assertIsInstance(row.tooltip, ui.Tooltip)
        self.assertEqual(row.tooltip.title, "Padded Vest")

    # -- option rows: uniform menu rows with the decision figure ------------

    def test_weapon_option_rows_use_value_and_rarity_colour(self):
        self.eng.player.owned_weapon_ids = (
            *self.eng.player.owned_weapon_ids, "sword", "rimebrand")
        buttons = self._draw_character("weapon")
        equipped_id = self.eng.player.equipped_weapon_id
        equipped_name = self.eng.content.weapons[equipped_id].name
        equipped_row = next(b for b in buttons if b.label == equipped_name)
        self.assertEqual(equipped_row.value, "equipped")
        sword = next(b for b in buttons if b.label == "Sword")
        bonus = (self.eng.content.weapons["sword"].damage_bonus
                 - self.eng.content.weapons[equipped_id].damage_bonus)
        self.assertEqual(sword.value, f"{bonus:+} dmg")
        self.assertEqual(sword.label_color,
                         chatlog.rarity_color(self.eng.content.weapons["sword"].rarity))
        locked = next(b for b in buttons if b.label == "Rimebrand")
        self.assertTrue(locked.restricted)
        self.assertTrue(locked.value.startswith("needs Lv"))

    def test_gear_option_rows_show_delta_as_value(self):
        self.eng.player.owned_gear_ids = ("tin_amulet", "sage_amulet")
        self.eng.equip_gear("tin_amulet", "amulet")
        buttons = self._draw_character("amulet")
        row = next(b for b in buttons if b.label == "Sage Amulet")
        self.assertTrue(row.value)                     # a delta or 'same'
        self.assertNotIn("(", row.value)
        self.assertIsInstance(row.tooltip, ui.Tooltip)


if __name__ == "__main__":
    unittest.main()
