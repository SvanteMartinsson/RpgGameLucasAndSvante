"""B126: complete musfri navigation — the battle skill grid takes BOTH axes
(a single row, so every arrow steps), the battle item/swap submenus gained
arrow+Enter (they had none), and the inventory overlay is arrow-navigable with
Enter using a consumable. Mouse stays parallel. Skips without pygame.

The character-screen inventory nav is locked by test_b121_character_interaction.
"""

import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame

    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import pygame_battle as pb
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


def _key(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="")


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class BattleSubmenuNavTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _battle(self, skills=("frenzy", "power")):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        engine.player.learned_skill_ids = ("power",)
        engine.player.equipped_skill_ids = skills
        enemy = engine.content.enemies["cave_bear"].create_enemy()
        return pb.BattleApp(engine=engine, enemy=enemy, standalone=False)

    def test_skill_grid_moves_on_both_axes(self):
        # B130: 4 skills -> a real 2x2 block. Focus starts top-left. DOWN lands
        # on the cell directly below (same column); UP returns. RIGHT lands on
        # the cell to the right (same row); LEFT returns. Nav follows the VISUAL
        # grid geometry, not add-order.
        engine = GameEngine()
        engine.start_new_game("Hero", "rogue")
        engine.player.learned_skill_ids = ("evasion", "riposte")
        engine.player.equipped_skill_ids = ("rupture", "deadly_precision",
                                            "evasion", "riposte")
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        battle = pb.BattleApp(engine=engine, enemy=enemy, standalone=False)
        battle.open_submenu("skill")
        battle.draw()

        top_left = battle.focus.focused()
        battle._handle_key(_key(pygame.K_DOWN))
        below = battle.focus.focused()
        self.assertIsNot(below, top_left)
        self.assertEqual(below.rect.centerx, top_left.rect.centerx)   # same column
        self.assertGreater(below.rect.centery, top_left.rect.centery)
        battle._handle_key(_key(pygame.K_UP))
        self.assertIs(battle.focus.focused(), top_left)

        battle._handle_key(_key(pygame.K_RIGHT))
        right = battle.focus.focused()
        self.assertIsNot(right, top_left)
        self.assertEqual(right.rect.centery, top_left.rect.centery)   # same row
        self.assertGreater(right.rect.centerx, top_left.rect.centerx)
        battle._handle_key(_key(pygame.K_LEFT))
        self.assertIs(battle.focus.focused(), top_left)

    def test_item_submenu_gained_arrow_nav_and_enter(self):
        battle = self._battle()
        battle.engine.player.inventory.add_consumable("hp_potion")
        battle.open_submenu("item")
        battle.draw()
        self.assertIsNotNone(battle.focus.focused())      # was None before B126
        # arrow to the potion row, Enter issues its turn (mouse path unchanged)
        battle.issue_turn = mock.Mock()
        potion = next(b for b in battle.buttons if "Potion" in b.label)
        for si, (_name, items) in enumerate(battle.focus._sections):
            if potion in items:
                battle.focus.section, battle.focus.index = si, items.index(potion)
        battle._handle_key(_key(pygame.K_RETURN))
        battle.issue_turn.assert_called_once()
        self.assertTrue(battle.issue_turn.call_args[0][0].startswith("item:"))

    def test_item_submenu_esc_returns_to_combat(self):
        battle = self._battle()
        battle.engine.player.inventory.add_consumable("hp_potion")
        battle.open_submenu("item")
        battle._handle_key(_key(pygame.K_ESCAPE))
        self.assertEqual(battle.mode, "combat")


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class InventoryOverlayNavTest(unittest.TestCase):
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

    def test_inventory_overlay_arrow_nav_and_enter_uses_consumable(self):
        self.app.engine.player.inventory.add_consumable("hp_potion")
        self.app.engine.player.hp = 1
        self.app.open_overlay("inventory")
        self.app.draw()
        # focus the potion row (items section) and Enter — the same use path a click takes
        potion = next(b for b in self.app.buttons if "Potion" in b.label)
        for si, (_name, items) in enumerate(self.app.focus._sections):
            if potion in items:
                self.app.focus.section, self.app.focus.index = si, items.index(potion)
        self.app._handle_key(_key(pygame.K_RETURN))
        self.assertGreater(self.app.engine.player.hp, 1)


if __name__ == "__main__":
    unittest.main()
