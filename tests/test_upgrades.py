"""B37 Slice 2: the weapon/armour upgrade system + miscellaneous materials.

Locks RULES/RELATIONS (tier never changes, exclusion respected, one-time upgrade,
deltas stored separately from damage_bonus, material/gold cost), not placeholder
numbers.
"""

import os
import random
import tempfile
import unittest

from rpg_game.core import combat, data_loader, upgrades
from rpg_game.core.entities import LootDrop
from rpg_game.core.game import GameEngine


class MaterialsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = data_loader.load_content()

    def test_materials_exist_as_miscellaneous(self):
        for mid in ("worg_tooth", "worg_claw", "grave_iron", "chill_crystal",
                    "blessed_ash", "iron_scrap"):
            self.assertIn(mid, self.content.items, mid)
            self.assertEqual(self.content.items[mid].kind, "miscellaneous", mid)

    def test_materials_drop_from_their_enemies(self):
        engine = GameEngine(rng=random.Random(0))
        engine.start_new_game("H", "fighter")
        worg = self.content.enemies["hollow_worg"].create_enemy()
        pool_ids = {e["item_id"] for e in engine.loot_pool(worg)}
        self.assertIn("worg_tooth", pool_ids)
        self.assertIn("worg_claw", pool_ids)

    def test_collected_materials_stack_in_inventory(self):
        engine = GameEngine(rng=random.Random(0))
        engine.start_new_game("H", "fighter")
        engine.collect_loot(LootDrop("worg_tooth", "Worg Tooth", "miscellaneous", 1))
        engine.collect_loot(LootDrop("worg_tooth", "Worg Tooth", "miscellaneous", 1))
        self.assertEqual(engine.player.inventory.count("worg_tooth"), 2)


def _stocked(class_id="fighter", level=8):
    engine = GameEngine(rng=random.Random(1))
    engine.start_new_game("H", class_id)
    engine.player.level = level
    engine.player.gold = 5000
    engine.player.inventory.consumables.update(
        {"iron_scrap": 20, "grave_iron": 20, "worg_tooth": 20, "worg_claw": 20, "chill_crystal": 20}
    )
    return engine


def _own_and_equip(engine, weapon_id):
    p = engine.player
    p.owned_weapon_ids = (*p.owned_weapon_ids, weapon_id)
    weapon = engine.content.weapons[weapon_id]
    combat.resolve_action(p, p, combat.create_weapon_swap_action(weapon), engine.rng, weapon=weapon)
    engine.recompute_equipment()


