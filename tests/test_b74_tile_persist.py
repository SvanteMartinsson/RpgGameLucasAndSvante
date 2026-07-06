"""B74: loads restore the EXACT saved overworld tile.

Locks: sync_location keeps player.overworld_tile fresh, a wild-tile save loads
back to the same tile (not the pool-container town), legacy saves without the
field fall back to the place's town tile, and a since-blocked tile falls back
too. Skips without pygame.
"""

import json
import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class TilePersistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.app = OverworldApp()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "save.json")

    def test_sync_location_keeps_the_field_fresh(self):
        self.app.world.set_tile(20, 50)
        self.app.sync_location()
        self.assertEqual(self.app.engine.player.overworld_tile, (20, 50))

    def test_wild_save_loads_back_to_the_same_tile(self):
        self.app.world.set_tile(20, 50)          # cainos wilds (region burg_54)
        self.app.sync_location()
        self.assertEqual(self.app.engine.player.current_place_id, "burg_54")
        self.app.engine.save(self.path)
        self.app.world.set_tile(51, 52)          # walk away
        self.app.sync_location()
        self.app._load_save(self.path)
        self.assertEqual(tuple(self.app.world.current_tile), (20, 50))

    def test_legacy_save_without_field_falls_back_to_the_town_tile(self):
        self.app.world.set_tile(20, 50)
        self.app.sync_location()
        self.app.engine.save(self.path)
        raw = json.load(open(self.path))
        raw["player"].pop("overworld_tile")      # simulate a pre-B74 save
        json.dump(raw, open(self.path, "w"))
        self.app._load_save(self.path)
        expected = self.app.town_tile_by_place["burg_54"]
        self.assertEqual(tuple(self.app.world.current_tile), tuple(expected))

    def test_blocked_saved_tile_falls_back(self):
        self.app.world.set_tile(20, 50)
        self.app.sync_location()
        self.app.engine.save(self.path)
        raw = json.load(open(self.path))
        blocked = next(iter(self.app.world.blocked))
        raw["player"]["overworld_tile"] = list(blocked)
        json.dump(raw, open(self.path, "w"))
        self.app._load_save(self.path)
        self.assertNotEqual(tuple(self.app.world.current_tile), tuple(blocked))


if __name__ == "__main__":
    unittest.main()
