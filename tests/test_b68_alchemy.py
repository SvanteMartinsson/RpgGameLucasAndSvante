"""B68: alchemy — brew potions from materials + gold.

Locks: a brew consumes exactly its materials + gold and yields the output;
blockers (gold/materials) refuse without consuming anything; recipes validate
at load (unknown output/material fails); brewing stays cheaper than the shop
price but never free; the apothecary screen dims unaffordable rows.
"""

import os
import random
import unittest

from rpg_game.core import alchemy
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def _engine():
    engine = GameEngine(rng=random.Random(0))
    engine.start_new_game("Hero", "fighter")
    return engine


class BrewCoreTests(unittest.TestCase):
    def test_brew_consumes_and_produces(self):
        engine = _engine()
        player = engine.player
        player.gold = 100
        for _ in range(3):
            player.inventory.add_consumable("bone_dust")
        result = engine.brew("brew_hp")
        self.assertTrue(result.success)
        self.assertEqual(player.inventory.count("hp_potion"), 1)
        self.assertEqual(player.inventory.count("bone_dust"), 0)
        self.assertEqual(player.gold, 80)

    def test_missing_materials_refuse_without_consuming(self):
        engine = _engine()
        engine.player.gold = 100
        result = engine.brew("brew_hp")
        self.assertFalse(result.success)
        self.assertEqual(engine.player.gold, 100)

    def test_missing_gold_refuses_without_consuming(self):
        engine = _engine()
        player = engine.player
        player.gold = 0
        for _ in range(3):
            player.inventory.add_consumable("bone_dust")
        result = engine.brew("brew_hp")
        self.assertFalse(result.success)
        self.assertEqual(player.inventory.count("bone_dust"), 3)

    def test_unknown_recipe_fails(self):
        self.assertFalse(_engine().brew("brew_of_wonder").success)

    def test_every_brew_is_cheaper_than_the_shop_but_never_free(self):
        content = load_content()
        for recipe in content.brew_recipes.values():
            shop_price = content.items[recipe.output].price
            material_value = sum(content.items[mid].price * count
                                 for mid, count in recipe.materials)
            self.assertLess(recipe.gold + material_value, shop_price,
                            f"{recipe.id} is not worth brewing")
            self.assertGreater(recipe.gold, 0, f"{recipe.id} is free")


class BrewValidationTests(unittest.TestCase):
    def test_unknown_output_fails_at_load(self):
        from rpg_game.core.data_loader import _validate_brews
        from rpg_game.core.alchemy import BrewRecipe
        content = load_content()
        broken = {"x": BrewRecipe(id="x", output="no_such", gold=1, materials=())}
        with self.assertRaisesRegex(ValueError, "outputs unknown"):
            _validate_brews(broken, content.items)

    def test_unknown_material_fails_at_load(self):
        from rpg_game.core.data_loader import _validate_brews
        from rpg_game.core.alchemy import BrewRecipe
        content = load_content()
        broken = {"x": alchemy.BrewRecipe(id="x", output="hp_potion", gold=1,
                                          materials=(("no_such", 1),))}
        with self.assertRaisesRegex(ValueError, "unknown material"):
            _validate_brews(broken, content.items)


try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class ApothecaryScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_rows_dim_until_affordable(self):
        app = OverworldApp()
        app.screen = pygame.Surface((1024, 680))
        player = app.engine.player
        player.gold = 55
        for _ in range(3):
            player.inventory.add_consumable("bone_dust")
        app.mode = "apothecary"
        app.buttons = []
        app.hover.begin()
        app._draw_apothecary()
        by_label = {b.label: b for b in app.buttons if "—" in b.label}
        hp_row = next(b for l, b in by_label.items() if l.startswith("HP Potion"))
        mana_row = next(b for l, b in by_label.items() if l.startswith("Mana Potion"))
        self.assertTrue(hp_row.enabled)        # 3/3 bone dust + gold
        self.assertFalse(mana_row.enabled)     # no tattered cloth

    def test_clicking_a_row_brews(self):
        app = OverworldApp()
        player = app.engine.player
        player.gold = 55
        for _ in range(3):
            player.inventory.add_consumable("bone_dust")
        app._brew("brew_hp")
        self.assertEqual(player.inventory.count("hp_potion"), 1)


if __name__ == "__main__":
    unittest.main()
