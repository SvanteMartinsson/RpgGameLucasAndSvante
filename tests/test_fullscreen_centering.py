"""Display anchoring across screens.

Two models coexist:
- FLUID screens (start menu, overworld) size their canvas to the live display,
  so present() is the identity transform and they FILL the window (ox == 0).
- FIXED-canvas screens (battle, character creation) draw a design-size canvas
  that present() centers as an island (ox > 0) on a larger display.

Skips when pygame/pytmx are not installed.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation.pygame_overworld import OverworldApp
    from rpg_game.presentation.pygame_battle import BattleApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False

DISPLAY = (1400, 900)  # larger than every canvas -> everything should center


def _canvas_center(transform, canvas_size):
    ox, oy, scale = transform
    return (ox + canvas_size[0] * scale / 2, oy + canvas_size[1] * scale / 2)


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class FullscreenCenteringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _overworld_transform(self):
        app = OverworldApp()
        app.display = pygame.Surface(DISPLAY)
        app.draw()
        return app._transform, app.screen.get_size()

    def _battle_transform(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        for pid, place in engine.content.places.items():
            if place.encounters:
                engine.player.current_place_id = pid
                break
        battle = BattleApp(engine=engine, enemy=engine.create_encounter(), standalone=False)
        battle.display = pygame.Surface(DISPLAY)
        battle.draw()
        return battle._transform, battle.screen.get_size()

    def test_overworld_is_fluid_fills_the_window(self):
        # The overworld canvas tracks the live display, so it fills the window
        # (identity transform, no island) and the camera shows more world.
        app = OverworldApp()
        app.display = pygame.Surface(DISPLAY)
        app.draw()
        self.assertEqual(app.screen.get_size(), DISPLAY)   # canvas == display
        self.assertEqual(app._transform, (0, 0, 1.0))       # identity -> no margins
        self.assertIsNot(app.screen, app.display)

    def test_fixed_canvas_battle_centers_when_display_is_larger(self):
        # Battle keeps a fixed design canvas -> centered island on a big display.
        transform, _size = self._battle_transform()
        ox, oy, _scale = transform
        self.assertGreater(ox, 0)
        self.assertGreater(oy, 0)

    def test_converted_fluid_screen_anchors_at_origin(self):
        # A fluid screen sizes its canvas to the display; present() then centers
        # nothing. This documents that the island assumption above does NOT apply
        # to converted screens, without breaking the fixed ones.
        from rpg_game.presentation.pygame_canvas import present
        display = pygame.Surface(DISPLAY)
        canvas = pygame.Surface(display.get_size())  # fluid: canvas == display
        ox, oy, scale = present(display, canvas, (18, 20, 28))
        self.assertEqual((ox, oy, scale), (0, 0, 1.0))

    def test_all_screens_share_the_same_center_anchor(self):
        ow_t, ow_size = self._overworld_transform()
        bt_t, bt_size = self._battle_transform()
        screen_center = (DISPLAY[0] / 2, DISPLAY[1] / 2)
        # Each canvas, whatever its size, is centered on the same display point.
        self.assertEqual(_canvas_center(ow_t, ow_size), screen_center)
        self.assertEqual(_canvas_center(bt_t, bt_size), screen_center)

    def test_windowed_equal_size_has_no_offset(self):
        app = OverworldApp()
        app.display = pygame.Surface(app.view_size)  # window == canvas
        app.draw()
        self.assertEqual(app._transform, (0, 0, 1.0))

    def test_overworld_click_maps_through_the_transform(self):
        # A click on the display maps back into canvas space (so buttons still hit
        # after centering). Open a town menu and click its first button's center.
        app = OverworldApp()
        app.display = pygame.Surface(DISPLAY)
        app.world.set_tile(14, 10)  # Hordanita
        app.sync_location()
        app.mode = "townmenu"
        app.draw()
        self.assertTrue(app.buttons)
        ox, oy, scale = app._transform
        btn = app.buttons[0]
        display_point = (ox + btn.rect.centerx * scale, oy + btn.rect.centery * scale)
        from rpg_game.presentation.pygame_canvas import to_canvas
        self.assertTrue(btn.rect.collidepoint(to_canvas(display_point, app._transform)))


if __name__ == "__main__":
    unittest.main()
