"""B138: hollow_worg walks Moerk-skogen day and night.

Lucas's call: mork_skog had no night-flavoured species at all (B136e reported it —
no undead/spirit/cursed anywhere in the zone), so hollow_worg (beast+cursed,
corridor 5-10) joins the forest in BOTH phases. A pure data change: the level
bands, stats, HP and damage are all untouched, and the creature already existed
in the world's ecosystem — it just wasn't in the forest's pools.
"""

import random
import unittest

from rpg_game.core import spawns
from rpg_game.core.data_loader import _read_json, _theme_for_tile, load_content
from rpg_game.core.world import roll_enemy_level

WORG = "hollow_worg"
# The bar B138 applied: an area's band must sit ENTIRELY INSIDE the corridor, not
# merely intersect it. skog_goblin_west (band 4-6) fails that and is excluded.
SKOG_AREAS = ("skog_beast_north", "skog_plant_south", "skog_deep_east")
EXCLUDED = "skog_goblin_west"


class SkogWorgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = load_content()
        cls.themes = _read_json("maps/core_zone.json").get("ground_themes", ())
        cls.worg = cls.content.enemies[WORG]

    def _area(self, area_id):
        return next(a for a in self.content.spawn_areas if a.id == area_id)

    def _center(self, area_id):
        x0, y0, x1, y1 = self._area(area_id).rect
        return ((x0 + x1) // 2, (y0 + y1) // 2)

    def _pool(self, tile, phase, region="burg_146"):
        return spawns.pool_at(self.content.spawn_areas, self.content.spawn_fallbacks,
                              tile, region, phase=phase,
                              night_fallbacks=self.content.spawn_fallbacks_night)

    def test_the_worg_is_beast_and_cursed_so_it_belongs_to_both_phases(self):
        tags = set(self.worg.tags)
        self.assertIn("beast", tags)     # day-affine
        self.assertIn("cursed", tags)    # night-affine
        self.assertEqual((self.worg.level_min, self.worg.level_max), (5, 10))

    def test_it_is_in_the_skog_pools_in_both_phases(self):
        for area_id in SKOG_AREAS:
            area = self._area(area_id)
            for phase in (spawns.DAY, spawns.NIGHT):
                self.assertIn(WORG, dict(area.roster(phase)), f"{area_id} @ {phase}")

    def test_the_region_fallback_carries_it_in_both_phases(self):
        self.assertIn(WORG, dict(self.content.spawn_fallbacks["burg_146"]))
        self.assertIn(WORG, dict(self.content.spawn_fallbacks_night["burg_146"]))

    def test_mork_skog_now_has_a_night_flavoured_species(self):
        # The whole point: B136e's finding was that the forest's night roster was
        # entirely NEUTRAL species (goblins and spiders), with nothing
        # undead/spirit/cursed in it.
        night = set()
        for area in self.content.spawn_areas:
            x0, y0, x1, y1 = area.rect
            if _theme_for_tile(self.themes, (x0 + x1) // 2, (y0 + y1) // 2) != "mork_skog":
                continue
            night.update(e for e, _w in area.roster(spawns.NIGHT))
        self.assertIn(WORG, night)
        flavoured = {e for e in night
                     if {"undead", "spirit", "cursed"} & set(self.content.enemies[e].tags)}
        self.assertEqual(flavoured, {WORG})
        # and the roster grew rather than replacing what was there
        self.assertLessEqual({"goblin_raider", "goblin_shaman", "broodmother_spider"}, night)

    def test_the_excluded_area_kept_its_band_below_the_corridor(self):
        area = self._area(EXCLUDED)
        self.assertLess(area.level_min, self.worg.level_min)   # 4 < 5
        for phase in (spawns.DAY, spawns.NIGHT):
            self.assertNotIn(WORG, dict(area.roster(phase)), f"{EXCLUDED} @ {phase}")

    def test_every_hosting_band_sits_inside_the_corridor(self):
        for area_id in SKOG_AREAS:
            area = self._area(area_id)
            self.assertGreaterEqual(area.level_min, self.worg.level_min, area_id)
            self.assertLessEqual(area.level_max, self.worg.level_max, area_id)

    def test_it_stays_the_rarest_thing_in_every_pool_it_joins(self):
        for area_id in SKOG_AREAS:
            area = self._area(area_id)
            for phase in (spawns.DAY, spawns.NIGHT):
                roster = area.roster(phase)
                weights = dict(roster)
                self.assertLess(weights[WORG],
                                min(w for e, w in roster if e != WORG),
                                f"{area_id} @ {phase}")

    def test_overlapping_areas_never_push_it_out_of_the_rare_band(self):
        # B48 SUMS weights where areas overlap, and the worg now sits in three
        # overlapping skog rectangles — so scan every forest tile, not just centres.
        worst = 0.0
        for y in range(0, 100):
            for x in range(83, 159):
                if _theme_for_tile(self.themes, x, y) != "mork_skog":
                    continue
                for phase in (spawns.DAY, spawns.NIGHT):
                    pool = dict(self._pool((x, y), phase))
                    if WORG in pool:
                        worst = max(worst, pool[WORG] / sum(pool.values()))
        self.assertGreater(worst, 0.0)
        self.assertLess(worst, 0.20, "the worg stopped being a rare spawn")

    def test_no_pool_in_the_forest_is_empty_in_either_phase(self):
        for y in range(0, 100, 3):
            for x in range(83, 159, 3):
                if _theme_for_tile(self.themes, x, y) != "mork_skog":
                    continue
                for phase in (spawns.DAY, spawns.NIGHT):
                    self.assertTrue(self._pool((x, y), phase), (x, y, phase))

    def test_the_level_bands_are_untouched(self):
        # The band is what makes this not a difficulty change: a worg rolled in
        # the forest obeys the SAME band the area already used, in both phases.
        for area_id in SKOG_AREAS:
            tile = self._center(area_id)
            band = spawns.band_at(self.content.spawn_areas, tile)
            area = self._area(area_id)
            self.assertEqual(band, (area.level_min, area.level_max))
            for phase in (spawns.DAY, spawns.NIGHT):
                pool = self._pool(tile, phase)
                rng = random.Random(17)
                levels = [roll_enemy_level(self.worg, rng, band=band) for _ in range(200)]
                self.assertGreaterEqual(min(levels), band[0], (area_id, phase))
                self.assertLessEqual(max(levels), band[1], (area_id, phase))
                self.assertTrue(pool)

    def test_the_zone_band_did_not_move(self):
        self.assertEqual(self.content.zone_bands["mork_skog"], (4, 9))

    def test_the_bounty_invariant_still_holds(self):
        # No species may become night-exclusive to a zone, or B135e could roll a
        # bounty naming an enemy the player cannot find in daylight.
        per_zone = {}
        for area in self.content.spawn_areas:
            x0, y0, x1, y1 = area.rect
            zone = _theme_for_tile(self.themes, (x0 + x1) // 2, (y0 + y1) // 2)
            if not zone:
                continue
            buckets = per_zone.setdefault(zone, {spawns.DAY: set(), spawns.NIGHT: set()})
            for phase in (spawns.DAY, spawns.NIGHT):
                buckets[phase].update(e for e, _w in area.roster(phase))
        for zone, buckets in per_zone.items():
            self.assertEqual(buckets[spawns.NIGHT] - buckets[spawns.DAY], set(), zone)
        self.assertIn(WORG, self.content.zone_enemies["mork_skog"])

    def test_the_engine_really_spawns_it_in_the_forest(self):
        from rpg_game.core.game import GameEngine
        engine = GameEngine(content=self.content, rng=random.Random(5))
        engine.start_new_game("Hero", "fighter")
        tile = self._center("skog_deep_east")
        band = spawns.band_at(self.content.spawn_areas, tile)
        for phase in (spawns.DAY, spawns.NIGHT):
            pool = self._pool(tile, phase)
            seen, levels = set(), []
            for _ in range(600):
                enemy = engine.create_encounter(pool=pool, band=band, zone="mork_skog")
                seen.add(enemy.id)
                levels.append(enemy.level)
            self.assertIn(WORG, seen, phase)
            self.assertGreaterEqual(min(levels), band[0], phase)
            self.assertLessEqual(max(levels), band[1], phase)


if __name__ == "__main__":
    unittest.main()
