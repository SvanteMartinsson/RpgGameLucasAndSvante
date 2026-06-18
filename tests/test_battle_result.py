"""Single-battle press-to-continue result view.

Skips when pygame/pytmx are not installed.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation.pygame_battle import BattleApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


def _wild_enemy(engine):
    for place_id, place in engine.content.places.items():
        if place.encounters:
            engine.player.current_place_id = place_id
            break
    return engine.create_encounter()


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class BattleResultTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _fight_to_end(self, battle):
        for _ in range(800):
            if battle.mode == "result" or not battle.running:
                return
            if battle.mode == "stat_choice":
                battle.apply_stat("hp")
            else:
                battle.issue_turn("attack")

    def test_single_battle_pauses_on_result_before_returning(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        battle = BattleApp(engine=engine, enemy=_wild_enemy(engine), standalone=False)
        self._fight_to_end(battle)
        self.assertEqual(battle.mode, "result")
        self.assertTrue(battle.running)          # not yet returned to overworld
        self.assertEqual(battle.outcome, "")     # outcome only set on continue
        self.assertIn(battle._pending_outcome, ("victory", "defeat", "fled"))

    def test_any_key_continues_and_finishes(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        battle = BattleApp(engine=engine, enemy=_wild_enemy(engine), standalone=False)
        self._fight_to_end(battle)
        pending = battle._pending_outcome
        battle._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, unicode=" "))
        self.assertFalse(battle.running)
        self.assertEqual(battle.outcome, pending)

    def test_standalone_mode_unchanged(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        battle = BattleApp(engine=engine)  # standalone demo mode
        for _ in range(800):
            if battle.mode in ("victory_idle", "game_over") or not battle.running:
                break
            if battle.mode == "stat_choice":
                battle.apply_stat("hp")
            else:
                battle.issue_turn("attack")
        self.assertIn(battle.mode, ("victory_idle", "game_over"))


if __name__ == "__main__":
    unittest.main()
