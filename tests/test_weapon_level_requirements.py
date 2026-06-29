import random
import unittest
from dataclasses import replace

from rpg_game.core import combat
from rpg_game.core.entities import Enemy
from rpg_game.core.game import GameEngine


class FighterStartWeaponTest(unittest.TestCase):
    def test_fighter_starts_with_worn_shortsword(self):
        # B33: the fighter opens with the weak worn_shortsword (d2), not the sword.
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        self.assertEqual(engine.player.equipped_weapon_id, "worn_shortsword")
        self.assertEqual(engine.player.owned_weapon_ids, ("worn_shortsword",))
        self.assertEqual(engine.content.weapons["worn_shortsword"].damage_bonus, 2)


class WeaponLevelRequirementTests(unittest.TestCase):
    def test_weapon_required_level_uses_tier_minus_2_floor_1(self):
        engine = GameEngine(rng=random.Random(1))

        self.assertEqual(combat.weapon_required_level(engine.content.weapons["sword"]), 1)
        self.assertEqual(combat.weapon_required_level(engine.content.weapons["longsword"]), 1)
        self.assertEqual(combat.weapon_required_level(engine.content.weapons["steel_greatsword"]), 1)
        self.assertEqual(combat.weapon_required_level(engine.content.weapons["consecrated_maul"]), 2)
        self.assertEqual(combat.weapon_required_level(engine.content.weapons["pyre_scepter"]), 3)
        self.assertEqual(combat.weapon_required_level(engine.content.weapons["worldsplitter"]), 4)

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
        self.assertIn("needs level 4", result.events[0])
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
        engine.player.level = 4
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
        self.assertIn("Requires level 3", result.message)

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
