import random
import unittest

from rpg_game.core import combat
from rpg_game.core.game import GameEngine


class ClericClassTests(unittest.TestCase):
    def test_mend_scales_with_wisdom_and_never_overheals(self):
        # B-wisdom: mend is no longer a flat 25 — it scales with the caster's wisdom.
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Cleric", "cleric")
        target = engine.content.enemies["giant_rat"].create_enemy()
        engine.player.max_hp = 500

        engine.player.hp = 50
        result = combat.resolve_action(engine.player, target, engine.content.actions["mend"], engine.rng)
        low_heal = engine.player.hp - 50
        self.assertGreater(low_heal, 0)
        self.assertEqual(result.events[0], "Cleric used Mend.")  # action line precedes effect

        engine.player.wisdom += 40           # more wisdom -> a bigger heal
        engine.player.hp = 50
        combat.resolve_action(engine.player, target, engine.content.actions["mend"], engine.rng)
        high_heal = engine.player.hp - 50
        self.assertGreater(high_heal, low_heal)

        # never overheals past the (derived) max
        engine.player.hp = engine.effective_stat("max_hp") - 1
        combat.resolve_action(engine.player, target, engine.content.actions["mend"], engine.rng)
        self.assertEqual(engine.player.hp, engine.effective_stat("max_hp"))

    def test_sanctuary_regens_8_for_exactly_3_rounds(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Cleric", "cleric")
        target = engine.content.enemies["giant_rat"].create_enemy()
        engine.player.hp = 50

        combat.resolve_action(engine.player, target, engine.content.actions["sanctuary"], engine.rng)

        combat.tick_statuses(engine.player, "round_end")
        self.assertEqual(engine.player.hp, 58)
        combat.tick_statuses(engine.player, "round_end")
        self.assertEqual(engine.player.hp, 66)
        combat.tick_statuses(engine.player, "round_end")
        self.assertEqual(engine.player.hp, 74)
        combat.tick_statuses(engine.player, "round_end")
        self.assertEqual(engine.player.hp, 74)
        self.assertEqual(engine.player.active_statuses, [])

    def test_drain_heals_50_percent_of_damage_with_half_up_rounding(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Cleric", "cleric")
        target = engine.content.enemies["giant_rat"].create_enemy()
        target.hp = 100
        engine.player.hp = 80

        result = combat.resolve_action(
            engine.player,
            target,
            engine.content.actions["drain"],
            engine.rng,
            weapon=engine.content.weapons["holy_mace"],
        )

        # drain heals 50% of the damage dealt (half-up); the damage is now wisdom-
        # scaled, so assert the RATIO, not a fixed number.
        from rpg_game.core.progression import round_half_up
        self.assertGreater(result.total_damage, 0)
        self.assertEqual(engine.player.hp, 80 + round_half_up(result.total_damage * 0.5))
        self.assertEqual(target.hp, 100 - result.total_damage)

    def test_curse_reduces_power_by_4_for_3_rounds_then_restores(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Cleric", "cleric")
        target = engine.content.enemies["giant_rat"].create_enemy()
        target.damage = 10

        combat.resolve_action(engine.player, target, engine.content.actions["curse"], engine.rng)

        self.assertEqual(target.damage, 6)
        combat.tick_statuses(target, "round_end")
        self.assertEqual(target.damage, 6)
        combat.tick_statuses(target, "round_end")
        self.assertEqual(target.damage, 6)
        combat.tick_statuses(target, "round_end")
        self.assertEqual(target.damage, 10)
        self.assertEqual(target.active_statuses, [])

    def test_virulence_adds_1_duration_and_2_magnitude_to_own_poisons(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Cleric", "cleric")
        target_without = engine.content.enemies["giant_rat"].create_enemy()
        target_with = engine.content.enemies["giant_rat"].create_enemy()

        combat.resolve_action(engine.player, target_without, engine.content.actions["plague_bolt"], engine.rng)
        engine.player.talent_points = 3
        engine.allocate_talent("cleric_pest_p1_plague_bolt")
        engine.allocate_talent("cleric_pest_p2_drain")
        engine.allocate_talent("cleric_pest_p3_virulence")
        combat.resolve_action(engine.player, target_with, engine.content.actions["plague_bolt"], engine.rng)

        normal_poison = target_without.active_statuses[0]
        virulent_poison = target_with.active_statuses[0]
        # plague_bolt's base magnitude is now wisdom-scaled; virulence adds a fixed
        # +2 magnitude / +1 duration on top, so assert the RELATIONSHIP.
        self.assertEqual(normal_poison.duration, 3)
        self.assertEqual(virulent_poison.magnitude, normal_poison.magnitude + 2)
        self.assertEqual(virulent_poison.duration, normal_poison.duration + 1)

    def test_talent_prereq_and_talent_points_are_enforced(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Cleric", "cleric")
        engine.player.talent_points = 1

        # prereq enforcement: a tier-3 node is locked until its tier-2 prereq is learned
        with self.assertRaises(ValueError):
            engine.allocate_talent("cleric_light_l3_devotion")

        available = {talent.id for talent in engine.available_talents()}
        self.assertNotIn("cleric_light_l1_smite", available)            # starter pre-learned
        self.assertIn("cleric_light_l1_smite", engine.player.learned_talent_ids)
        self.assertIn("cleric_light_l2_mend", available)                # prereq (smite) met free
        self.assertIn("cleric_pest_p1_plague_bolt", available)          # other branch root

        # points enforcement: spend the one point, the next allocation is then rejected
        engine.allocate_talent("cleric_light_l2_mend")
        self.assertEqual(engine.player.talent_points, 0)
        with self.assertRaises(ValueError):
            engine.allocate_talent("cleric_pest_p1_plague_bolt")

    def test_max_4_equipped_skills_is_enforced(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Cleric", "cleric")
        engine.player.equipped_skill_ids = ("smite", "mend", "sanctuary", "plague_bolt")
        engine.player.talent_points = 1
        engine.player.learned_talent_ids.update({
            "cleric_pest_p1_plague_bolt",
        })

        with self.assertRaises(ValueError):
            engine.allocate_talent("cleric_pest_p2_drain")

        self.assertEqual(engine.player.talent_points, 1)
        self.assertNotIn("cleric_pest_p2_drain", engine.player.learned_talent_ids)


if __name__ == "__main__":
    unittest.main()
