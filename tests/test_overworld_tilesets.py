"""Cainos/themed tilesets wired into the overworld + per-zone base ground.
Presentation/assets only — collision, regions and spawns are unchanged.

Skips when pygame/pytmx are not installed.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from pytmx.util_pygame import load_pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp, ZONE_CONFIG, DEFAULT_MAP
    from rpg_game.presentation import pygame_overworld

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False

# Expected tileset sources: placeholder + cainos(3) + 6 themes x 3.
THEMES = ("grave_heath", "cursed_mire", "frostfell", "ash_waste", "mork_skog", "karr")
ZONE_THEME_TILE = {  # (tile_x, tile_y) -> expected ground tileset name
    # The per-zone colouring was reverted (unify_overworld_theme.py): the whole
    # map now renders one uniform cainos ground, so the seam is gone. Gameplay
    # regions (encounters/levels) are unchanged.
    (0, 10): "cainos_grass",   # core
    (34, 10): "cainos_grass",  # western forest — same palette now
    (45, 10): "cainos_grass",  # deep-west swamp — same palette now
}


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class OverworldTilesetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()
        self.tmx = self.app.world.tmx

    def test_all_tileset_sources_load_via_pytmx(self):
        names = {ts.name for ts in self.tmx.tilesets}
        self.assertIn("cainos_grass", names)
        self.assertIn("cainos_stone", names)
        self.assertIn("cainos_wall", names)
        for theme in THEMES:
            self.assertIn(f"{theme}_grass", names)
            self.assertIn(f"{theme}_stone", names)
            self.assertIn(f"{theme}_wall", names)

    def test_whole_map_renders_one_uniform_cainos_ground(self):
        ground = self.tmx.get_layer_by_name("ground")
        for (x, y), expected in ZONE_THEME_TILE.items():
            gid = ground.data[y][x]
            self.assertEqual(self.tmx.get_tileset_from_gid(gid).name, expected, (x, y))

    def test_themed_grass_registered_but_no_longer_used_for_ground(self):
        ground = self.tmx.get_layer_by_name("ground")
        used = {self.tmx.get_tileset_from_gid(ground.data[y][x]).name
                for y in range(self.tmx.height) for x in range(self.tmx.width)}
        self.assertEqual(used, {"cainos_grass"})  # uniform; no per-zone seam
        # The themed sheets stay registered as sources, so re-theming later is trivial.
        names = {ts.name for ts in self.tmx.tilesets}
        for reserved in ("mork_skog_grass", "cursed_mire_grass", "grave_heath_grass",
                         "frostfell_grass", "ash_waste_grass", "karr_grass"):
            self.assertIn(reserved, names)

    def test_every_ground_tile_has_a_real_image(self):
        ground = self.tmx.get_layer_by_name("ground")
        images = [img for _x, _y, img in ground.tiles()]
        self.assertEqual(len(images), self.tmx.width * self.tmx.height)
        self.assertTrue(all(img is not None for img in images))

    def test_missing_tile_image_falls_back_without_crashing(self):
        layer = self.tmx.get_layer_by_name("ground")
        layer.tiles = lambda: [(0, 0, None), (1, 0, None)]  # simulate graphics-less tiles
        try:
            self.app.draw()  # must not raise
        finally:
            del layer.tiles  # restore the bound method

    def test_relative_sources_load_from_an_unrelated_cwd(self):
        cwd = os.getcwd()
        import tempfile
        with tempfile.TemporaryDirectory() as other:
            os.chdir(other)
            try:
                tmx = load_pygame(os.path.join(os.path.dirname(DEFAULT_MAP), "overworld.tmx"))
                self.assertEqual(len(tmx.tilesets), 28)
                ground = tmx.get_layer_by_name("ground")
                self.assertTrue(all(img is not None for _x, _y, img in ground.tiles()))
            finally:
                os.chdir(cwd)

    def test_collision_and_spawns_unchanged(self):
        # walls layer preserved verbatim -> same blocked tiles, gates and regions
        self.assertIn((0, 0), self.app.world.blocked)        # border wall
        self.assertNotIn((14, 10), self.app.world.blocked)   # Hordanita start tile walkable
        self.assertEqual(self.app.zone.wild_region_at((14, 8)), "burg_54")
        self.assertEqual(self.app.zone.wild_region_at((34, 8)), "burg_146")
        self.assertEqual(self.app.zone.wild_region_at((45, 8)), "burg_320")


if __name__ == "__main__":
    unittest.main()
