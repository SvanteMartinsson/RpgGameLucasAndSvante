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
        self.assertEqual(weapons["worldsplitter"].required_level, 14)

    def test_weapon_type_is_exposed_and_surfaced(self):
        # B4: the weapon TYPE (category) + stats live in the snapshot, and the
        # presentation text helpers surface them so a NAMED weapon's type (e.g.
        # is Venomfang a melee or a magic weapon?) is no longer invisible.
        from rpg_game.presentation import ui_text as T

        engine = GameEngine()
        engine.start_new_game("Hero", "mage")
        engine.player.owned_weapon_ids = ("staff", "venomfang")
        snapshot = view.build_snapshot(engine)
        weapons = {weapon.id: weapon for weapon in snapshot.weapons}

        # data is exposed on the snapshot
        self.assertEqual(weapons["staff"].category, "magic")
        self.assertEqual(weapons["venomfang"].category, "melee")
        self.assertEqual(weapons["venomfang"].damage_type, "poison")  # B37: name now matches the type

        # presentation surfaces the type + stats in the visible strings
        label = T.weapon_label(weapons["venomfang"])
        self.assertIn("Venomfang", label)
        self.assertIn("Melee", label)
        preview = T.weapon_preview(weapons["staff"])
        for token in ("Magic", "tier", "Lv"):
            self.assertIn(token, preview)

    def test_snapshot_is_immutable(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        snapshot = view.build_snapshot(engine)

        with self.assertRaises(FrozenInstanceError):
            snapshot.player.gold = 999


if __name__ == "__main__":
    unittest.main()
