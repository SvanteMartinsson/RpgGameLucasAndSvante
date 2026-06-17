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


if __name__ == "__main__":
    unittest.main()
