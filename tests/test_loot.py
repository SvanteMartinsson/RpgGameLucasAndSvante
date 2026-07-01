import random
import unittest

from rpg_game.core.entities import Enemy, LootDrop
from rpg_game.core.game import GameEngine, loot_rarity_for_denominator


def _engine(seed: int = 0) -> GameEngine:
    engine = GameEngine(rng=random.Random(seed))
    engine.start_new_game("Hero", "fighter")  # starts at a has_store city
    return engine


def _enemy(loot, drop_chance=1.0, rare_access=False) -> Enemy:
    return Enemy(
        id="t", name="Test", level=1, max_hp=1, hp=1, damage=1, armor=0, speed=1,
        resistances={}, action_ids=(), xp_reward=0, gold_min=0, gold_max=0,
        loot_table=tuple(loot), drop_chance=drop_chance, rare_table_access=rare_access,
    )


class DropChanceTests(unittest.TestCase):
    def test_drop_chance_zero_never_drops(self):
        loot = [{"item_id": "rat_pelt", "weight": 1, "rarity_tier": 1}]
        for seed in range(50):
            engine = _engine(seed)
            self.assertIsNone(engine.roll_loot(_enemy(loot, drop_chance=0.0)))

    def test_drop_chance_one_always_drops(self):
        loot = [{"item_id": "rat_pelt", "weight": 1, "rarity_tier": 1}]
        for seed in range(50):
            engine = _engine(seed)
            self.assertIsNotNone(engine.roll_loot(_enemy(loot, drop_chance=1.0)))


class WeightedDrawTests(unittest.TestCase):
    def test_known_seed_yields_known_item(self):
        loot = [
            {"item_id": "rat_pelt", "weight": 1, "rarity_tier": 1},
            {"item_id": "bone_dust", "weight": 1, "rarity_tier": 1},
        ]
        self.assertEqual(_engine(0).roll_loot(_enemy(loot)).item_id, "bone_dust")
        self.assertEqual(_engine(4).roll_loot(_enemy(loot)).item_id, "rat_pelt")

    def test_draw_follows_weights(self):
        loot = [
            {"item_id": "rat_pelt", "weight": 9, "rarity_tier": 1},
            {"item_id": "bone_dust", "weight": 1, "rarity_tier": 1},
        ]
        counts = {"rat_pelt": 0, "bone_dust": 0}
        for seed in range(400):
            counts[_engine(seed).roll_loot(_enemy(loot)).item_id] += 1
        self.assertGreater(counts["rat_pelt"], counts["bone_dust"] * 4)


class LootRarityTests(unittest.TestCase):
    def test_rarity_classes_use_drop_rate_denominator_ranges(self):
        self.assertEqual(loot_rarity_for_denominator(1), "common")
        self.assertEqual(loot_rarity_for_denominator(20), "common")
        self.assertEqual(loot_rarity_for_denominator(21), "uncommon")
        self.assertEqual(loot_rarity_for_denominator(50), "uncommon")
        self.assertEqual(loot_rarity_for_denominator(51), "rare")
        self.assertEqual(loot_rarity_for_denominator(70), "rare")
        self.assertEqual(loot_rarity_for_denominator(100), "rare")
        self.assertEqual(loot_rarity_for_denominator(150), "rare")
        self.assertEqual(loot_rarity_for_denominator(151), "mega rare")
        self.assertEqual(loot_rarity_for_denominator(300), "mega rare")
        self.assertEqual(loot_rarity_for_denominator(301), "legendary")
        self.assertEqual(loot_rarity_for_denominator(500), "legendary")

    def test_drop_rarity_is_the_authored_item_rarity_not_the_drop_rate(self):
        # The SHOWN rarity is the item's authored rarity (so chat == inventory), NOT
        # the drop-luck denominator. bone_dust is a miscellaneous item -> common,
        # even though it dropped at a 1/70 chance (still tracked in the denominator).
        engine = GameEngine(rng=SequenceRng([0.0, 0.99]))
        engine.start_new_game("Hero", "fighter")
        loot = [
            {"item_id": "rat_pelt", "weight": 69, "rarity_tier": 1},
            {"item_id": "bone_dust", "weight": 1, "rarity_tier": 1},
        ]

        drop = engine.roll_loot(_enemy(loot, drop_chance=1.0))

        self.assertEqual(drop.item_id, "bone_dust")
        self.assertEqual(drop.drop_rate_denominator, 70)   # true drop chance still tracked
        self.assertEqual(drop.rarity, "common")            # authored, not the 1/70 label

    def test_different_drop_rates_inside_same_rarity_class_are_grouped(self):
        engine = _engine()
        enemy_70 = _enemy(
            [
                {"item_id": "rat_pelt", "weight": 69, "rarity_tier": 1},
                {"item_id": "bone_dust", "weight": 1, "rarity_tier": 1},
            ],
            drop_chance=1.0,
        )
        enemy_100 = _enemy(
            [
                {"item_id": "rat_pelt", "weight": 99, "rarity_tier": 1},
                {"item_id": "bone_dust", "weight": 1, "rarity_tier": 1},
            ],
            drop_chance=1.0,
        )

        denominator_70 = engine.loot_drop_denominator(enemy_70, enemy_70.loot_table[1])
        denominator_100 = engine.loot_drop_denominator(enemy_100, enemy_100.loot_table[1])

        self.assertEqual(denominator_70, 70)
        self.assertEqual(denominator_100, 100)
        self.assertEqual(loot_rarity_for_denominator(denominator_70), "rare")
        self.assertEqual(loot_rarity_for_denominator(denominator_100), "rare")

    def test_drop_event_displays_rarity_without_exact_drop_rate(self):
        engine = GameEngine(rng=SequenceRng([0.0, 0.0, 0.0, 0.0, 0.99]))
        engine.start_new_game("Hero", "fighter")
        enemy = _enemy(
            [
                {"item_id": "rat_pelt", "weight": 69, "rarity_tier": 1},
                {"item_id": "bone_dust", "weight": 1, "rarity_tier": 1},
            ],
            drop_chance=1.0,
        )

        result = engine.run_combat_turn(enemy, "attack")

        self.assertEqual(result.outcome, "victory")
        self.assertEqual(result.loot_drop.rarity, "common")   # bone_dust authored rarity
        self.assertTrue(any("[common]" in event for event in result.events))
        self.assertFalse(any("1/70" in event for event in result.events))


