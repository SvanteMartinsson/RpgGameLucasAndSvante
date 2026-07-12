import unittest

from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine


class InventoryTests(unittest.TestCase):
    def test_hp_potion_is_stackable_and_consumed(self):
        engine = GameEngine(content=load_content())
        engine.start_new_game("Tester", "fighter")
        engine.player.inventory.add_consumable("hp_potion", 2)
        engine.player.hp = 40

        result = engine.use_consumable("hp_potion")

        self.assertTrue(result.success)
        # heals +50, capped at max HP (class-identity pass lowered fighter's base)
        self.assertEqual(engine.player.hp, min(90, engine.effective_stat("max_hp")))
        self.assertEqual(engine.player.inventory.count("hp_potion"), 1)


if __name__ == "__main__":
    unittest.main()
