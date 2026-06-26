import json
import os
import tempfile
import unittest

from rpg_game.core.entities import ActiveStatus
from rpg_game.core.game import GameEngine


class SaveLoadTests(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self._dir.name, "savegame.json")

    def tearDown(self):
        self._dir.cleanup()

    def _rich_engine(self) -> GameEngine:
        engine = GameEngine()
        engine.start_new_game("Hero", "cleric")
        player = engine.player
        player.gold = 123
        player.hp = 42
        player.mana = 7
        player.xp = 80
        player.talent_points = 2
        engine.allocate_talent("cleric_light_l2_mend")
        player.owned_weapon_ids = ("holy_mace", "staff", "rimebrand")
        player.equipped_weapon_id = "staff"
        player.inventory.add_consumable("hp_potion", 3)
        player.inventory.add_consumable("rat_pelt", 2)
        player.active_statuses.append(
            ActiveStatus(type="regen", magnitude=8, duration=3, tick_timing="round_end")
        )
        player.cooldowns["smite"] = 2
        return engine

    def test_round_trip_reproduces_identical_state(self):
        engine = self._rich_engine()
        engine.save(self.path)

        loaded = GameEngine(content=engine.content)
        result = loaded.load(self.path)

        self.assertTrue(result.success)
        # Whole-player equality covers every field (inventory, statuses, sets, tuples).
        self.assertEqual(loaded.player, engine.player)
        # Spot-check the headline fields too.
        self.assertEqual(loaded.player.gold, 123)
        self.assertEqual(loaded.player.hp, 42)
        self.assertEqual(loaded.player.equipped_weapon_id, "staff")
        self.assertEqual(loaded.player.owned_weapon_ids, ("holy_mace", "staff", "rimebrand"))
        self.assertEqual(loaded.player.learned_talent_ids, engine.player.learned_talent_ids)
        self.assertEqual(loaded.player.equipped_skill_ids, engine.player.equipped_skill_ids)
        # rest_voucher is granted at new game (B20) and round-trips like any item.
        self.assertEqual(loaded.player.inventory.consumables,
                         {"rest_voucher": 1, "hp_potion": 3, "rat_pelt": 2})
        self.assertEqual(loaded.player.current_place_id, engine.player.current_place_id)

    def test_save_returns_structured_result_and_writes_file(self):
        engine = self._rich_engine()
        result = engine.save(self.path)
        self.assertTrue(result.success)
        self.assertTrue(os.path.exists(self.path))

    def test_load_with_missing_fields_does_not_crash_and_defaults(self):
        with open(self.path, "w", encoding="utf-8") as save_file:
            json.dump({"player": {"name": "Old Hero", "gold": 5}}, save_file)

        engine = GameEngine()
        result = engine.load(self.path)

        self.assertTrue(result.success)
        self.assertEqual(engine.player.name, "Old Hero")
        self.assertEqual(engine.player.gold, 5)
        self.assertEqual(engine.player.level, 1)  # defaulted
        self.assertEqual(engine.player.owned_weapon_ids, ())  # defaulted
        self.assertEqual(engine.player.current_place_id, engine.content.start_place_id)  # defaulted
        # the engine remains usable
        self.assertIsNotNone(engine.current_place())

    def test_load_missing_file_returns_failure(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        result = engine.load(os.path.join(self._dir.name, "nope.json"))
        self.assertFalse(result.success)


if __name__ == "__main__":
    unittest.main()
