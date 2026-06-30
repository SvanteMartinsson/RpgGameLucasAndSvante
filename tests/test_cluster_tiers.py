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
        # a town's cosmetic prop (shrine) renders but has no door -> not in entrances.
        anchor = (50, 50)
        tmpl = tc.resolve_template("town", shop_category="weapons", prop="shrine")
        self.assertIn("shrine", [b[0] for b in tmpl])           # it IS placed/rendered
        self.assertNotIn("shrine", tc.cluster_entrances(anchor, tmpl))  # but has no door
        # and so no cobble spur reaches it
        net = tc.cobble_network(anchor, template=tmpl)
        shrine = next(b for b in tc.cluster_buildings(anchor, tmpl) if b[0] == "shrine")
        door = tc.entrance_tile(anchor, shrine[1] - anchor[0], shrine[2] - anchor[1], shrine[3], shrine[4], shrine[5])
        self.assertNotIn(door, net)

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
