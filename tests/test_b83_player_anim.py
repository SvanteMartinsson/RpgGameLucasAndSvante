"""B83: the player's walk/idle animation (Lucas's hooded sprite).

Locks: the build tool's sheets exist with a clean grid, the app loads 8x4 walk
frames + 4 idle frames at 1.5-tile height, the 8-way facing map, the
walk/idle cadence (7.5 vs 4 fps in 60 fps ticks) and the yellow-square
fallback when sheets are missing. Skips without pygame."""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation import overworld_render as ow
    from rpg_game.presentation.pygame_overworld import OverworldApp
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class PlayerAnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.app = OverworldApp()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_sheets_exist_with_a_clean_grid(self):
        walk = pygame.image.load(ow.PLAYER_WALK_SHEET)
        idle = pygame.image.load(ow.PLAYER_IDLE_SHEET)
        self.assertEqual(walk.get_width() % 4, 0)
        self.assertEqual(walk.get_height() % 8, 0)
        self.assertEqual(idle.get_width(), walk.get_width())
        self.assertEqual(idle.get_height(), walk.get_height() // 8)

    def test_app_loads_all_frames_at_player_scale(self):
        frames = self.app._player_frames
        self.assertIsNotNone(frames)
        self.assertEqual(len(frames["walk"]), 8)
        self.assertTrue(all(len(row) == 4 for row in frames["walk"]))
        self.assertEqual(len(frames["idle"]), 4)
        expected_h = round(self.app.world.th * ow.PLAYER_SPRITE_TILES)
        self.assertEqual(frames["walk"][0][0].get_height(), expected_h)
        self.assertEqual(frames["idle"][0].get_height(), expected_h)

    def test_eight_way_facing_map(self):
        cases = {(0, -1): 0, (1, -1): 1, (1, 0): 2, (1, 1): 3,
                 (0, 1): 4, (-1, 1): 5, (-1, 0): 6, (-1, -1): 7}
        for (dx, dy), row in cases.items():
            self.assertEqual(ow.player_facing(dx, dy), row, (dx, dy))
        self.assertEqual(ow.player_facing(0, 0, fallback=6), 6)   # standing keeps facing

    def test_walk_ticks_faster_than_idle(self):
        self.app._player_frame = 0
        self.app._player_anim_clock = 0
        self.app._player_moving = False
        for _ in range(ow.IDLE_FRAME_TICKS):
            self.app._tick_player_anim()
        self.assertEqual(self.app._player_frame, 1)               # 4 fps idle
        self.app._player_moving = True
        for _ in range(ow.WALK_FRAME_TICKS):
            self.app._tick_player_anim()
        self.assertEqual(self.app._player_frame, 2)               # 7.5 fps walk

    def test_missing_sheets_fall_back_to_the_square(self):
        self.app.screen = pygame.Surface((1024, 680))
        saved = self.app._player_frames
        self.app._player_frames = None
        try:
            self.app.draw()   # must not raise — classic square path
        finally:
            self.app._player_frames = saved


if __name__ == "__main__":
    unittest.main()
