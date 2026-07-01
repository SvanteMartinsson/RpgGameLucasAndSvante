"""8 mage towers spread across the zones (data-only placement, prop:"tower").

Locks WHICH towns carry the tower prop (and that the start town never does), and
that the towns whose tier actually renders the prop get a reachable armour-station
door. burg_146 is a town-tier tournament town: its @flex slot is town_hall, so it
carries the prop in data but does NOT render a tower — documented here so the
caveat is explicit.
"""

import json
import os
import unittest
from collections import deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from rpg_game.core.data_loader import DATA_DIR

TOWER_TOWNS = {
    "burg_200", "burg_67", "burg_146", "burg_219",
    "burg_149", "burg_54", "burg_105", "burg_117",
}
# Renders a tower today (burg_146 is a tournament town -> @flex is town_hall).
RENDERS_TOWER = TOWER_TOWNS - {"burg_146"}

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp
    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


class MageTowerDataTest(unittest.TestCase):
    def test_exactly_eight_towns_carry_the_tower_prop_and_not_the_start_town(self):
        core = json.loads((DATA_DIR / "maps" / "core_zone.json").read_text())
        tower = {t["place_id"] for t in core["towns"] if t.get("prop") == "tower"}
        self.assertEqual(tower, TOWER_TOWNS)
        self.assertEqual(len(tower), 8)
        self.assertNotIn("burg_5", tower)   # never the start town


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class MageTowerRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.app = OverworldApp()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _reachable(self):
        zone, world = self.app.zone, self.app.world
        W, H = world.tmx.width, world.tmx.height
        start = zone.start_tile
        blocked = world.blocked - set(world.gate_messages)
        seen, q = {start}, deque([start])
        while q:
            x, y = q.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < W and 0 <= ny < H and (nx, ny) not in blocked and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    q.append((nx, ny))
        return seen

    def test_rendering_towns_get_a_reachable_armour_station_door(self):
        seen = self._reachable()
        tower_doors = {bid_pid[0]: tile for tile, bid_pid in self.app.door_index.items()
                       if bid_pid[1] == "tower"}
        # Every town whose tier renders the prop has a tower door, and it's reachable.
        self.assertEqual(set(tower_doors), RENDERS_TOWER)
        for pid, tile in tower_doors.items():
            self.assertIn(tile, seen, f"{pid} tower door unreachable")
            self.assertEqual(self.app.engine.station_category("tower"), "armour")

    def test_all_towns_still_reachable(self):
        seen = self._reachable()
        for tile in self.app.zone.towns:
            self.assertIn(tile, seen)


if __name__ == "__main__":
    unittest.main()
