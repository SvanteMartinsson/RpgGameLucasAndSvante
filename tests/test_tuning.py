import random
import unittest
from dataclasses import replace

from rpg_game.core.game import GameEngine
from rpg_game.presentation import terminal


def _sell_here(engine, *item_ids):
    """Make the player's current store sell the given items (decouples the buy
    mechanic from per-store curated stock)."""
    place = engine.content.places[engine.player.current_place_id]
    engine.content.places[place.id] = replace(place, store_inventory=item_ids)


class WeaponOwnershipTests(unittest.TestCase):
    def test_new_tank_owns_only_starting_weapon(self):
        engine = GameEngine()
        engine.start_new_game("Tank", "tank")

        self.assertEqual(engine.player.owned_weapon_ids, ("mace",))
        self.assertEqual([weapon.id for weapon in engine.owned_weapons()], ["mace"])

    def test_buying_weapon_adds_to_owned_and_equips(self):
        engine = GameEngine()
        engine.start_new_game("Tank", "tank")
        engine.player.gold = 1000
        _sell_here(engine, "axe")

        result = engine.buy_item("axe")

        self.assertTrue(result.success)
        self.assertEqual(set(engine.player.owned_weapon_ids), {"mace", "axe"})
        self.assertEqual(engine.player.equipped_weapon_id, "axe")

    def test_swap_menu_lists_only_owned_weapons(self):
        engine = GameEngine()
        engine.start_new_game("Tank", "tank")

        owned = [weapon.id for weapon in engine.owned_weapons()]
        self.assertEqual(owned, ["mace"])
        self.assertIn("axe", engine.content.weapons)  # exists in content...
        self.assertNotIn("axe", owned)  # ...but is not listed until owned

        engine.player.gold = 1000
        _sell_here(engine, "axe")
        engine.buy_item("axe")
        self.assertIn("axe", [weapon.id for weapon in engine.owned_weapons()])

    def test_swapping_to_unowned_weapon_is_rejected(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Tank", "tank")
        enemy = engine.content.enemies["giant_rat"].create_enemy()

        with self.assertRaises(ValueError):
            engine.run_combat_turn(enemy, "swap:axe")


class CounterDisplayTests(unittest.TestCase):
    def test_counter_description_shows_power_scaling_not_zero(self):
        engine = GameEngine()
        engine.start_new_game("Tank", "tank")

        effect = engine.content.actions["counter"].effects[0]
        description = terminal.describe_effect(effect)

        self.assertNotIn("reflect 0", description)
        self.assertIn("Power", description)


if __name__ == "__main__":
    unittest.main()
