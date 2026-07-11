"""B8 Slice 2a: tier-driven cluster templates generalised to all 17 towns.

Pure-template tests (resolve_template) + the system rules: a bed in every town,
cosmetic buildings have no door, town_hall only where a tournament lives. The
exact tier/category/prop VALUES are provisional (Lucas tunes in 2b) — these tests
lock the SYSTEM, not the seed.
"""

import unittest

from rpg_game.presentation import town_cluster as tc

REST = {"inn", "cottage"}


class ResolveTemplateTests(unittest.TestCase):
    def test_capital_is_the_original_six_building_l(self):
        cap = tc.resolve_template("capital")
        self.assertEqual([b[0] for b in cap],
                         ["church", "town_hall", "inn", "blacksmith", "barracks", "shop"])
        self.assertEqual(cap, tc.CLUSTER_TEMPLATES["capital"])  # byte-identical

    def test_trade_building_follows_shop_category(self):
        for cat, expect in (("weapons", "blacksmith"), ("armor", "barracks"), ("general", "shop")):
            town = tc.resolve_template("town", shop_category=cat)
            self.assertIn(expect, [b[0] for b in town], cat)

    def test_town_hall_only_when_tournament(self):
        self.assertNotIn("town_hall", [b[0] for b in tc.resolve_template("city", prop="warehouse")])
        self.assertIn("town_hall", [b[0] for b in tc.resolve_template("city", prop="warehouse", has_tournament=True)])
        # a village WITH a tournament still gets a town_hall (burg_121 case)
        self.assertIn("town_hall", [b[0] for b in tc.resolve_template("village", has_tournament=True)])

    def test_every_tier_has_exactly_one_rest_door(self):
        for tier in ("capital", "city", "town", "village"):
            for tourn in (False, True):
                for cat in (None, "weapons", "armor", "general"):
                    tmpl = tc.resolve_template(tier, shop_category=cat, prop="shrine", has_tournament=tourn)
                    rests = [b[0] for b in tmpl if b[0] in REST]
                    self.assertEqual(len(rests), 1, (tier, tourn, cat, rests))

    def test_village_is_smallest_capital_is_largest(self):
        sizes = {t: len(tc.resolve_template(t, prop="shrine")) for t in
                 ("capital", "city", "town", "village")}
        self.assertEqual(sizes["village"], 2)
        self.assertLess(sizes["village"], sizes["town"])
        self.assertLess(sizes["town"], sizes["city"])
        self.assertEqual(sizes["capital"], 6)

    def test_cosmetic_buildings_get_no_entrance(self):
        # a town's cosmetic prop (warehouse) renders but has no door -> not in entrances.
        anchor = (50, 50)
        tmpl = tc.resolve_template("town", shop_category="weapons", prop="warehouse")
        self.assertIn("warehouse", [b[0] for b in tmpl])        # it IS placed/rendered
        self.assertNotIn("warehouse", tc.cluster_entrances(anchor, tmpl))  # but has no door
        # and so no cobble spur reaches it
        net = tc.cobble_network(anchor, template=tmpl)
        ware = next(b for b in tc.cluster_buildings(anchor, tmpl) if b[0] == "warehouse")
        door = tc.entrance_tile(anchor, ware[1] - anchor[0], ware[2] - anchor[1], ware[3], ware[4], ware[5])
        self.assertNotIn(door, net)

    def test_shrine_is_functional_with_a_door_and_cobble(self):
        # Church C (2026-07-11): the shrine left COSMETIC_BUILDINGS — it gets a
        # real entrance and a cobble spur, exactly like the mage tower did.
        anchor = (50, 50)
        for tier, kwargs in (("village", {}), ("town", {"shop_category": "weapons"})):
            tmpl = tc.resolve_template(tier, prop="shrine", **kwargs)
            self.assertIn("shrine", [b[0] for b in tmpl], tier)
            ents = tc.cluster_entrances(anchor, tmpl)
            self.assertIn("shrine", ents, tier)                 # it HAS a door now
            net = tc.cobble_network(anchor, template=tmpl)
            self.assertIn(ents["shrine"], net, tier)            # the spur reaches it
        # the village template places the shrine facing front -> door due south.
        tmpl = tc.resolve_template("village", prop="shrine")
        shrine = next(b for b in tmpl if b[0] == "shrine")
        _bid, dx, dy, fw, fh, facing, _flip = shrine
        self.assertEqual(facing, "front")
        self.assertEqual(tc.cluster_entrances(anchor, tmpl)["shrine"],
                         (anchor[0] + dx + fw // 2, anchor[1] + dy + fh))

    def test_shrine_door_maps_the_respawn_service(self):
        from rpg_game.presentation.overworld_buildings import (
            BUILDING_FUNCTION, BUILDING_TITLES)
        self.assertEqual(BUILDING_FUNCTION["shrine"], "relocate_respawn")
        self.assertEqual(BUILDING_TITLES["shrine"], "Shrine")

    def test_footprints_disjoint_and_entrances_clear_all_combos(self):
        anchor = (60, 60)
        for tier in ("capital", "city", "town", "village"):
            for tourn in (False, True):
                tmpl = tc.resolve_template(tier, shop_category="general", prop="warehouse", has_tournament=tourn)
                seen, overlap = set(), set()
                for b in tmpl:
                    fp = tc.building_footprint(anchor, b[1], b[2], b[3], b[4])
                    overlap |= seen & fp
                    seen |= fp
                self.assertEqual(overlap, set(), (tier, tourn))
                foot = tc.cluster_footprints(anchor, tmpl)
                for ent in tc.cluster_entrances(anchor, tmpl).values():
                    self.assertNotIn(ent, foot, (tier, tourn, ent))


if __name__ == "__main__":
    unittest.main()
