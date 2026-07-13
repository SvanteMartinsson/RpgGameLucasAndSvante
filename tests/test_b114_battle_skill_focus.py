"""B114: battle skills can be selected and confirmed without a mouse."""

import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from rpg_game.core.game import GameEngine
from rpg_game.presentation import chatlog
from rpg_game.presentation import pygame_battle as pb


class BattleSkillFocusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _battle(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        engine.player.learned_skill_ids = ("power",)
        engine.player.equipped_skill_ids = ("frenzy", "power")
        enemy = engine.content.enemies["cave_bear"].create_enemy()
        battle = pb.BattleApp(engine=engine, enemy=enemy, standalone=False)
        battle.open_submenu("skill")
        battle.draw()
        return battle

    def _key(self, battle, key):
        battle._handle_key(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=""))

    def test_first_skill_is_focused_on_open_and_arrows_move(self):
        battle = self._battle()
        self.assertEqual(battle.focus.focused().label, "Frenzy")
        self._key(battle, pygame.K_RIGHT)
        self.assertEqual(battle.focus.focused().label, "Power attack")
        # B130: two skills share one grid row, so LEFT (not UP) returns.
        self._key(battle, pygame.K_LEFT)
        self.assertEqual(battle.focus.focused().label, "Frenzy")

    def test_enter_confirms_enabled_focused_skill(self):
        battle = self._battle()
        self._key(battle, pygame.K_RIGHT)   # B130: step to the second skill in the row
        battle.issue_turn = mock.Mock()
        self._key(battle, pygame.K_RETURN)
        battle.issue_turn.assert_called_once_with("power")

    def test_blocked_skill_focus_enter_logs_full_mana_reason(self):
        battle = self._battle()
        battle.engine.player.mana = 2
        battle.draw()  # refresh blocker snapshot/buttons
        self.assertFalse(battle.focus.focused().enabled)
        self._key(battle, pygame.K_RETURN)
        self.assertEqual(chatlog.plain(battle.event_log[-1][0]), "Frenzy: Mana 2/6")
        self.assertEqual(battle.mode, "submenu")  # no turn consumed

    def test_escape_returns_to_combat(self):
        battle = self._battle()
        self._key(battle, pygame.K_ESCAPE)
        self.assertEqual(battle.mode, "combat")


if __name__ == "__main__":
    unittest.main()