class UpgradeRuleTest(unittest.TestCase):
    def test_rarity_gates_upgradability(self):
        content = data_loader.load_content()
        self.assertTrue(upgrades.is_upgradable(content, "worgfang"))        # rare weapon
        self.assertTrue(upgrades.is_upgradable(content, "iron_cuirass"))    # rare gear
        self.assertFalse(upgrades.is_upgradable(content, "training_cap"))   # common gear

    def test_exclusion_list_hides_a_rare_item(self):
        content = data_loader.load_content()
        # worldsplitter is legendary (>= rare) but excluded -> not upgradable.
        self.assertEqual(content.weapons["worldsplitter"].rarity, "legendary")
        self.assertIn("worldsplitter", upgrades.UPGRADE_EXCLUSIONS)
        self.assertFalse(upgrades.is_upgradable(content, "worldsplitter"))

    def test_tier_and_required_level_unchanged_by_a_damage_upgrade(self):
        engine = _stocked()
        _own_and_equip(engine, "steel_greatsword")
        weapon = engine.content.weapons["steel_greatsword"]
        self.assertEqual(weapon.tier, 4)                                    # tier-4 regression target
        tier_before = weapon.tier
        req_before = combat.weapon_required_level(weapon)
        base_damage_bonus = weapon.damage_bonus
        dmg_before = engine.effective_stat("damage")

        result = engine.apply_item_upgrade("steel_greatsword", "honed")     # +5 damage, +3 crit
        self.assertTrue(result.success, result.message)
        self.assertGreater(engine.effective_stat("damage"), dmg_before)     # delta applied
        # Tier / required-level / base damage_bonus all untouched.
        self.assertEqual(engine.content.weapons["steel_greatsword"].tier, tier_before)
        self.assertEqual(combat.weapon_required_level(engine.content.weapons["steel_greatsword"]), req_before)
        self.assertEqual(engine.content.weapons["steel_greatsword"].damage_bonus, base_damage_bonus)

    def test_upgrade_is_one_time(self):
        engine = _stocked()
        _own_and_equip(engine, "steel_greatsword")
        self.assertTrue(engine.apply_item_upgrade("steel_greatsword", "honed").success)
        blocked = engine.apply_item_upgrade("steel_greatsword", "frostforged")
        self.assertFalse(blocked.success)
        self.assertIn("already", blocked.message.lower())

    def test_upgrade_consumes_exact_gold_and_materials(self):
        engine = _stocked()
        _own_and_equip(engine, "steel_greatsword")
        variant = upgrades.variant_for(engine.content, "steel_greatsword", "honed")
        gold_before = engine.player.gold
        have = {m: engine.player.inventory.count(m) for m, _ in variant.materials}
        engine.apply_item_upgrade("steel_greatsword", "honed")
        self.assertEqual(engine.player.gold, gold_before - variant.gold)
        for material_id, need in variant.materials:
            self.assertEqual(engine.player.inventory.count(material_id), have[material_id] - need)

    def test_upgrade_blocked_when_short_on_materials(self):
        engine = _stocked()
        _own_and_equip(engine, "worgfang")
        engine.player.inventory.consumables["worg_claw"] = 0   # savage needs worg_claw
        result = engine.apply_item_upgrade("worgfang", "savage")
        self.assertFalse(result.success)
        self.assertNotIn("worgfang", engine.player.item_upgrades)   # nothing consumed/recorded

    def test_deltas_are_stored_separately_from_damage_bonus(self):
        engine = _stocked()
        _own_and_equip(engine, "steel_greatsword")
        engine.apply_item_upgrade("steel_greatsword", "honed")
        # The record is the variant id; the flat lives in upgrade_stat_bonuses,
        # NOT in the (frozen, shared) weapon's damage_bonus.
        self.assertEqual(engine.player.item_upgrades["steel_greatsword"], "honed")
        self.assertEqual(engine.player.upgrade_stat_bonuses.get("damage"), 5)
        self.assertEqual(engine.content.weapons["steel_greatsword"].damage_bonus, 18)

    def test_element_variant_adds_a_damage_component_not_a_proc(self):
        engine = _stocked()
        _own_and_equip(engine, "worgfang")
        engine.apply_item_upgrade("worgfang", "frostfang")   # element frost +7
        enemy = engine.content.enemies["giant_rat"].create_enemy(); enemy.hp = 999
        weapon = engine.content.weapons["worgfang"]
        result = combat.resolve_action(engine.player, enemy, combat.player_attack_action(),
                                       random.Random(3), weapon=weapon)
        types = {c.damage_type for c in result.damage_components}
        self.assertIn("frost", types)
        self.assertIn("physical", types)
        # No status/proc applied — v1 element is a damage component only.
        self.assertEqual(enemy.active_statuses, [])

    def test_old_save_loads_without_upgrade_data(self):
        engine = _stocked()
        _own_and_equip(engine, "worgfang")
        engine.apply_item_upgrade("worgfang", "savage")
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "s.json")
            engine.save(path)
            # Simulate an OLD save: strip the upgrade key entirely.
            import json
            with open(path) as handle:
                data = json.load(handle)
            data["player"].pop("item_upgrades", None)
            with open(path, "w") as handle:
                json.dump(data, handle)
            loaded = GameEngine(content=engine.content)
            self.assertTrue(loaded.load(path).success)
            self.assertEqual(loaded.player.item_upgrades, {})

    def test_upgrade_survives_save_load(self):
        engine = _stocked()
        _own_and_equip(engine, "worgfang")
        engine.apply_item_upgrade("worgfang", "savage")
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "s.json")
            engine.save(path)
            loaded = GameEngine(content=engine.content)
            loaded.load(path)
        self.assertEqual(loaded.player.item_upgrades["worgfang"], "savage")


try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp
    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame not installed")
class UpgradeStationUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1180, 760))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _app(self):
        app = OverworldApp()
        p = app.engine.player
        p.level = 11
        p.gold = 1000
        p.owned_weapon_ids = (*p.owned_weapon_ids, "worgfang", "steel_greatsword")
        p.owned_gear_ids = (*p.owned_gear_ids, "iron_cuirass")
        p.inventory.consumables.update(
            {"worg_tooth": 5, "worg_claw": 4, "chill_crystal": 3, "iron_scrap": 8, "grave_iron": 6}
        )
        app.engine.recompute_equipment()
        return app

    def test_blacksmith_station_opens_with_weapons_and_renders(self):
        app = self._app()
        app._open_upgrade_station("blacksmith")
        self.assertEqual(app.mode, "upgrade_station")
        self.assertIn(app.selected_upgrade_item, ("worgfang", "steel_greatsword"))
        app.draw()  # must not raise
        labels = [b.label for b in app.buttons]
        self.assertTrue(any("Reforge" in l for l in labels))

    def test_reforge_button_applies_upgrade_and_spends_resources(self):
        app = self._app()
        gold_before = app.engine.player.gold
        app._open_upgrade_station("blacksmith")
        app.select_upgrade_item("worgfang")
        app.apply_upgrade("worgfang", "savage")   # needs worg_claw:3, gold 280
        self.assertTrue(app.engine.is_item_upgraded("worgfang"))
        self.assertEqual(app.engine.player.gold, gold_before - 280)

    def test_insufficient_materials_marks_reforge_restricted(self):
        app = self._app()
        app.engine.player.inventory.consumables.update(
            {"worg_tooth": 0, "worg_claw": 0, "chill_crystal": 0}
        )
        app._open_upgrade_station("blacksmith")
        app.select_upgrade_item("worgfang")
        app.draw()
        reforge = [b for b in app.buttons if "Reforge" in b.label]
        self.assertTrue(reforge)
        self.assertTrue(all(b.restricted for b in reforge))   # clickable but sperred

    def test_character_panel_tags_a_rare_weapon_as_upgradable(self):
        app = self._app()
        app.overlay = "character"
        app.selected_equipment_slot = "weapon"
        app.draw()  # must not raise; tags are queued + flushed during the draw
        # The rare weapon is tagged Upgradable; the common starter weapon is not.
        self.assertTrue(app.engine.is_upgradable("worgfang"))
        self.assertFalse(app.engine.is_upgradable("worn_shortsword"))


class StationRoutingTest(unittest.TestCase):
    def test_blacksmith_routes_weapons_mage_tower_and_barracks_route_armour(self):
        content = data_loader.load_content()
        self.assertEqual(upgrades.station_category("blacksmith"), "weapon")
        self.assertEqual(upgrades.station_category("mage_tower"), "armour")
        self.assertEqual(upgrades.station_category("barracks"), "armour")
        self.assertIsNone(upgrades.station_category("inn"))
        # category match is enforced both ways
        self.assertTrue(upgrades.station_can_upgrade("blacksmith", content, "worgfang"))
        self.assertFalse(upgrades.station_can_upgrade("blacksmith", content, "iron_cuirass"))
        self.assertTrue(upgrades.station_can_upgrade("mage_tower", content, "iron_cuirass"))
        self.assertFalse(upgrades.station_can_upgrade("mage_tower", content, "worgfang"))

    def test_station_tier_is_max_noop_so_any_tier_is_handled(self):
        content = data_loader.load_content()
        # worldsplitter is the highest-tier weapon; the no-op tier gate still passes
        # the tier check (it's only excluded by the exclusion list, not by tier).
        self.assertGreaterEqual(upgrades.station_tier("blacksmith"), upgrades.item_tier(content, "worldsplitter"))

    def test_station_lists_only_owned_upgradable_items_of_its_category(self):
        engine = _stocked()
        engine.player.owned_weapon_ids = ("knife", "worgfang", "steel_greatsword")  # knife is common
        engine.player.owned_gear_ids = ("iron_cuirass", "training_cap")             # cap is common
        weapons = engine.station_upgradable_items("blacksmith")
        armour = engine.station_upgradable_items("barracks")
        self.assertEqual(set(weapons), {"worgfang", "steel_greatsword"})
        self.assertEqual(set(armour), {"iron_cuirass"})


if __name__ == "__main__":
    unittest.main()
