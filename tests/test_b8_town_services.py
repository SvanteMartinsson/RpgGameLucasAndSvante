"""B8 2b: town services — per-town stores, gear pricing, the apothecary door
and stable fast travel.

Locks: every shop_category town carries a real, category-matching inventory
(no greater potions, weapons commons-only, capital untouched), gear value
scales with tier (the flat-value giveaway is gone), fast_travel_cost follows
distance + the departure zone's B62 economy, the coach board lists only
DISCOVERED stables and moves gold+place through the engine, the apothecary
door opens brewing and the general shop's interim button is gone. Skips
without pygame.
"""

import json
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

try:
    import pygame
    from rpg_game.core import progression, store
    from rpg_game.core.data_loader import load_content
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import fog
    from rpg_game.presentation.overworld_buildings import BUILDING_FUNCTION
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


def _towns():
    with open(os.path.join(ROOT, "rpg_game", "data", "maps", "core_zone.json")) as fh:
        return json.load(fh)["towns"]


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class StoreDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = load_content()

    def test_every_shop_category_town_has_a_matching_store(self):
        kind_of = {}
        for wid in self.content.weapons:
            kind_of[wid] = "weapon"
        for gid in self.content.gear_items:
            kind_of[gid] = "gear"
        for iid, item in self.content.items.items():
            kind_of[iid] = "consumable" if item.kind in ("consumable", "tome") else item.kind
        allowed = {"weapons": {"weapon"}, "armor": {"gear"}, "general": {"consumable"}}
        for town in _towns():
            category = town.get("shop_category")
            tier = town.get("tier")
            place = self.content.places[town["place_id"]]
            if not category and tier not in ("capital", "city"):
                continue
            self.assertTrue(place.has_store, town["place_id"])
            self.assertTrue(place.store_inventory, town["place_id"])
            if category:                     # single-door town: content matches it
                kinds = {kind_of[i] for i in place.store_inventory}
                self.assertLessEqual(kinds, allowed[category],
                                     f"{town['place_id']}: {kinds}")

    def test_no_store_sells_greater_potions_rares_or_boss_gear(self):
        for place in self.content.places.values():
            for item_id in place.store_inventory:
                self.assertNotIn("greater", item_id, place.id)
                weapon = self.content.weapons.get(item_id)
                if weapon is not None:
                    self.assertEqual(weapon.rarity, "common", item_id)
                gear = self.content.gear_items.get(item_id)
                if gear is not None:
                    self.assertLess(gear.tier, 5, item_id)   # t5 = boss rewards

    def test_capital_inventory_is_untouched(self):
        place = self.content.places["burg_5"]
        self.assertEqual(place.store_inventory, (
            "lesser_hp_potion", "lesser_mana_potion", "hp_potion", "antidote",
            "sword", "hunting_bow", "training_cap", "threadbare_gloves",
            "worn_boots", "padded_vest"))

    def test_gear_value_scales_with_tier(self):
        by_tier = {}
        for gear in self.content.gear_items.values():
            by_tier.setdefault(gear.tier, gear)
        values = {tier: store.gear_value(g) for tier, g in sorted(by_tier.items())}
        self.assertEqual(sorted(values), sorted(values.keys()))
        for low, high in zip(sorted(values)[:-1], sorted(values)[1:]):
            self.assertLess(values[low], values[high])
        t5 = next(g for g in self.content.gear_items.values() if g.tier == 5)
        self.assertGreaterEqual(store.gear_value(t5), 480)   # no more 72g mantles

    def test_service_props_are_placed_per_zone(self):
        props = {t["place_id"]: t.get("prop") for t in _towns()}
        self.assertEqual([p for p, v in props.items() if v == "stable"],
                         ["burg_235", "burg_200", "burg_54", "burg_53"])
        self.assertEqual([p for p, v in props.items() if v == "apothecary"],
                         ["burg_219", "burg_149"])


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class FastTravelRuleTest(unittest.TestCase):
    def test_cost_grows_with_distance_and_zone(self):
        near = progression.fast_travel_cost(100, 1)
        far = progression.fast_travel_cost(300, 1)
        self.assertLess(near, far)
        cheap = progression.fast_travel_cost(150, 1)
        dear = progression.fast_travel_cost(150, 4)
        self.assertLess(cheap, dear)

    def test_cost_matches_the_b62_anchor(self):
        # A typical neighbouring hop (~150 tiles) costs ~2 fights of the
        # departure zone's net income (B62: 11/56/59/108 g/fight).
        for zone, net in progression.FAST_TRAVEL_ZONE_NET.items():
            cost = progression.fast_travel_cost(150, zone)
            self.assertEqual(cost, progression.round_half_up(net * 2.0))

    def test_engine_fast_travel_moves_gold_and_place(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        engine.player.gold = 100
        result = engine.fast_travel("burg_235", 40)
        self.assertTrue(result.success)
        self.assertEqual(engine.player.gold, 60)
        self.assertEqual(engine.player.current_place_id, "burg_235")

    def test_engine_fast_travel_rejects_short_gold_and_same_place(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        engine.player.gold = 5
        denied = engine.fast_travel("burg_235", 40)
        self.assertFalse(denied.success)
        self.assertEqual(engine.player.gold, 5)
        engine.player.gold = 100
        engine.enter_place("burg_235")
        same = engine.fast_travel("burg_235", 40)
        self.assertFalse(same.success)


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class ServiceDoorsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()

    def test_building_function_maps_the_new_doors(self):
        self.assertEqual(BUILDING_FUNCTION["apothecary"], "brew")
        self.assertEqual(BUILDING_FUNCTION["stable"], "fast_travel")

    def test_apothecary_door_opens_brewing(self):
        self.app.do_action("brew")
        self.assertEqual(self.app.mode, "apothecary")

    def test_shop_menu_no_longer_offers_brewing(self):
        self.app.building_menu = ("burg_5", "shop")
        self.app.mode = "building"
        self.app.draw()
        self.assertFalse([b for b in self.app.buttons if "Brew" in b.label])

    def test_economy_zone_uses_the_heath_y_band(self):
        self.assertEqual(self.app.zone.economy_zone_for_tile((51, 52)), 1)    # cainos
        self.assertEqual(self.app.zone.economy_zone_for_tile((136, 84)), 2)   # skog
        self.assertEqual(self.app.zone.economy_zone_for_tile((218, 60)), 3)   # mire
        self.assertEqual(self.app.zone.economy_zone_for_tile((72, 180)), 4)   # heath wins on y

    def test_coach_board_lists_only_discovered_stables(self):
        player = self.app.engine.player
        self.assertEqual(self.app._fast_travel_offers(), [])   # nothing revealed
        fog.reveal_rect(player.revealed_tiles, self.app.world.tmx.width,
                        self.app.world.tmx.height, 106, 107, 44, 45)  # discover Jinosa
        offers = self.app._fast_travel_offers()
        self.assertEqual([o[0] for o in offers], ["burg_235"])
        pid, tile, label, cost = offers[0]
        here = self.app.world.current_tile
        distance = abs(tile[0] - here[0]) + abs(tile[1] - here[1])
        zone = self.app.zone.economy_zone_for_tile(here)
        self.assertEqual(cost, progression.fast_travel_cost(distance, zone))

    def test_riding_the_coach_moves_the_player_and_charges_gold(self):
        player = self.app.engine.player
        player.gold = 500
        fog.reveal_rect(player.revealed_tiles, self.app.world.tmx.width,
                        self.app.world.tmx.height, 106, 107, 44, 45)
        pid, tile, _label, cost = self.app._fast_travel_offers()[0]
        self.app.mode = "fast_travel"
        self.app._ride_stable(pid, tile, cost)
        self.assertEqual(self.app.mode, "walk")
        self.assertEqual(player.gold, 500 - cost)
        self.assertEqual(player.current_place_id, "burg_235")
        self.assertEqual(self.app.world.current_tile, (106, 44))

    def test_short_gold_ride_is_refused_in_place(self):
        player = self.app.engine.player
        player.gold = 0
        fog.reveal_rect(player.revealed_tiles, self.app.world.tmx.width,
                        self.app.world.tmx.height, 106, 107, 44, 45)
        pid, tile, _label, cost = self.app._fast_travel_offers()[0]
        start_place = player.current_place_id
        self.app._ride_stable(pid, tile, cost)
        self.assertEqual(player.current_place_id, start_place)
        self.assertEqual(player.gold, 0)

    def test_fast_travel_screen_draws(self):
        player = self.app.engine.player
        fog.reveal_rect(player.revealed_tiles, self.app.world.tmx.width,
                        self.app.world.tmx.height, 106, 107, 44, 45)
        self.app.mode = "fast_travel"
        self.app.draw()
        labels = [b.label for b in self.app.buttons]
        self.assertTrue(any("Jinosa" in l for l in labels))


if __name__ == "__main__":
    unittest.main()
