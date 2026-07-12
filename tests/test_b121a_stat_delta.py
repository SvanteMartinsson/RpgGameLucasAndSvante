"""B121a: the character-screen stat rows (total + from_gear) are computed in the
core and exposed on the snapshot, so the presentation only draws them.

Covers: empty vs full equipment (from_gear = 0 vs the gear contribution), the
weapon's damage_bonus folded into the Power row, and total == effective_stat.
"""

import random
import unittest

from rpg_game.core import view
from rpg_game.core.game import GameEngine


class StatDeltaSnapshotTests(unittest.TestCase):
    def make_engine(self) -> GameEngine:
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Hero", "fighter")
        return engine

    def own(self, engine: GameEngine, *gear_ids: str) -> None:
        engine.player.owned_gear_ids = tuple(dict.fromkeys((*engine.player.owned_gear_ids, *gear_ids)))

    def stat_row(self, snapshot, stat):
        return next(row for row in snapshot.player.stats if row.stat == stat)

    def test_bare_character_has_zero_gear_delta(self):
        engine = self.make_engine()  # a fresh fighter starts with no gear equipped

        snapshot = view.build_snapshot(engine)
        weapon = engine.content.weapons[engine.player.equipped_weapon_id]

        for row in snapshot.player.stats:
            if row.stat == "damage":
                # The Power row always carries the equipped weapon's flat bonus.
                self.assertEqual(row.from_gear, weapon.damage_bonus)
                self.assertEqual(row.total, engine.effective_stat("damage") + weapon.damage_bonus)
            else:
                self.assertEqual(row.from_gear, 0)
                self.assertEqual(row.total, engine.effective_stat(row.stat))

    def test_equipped_gear_shows_up_in_from_gear_and_total(self):
        engine = self.make_engine()
        # padded_vest: armor +2, max_hp +5 ; novice_ring: damage +1
        self.own(engine, "padded_vest", "novice_ring")
        base_armor = engine.player.armor
        base_hp = engine.player.max_hp
        weapon = engine.content.weapons[engine.player.equipped_weapon_id]

        self.assertTrue(engine.equip_gear("padded_vest", "chest").success)
        self.assertTrue(engine.equip_gear("novice_ring").success)

        snapshot = view.build_snapshot(engine)

        armor = self.stat_row(snapshot, "armor")
        self.assertEqual(armor.from_gear, 2)
        self.assertEqual(armor.total, base_armor + 2)

        max_hp = self.stat_row(snapshot, "max_hp")
        self.assertEqual(max_hp.from_gear, 5)
        self.assertEqual(max_hp.total, base_hp + 5)

        power = self.stat_row(snapshot, "damage")
        self.assertEqual(power.from_gear, weapon.damage_bonus + 1)
        self.assertEqual(power.total, engine.effective_stat("damage") + weapon.damage_bonus)
        # The Power total stays in lock-step with the existing total_damage field.
        self.assertEqual(power.total, snapshot.player.total_damage)

    def test_unequip_restores_zero_gear_delta(self):
        engine = self.make_engine()
        self.own(engine, "padded_vest")
        engine.equip_gear("padded_vest", "chest")
        engine.unequip_gear("chest")

        snapshot = view.build_snapshot(engine)
        armor = self.stat_row(snapshot, "armor")
        self.assertEqual(armor.from_gear, 0)
        self.assertEqual(armor.total, engine.player.armor)

    def test_stat_rows_labels_and_coverage(self):
        engine = self.make_engine()
        snapshot = view.build_snapshot(engine)
        rows = {row.stat: row.label for row in snapshot.player.stats}
        # Power is the display label for the damage stat (per CHARACTER_SCREEN.md).
        self.assertEqual(rows.get("damage"), "Power")
        for stat in ("max_hp", "max_mana", "armor", "speed", "crit_chance", "wisdom"):
            self.assertIn(stat, rows)


if __name__ == "__main__":
    unittest.main()
