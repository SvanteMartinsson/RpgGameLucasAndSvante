"""Playtest quick-wins B49-B52 (pygame; skips without it).

B49 enemy level on the combat nameplate; B50 the combat log scrolls (clamped);
B51 bushes get their own colour on the map (distinct from rock); B52 seam bridge
decks are rotated so their planks run across the walking direction.
"""

import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import chatlog
    from rpg_game.presentation.pygame_battle import BattleApp, enemy_nameplate
    from rpg_game.presentation.pygame_overworld import (
        OverworldApp, MAP_BUSH, MAP_OBSTACLE, BRIDGE_TILESETS)
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class CombatScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _battle(self):
        engine = GameEngine(rng=random.Random(0))
        engine.start_new_game("Hero", "fighter")
        enemy = engine.content.enemies["cave_bear"].create_enemy()
        return BattleApp(engine=engine, enemy=enemy, standalone=False,
                         event_log=__import__("collections").deque())

    def test_b49_nameplate_shows_name_and_level(self):
        plate = enemy_nameplate(self._battle().enemy)
        self.assertIn("Cave Bear", plate)
        self.assertIn("Lv 3", plate)   # cave_bear base level 3

    def test_b50_combat_log_scroll_is_clamped(self):
        battle = self._battle()
        for i in range(60):
            chatlog.push(battle.event_log, f"line {i}")
        top = battle._log_scroll_max()
        self.assertGreater(top, 0)                 # there IS backlog to scroll
        battle.scroll_log(1000)
        self.assertEqual(battle.log_scroll, top)   # clamped to the top
        battle.scroll_log(-1000)
        self.assertEqual(battle.log_scroll, 0)     # clamped to newest


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class MapRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()

    def test_b51_bushes_get_their_own_colour_distinct_from_rock(self):
        self.assertNotEqual(MAP_BUSH, MAP_OBSTACLE)
        surf = self.app._build_map_terrain()
        w, h = surf.get_size()
        colours = {surf.get_at((x, y))[:3] for y in range(h) for x in range(w)}
        self.assertIn(MAP_BUSH, colours)      # bushes render in their own green
        self.assertIn(MAP_OBSTACLE, colours)  # rock/grave props still grey

    def test_b52_bridge_decks_are_rotated_non_bridge_tiles_are_not(self):
        tmx = self.app.world.tmx
        bridge_gid = non_bridge_gid = None
        for layer in tmx.visible_layers:
            data = getattr(layer, "data", None)
            if data is None:
                continue
            for y in range(tmx.height):
                for x in range(tmx.width):
                    gid = data[y][x]
                    if not gid:
                        continue
                    ts = tmx.get_tileset_from_gid(gid)
                    if ts and ts.name in BRIDGE_TILESETS and bridge_gid is None:
                        bridge_gid = gid
                    elif ts and ts.name not in BRIDGE_TILESETS and non_bridge_gid is None:
                        non_bridge_gid = gid
                if bridge_gid and non_bridge_gid:
                    break
        self.assertIsNotNone(bridge_gid, "no bridge tile on the map")
        img = tmx.get_tile_image_by_gid(bridge_gid)
        self.assertIsNot(self.app._bridge_deck_image(bridge_gid, img), img)   # rotated
        img2 = tmx.get_tile_image_by_gid(non_bridge_gid)
        self.assertIs(self.app._bridge_deck_image(non_bridge_gid, img2), img2)  # untouched


if __name__ == "__main__":
    unittest.main()
