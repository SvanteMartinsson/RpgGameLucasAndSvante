"""B40 S3: the shop follows the menu spec.

Locks: buy/sell rows show name + price (value slot) with rarity as the name's
colour, stats + a vs-equipped delta live in the hover tooltip, unaffordable
rows are restricted (dimmed but clickable so the click explains), and the tome
shop follows the same row idiom. Skips without pygame.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation import chatlog, ui
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class ShopMenuSpecTest(unittest.TestCase):
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

    def _draw_store(self, category="weapons"):
        self.app.mode = "store"
        self.app.store_category = category
        self.app.draw()
        return self.app.buttons

    def _buy_rows(self, category="weapons"):
        buttons = self._draw_store(category)
        entry_ids = {e.id: e for e in self.eng.store_entries(category)}
        rows = []
        for b in buttons:
            match = next((e for e in entry_ids.values() if e.name == b.label), None)
            if match is not None:
                rows.append((match, b))
        return rows

    def test_buy_row_shows_price_as_value_and_stats_on_hover(self):
        rows = self._buy_rows("weapons")
        self.assertTrue(rows)
        entry, button = rows[0]
        self.assertEqual(button.value, f"{entry.price}g")
        self.assertIsInstance(button.tooltip, ui.Tooltip)
        self.assertTrue(any("Damage bonus" in line for line in button.tooltip.lines))
        weapon = self.eng.content.weapons[entry.id]
        self.assertEqual(button.label_color, chatlog.rarity_color(weapon.rarity))
        self.assertNotIn("g", button.label)   # price is not baked into the name

    def test_weapon_tooltip_carries_vs_equipped_delta(self):
        rows = self._buy_rows("weapons")
        entry, button = next((e, b) for e, b in rows
                             if e.id != self.eng.player.equipped_weapon_id)
        self.assertTrue(any("Vs equipped" in line for line in button.tooltip.lines))

    def test_unaffordable_row_is_restricted_but_still_explains(self):
        self.eng.player.gold = 0
        rows = self._buy_rows("weapons")
        entry, button = rows[0]
        self.assertTrue(button.restricted)
        self.assertTrue(button.enabled)          # click still fires...
        button.on_click()                        # ...and the engine explains
        self.assertEqual(self.eng.player.gold, 0)
        self.assertIn(entry.id, {e.id for e in self.eng.store_entries("weapons")})

    def test_sell_row_shows_count_and_value(self):
        self.eng.player.inventory.add_consumable("bone_dust")
        self.eng.player.inventory.add_consumable("bone_dust")
        buttons = self._draw_store("general")
        row = next(b for b in buttons if b.label == "Bone Dust")
        entry = next(e for e in self.eng.sellable_entries("general") if e.id == "bone_dust")
        self.assertEqual(row.value, f"x2 · {entry.value}g")
        self.assertTrue(any("Sells for" in line for line in row.tooltip.lines))

    def test_gear_delta_line_compares_against_worn_piece(self):
        self.eng.player.owned_gear_ids = ("tin_amulet", "sage_amulet")
        self.eng.equip_gear("tin_amulet", "amulet")
        line = self.app._gear_delta_line(self.eng.content.gear_items["sage_amulet"])
        self.assertTrue(line.startswith("Vs equipped:"))
        self.assertNotIn("(", line)              # spec point 3: no parentheses

    def test_tome_rows_follow_the_row_idiom(self):
        # Draw the mage-tower tome shop directly.
        self.app.tome_building = "tower"
        self.app.mode = "tome_shop"
        self.app.draw()
        tomes = self.eng.tomes_for_sale("tower")
        self.assertTrue(tomes)
        row = next(b for b in self.app.buttons if b.label == tomes[0].name)
        self.assertIn(row.value, (f"{tomes[0].price}g", "known", "owned"))
        self.assertIsInstance(row.tooltip, ui.Tooltip)
        self.assertTrue(any("Teaches" in line for line in row.tooltip.lines))


if __name__ == "__main__":
    unittest.main()