class TierGateTests(unittest.TestCase):
    def test_enemy_without_rare_access_never_drops_tier_4_plus(self):
        engine = _engine()
        pool_tiers = [int(e["rarity_tier"]) for e in engine.loot_pool(engine.content.enemies["giant_rat"].create_enemy())]
        self.assertTrue(all(tier <= 3 for tier in pool_tiers))

        # even with a tier-4 entry injected, the gate filters it out
        loot = [
            {"item_id": "rat_pelt", "weight": 1, "rarity_tier": 1},
            {"item_id": "worldsplitter", "weight": 1, "rarity_tier": 6},
        ]
        for seed in range(60):
            drop = _engine(seed).roll_loot(_enemy(loot, drop_chance=1.0, rare_access=False))
            self.assertEqual(drop.item_id, "rat_pelt")

    def test_rare_table_reached_only_with_access_and_level(self):
        engine = _engine()
        grunt_pool = {str(e["item_id"]) for e in engine.loot_pool(engine.content.enemies["giant_rat"].create_enemy())}
        bear_pool = {str(e["item_id"]) for e in engine.loot_pool(engine.content.enemies["cave_bear"].create_enemy())}
        boar_pool = {str(e["item_id"]) for e in engine.loot_pool(engine.content.enemies["wild_boar"].create_enemy())}
        worg_pool = {str(e["item_id"]) for e in engine.loot_pool(engine.content.enemies["hollow_worg"].create_enemy())}

        rare_ids = {str(e["item_id"]) for e in engine.content.rare_loot_table}
        self.assertFalse(grunt_pool & rare_ids)            # no rare access at all
        # B24-flag: below level 5 the SHARED rare table is capped at tier 3, so a L3
        # wild kill yields NO rare-table weapon (consecrated_maul/venomfang are tier 4).
        self.assertFalse(bear_pool & rare_ids)             # L3: shared rare table fully gated
        self.assertNotIn("consecrated_maul", bear_pool)    # tier 4 rare-table item gone at low level
        # A mid-tier (L6) enemy reaches the tier-4 and tier-5 rare weapons but not
        # the tier-6 worldsplitter (that needs L8).
        self.assertIn("consecrated_maul", boar_pool)       # tier 4 reachable from L6
        self.assertIn("pyre_scepter", boar_pool)           # tier 5 reachable from L6
        self.assertNotIn("worldsplitter", boar_pool)       # tier 6 still gated below L8
        self.assertTrue(rare_ids <= worg_pool)             # L8 enemy reaches the whole table


