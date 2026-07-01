"""Menu-foundation Slice 1, Unit 1: ONE unified Button.

Both pygame screens now share a single Button dataclass (the superset of the two
old ones). This locks: the field/default contract, that both screens reference
the SAME class (single source of truth), and that the migration stayed
behaviour-preserving — battle buttons still carry their hotkey and overworld
level-locked rows still carry `restricted`. Skips without pygame.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import ui
    from rpg_game.presentation import pygame_battle as pb
    from rpg_game.presentation import pygame_overworld as po

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class UnifiedButtonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_button_is_the_superset_with_expected_defaults(self):
        b = ui.Button(pygame.Rect(0, 0, 10, 10), "Go", lambda: None)
        self.assertEqual((b.enabled, b.restricted, b.hotkey, b.sublabel),
                         (True, False, "", ""))
        b2 = ui.Button(pygame.Rect(0, 0, 1, 1), "X", lambda: None,
                       enabled=False, restricted=True, hotkey="a", sublabel="sub")
        self.assertEqual((b2.enabled, b2.restricted, b2.hotkey, b2.sublabel),
                         (False, True, "a", "sub"))

    def test_both_screens_use_the_one_button_class(self):
        # single source of truth: no more two separate Button dataclasses
        self.assertIs(pb.Button, ui.Button)
        self.assertIs(po.Button, ui.Button)

    def test_on_click_may_be_a_non_callable(self):
        # the start menu stores a plain string result in on_click
        b = ui.Button(pygame.Rect(0, 0, 1, 1), "New Game", "new_game")
        self.assertEqual(b.on_click, "new_game")

    def test_battle_action_buttons_keep_their_hotkeys(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "hunter")
        enemy = engine.content.enemies["cave_bear"].create_enemy()
        battle = pb.BattleApp(engine=engine, enemy=enemy, standalone=False)
        battle.set_mode("combat")
        battle.draw()
        # every action button carries a hotkey (migration used hotkey=... keyword,
        # not the 5th positional which is now `restricted`).
        self.assertTrue(battle.buttons)
        for b in battle.buttons:
            self.assertTrue(b.hotkey, f"{b.label} lost its hotkey")
            self.assertFalse(b.restricted, f"{b.label} mis-set restricted")

    def test_overworld_add_button_sets_restricted(self):
        app = po.OverworldApp()
        app.buttons = []
        app._add_button(pygame.Rect(0, 0, 10, 10), "Locked", lambda: None,
                        enabled=True, restricted=True)
        self.assertTrue(app.buttons[-1].restricted)
        self.assertEqual(app.buttons[-1].hotkey, "")   # 5th positional is restricted, not hotkey


if __name__ == "__main__":
    unittest.main()
