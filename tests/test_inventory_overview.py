"""Inventory shows everything owned (with counts) and routes equippables to the
Character panel. Pure presentation — equip still happens via the engine path in
Character. Skips when pygame/pytmx are not installed.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False

ALL_CATEGORIES = {
    "consumables", "miscellaneous", "weapon",
    "head", "chest", "hands", "legs", "feet", "amulet", "ring",
}


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class InventoryOverviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()
        self.eng = self.app.engine

    # -- everything owned, with counts, nothing hidden ----------------------

    def test_overview_lists_every_category_including_empty_zero(self):
        counts = self.app.inventory_counts()
        self.assertEqual(set(counts), ALL_CATEGORIES)
        # a fresh fighter owns only the starting weapon; gear slots read 0
        self.assertEqual(counts["amulet"], 0)
        self.assertEqual(counts["chest"], 0)
        self.assertEqual(counts["weapon"], len(self.eng.player.owned_weapon_ids))

    def test_owned_amulet_is_discoverable(self):
        # The bug: an owned amulet was invisible. Now it shows under its category.
        self.eng.player.owned_gear_ids = ("tin_amulet",)
        self.assertEqual(self.app.inventory_counts()["amulet"], 1)
        labels = [text for _id, text, _cb, _en in self.app.inventory_category_items("amulet")]
        self.assertTrue(any("Tin Amulet" in t for t in labels))

    # -- counts track the owned source -------------------------------------

    def test_counts_update_on_pickup_and_removal(self):
        self.assertEqual(self.app.inventory_counts()["head"], 0)
        self.eng.player.owned_gear_ids = ("iron_helm",)
        self.assertEqual(self.app.inventory_counts()["head"], 1)
        self.eng.player.owned_gear_ids = ()
        self.assertEqual(self.app.inventory_counts()["head"], 0)

    def test_equipping_a_weapon_keeps_it_counted_as_owned(self):
        self.eng.player.owned_weapon_ids = ("knife", "sword")
        before = self.app.inventory_counts()["weapon"]
        self.eng.player.equipped_weapon_id = "sword"  # still owned
        self.assertEqual(self.app.inventory_counts()["weapon"], before)

    def test_consumable_and_junk_counts_from_the_bag(self):
        self.eng.player.inventory.consumables.clear()  # isolate from the new-game grant
        self.eng.player.inventory.add_consumable("hp_potion")
        self.eng.player.inventory.add_consumable("hp_potion")
        self.eng.player.inventory.add_consumable("bone_dust")
        counts = self.app.inventory_counts()
        self.assertEqual(counts["consumables"], 2)
        self.assertEqual(counts["miscellaneous"], 1)

    # -- routing to Character (no equip logic in inventory) ----------------

    def test_gear_item_routes_to_character_on_its_slot(self):
        self.eng.player.owned_gear_ids = ("tin_amulet",)
        self.app.overlay = "inventory"
        rows = self.app.inventory_category_items("amulet")
        rows[0][2]()  # click the amulet
        self.assertEqual(self.app.overlay, "character")
        self.assertEqual(self.app.selected_equipment_slot, "amulet")

    def test_weapon_item_routes_to_character_weapon_slot(self):
        self.app.overlay = "inventory"
        rows = self.app.inventory_category_items("weapon")
        rows[0][2]()
        self.assertEqual(self.app.overlay, "character")
        self.assertEqual(self.app.selected_equipment_slot, "weapon")

    def test_ring_routes_to_first_empty_ring_slot(self):
        self.eng.player.owned_gear_ids = ("novice_ring",)
        self.app.inventory_equip_handoff("ring")
        self.assertEqual(self.app.overlay, "character")
        self.assertIn(self.app.selected_equipment_slot, ("ring_1", "ring_2", "ring_3"))

    # -- consumable use unchanged ------------------------------------------

    def test_consumable_use_still_goes_through_engine(self):
        self.eng.player.inventory.add_consumable("hp_potion")
        self.eng.player.hp = 1
        rows = self.app.inventory_category_items("consumables")
        next(r for r in rows if r[0] == "hp_potion")[2]()
        self.assertGreater(self.eng.player.hp, 1)
        self.assertEqual(self.eng.player.inventory.count("hp_potion"), 0)

    def test_miscellaneous_is_listed_but_inert(self):
        self.eng.player.inventory.add_consumable("bone_dust")
        rows = self.app.inventory_category_items("miscellaneous")
        bone = next(r for r in rows if r[0] == "bone_dust")
        self.assertIsNone(bone[2])  # no on_click — not usable

    # -- Character slot counts mirror the inventory ------------------------

    def _slots(self):
        from rpg_game.core.view import build_snapshot
        return build_snapshot(self.eng).equipment_slots

    def test_character_slot_count_matches_inventory_for_every_slot(self):
        # Own a spread of gear; each slot's (N) must equal the inventory's count
        # for that slot's category (same single source).
        self.eng.player.owned_gear_ids = ("tin_amulet", "iron_helm", "novice_ring", "swift_ring")
        counts = self.app.inventory_counts()
        for slot in self._slots():
            self.assertEqual(self.app.slot_owned_count(slot), counts[slot.slot_type], slot.id)

    def test_three_ring_slots_share_one_pool(self):
        self.eng.player.owned_gear_ids = ("novice_ring", "swift_ring")  # 2 owned rings
        ring_slots = [s for s in self._slots() if s.slot_type == "ring"]
        self.assertEqual([s.id for s in ring_slots], ["ring_1", "ring_2", "ring_3"])
        for slot in ring_slots:
            self.assertEqual(self.app.slot_owned_count(slot), 2)  # all show the shared total
        self.assertEqual(self.app.inventory_counts()["ring"], 2)

    def test_empty_slot_still_reports_owned_count(self):
        self.eng.player.owned_gear_ids = ("tin_amulet", "sage_amulet")  # owned, none equipped
        amulet = next(s for s in self._slots() if s.id == "amulet")
        self.assertEqual(amulet.equipped_item_id, "")     # slot is empty
        self.assertEqual(self.app.slot_owned_count(amulet), 2)  # but options exist

    def test_equipped_item_is_included_in_the_count(self):
        # Mirror the inventory: an equipped item still counts as owned.
        self.eng.player.owned_gear_ids = ("novice_ring",)
        self.eng.equip_gear("novice_ring", "ring_1")
        ring = next(s for s in self._slots() if s.id == "ring_1")
        self.assertEqual(ring.equipped_item_id, "novice_ring")
        self.assertEqual(self.app.slot_owned_count(ring), 1)
        self.assertEqual(self.app.slot_owned_count(ring), self.app.inventory_counts()["ring"])

    # -- renders in every category without crashing ------------------------

    def test_renders_all_categories(self):
        self.eng.player.owned_gear_ids = ("tin_amulet", "iron_helm")
        self.eng.player.inventory.add_consumable("hp_potion")
        for category in ALL_CATEGORIES:
            self.app.overlay = "inventory"
            self.app.inventory_category = category
            self.app.draw()


if __name__ == "__main__":
    unittest.main()
