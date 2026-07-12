"""B107 S1: hero idle + attack choreography per the approved battle mock.

Locks: the ms->frame parameters, the action->weight mapping table, the
timeline (windup/dash/impact/return), the impact-spawned weighted numbers,
the idle A-B-C-B stepping, skip-click's jump-to-end-state, and determinism —
the choreography draws NOTHING from the engine's RNG stream.
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
    from rpg_game.presentation import battle_choreo
    from rpg_game.presentation import pygame_battle as pb
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


def _resolution(components=(), style="", action_id="attack"):
    resolution = combat.ActionResolution(action_id, "A", "Hero", "T")
    resolution.damage_components = [combat.DamageComponent(a, t) for a, t in components]
    resolution.rolled_style_id = style
    return resolution


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class WeightMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.content = GameEngine().content

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_non_damage_actions_get_no_choreography(self):
        self.assertIsNone(battle_choreo.action_weight(_resolution(), None))

    def test_base_attack_maps_by_rolled_style(self):
        hit = (((10, "physical"),))
        for style, expected in (("quick", "quick"), ("power", "power"), ("normal", "normal")):
            res = _resolution(hit, style=style)
            self.assertEqual(battle_choreo.action_weight(res, None), expected, style)

    def test_skill_multiplier_bands(self):
        hit = (((10, "physical"),))
        # >=1.5 -> power (e.g. a heavy nuke), <1.0 -> quick, else normal
        heavy = next(a for a in self.content.actions.values()
                     if a.kind == "skill" and any(
                         e.type == "instant_damage" and (e.multiplier or 1.0) >= 1.5
                         and getattr(e, "hits", 1) == 1 for e in a.effects)
                     and not any(getattr(e, "hits", 1) > 1 for e in a.effects))
        self.assertEqual(battle_choreo.action_weight(
            _resolution(hit, action_id=heavy.id), heavy), "power", heavy.id)
        multi = next(a for a in self.content.actions.values()
                     if any(getattr(e, "hits", 1) > 1 for e in a.effects))
        self.assertEqual(battle_choreo.action_weight(
            _resolution(hit, action_id=multi.id), multi), "quick", multi.id)

    def test_mock_parameters_survive_ms_conversion(self):
        w = battle_choreo.WEIGHTS
        self.assertEqual(w["quick"]["dash_px"], 90)
        self.assertEqual(w["quick"]["dash"], battle_choreo.frames(110))
        self.assertEqual(w["normal"]["dash_px"], 120)
        self.assertEqual(w["power"]["windup_px"], -28)
        self.assertEqual(w["power"]["num_color"], (0xF4, 0xD0, 0x6F))
        self.assertEqual((w["quick"]["num_size"], w["normal"]["num_size"],
                          w["power"]["num_size"]), (28, 32, 40))


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class TimelineTests(unittest.TestCase):
    def test_power_winds_up_backwards_then_dashes_and_returns(self):
        choreo = battle_choreo.Choreography("power")
        offsets = []
        while not choreo.done:
            choreo.update()
            offsets.append(choreo.hero_offset())
        self.assertLess(min(offsets[:battle_choreo.WEIGHTS["power"]["windup"]]), 0)
        self.assertEqual(max(offsets), battle_choreo.WEIGHTS["power"]["dash_px"])
        self.assertEqual(offsets[-1], 0)                    # returned home
        self.assertTrue(choreo.impact_done)

    def test_fx_plays_steps4_forwards_after_impact(self):
        choreo = battle_choreo.Choreography("quick")
        seen = []
        while not choreo.done:
            choreo.update()
            frame = choreo.fx_frame()
            if frame is not None:
                seen.append(frame)
        self.assertEqual(sorted(set(seen)), [0, 1, 2, 3])
        self.assertEqual(seen, sorted(seen))                # forwards, no reverse

    def test_finish_jumps_to_end_state_and_still_delivers_impact(self):
        choreo = battle_choreo.Choreography("normal")
        choreo.update()
        choreo.finish()
        self.assertTrue(choreo.done)
        self.assertTrue(choreo.impact_done)
        self.assertEqual(choreo.hero_offset(), 0)


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class HeroIdleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_sheet_slices_to_four_scaled_frames(self):
        frames = pb.hero_idle_frames()
        self.assertIsNotNone(frames)
        self.assertEqual(len(frames), 4)
        fw, fh = pb.HERO_FRAME_SIZE
        self.assertEqual(frames[0].get_size(), (fw * pb.HERO_SCALE, fh * pb.HERO_SCALE))
        self.assertEqual(fh * pb.HERO_SCALE, 87)   # B111: half-height battle hero
        self.assertLess(frames[0].get_height(), pb.TIER_HEIGHT["small"])

    def test_idle_steps_a_b_c_b(self):
        period = pb.HERO_IDLE_PERIOD
        sequence = [pb.hero_idle_index(t) for t in range(period)]
        # 4 discrete steps, in A-B-C-B order
        compact = [sequence[0]]
        for v in sequence:
            if v != compact[-1]:
                compact.append(v)
        self.assertEqual(compact, [0, 1, 2, 1])


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _battle(self, seed=0, fx=True):
        engine = GameEngine(rng=random.Random(seed))
        engine.start_new_game("Hero", "fighter")
        enemy = engine.content.enemies["cave_bear"].create_enemy()
        battle = pb.BattleApp(engine=engine, enemy=enemy, standalone=False,
                              event_log=collections.deque())
        battle._combat_fx = fx
        return battle

    def test_choreography_consumes_no_engine_rng(self):
        # Same seed, fx on vs off: the round's mechanical outcome is identical
        # and the engine RNG ends in the same state -> pure presentation.
        states = []
        logs = []
        for fx in (True, False):
            battle = self._battle(seed=11, fx=fx)
            battle.issue_turn("attack")
            battle.flush_sequence()
            for _ in range(90):     # run the presentation clock dry
                battle.draw()
            states.append(battle.engine.rng.getstate())
            logs.append((battle.enemy.hp if battle.enemy else None,
                         battle.engine.player.hp))
        self.assertEqual(states[0], states[1])
        self.assertEqual(logs[0], logs[1])

    def test_playback_holds_while_the_swing_is_live(self):
        battle = self._battle(seed=3)
        battle.issue_turn("attack")
        if battle._choreo is not None:
            queued = len(battle._sequence)
            battle._tick_sequence()      # must NOT advance mid-choreography
            self.assertEqual(len(battle._sequence), queued)

    def test_flush_fast_forwards_choreography_and_death_fade(self):
        battle = self._battle(seed=5)
        battle.enemy.hp = 1              # guarantee the kill
        battle.issue_turn("attack")
        battle.flush_sequence()
        self.assertIsNone(battle._choreo)
        self.assertEqual(battle._choreo_pending, [])
        if battle._death_fade >= 0:      # ghost jumped to its end state
            self.assertEqual(battle._death_fade, battle_choreo.DEATH_FADE)

    def test_action_buttons_use_badges_not_bracket_text(self):
        battle = self._battle()
        battle.draw()
        labels = [b.label for b in battle.buttons]
        self.assertTrue(labels)
        for label in labels:
            self.assertFalse(label.startswith("["), label)
        hotkeys = {b.hotkey for b in battle.buttons if b.hotkey}
        self.assertTrue({"a", "s"} <= hotkeys)


if __name__ == "__main__":
    unittest.main()