class GearDropDataTests(unittest.TestCase):
    def test_authored_gear_pool_covers_slots_tiers_and_rarities(self):
        content = _engine().content
        slot_types = {gear.slot_type for gear in content.gear_items.values()}
        rarities = {gear.rarity for gear in content.gear_items.values()}
        tiers = {gear.tier for gear in content.gear_items.values()}

        self.assertTrue({"head", "chest", "hands", "legs", "feet", "amulet", "ring"} <= slot_types)
        self.assertTrue({"common", "uncommon", "rare"} <= rarities)
        self.assertGreaterEqual(max(tiers), 5)
        self.assertEqual(content.gear_items["veteran_ring"].level_req, 3)

    def test_low_tier_gear_can_drop_from_early_enemy(self):
        engine = _engine()
        pool = engine.loot_pool(engine.content.enemies["giant_rat"].create_enemy())
        gear_entries = [entry for entry in pool if str(entry["item_id"]) in engine.content.gear_items]

        self.assertTrue(any(engine.content.gear_items[str(entry["item_id"])].tier <= 2 for entry in gear_entries))
        self.assertIn("training_cap", {str(entry["item_id"]) for entry in gear_entries})
        steel = next(entry for entry in pool if entry["item_id"] == "steel_greatsword")
        self.assertEqual(steel["weight"], 5)
        self.assertEqual(steel["rarity_tier"], 3)

    def test_gear_loot_drop_uses_gear_kind_and_tier(self):
        engine = GameEngine(rng=SequenceRng([0.0, 0.99]))
        engine.start_new_game("Hero", "fighter")
        enemy = _enemy(
            [
                {"item_id": "rat_pelt", "weight": 1, "rarity_tier": 1},
                {"item_id": "training_cap", "weight": 1, "rarity_tier": 1},
            ],
            drop_chance=1.0,
        )

        drop = engine.roll_loot(enemy)
        engine.collect_loot(drop)

        self.assertEqual(drop.kind, "gear")
        self.assertEqual(drop.tier, 1)
        self.assertIn("training_cap", engine.player.owned_gear_ids)


class PerEnemyUniqueTableTests(unittest.TestCase):
    """B6: every drop-capable enemy has a COMMON table (loot_table) plus a
    signature UNIQUE table (unique_table) whose item drops at ~3-8%, giving a
    reason to hunt that specific enemy."""

    SIGNATURES = {
        "giant_rat": "gnaw_charm", "undead": "grave_band", "cave_bear": "bearclaw_grips",
        "undead_priest": "censer_pendant", "plague_acolyte": "plaguebearer_mask",
        "dire_wolf": "direpelt_cloak", "wild_boar": "tusk_pendant", "treant": "heartwood_ring",
        "mutated_mudcrab": "carapace_plate", "bog_wraith": "wraithlight_band",
        "tar_beast": "tarheart_amulet", "hollow_worg": "worgfang",
    }

    # New-enemy data slice: registered with placeholder loot and NO unique yet
    # (real uniques — e.g. skeleton_warrior's frostfire sword — are the loot slice).
    NEW_PLACEHOLDER_ENEMIES = {
        "wild_dog", "wild_stag", "giant_spider", "goblin_scrapper", "mire_lurker",
        "bog_leech", "rotting_fiend", "witchlight", "bog_hag", "ghoul",
        "grave_hound", "shade", "cursed_wight", "skeleton_warrior",
    }

    def test_every_drop_capable_enemy_has_unique_and_common_tables(self):
        content = _engine().content
        for eid, tmpl in content.enemies.items():
            if tmpl.drop_chance <= 0:        # arena opponents drop nothing
                continue
            self.assertTrue(tmpl.loot_table, f"{eid} has no common table")
            if eid in self.NEW_PLACEHOLDER_ENEMIES:
                continue                     # uniques deferred to the loot slice
            self.assertTrue(tmpl.unique_table, f"{eid} has no unique table")

    def test_signature_unique_drops_in_target_band(self):
        # Expected rate is deterministic from the weights -> no RNG flakiness:
        # drop_chance * signature_weight / total_pool_weight, must land in 3-8%.
        engine = _engine()
        for eid, sig in self.SIGNATURES.items():
            enemy = engine.content.enemies[eid].create_enemy()
            pool = engine.loot_pool(enemy)
            total = sum(float(e["weight"]) for e in pool)
            sig_weight = sum(float(e["weight"]) for e in pool if e["item_id"] == sig)
            self.assertGreater(sig_weight, 0, f"{sig} not in {eid} pool")
            rate = enemy.drop_chance * sig_weight / total
            self.assertTrue(0.03 <= rate <= 0.08, f"{eid} signature rate {rate:.3f} outside 3-8%")

    def test_signature_actually_resolves_from_roll(self):
        # the unique item is reachable through the normal weighted roll path
        for eid, sig in self.SIGNATURES.items():
            seen = False
            for seed in range(300):
                engine = _engine(seed)
                drop = engine.roll_loot(engine.content.enemies[eid].create_enemy())
                if drop and drop.item_id == sig:
                    seen = True
                    break
            self.assertTrue(seen, f"{eid} signature {sig} never dropped in 300 rolls")


