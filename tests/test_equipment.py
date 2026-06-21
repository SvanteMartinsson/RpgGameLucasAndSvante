import random
import tempfile
import unittest

from rpg_game.core import combat
from rpg_game.core.entities import EffectSpec, Weapon
from rpg_game.core.game import GameEngine


class EquipmentCoreTests(unittest.TestCase):
    def make_engine(self) -> GameEngine:
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Gear", "fighter")
        return engine

    def own(self, engine: GameEngine, *gear_ids: str) -> None:
        engine.player.owned_gear_ids = tuple(dict.fromkeys((*engine.player.owned_gear_ids, *gear_ids)))

    def test_effective_stats_change_on_equip_and_unequip(self):
        engine = self.make_engine()
        self.own(engine, "padded_vest")

        result = engine.equip_gear("padded_vest", "chest")

        self.assertTrue(result.success)
        self.assertEqual(engine.gear_modifier_total("armor"), 2)
        self.assertEqual(engine.gear_modifier_total("max_hp"), 5)
        self.assertEqual(engine.effective_stat("armor"), engine.player.armor + 2)
        self.assertEqual(engine.effective_stat("max_hp"), engine.player.max_hp + 5)

        result = engine.unequip_gear("chest")

        self.assertTrue(result.success)
        self.assertEqual(engine.effective_stat("armor"), engine.player.armor)
        self.assertEqual(engine.effective_stat("max_hp"), engine.player.max_hp)

    def test_combat_reads_effective_armor_crit_speed_and_damage(self):
        engine = self.make_engine()
        engine.player.crit_chance = 0
        self.own(engine, "padded_vest", "lucky_loop", "swift_ring", "novice_ring")
        engine.equip_gear("padded_vest", "chest")
        engine.equip_gear("lucky_loop")
        engine.equip_gear("swift_ring")
        engine.equip_gear("novice_ring")
        enemy = engine.content.enemies["giant_rat"].create_enemy()

        damage_effect = EffectSpec(type="damage", scale="flat", magnitude=10, damage_type="physical")
        self.assertEqual(combat.calculate_effect_damage(enemy, engine.player, None, damage_effect), 8)
        self.assertEqual(combat.effective_crit_chance(engine.player, damage_effect), 3)
        self.assertEqual(combat.ordered_by_speed(engine.player, enemy)[0], engine.player)

        attack_effect = EffectSpec(type="damage", scale="basic_attack", multiplier=1.0, damage_type="weapon")
        self.assertEqual(
            combat.calculate_effect_damage(engine.player, enemy, Weapon("knife", "Knife", 0, 0), attack_effect),
            engine.player.base_damage + 1,
        )

    def test_wrong_slot_and_level_requirement_block_without_mutation(self):
        engine = self.make_engine()
        self.own(engine, "training_cap", "veteran_ring")

        wrong_slot = engine.equip_gear("training_cap", "chest")
        high_level = engine.equip_gear("veteran_ring")

        self.assertFalse(wrong_slot.success)
        self.assertFalse(high_level.success)
        self.assertEqual(engine.player.equipped_gear, {})
        self.assertEqual(engine.effective_stat("damage"), engine.player.base_damage)

    def test_three_rings_equip_and_fourth_requires_unequip(self):
        engine = self.make_engine()
        self.own(engine, "novice_ring", "swift_ring", "focus_band", "lucky_loop")

        self.assertTrue(engine.equip_gear("novice_ring").success)
        self.assertTrue(engine.equip_gear("swift_ring").success)
        self.assertTrue(engine.equip_gear("focus_band").success)
        fourth = engine.equip_gear("lucky_loop")

        self.assertFalse(fourth.success)
        self.assertEqual(set(engine.player.equipped_gear), {"ring_1", "ring_2", "ring_3"})

        self.assertTrue(engine.unequip_gear("ring_2").success)
        self.assertTrue(engine.equip_gear("lucky_loop").success)

    def test_hp_and_mana_caps_do_not_heal_and_clamp_on_unequip(self):
        engine = self.make_engine()
        engine.player.hp = 50
        engine.player.mana = 5
        self.own(engine, "padded_vest", "focus_band")

        engine.equip_gear("padded_vest", "chest")
        engine.equip_gear("focus_band")

        self.assertEqual(engine.player.hp, 50)
        self.assertEqual(engine.player.mana, 5)
        self.assertEqual(engine.effective_stat("max_hp"), engine.player.max_hp + 5)
        self.assertEqual(engine.effective_stat("max_mana"), engine.player.max_mana + 10)

        engine.player.hp = engine.effective_stat("max_hp")
        engine.player.mana = engine.effective_stat("max_mana")
        engine.unequip_gear("chest")
        engine.unequip_gear("ring_1")

        self.assertEqual(engine.player.hp, engine.player.max_hp)
        self.assertEqual(engine.player.mana, engine.player.max_mana)

    def test_save_load_preserves_owned_and_equipped_gear(self):
        engine = self.make_engine()
        self.own(engine, "padded_vest", "novice_ring")
        engine.equip_gear("padded_vest", "chest")
        engine.equip_gear("novice_ring")

        with tempfile.TemporaryDirectory() as folder:
            path = f"{folder}/save.json"
            engine.save(path)
            loaded = GameEngine(content=engine.content)
            result = loaded.load(path)

        self.assertTrue(result.success)
        self.assertIn("padded_vest", loaded.player.owned_gear_ids)
        self.assertEqual(loaded.player.equipped_gear["chest"], "padded_vest")
        self.assertEqual(loaded.effective_stat("armor"), loaded.player.armor + 2)
        self.assertEqual(loaded.effective_stat("damage"), loaded.player.base_damage + 1)


if __name__ == "__main__":
    unittest.main()
