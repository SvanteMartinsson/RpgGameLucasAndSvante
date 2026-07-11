"""B63: world loot chests.

Core: opening pays gold + one rolled item through the normal LootDrop/collect
path, marks the chest opened (once), respects the tier cap, and the opened set
survives save/load. Data: >=4 chests per zone theme. Presentation (pygame):
chest tiles are solid, E next to a chest opens it, and every theme has both
sprites. Pygame parts skip without pygame.
"""

import os
import random
import unittest

from rpg_game.core import chests, persistence
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def _engine(seed=0):
    engine = GameEngine(rng=random.Random(seed))
    engine.start_new_game("Hero", "fighter")
    return engine


class ChestCoreTests(unittest.TestCase):
    def test_open_pays_gold_and_an_item_and_marks_opened(self):
        engine = _engine()
        gold_before = engine.player.gold
        result = engine.open_chest("chest_cainos_1")
        self.assertTrue(result.success)
        self.assertGreaterEqual(result.gold, 15)
        self.assertLessEqual(result.gold, 40)
        self.assertEqual(engine.player.gold, gold_before + result.gold)
        self.assertIsNotNone(result.drop)
        self.assertIn("chest_cainos_1", engine.player.opened_chest_ids)

    def test_a_chest_opens_only_once(self):
        engine = _engine()
        self.assertTrue(engine.open_chest("chest_cainos_1").success)
        again = engine.open_chest("chest_cainos_1")
        self.assertFalse(again.success)
        self.assertIn("empty", again.message.lower())

    def test_unknown_chest_fails(self):
        self.assertFalse(_engine().open_chest("chest_of_wonder").success)

    def test_tier_cap_filters_the_pool(self):
        content = load_content()
        heath4 = content.chests["chest_heath_4"]          # cap 5: tier-5 items eligible
        tiers = {int(e["rarity_tier"]) for e in chests.eligible_loot(heath4)}
        self.assertIn(5, tiers)
        capped = heath4.__class__(**{**heath4.__dict__, "tier_cap": 3})
        tiers_capped = {int(e["rarity_tier"]) for e in chests.eligible_loot(capped)}
        self.assertLessEqual(max(tiers_capped), 3)         # cap trims tier 5 out

    def test_rolled_items_never_exceed_the_cap(self):
        content = load_content()
        chest = content.chests["chest_heath_1"]            # cap 4
        rng = random.Random(5)
        for _ in range(300):
            _gold, entry = chests.roll_chest(chest, content, rng)
            self.assertLessEqual(int(entry["rarity_tier"]), chest.tier_cap)

    def test_opened_chests_survive_save_load(self):
        engine = _engine()
        engine.open_chest("chest_cainos_2")
        restored = persistence.deserialize_player(persistence.serialize_player(engine.player))
        self.assertIn("chest_cainos_2", restored.opened_chest_ids)


class ChestDataTests(unittest.TestCase):
    def test_at_least_four_chests_per_zone_theme(self):
        content = load_content()
        by_theme = {}
        for chest in content.chests.values():
            by_theme.setdefault(chest.theme, []).append(chest.id)
        for theme in ("cainos", "mork_skog", "cursed_mire", "grave_heath"):
            self.assertGreaterEqual(len(by_theme.get(theme, [])), 4, theme)

    def test_chest_loot_validation_rejects_unknown_items(self):
        from rpg_game.core.data_loader import _validate_chests
        from rpg_game.core.entities import ChestDef
        content = load_content()
        broken = {"x": ChestDef(id="x", tile=(0, 0), theme="cainos", gold_min=1,
                                gold_max=2, tier_cap=3,
                                loot_table=({"item_id": "no_such", "weight": 1, "rarity_tier": 1},))}
        with self.assertRaisesRegex(ValueError, "chest x references unknown item"):
            _validate_chests(broken, content.weapons, content.gear_items, content.items)


try:
    import pygame
    from rpg_game.presentation import chatlog
    from rpg_game.presentation.pygame_overworld import OverworldApp
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class ChestUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()

    def test_chest_tiles_are_solid(self):
        for tile in self.app.chest_tiles:
            self.assertIn(tile, self.app.world.blocked, tile)

    def test_every_theme_has_closed_and_open_sprites(self):
        for theme in ("cainos", "mork_skog", "cursed_mire", "grave_heath"):
            self.assertIsNotNone(self.app._chest_sprites.get((theme, False)), theme)
            self.assertIsNotNone(self.app._chest_sprites.get((theme, True)), theme)

    def test_e_next_to_a_chest_opens_it_and_logs_the_loot(self):
        self.app.world.set_tile(29, 40)          # beside chest_cainos_1 (30,40)
        self.assertTrue(self.app._try_open_chest())
        self.assertIn("chest_cainos_1", self.app.engine.player.opened_chest_ids)
        texts = [chatlog.plain(text) for text, _ in self.app.event_log]
        self.assertTrue(any("open the chest" in t for t in texts))
        # B100: the acquisition row names its source and carries the gold.
        self.assertTrue(any(t.startswith("Opened chest: ") and "gold" in t for t in texts))

    def test_e_far_from_any_chest_does_nothing(self):
        self.app.world.set_tile(45, 45)
        self.assertFalse(self.app._try_open_chest())

    def test_every_chest_is_adjacent_to_walkable_ground(self):
        # a chest you cannot stand next to can never be opened
        for tile in self.app.chest_tiles:
            x, y = tile
            neighbours = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
            self.assertTrue(any(n not in self.app.world.blocked for n in neighbours), tile)


if __name__ == "__main__":
    unittest.main()