class PickupTests(unittest.TestCase):
    def test_picked_up_weapon_is_owned_and_equippable(self):
        engine = _engine(1)
        drop = LootDrop("steel_greatsword", "Steel Greatsword", "weapon", 3)
        engine.collect_loot(drop)

        self.assertIn("steel_greatsword", engine.player.owned_weapon_ids)
        self.assertIn("steel_greatsword", [w.id for w in engine.owned_weapons()])

        engine.player.level = 5  # steel_greatsword (18 dmg -> t4) equips at L5; this tests the pickup/equip flow
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        engine.run_combat_turn(enemy, "swap:steel_greatsword")
        self.assertEqual(engine.player.equipped_weapon_id, "steel_greatsword")

    def test_duplicate_weapon_pickup_does_not_crash_or_duplicate(self):
        engine = _engine()
        drop = LootDrop("steel_greatsword", "Steel Greatsword", "weapon", 3)
        engine.collect_loot(drop)
        engine.collect_loot(drop)

        self.assertEqual(engine.player.owned_weapon_ids.count("steel_greatsword"), 1)

    def test_picked_up_consumable_and_miscellaneous_stack(self):
        engine = _engine()
        engine.collect_loot(LootDrop("hp_potion", "HP Potion", "consumable", 1))
        engine.collect_loot(LootDrop("hp_potion", "HP Potion", "consumable", 1))
        engine.collect_loot(LootDrop("rat_pelt", "Rat Pelt", "miscellaneous", 1))

        self.assertEqual(engine.player.inventory.count("hp_potion"), 2)
        self.assertEqual(engine.player.inventory.count("rat_pelt"), 1)


class SellingTests(unittest.TestCase):
    def test_selling_junk_gives_gold_and_removes_it(self):
        engine = _engine()
        engine.player.inventory.add_consumable("rat_pelt")
        engine.player.gold = 0

        result = engine.sell_item("rat_pelt")

        self.assertTrue(result.success)
        self.assertEqual(engine.player.gold, 3)  # round_half_up(6 * 0.5)
        self.assertEqual(engine.player.inventory.count("rat_pelt"), 0)

    def test_selling_unequipped_weapon_gives_gold_and_removes_it(self):
        engine = _engine()
        engine.player.owned_weapon_ids = ("sword", "axe")
        engine.player.equipped_weapon_id = "sword"
        engine.player.gold = 0

        result = engine.sell_item("axe")

        self.assertTrue(result.success)
        self.assertEqual(engine.player.gold, 88)  # round_half_up(175 * 0.5)
        self.assertNotIn("axe", engine.player.owned_weapon_ids)

    def test_cannot_sell_equipped_weapon(self):
        engine = _engine()
        engine.player.owned_weapon_ids = ("sword",)
        engine.player.equipped_weapon_id = "sword"

        result = engine.sell_item("sword")

        self.assertFalse(result.success)
        self.assertIn("sword", engine.player.owned_weapon_ids)

    def test_sellables_lists_junk_and_unequipped_weapons_only(self):
        engine = _engine()
        engine.player.owned_weapon_ids = ("sword", "axe")
        engine.player.equipped_weapon_id = "sword"
        engine.player.inventory.add_consumable("rat_pelt")
        engine.player.inventory.add_consumable("hp_potion")  # consumable, not sellable

        ids = {entry.id for entry in engine.sellable_entries()}

        self.assertEqual(ids, {"axe", "rat_pelt"})

    def test_selling_unequipped_gear_gives_gold_and_removes_it(self):
        engine = _engine()
        engine.player.owned_gear_ids = ("training_cap",)
        engine.player.gold = 0

        result = engine.sell_item("training_cap")

        self.assertTrue(result.success)
        self.assertGreater(engine.player.gold, 0)
        self.assertNotIn("training_cap", engine.player.owned_gear_ids)

    def test_cannot_sell_equipped_gear(self):
        engine = _engine()
        engine.player.owned_gear_ids = ("training_cap",)
        engine.equip_gear("training_cap", "head")

        result = engine.sell_item("training_cap")

        self.assertFalse(result.success)
        self.assertIn("training_cap", engine.player.owned_gear_ids)


class SequenceRng:
    def __init__(self, values):
        self.values = list(values)

    def random(self):
        if self.values:
            return self.values.pop(0)
        return 0.99

    def randint(self, minimum, _maximum):
        return minimum

    def choice(self, values):
        return values[0]


if __name__ == "__main__":
    unittest.main()
