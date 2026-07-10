"""B87: diagonal input must not be sqrt(2) faster than cardinal movement.

The overworld accumulates per-axis sub-pixel movement; before the fix each axis
got the full PLAYER_SPEED on a diagonal, so the velocity vector was ~1.41x
longer. Locks that the distance covered per frame is equal for cardinal and
diagonal input, while the per-axis try_move structure (wall-sliding) and the
sub-pixel accumulators stay intact. Skips without pygame/pytmx.
"""

import math
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp, PLAYER_SPEED

    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


class _Keys:
    def __init__(self, *pressed):
        self._pressed = set(pressed)

    def __getitem__(self, key):
        return 1 if key in self._pressed else 0


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class DiagonalSpeedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _distance_over_frames(self, keys, frames=100):
        app = OverworldApp()
        app.mode = "walk"
        app.overlay = None
        steps = []
        app.world.try_move = lambda sx, sy: steps.append((sx, sy)) or ""
        original = pygame.key.get_pressed
        pygame.key.get_pressed = lambda: keys
        try:
            for _ in range(frames):
                app.update()
        finally:
            pygame.key.get_pressed = original
        total_x = sum(s[0] for s in steps)
        total_y = sum(s[1] for s in steps)
        return math.hypot(total_x, total_y)

    def test_diagonal_distance_equals_cardinal_distance(self):
        cardinal = self._distance_over_frames(_Keys(pygame.K_RIGHT))
        diagonal = self._distance_over_frames(_Keys(pygame.K_RIGHT, pygame.K_DOWN))
        self.assertAlmostEqual(cardinal, 100 * PLAYER_SPEED, delta=2)
        # before the fix the diagonal covered ~sqrt(2)x the cardinal distance
        self.assertLess(abs(diagonal - cardinal), cardinal * 0.02)

    def test_cardinal_speed_is_unchanged(self):
        distance = self._distance_over_frames(_Keys(pygame.K_UP))
        self.assertAlmostEqual(distance, 100 * PLAYER_SPEED, delta=2)


if __name__ == "__main__":
    unittest.main()
