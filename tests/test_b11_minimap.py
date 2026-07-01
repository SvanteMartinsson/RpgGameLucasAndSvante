"""B11 Slice 2: minimap framing.

The minimap draw is pygame (render-review), but the window framing + edge clamp
is pure and unit-testable via fog.minimap_origin: the window centres on the
player, never leaves the map, and collapses to origin 0 when the map is smaller
than the window.
"""

import unittest

from rpg_game.presentation import fog


class MinimapOriginTests(unittest.TestCase):
    def test_centres_on_the_player_in_open_space(self):
        # 240x208 map, 44x33 window, player mid-map -> centred window
        self.assertEqual(fog.minimap_origin(100, 100, 240, 208, 44, 33), (100 - 22, 100 - 16))

    def test_clamps_at_the_top_left_corner(self):
        self.assertEqual(fog.minimap_origin(2, 1, 240, 208, 44, 33), (0, 0))

    def test_clamps_at_the_bottom_right_corner(self):
        left, top = fog.minimap_origin(239, 207, 240, 208, 44, 33)
        self.assertEqual((left, top), (240 - 44, 208 - 33))
        self.assertLessEqual(left + 44, 240)   # window stays inside the map
        self.assertLessEqual(top + 33, 208)

    def test_map_smaller_than_window_pins_origin_to_zero(self):
        self.assertEqual(fog.minimap_origin(5, 5, 20, 15, 44, 33), (0, 0))

    def test_window_width_is_several_times_the_walk_viewport(self):
        # spec: ~3-4x the ZOOM_TARGET_TILES_W (12) walk view
        try:
            from rpg_game.presentation.pygame_overworld import MINIMAP_TILES, ZOOM_TARGET_TILES_W
        except Exception:  # pragma: no cover - pygame not installed
            self.skipTest("pygame not installed")
        self.assertGreaterEqual(MINIMAP_TILES[0], 3 * ZOOM_TARGET_TILES_W)
        self.assertLessEqual(MINIMAP_TILES[0], 4 * ZOOM_TARGET_TILES_W)


if __name__ == "__main__":
    unittest.main()
