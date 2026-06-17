import random
import unittest

from rpg_game.core import combat
from rpg_game.core.game import GameEngine


class JunkNotUsableTests(unittest.TestCase):
    def test_using_junk_is_rejected_and_heals_nothing(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        engine.player.inventory.add_consumable("bone_dust", 2)
        engine.player.hp = 30

        result = engine.use_consumable("bone_dust")

        self.assertFalse(result.success)
        self.assertNotIn("healed 0", result.message)
        self.assertEqual(engine.player.hp, 30)  # unchanged
        self.assertEqual(engine.player.inventory.count("bone_dust"), 2)  # not consumed

    def test_player_with_only_junk_has_no_usable_consumables(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        engine.player.inventory.add_consumable("rat_pelt", 3)

        usable = [
            item_id
            for item_id in engine.player.inventory.consumables
            if engine.content.items[item_id].kind == "consumable"
        ]
        self.assertEqual(usable, [])


class EquipWeaponOutOfCombatTests(unittest.TestCase):
    def test_equipping_valid_owned_weapon_succeeds(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Hero", "fighter")
        engine.player.owned_weapon_ids = ("sword", "axe")
        engine.player.equipped_weapon_id = "sword"

        weapon = engine.content.weapons["axe"]
        action = combat.create_weapon_swap_action(weapon)
        result = combat.resolve_action(engine.player, engine.player, action, engine.rng, weapon=weapon)

        self.assertFalse(result.blocked)
        self.assertEqual(engine.player.equipped_weapon_id, "axe")

    def test_equipping_weapon_above_level_is_blocked(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Hero", "fighter")  # level 1
        engine.player.owned_weapon_ids = ("sword", "worldsplitter")  # tier 6 -> needs level 4
        engine.player.equipped_weapon_id = "sword"

        weapon = engine.content.weapons["worldsplitter"]
        action = combat.create_weapon_swap_action(weapon)
        result = combat.resolve_action(engine.player, engine.player, action, engine.rng, weapon=weapon)

        self.assertTrue(result.blocked)
        self.assertEqual(engine.player.equipped_weapon_id, "sword")  # unchanged


if __name__ == "__main__":
    unittest.main()
