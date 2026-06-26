import random
import unittest

from rpg_game.core.game import GameEngine


def _cleric_with_points(points: int = 12) -> GameEngine:
    engine = GameEngine(rng=random.Random(1))
    engine.start_new_game("Cleric", "cleric")
    engine.player.talent_points = points
    return engine


class SkillEquippingTests(unittest.TestCase):
    def test_equippable_skills_lists_unlocked_actives(self):
        engine = _cleric_with_points()
        engine.allocate_talent("cleric_light_l2_mend")

        ids = {skill.id for skill in engine.equippable_skills()}

        self.assertEqual(ids, {"smite", "mend"})

    def test_equip_rejects_locked_skill(self):
        engine = _cleric_with_points()

        with self.assertRaises(ValueError):
            engine.equip_skill("curse")  # not unlocked

    def test_equip_rejects_when_four_already_equipped(self):
        engine = _cleric_with_points()
        engine.allocate_talent("cleric_light_l2_mend")
        engine.allocate_talent("cleric_pest_p1_plague_bolt")
        engine.allocate_talent("cleric_pest_p2_drain")
        # smite, mend, plague_bolt, drain auto-equipped -> 4 full
        self.assertEqual(len(engine.player.equipped_skill_ids), 4)
        # free a slot, unlock a fifth active, then re-fill
        engine.unequip_skill("drain")
        engine.allocate_talent("cleric_light_l3_devotion")  # passive
        engine.allocate_talent("cleric_light_l4_sanctuary")  # auto-equips -> 4 again

        with self.assertRaises(ValueError):
            engine.equip_skill("drain")  # drain unlocked but no free slot

    def test_unequip_then_equip_swaps_skill(self):
        engine = _cleric_with_points()
        engine.allocate_talent("cleric_light_l2_mend")
        engine.allocate_talent("cleric_pest_p1_plague_bolt")
        engine.allocate_talent("cleric_pest_p2_drain")

        engine.unequip_skill("mend")
        self.assertNotIn("mend", engine.player.equipped_skill_ids)

        engine.equip_skill("mend")
        self.assertIn("mend", engine.player.equipped_skill_ids)
        self.assertLessEqual(len(engine.player.equipped_skill_ids), 4)

    def test_unequip_rejects_not_equipped(self):
        engine = _cleric_with_points()

        with self.assertRaises(ValueError):
            engine.unequip_skill("mend")  # not equipped


class FleeTests(unittest.TestCase):
    def test_flee_success_ends_encounter_without_damage(self):
        engine = GameEngine(rng=random.Random(1))  # first roll 0.134 < 0.60 (even level)
        engine.start_new_game("Hero", "fighter")
        rat = engine.content.enemies["giant_rat"].create_enemy()

        result = engine.attempt_flee(rat)

        self.assertEqual(result.outcome, "fled")
        self.assertEqual(engine.player.hp, engine.player.max_hp)
        self.assertEqual(rat.hp, rat.max_hp)

    def test_flee_failure_gives_enemy_a_free_attack(self):
        engine = GameEngine(rng=random.Random(0))  # first roll 0.844 >= 0.60 (even level)
        engine.start_new_game("Hero", "fighter")
        rat = engine.content.enemies["giant_rat"].create_enemy()

        result = engine.attempt_flee(rat)

        self.assertEqual(result.outcome, "ongoing")
        self.assertEqual(engine.player.hp, 92)  # took the free hit (rolled enemy attack)
        self.assertTrue(any("failed to flee" in event for event in result.events))

    def test_flee_chance_drops_against_higher_level_enemy(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Hero", "fighter")  # level 1
        weak = engine.content.enemies["giant_rat"].create_enemy()
        strong = engine.content.enemies["giant_rat"].create_enemy()
        strong.level = engine.player.level + 5  # well above the player

        self.assertGreater(engine.flee_chance(weak), engine.flee_chance(strong))


if __name__ == "__main__":
    unittest.main()
