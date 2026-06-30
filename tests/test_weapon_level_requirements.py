import random
import unittest
from dataclasses import replace

from rpg_game.core import combat
from rpg_game.core.entities import Enemy
from rpg_game.core.game import GameEngine


class FighterStartWeaponTest(unittest.TestCase):
    def test_fighter_starts_with_worn_shortsword(self):
        # B33/B37: the fighter opens with the worn_shortsword, now a pure tier-0
        # starter (d0) — no damage bonus over the bare stat.
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        self.assertEqual(engine.player.equipped_weapon_id, "worn_shortsword")
        self.assertEqual(engine.player.owned_weapon_ids, ("worn_shortsword",))
        self.assertEqual(engine.content.weapons["worn_shortsword"].damage_bonus, 0)
        self.assertEqual(engine.content.weapons["worn_shortsword"].tier, 0)


class WeaponLevelRequirementTests(unittest.TestCase):
    def test_required_level_follows_derived_tier(self):
        # B37: tier is derived from damage (ceil/5) and the equip level is decoupled:
        # t0-2 -> L1, t3 -> L3, t4 -> L5, t5 -> L8, t6 -> L11, t7+ -> L14.
        engine = GameEngine(rng=random.Random(1))
        req = lambda wid: combat.weapon_required_level(engine.content.weapons[wid])

        self.assertEqual(req("sword"), 1)               # 5 -> t1
        self.assertEqual(req("axe"), 1)                 # 9 -> t2
        self.assertEqual(req("longsword"), 3)           # 14 -> t3
        self.assertEqual(req("steel_greatsword"), 5)    # 18 -> t4
        self.assertEqual(req("consecrated_maul"), 8)    # 24 -> t5
        self.assertEqual(req("pyre_scepter"), 11)       # 28 -> t6
        self.assertEqual(req("worldsplitter"), 14)      # 38 -> t8

    def test_tier_is_derived_from_damage(self):
        engine = GameEngine(rng=random.Random(1))
        tier = lambda wid: engine.content.weapons[wid].tier
        self.assertEqual(tier("knife"), 0)              # 0 damage -> tier 0
        self.assertEqual(tier("sword"), 1)              # 5  -> ceil 1
        self.assertEqual(tier("axe"), 2)                # 9  -> ceil 2
        self.assertEqual(tier("longsword"), 3)          # 14 -> ceil 3
        self.assertEqual(tier("worldsplitter"), 8)      # 38 -> ceil 8
        self.assertEqual(combat.weapon_tier_from_damage(0), 0)
        self.assertEqual(combat.weapon_tier_from_damage(1), 1)
        self.assertEqual(combat.weapon_tier_from_damage(25), 5)
        self.assertEqual(combat.weapon_tier_from_damage(26), 6)

    def test_combat_swap_to_too_high_tier_is_blocked_without_state_mutation(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Fighter", "fighter")
        engine.player.owned_weapon_ids = (*engine.player.owned_weapon_ids, "worldsplitter")
        enemy = make_enemy()
        before = (
            engine.player.hp,
            engine.player.mana,
            engine.player.equipped_weapon_id,
            engine.player.owned_weapon_ids,
            enemy.hp,
            dict(engine.player.cooldowns),
            dict(enemy.cooldowns),
        )

        result = engine.run_combat_turn(enemy, "swap:worldsplitter")

        self.assertEqual(result.outcome, "blocked")
        self.assertIn("needs level 14", result.events[0])
        self.assertEqual(
            (
                engine.player.hp,
                engine.player.mana,
                engine.player.equipped_weapon_id,
                engine.player.owned_weapon_ids,
                enemy.hp,
                dict(engine.player.cooldowns),
                dict(enemy.cooldowns),
            ),
            before,
        )

    def test_combat_swap_to_high_tier_succeeds_at_required_level(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Fighter", "fighter")
        engine.player.level = 14
        engine.player.owned_weapon_ids = (*engine.player.owned_weapon_ids, "worldsplitter")
        enemy = make_enemy()

        result = engine.run_combat_turn(enemy, "swap:worldsplitter")

        self.assertEqual(result.outcome, "ongoing")
        self.assertEqual(engine.player.equipped_weapon_id, "worldsplitter")

    def test_store_buy_keeps_high_tier_owned_but_does_not_equip_below_required_level(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Fighter", "fighter")
        engine.player.gold = 5000
        place = engine.current_place()
        engine.content.places[place.id] = replace(place, store_inventory=("pyre_scepter",))

        result = engine.buy_item("pyre_scepter")

        self.assertTrue(result.success)
        self.assertIn("pyre_scepter", engine.player.owned_weapon_ids)
        self.assertEqual(engine.player.equipped_weapon_id, "worn_shortsword")  # fighter start weapon
        self.assertIn("Requires level 11", result.message)               # pyre_scepter 28 -> t6 -> L11

    def test_store_tier_2_weapon_equips_at_level_1(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Fighter", "fighter")
        engine.player.gold = 500
        place = engine.content.places[engine.player.current_place_id]
        engine.content.places[place.id] = replace(place, store_inventory=("axe",))

        result = engine.buy_item("axe")

        self.assertTrue(result.success)
        self.assertIn("axe", engine.player.owned_weapon_ids)
        self.assertEqual(engine.player.equipped_weapon_id, "axe")


def make_enemy() -> Enemy:
    return Enemy(
        id="dummy",
        name="Dummy",
        level=1,
        max_hp=100,
        hp=100,
        damage=1,
        armor=0,
        speed=1,
        resistances={},
        action_ids=("quick",),
        xp_reward=0,
        gold_min=0,
        gold_max=0,
    )


if __name__ == "__main__":
    unittest.main()
