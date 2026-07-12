"""B109: animated enemy idle sheets in battle.

Locks the STEG 0 measurement (all 32 sheets are 4-frame horizontal strips, not
square), the id<->file mapping (cave_bear uses the bear sheet), the two authored
shapes (unique-4 cycle vs baked A-B-C-B pendulum), the toggle fallback to the
static still, and determinism (the idle draws NOTHING from the engine RNG).
"""

import collections
import glob
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import pygame_battle as pb
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


def _sheet_ids():
    files = glob.glob(os.path.join(pb.ENEMY_IDLE_DIR, "*_idle_sheet.png"))
    return sorted(os.path.basename(f)[:-len("_idle_sheet.png")] for f in files)


def _px(surface):
    return pygame.image.tostring(surface, "RGBA")


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class SheetLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_every_sheet_is_a_four_frame_strip(self):
        # STEG 0: all 32 widths divide by 4; frames are width//4 x height.
        ids = _sheet_ids()
        self.assertEqual(len(ids), 32)
        for sid in ids:
            path = os.path.join(pb.ENEMY_IDLE_DIR, f"{sid}_idle_sheet.png")
            sheet = pygame.image.load(path).convert_alpha()
            self.assertEqual(sheet.get_width() % pb.ENEMY_IDLE_FRAMES, 0, sid)

    def test_frames_scale_to_tier_height(self):
        # A direct-match enemy: 4 frames, each at the enemy's tier height.
        frames = pb.enemy_idle_frames("ghoul")
        self.assertIsNotNone(frames)
        self.assertEqual(len(frames), 4)
        for f in frames:
            self.assertEqual(f.get_height(), pb.enemy_sprite_height("ghoul"))

    def test_cave_bear_uses_the_bear_sheet(self):
        # The one id<->file glitch: enemy id cave_bear, sheet file bear.
        self.assertTrue(pb._enemy_idle_sheet_path("cave_bear").endswith("bear_idle_sheet.png"))
        self.assertEqual(len(pb.enemy_idle_frames("cave_bear")), 4)

    def test_missing_sheet_returns_none(self):
        # A wild enemy with a still but no animated sheet -> None (still fallback).
        self.assertIsNone(pb.enemy_idle_frames("skeleton_warrior"))

    def test_pendulum_sheet_has_duplicate_tail_frame(self):
        # giant_rat is a measured pendulum (frame 3 == frame 1): the loop swings
        # back on the baked duplicate rather than a separate reverse pass.
        frames = pb.enemy_idle_frames("giant_rat")
        self.assertEqual(_px(frames[3]), _px(frames[1]))
        self.assertNotEqual(_px(frames[0]), _px(frames[1]))

    def test_cycle_sheet_has_four_distinct_frames(self):
        # ghoul is a measured 4-unique cycle: no two frames are identical.
        frames = pb.enemy_idle_frames("ghoul")
        seen = {_px(f) for f in frames}
        self.assertEqual(len(seen), 4)


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class IdleIndexTests(unittest.TestCase):
    def test_index_walks_0_1_2_3_in_order(self):
        period = pb.enemy_idle_period("ghoul")
        seq = [pb.enemy_idle_index("ghoul", t) for t in range(period)]
        self.assertEqual(min(seq), 0)
        self.assertEqual(max(seq), 3)
        compact = [seq[0]]
        for v in seq:
            if v != compact[-1]:
                compact.append(v)
        self.assertEqual(compact, [0, 1, 2, 3])   # forward cycle, no reverse

    def test_period_override_shortens_the_cycle(self):
        try:
            pb.ENEMY_IDLE_PERIOD_MS["ghoul"] = 300
            self.assertEqual(pb.enemy_idle_period("ghoul"),
                             pb.battle_choreo.frames(300))
            self.assertLess(pb.enemy_idle_period("ghoul"), pb.ENEMY_IDLE_PERIOD)
        finally:
            pb.ENEMY_IDLE_PERIOD_MS.pop("ghoul", None)


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class ToggleAndDeterminismTests(unittest.TestCase):
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

    def test_toggle_off_uses_the_static_still(self):
        battle = self._battle(fx=False)
        got = battle._enemy_stage_sprite(battle.enemy)
        self.assertIs(got, pb.enemy_sprite("cave_bear"))   # not an idle frame

    def test_toggle_on_uses_an_idle_frame(self):
        battle = self._battle(fx=True)
        frames = pb.enemy_idle_frames("cave_bear")
        self.assertIn(battle._enemy_stage_sprite(battle.enemy), frames)

    def test_idle_consumes_no_engine_rng(self):
        # Same seed, animations on vs off: identical mechanical outcome and RNG
        # end-state -> the enemy idle is pure presentation.
        states, outcomes = [], []
        for fx in (True, False):
            battle = self._battle(seed=17, fx=fx)
            battle.issue_turn("attack")
            battle.flush_sequence()
            for _ in range(90):
                battle.draw()
            states.append(battle.engine.rng.getstate())
            outcomes.append((battle.enemy.hp if battle.enemy else None,
                             battle.engine.player.hp))
        self.assertEqual(states[0], states[1])
        self.assertEqual(outcomes[0], outcomes[1])


if __name__ == "__main__":
    unittest.main()
