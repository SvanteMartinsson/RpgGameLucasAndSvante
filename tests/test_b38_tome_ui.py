"""B38 tome UI: the mage-tower tome shop + inventory hookup (pygame).

The engine mechanic is covered by test_b38_tomes; this locks the presentation
wiring — a mage tower offers tomes, the shop mode buys them, a bought tome shows
in the inventory's usable (consumables) list, and closing returns to walk.
Skips without pygame/pytmx.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class TomeShopUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()
        self.app.engine.player.gold = 400
        self.app.engine.player.level = 8

    def test_mage_tower_offers_tomes_but_a_blacksmith_does_not(self):
        self.assertTrue(self.app.engine.tomes_for_sale("tower"))
        self.assertFalse(self.app.engine.tomes_for_sale("blacksmith"))

    def test_open_and_close_tome_shop_mode(self):
        self.app._open_tome_shop("tower")
        self.assertEqual(self.app.mode, "tome_shop")
        self.assertEqual(self.app.tome_building, "tower")
        self.app._close_tome_shop()
        self.assertEqual(self.app.mode, "walk")
        self.assertIsNone(self.app.tome_building)

    def test_buy_puts_a_usable_tome_in_the_inventory(self):
        self.app._open_tome_shop("tower")
        self.app._buy_tome("tome_frost_shard")
        self.assertEqual(self.app.engine.player.inventory.count("tome_frost_shard"), 1)
        rows = self.app.inventory_category_items("consumables")
        tome = [r for r in rows if r[0] == "tome_frost_shard"]
        self.assertTrue(tome)                 # shows in the usable tab
        self.assertIsNotNone(tome[0][2])      # has a click handler (use -> learn)

    def test_draw_tome_shop_renders_without_error(self):
        self.app.screen = pygame.Surface((1024, 680))
        self.app.tome_building = "tower"
        self.app.mode = "tome_shop"
        self.app.buttons = []
        self.app.hover.begin()
        self.app._draw_tome_shop()            # must not raise
        # a Back button + at least the 8 tome buttons registered
        self.assertGreaterEqual(len(self.app.buttons), 9)


if __name__ == "__main__":
    unittest.main()
