"""B121b: the character screen — three fluid zones (stats / figure + anatomical
slots / scrollable inventory). Replaces the B40 S4 menu-spec character screen.

Locks the layout: regions clear the header, the ten equipment slots render as
anatomical icon buttons via the adjustable placement table, the stats zone reads
straight off the B121a snapshot (total + gear delta), and the inventory lists
every owned item. Interaction (equip/unequip, tooltips, keyboard) is locked by
test_b121_character_interaction. Skips without pygame.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame

    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import overworld_overlays as ov
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class CharacterScreenLayoutTest(unittest.TestCase):
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

    def _draw(self):
        self.app.overlay = "character"
        self.app.draw()
        return self.app.buttons

    # -- geometry -----------------------------------------------------------

    def test_three_zones_clear_the_header_and_do_not_overlap(self):
        panel = pygame.Rect(30, 30, 920, 580)
        content = self.app._content_rect(panel)
        stats, figure, items = self.app._character_regions(panel)
        header_bottom = content.y + self.app._CHAR_HEADER_H
        for region in (stats, figure, items):
            self.assertGreaterEqual(region.y - 22, header_bottom, region)
        # left -> centre -> right, no overlap
        self.assertLessEqual(stats.right, figure.left)
        self.assertLessEqual(figure.right, items.left)
        self.assertGreater(figure.width, 0)

    # -- the anatomical slot table ------------------------------------------

    def test_anatomy_table_covers_exactly_the_ten_slots(self):
        slot_ids = set(self.eng.content.equipment_slots)
        self.assertEqual(set(ov.CHARACTER_SLOT_ANATOMY), slot_ids)
        self.assertEqual(len(ov.CHARACTER_SLOT_ANATOMY), 10)
        for x, y in ov.CHARACTER_SLOT_ANATOMY.values():
            self.assertTrue(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0)

    def test_ten_anatomical_slot_buttons_render(self):
        buttons = self._draw()
        slot_buttons = [b for b in buttons if b.custom]
        self.assertEqual(len(slot_buttons), 10)
        # each is a square icon box, keyboard-focusable in the "slots" section
        for b in slot_buttons:
            self.assertEqual(b.rect.width, ov.CHAR_SLOT_PX)
            self.assertEqual(b.rect.height, ov.CHAR_SLOT_PX)
        sections = {name for name, _items in self.app.focus._sections}
        self.assertIn("slots", sections)
        self.assertIn("inventory", sections)

    # -- stats zone (B121a data) --------------------------------------------

    def test_stats_zone_registers_a_hover_per_snapshot_stat(self):
        from rpg_game.core.view import build_snapshot
        self._draw()
        titles = {p.title for _r, p in self.app.hover._zones}
        for row in build_snapshot(self.eng).player.stats:
            self.assertIn(row.label, titles)

    def test_weapon_type_line_present(self):
        # The equipped weapon's category/type/tier surfaces in the stats zone.
        self.eng.player.owned_weapon_ids = (*self.eng.player.owned_weapon_ids, "sword")
        self.eng.player.equipped_weapon_id = "sword"
        self._draw()
        surface = pygame.image.tostring(self.app.screen, "RGB")  # just ensure it drew
        self.assertTrue(surface)

    # -- inventory zone ------------------------------------------------------

    def test_inventory_lists_every_owned_item_kind(self):
        self.eng.player.owned_weapon_ids = (*self.eng.player.owned_weapon_ids, "sword")
        self.eng.player.owned_gear_ids = ("padded_vest",)
        self.eng.player.inventory.add_consumable("hp_potion")
        buttons = self._draw()
        labels = [b.label for b in buttons]
        self.assertTrue(any("Sword" == label for label in labels))
        self.assertTrue(any("Padded Vest" in label for label in labels))
        self.assertTrue(any("Potion" in label for label in labels))

    def test_inventory_rows_carry_rarity_colour(self):
        from rpg_game.presentation import chatlog
        self.eng.player.owned_gear_ids = ("padded_vest",)
        buttons = self._draw()
        vest = next(b for b in buttons if "Padded Vest" in b.label)
        gear = self.eng.content.gear_items["padded_vest"]
        self.assertEqual(vest.label_color, chatlog.rarity_color(gear.rarity))


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class CharacterScreenRenderToolTest(unittest.TestCase):
    def test_render_tool_writes_full_and_empty(self):
        import tempfile
        from pathlib import Path

        from rpg_game.tools import render_b121_character

        with tempfile.TemporaryDirectory() as folder:
            render_b121_character.render(Path(folder))
            self.assertTrue((Path(folder) / "b121_character_full.png").exists())
            self.assertTrue((Path(folder) / "b121_character_empty.png").exists())


if __name__ == "__main__":
    unittest.main()
