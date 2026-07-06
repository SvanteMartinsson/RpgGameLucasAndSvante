"""B75: staged round playback — one actor at a time, input locked, skip-click
behind a setting (default OFF).

Locks: a multi-actor round queues steps and logs them one tick at a time
(SEQUENCE_FRAMES apart), the first step lands instantly, input (issue_turn +
action buttons) is locked during playback, the finale (victory lines/mode)
waits for the queue, skip-click drains only when the setting is on, and
flush_sequence resolves everything for synchronous callers. Skips without
pygame.
"""

import collections
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.core import combat
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import pygame_battle as pb
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


def _two_actor_result(outcome="ongoing"):
    hero = combat.ActionResolution("attack", "Attack", "Hero", "Cave Bear")
    hero.events = ["Hero used Attack.", "Hero's Attack dealt 9 physical to Cave Bear."]
    bear = combat.ActionResolution("normal", "Normal attack", "Cave Bear", "Hero")
    bear.events = ["Cave Bear's Normal attack dealt 7 physical to Hero."]
    return combat.CombatTurnResult(
        outcome=outcome,
        events=hero.events + bear.events,
        action_resolutions=[hero, bear],
        xp_gained=5 if outcome == "victory" else 0,
        gold_gained=7 if outcome == "victory" else 0,
    )


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class RoundSequencingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _battle(self):
        engine = GameEngine(rng=random.Random(0))
        engine.start_new_game("Hero", "fighter")
        enemy = engine.content.enemies["cave_bear"].create_enemy()
        battle = pb.BattleApp(engine=engine, enemy=enemy, standalone=False,
                              event_log=collections.deque())
        battle.event_log.clear()
        return battle

    def test_first_step_is_instant_and_the_rest_wait_for_the_clock(self):
        battle = self._battle()
        battle._consume_result(_two_actor_result())
        texts = [str(t) for t, _c in battle.event_log]
        self.assertTrue(any("Hero used Attack" in t for t in texts))
        self.assertFalse(any("Cave Bear's Normal" in t for t in texts))   # queued
        self.assertTrue(battle._locked)
        for _ in range(pb.SEQUENCE_FRAMES):
            battle._tick_sequence()
        texts = [str(t) for t, _c in battle.event_log]
        self.assertTrue(any("Cave Bear's Normal" in str(t) for t, _c in battle.event_log))
        self.assertFalse(battle._locked)

    def test_input_is_locked_during_playback(self):
        battle = self._battle()
        battle._consume_result(_two_actor_result())
        self.assertTrue(battle._locked)
        turns_before = battle.engine.player.cooldowns
        battle.issue_turn("attack")          # swallowed — no new round starts
        self.assertTrue(battle._locked)
        snapshot = __import__("rpg_game.core.view", fromlist=["build_snapshot"]).build_snapshot(battle.engine)
        battle.buttons = []
        battle._build_action_buttons(snapshot)
        self.assertTrue(all(not b.enabled for b in battle.buttons))

    def test_victory_lines_wait_for_the_finale(self):
        battle = self._battle()
        battle._consume_result(_two_actor_result(outcome="victory"))
        texts = [str(t) for t, _c in battle.event_log]
        self.assertFalse(any("Victory!" in t for t in texts))   # not yet
        battle.flush_sequence()
        texts = [pb.chatlog.plain(t) for t, _c in battle.event_log]
        self.assertTrue(any("Victory!" in t for t in texts))
        self.assertEqual(battle.mode, "result")   # non-standalone shows the result

    def test_skip_click_only_works_with_the_setting_on(self):
        battle = self._battle()
        battle._combat_skip = False
        battle._consume_result(_two_actor_result())
        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(10, 10))
        battle.handle_event(click)
        self.assertTrue(battle._locked)          # default OFF: click does nothing
        battle._combat_skip = True
        battle.handle_event(click)
        self.assertFalse(battle._locked)         # ON: drains instantly

    def test_setting_default_is_off(self):
        from rpg_game.presentation import settings as user_settings
        self.assertFalse(user_settings.DEFAULTS["combat_skip"])


if __name__ == "__main__":
    unittest.main()
