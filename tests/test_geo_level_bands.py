"""Geo level bands set in data (Lucas GO 2026-07-12).

The first-pass BFS-distance bands from docs/nightly/geo_proposal.md are now
authored in maps/core_zone.json's spawn_areas. These guards lock that every
area carries a band, that the AREA band drives the rolled level (precedence
AREA > region > template, per 5cc6504), and that the bands rise with distance
within a zone (cainos entry lower than its far reaches, heath likewise).
"""

import random
import unittest

from rpg_game.core import spawns, world
from rpg_game.core.data_loader import load_content

CONTENT = load_content()
AREAS = {a.id: a for a in CONTENT.spawn_areas}


class GeoBandDataTests(unittest.TestCase):
    def test_every_spawn_area_has_a_band(self):
        self.assertTrue(AREAS)
        for area in CONTENT.spawn_areas:
            self.assertTrue(area.level_min and area.level_max, area.id)
            self.assertLessEqual(area.level_min, area.level_max, area.id)

    def test_bands_rise_with_distance_within_a_zone(self):
        # entry areas sit at the zone's low end, far areas at the top
        self.assertLess(AREAS["cainos_generalists"].level_min,
                        AREAS["cainos_undead_north"].level_min)
        self.assertLess(AREAS["skog_goblin_west"].level_min,
                        AREAS["skog_deep_east"].level_min)
        self.assertLess(AREAS["heath_entry_northwest"].level_min,
                        AREAS["heath_ghoul_south"].level_min)

    def test_zone_entry_matches_zone_floor(self):
        # cainos is the starter zone — its nearest area bottoms at L1
        self.assertEqual(AREAS["cainos_generalists"].level_min, 1)
        # the heath is the endgame — its far areas top at L12
        self.assertEqual(AREAS["heath_ghoul_south"].level_max, 12)


class GeoBandRollTests(unittest.TestCase):
    def test_area_band_drives_the_rolled_level(self):
        # a tile covered only by cainos_generalists (L1-3) never rolls above 3
        area = AREAS["cainos_generalists"]
        x0, y0, x1, y1 = area.rect
        tile = (x0, y0)
        band = spawns.band_at(CONTENT.spawn_areas, tile)
        self.assertIsNotNone(band)
        rng = random.Random(3)
        template = CONTENT.enemies[area.enemies[0][0]]
        levels = {world.roll_enemy_level(template, rng, band=band) for _ in range(60)}
        self.assertTrue(levels <= set(range(band[0], band[1] + 1)) and levels)

    def test_far_heath_area_bands_are_endgame(self):
        # the far heath areas themselves carry the top band (a corner tile can
        # union with a lower-banded neighbour, so assert the area's own band)
        self.assertEqual((AREAS["heath_ghoul_south"].level_min,
                          AREAS["heath_ghoul_south"].level_max), (10, 12))
        self.assertEqual((AREAS["heath_northeast_pocket"].level_min,
                          AREAS["heath_northeast_pocket"].level_max), (10, 12))


if __name__ == "__main__":
    unittest.main()
