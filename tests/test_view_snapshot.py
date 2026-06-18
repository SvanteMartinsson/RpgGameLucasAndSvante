import unittest
from dataclasses import FrozenInstanceError

from rpg_game.core import view
from rpg_game.core.game import GameEngine


class ViewSnapshotTests(unittest.TestCase):
    def test_snapshot_exposes_player_place_and_connections(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "rogue")

        snapshot = view.build_snapshot(engine)

        self.assertEqual(snapshot.player.name, "Hero")
        self.assertEqual(snapshot.player.class_id, "rogue")
        self.assertEqual(snapshot.player.crit_chance, engine.player.crit_chance)
        self.assertEqual(snapshot.place.id, engine.content.start_place_id)
        self.assertGreater(len(snapshot.connections), 0)

    def test_snapshot_marks_weapon_level_requirements(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        engine.player.owned_weapon_ids = ("sword", "worldsplitter")

        snapshot = view.build_snapshot(engine)
        weapons = {weapon.id: weapon for weapon in snapshot.weapons}

        self.assertTrue(weapons["sword"].equippable)
        self.assertFalse(weapons["worldsplitter"].equippable)
        self.assertEqual(weapons["worldsplitter"].required_level, 4)

    def test_snapshot_is_immutable(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        snapshot = view.build_snapshot(engine)

        with self.assertRaises(FrozenInstanceError):
            snapshot.player.gold = 999


if __name__ == "__main__":
    unittest.main()
