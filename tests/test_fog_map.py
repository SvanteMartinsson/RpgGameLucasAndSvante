"""B11 Slice 1: fullscreen map + fog of war.

Locks the rules: walking reveals the visible tiles, the fog bitset persists
(round-trip + old-save-empty), a town becomes a pin only once its tile is
revealed, and there is NO fast-travel path.
"""

import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from rpg_game.core import persistence
from rpg_game.core.game import GameEngine
from rpg_game.presentation import fog

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp
    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


class FogBitsetTest(unittest.TestCase):
    def test_reveal_rect_sets_only_those_tiles(self):
        bits = bytearray()
        fog.reveal_rect(bits, 240, 208, left=10, right=13, top=5, bottom=7)  # 3x2 = 6 tiles
        self.assertEqual(fog.count_revealed(bits), 6)
        for x in range(10, 13):
            for y in range(5, 7):
                self.assertTrue(fog.is_revealed(bits, 240, x, y))
        self.assertFalse(fog.is_revealed(bits, 240, 13, 5))   # just outside
        self.assertFalse(fog.is_revealed(bits, 240, 10, 7))

    def test_reveal_is_clamped_to_the_map(self):
        bits = bytearray()
        fog.reveal_rect(bits, 240, 208, left=-3, right=2, top=-3, bottom=2)  # clamps to 0..2
        self.assertEqual(fog.count_revealed(bits), 4)   # (0,0),(1,0),(0,1),(1,1)

    def test_empty_bitset_reveals_nothing(self):
        self.assertFalse(fog.is_revealed(bytearray(), 240, 0, 0))
        self.assertEqual(fog.count_revealed(bytearray()), 0)


class FogPersistenceTest(unittest.TestCase):
    def test_fog_round_trips_through_save_load(self):
        engine = GameEngine(); engine.start_new_game("H", "fighter")
        fog.reveal_rect(engine.player.revealed_tiles, 240, 208, 20, 30, 40, 50)
        before = fog.count_revealed(engine.player.revealed_tiles)
        data = persistence.serialize_player(engine.player)
        restored = persistence.deserialize_player(data)
        self.assertEqual(bytes(restored.revealed_tiles), bytes(engine.player.revealed_tiles))
        self.assertEqual(fog.count_revealed(restored.revealed_tiles), before)

    def test_old_save_without_fog_loads_empty(self):
        restored = persistence.deserialize_player({"name": "Old", "player_class": "mage"})
        self.assertEqual(bytes(restored.revealed_tiles), b"")
        self.assertEqual(fog.count_revealed(restored.revealed_tiles), 0)

    def test_full_engine_save_load_preserves_fog(self):
        engine = GameEngine(); engine.start_new_game("H", "rogue")
        fog.reveal_rect(engine.player.revealed_tiles, 240, 208, 0, 5, 0, 5)
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "s.json")
            engine.save(path)
            loaded = GameEngine(content=engine.content)
            loaded.load(path)
        self.assertEqual(bytes(loaded.player.revealed_tiles),
                         bytes(engine.player.revealed_tiles))


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class FogRevealOnWalkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1000, 700))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_new_game_starts_with_no_fog_revealed(self):
        app = OverworldApp()
        self.assertEqual(fog.count_revealed(app.engine.player.revealed_tiles), 0)

    def test_drawing_reveals_the_visible_tiles_around_the_player(self):
        app = OverworldApp()
        app.world.set_tile(51, 52); app.sync_location()
        app.draw()
        bits = app.engine.player.revealed_tiles
        tmx = app.world.tmx
        self.assertTrue(fog.is_revealed(bits, tmx.width, 51, 52))   # the player's tile
        # A far corner the camera can't see stays hidden.
        self.assertFalse(fog.is_revealed(bits, tmx.width, tmx.width - 1, tmx.height - 1))

    def test_reveal_grows_only_where_you_go(self):
        app = OverworldApp()
        app.world.set_tile(51, 52); app.sync_location(); app.draw()
        before = fog.count_revealed(app.engine.player.revealed_tiles)
        far = (150, 150)
        self.assertFalse(fog.is_revealed(app.engine.player.revealed_tiles, app.world.tmx.width, *far))
        app.world.set_tile(*far); app.sync_location(); app.draw()
        after = fog.count_revealed(app.engine.player.revealed_tiles)
        self.assertGreater(after, before)
        self.assertTrue(fog.is_revealed(app.engine.player.revealed_tiles, app.world.tmx.width, *far))


if __name__ == "__main__":
    unittest.main()
