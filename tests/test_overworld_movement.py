"""Headless movement/collision tests for the Tiled overworld shell.

Skips when pygame/pytmx are not installed (e.g. the dependency-free core test
run with the system interpreter). Run inside the venv to exercise it.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation import pygame_overworld as M
    from rpg_game.presentation.pygame_overworld import Overworld, OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


class _HeldKey:
    """Fake pygame key-state: only the given key codes read as pressed."""
    def __init__(self, *down):
        self.down = set(down)

    def __getitem__(self, code):
        return 1 if code in self.down else 0


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class OverworldMovementTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.world = Overworld()

    def test_starts_on_a_free_tile(self):
        tx = self.world.player.centerx // self.world.tw
        ty = self.world.player.centery // self.world.th
        self.assertNotIn((tx, ty), self.world.blocked)

    def test_open_move_succeeds_and_reverses(self):
        before = self.world.player.copy()
        self.world.try_move(3, 0)
        self.assertEqual(self.world.player.x, before.x + 3)
        self.world.try_move(-3, 0)
        self.assertEqual(self.world.player, before)

    def test_border_wall_blocks_and_keeps_player_in_open_space(self):
        for _ in range(100):
            self.world.try_move(0, -3)
            self.world.try_move(-3, 0)
        self.assertFalse(self.world.is_blocked(self.world.player))
        self.assertGreaterEqual(self.world.player.left, self.world.tw - 1)
        self.assertGreaterEqual(self.world.player.top, self.world.th - 1)

    def test_axes_resolve_independently(self):
        self.world.player.topleft = (self.world.tw, self.world.th * 5)
        y0 = self.world.player.y
        self.world.try_move(-3, 3)  # blocked left, free down
        self.assertEqual(self.world.player.x, self.world.tw)
        self.assertEqual(self.world.player.y, y0 + 3)

    def test_interior_wall_blocks_passage(self):
        self.world.player.center = (9 * self.world.tw + self.world.tw // 2,
                                    5 * self.world.th + self.world.th // 2)
        for _ in range(40):
            self.world.try_move(3, 0)
        self.assertLess(self.world.player.centerx // self.world.tw, 10)

    def test_camera_clamps_within_map(self):
        ox, oy = self.world.camera_offset(400, 300)
        self.assertTrue(0 <= ox <= self.world.map_px_w - 400)
        self.assertTrue(0 <= oy <= self.world.map_px_h - 300)


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class OverworldWalkSpeedTest(unittest.TestCase):
    """The app's sub-pixel accumulator yields an effective 2.4 px/frame (20% under
    the old 3) even though the player rect is integer-only."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _run_frames(self, app, keys, n):
        orig = pygame.key.get_pressed
        pygame.key.get_pressed = lambda: keys
        try:
            for _ in range(n):
                app.update()
        finally:
            pygame.key.get_pressed = orig

    def test_speed_constant_is_20pct_under_three(self):
        self.assertAlmostEqual(M.PLAYER_SPEED, 0.8 * 3, places=6)
        self.assertAlmostEqual(M.PLAYER_SPEED, 2.4, places=6)

    def test_effective_speed_is_2_4_px_per_frame(self):
        app = OverworldApp()
        app.encounter_rate = 0                       # no battles mid-walk
        app.world.is_blocked = lambda rect: False     # isolate speed from collision
        x0 = app.world.player.x
        n = 200
        self._run_frames(app, _HeldKey(pygame.K_RIGHT), n)
        moved = app.world.player.x - x0
        self.assertAlmostEqual(moved / n, 2.4, delta=0.05)

    def test_standing_still_never_moves_even_with_leftover_fraction(self):
        app = OverworldApp()
        app._move_accum_x = 0.9                        # carried sub-pixel remainder
        x0, y0 = app.world.player.x, app.world.player.y
        self._run_frames(app, _HeldKey(), 5)           # no keys held
        self.assertEqual((app.world.player.x, app.world.player.y), (x0, y0))

    def test_teleport_resets_accumulator_no_drift(self):
        app = OverworldApp()
        app._move_accum_x, app._move_accum_y = 0.7, 0.7
        app.resolve_battle_outcome("defeat", None)     # respawn teleport
        self.assertEqual((app._move_accum_x, app._move_accum_y), (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
