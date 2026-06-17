import random
import unittest

from rpg_game.core import combat
from rpg_game.core.game import GameEngine


def _engine():
    engine = GameEngine(rng=random.Random(1))
    engine.start_new_game("Hero", "fighter")
    return engine


class HealerArchetypeTests(unittest.TestCase):
    def test_healer_heals_when_below_50_percent_and_ready(self):
        engine = _engine()
        priest = engine.content.enemies["undead_priest"].create_enemy()
        priest.hp = 15  # 37.5% of 40

        action = combat.choose_enemy_action(priest, engine.player, engine.content.actions, engine.rng)

        self.assertEqual(action.id, "priest_heal")

        result = combat.enemy_take_turn(priest, engine.player, engine.content.actions, engine.rng)
        self.assertEqual(priest.hp, 33)
        self.assertTrue(any("healed" in event for event in result.events))

    def test_healer_attacks_when_above_50_percent(self):
        engine = _engine()
        priest = engine.content.enemies["undead_priest"].create_enemy()
        priest.hp = 30  # 75% of 40

        action = combat.choose_enemy_action(priest, engine.player, engine.content.actions, engine.rng)

        self.assertEqual(action.id, "priest_strike")

    def test_healer_attacks_when_below_50_but_heal_on_cooldown(self):
        engine = _engine()
        priest = engine.content.enemies["undead_priest"].create_enemy()
        priest.hp = 15
        priest.cooldowns["priest_heal"] = 2  # heal not ready

        action = combat.choose_enemy_action(priest, engine.player, engine.content.actions, engine.rng)

        self.assertEqual(action.id, "priest_strike")

    def test_healer_attacks_when_below_50_but_out_of_mana(self):
        engine = _engine()
        priest = engine.content.enemies["undead_priest"].create_enemy()
        priest.hp = 15
        priest.mana = 0  # cannot afford heal

        action = combat.choose_enemy_action(priest, engine.player, engine.content.actions, engine.rng)

        self.assertEqual(action.id, "priest_strike")

    def test_heal_caps_at_max_hp(self):
        engine = _engine()
        priest = engine.content.enemies["undead_priest"].create_enemy()
        priest.hp = 30

        combat.resolve_action(priest, engine.player, engine.content.actions["priest_heal"], engine.rng)

        self.assertEqual(priest.hp, priest.max_hp)
        self.assertEqual(priest.hp, 40)


class AIRuleSystemTests(unittest.TestCase):
    def test_ai_priority_first_matching_ready_rule_fires(self):
        engine = _engine()
        priest = engine.content.enemies["undead_priest"].create_enemy()
        priest.hp = 10  # both rules could be relevant; rule 1 must win

        action = combat.choose_enemy_action(priest, engine.player, engine.content.actions, engine.rng)

        self.assertEqual(action.id, "priest_heal")

    def test_ai_never_selects_action_on_cooldown(self):
        engine = _engine()
        rat = engine.content.enemies["giant_rat"].create_enemy()  # no ai -> fallback
        rat.cooldowns["power"] = 3
        rat.cooldowns["normal"] = 3

        for _ in range(50):
            action = combat.choose_enemy_action(rat, engine.player, engine.content.actions, engine.rng)
            self.assertEqual(action.id, "quick")

    def test_fallback_is_uniform_among_ready_actions(self):
        engine = _engine()
        rat = engine.content.enemies["giant_rat"].create_enemy()  # no ai -> fallback

        chosen = {
            combat.choose_enemy_action(rat, engine.player, engine.content.actions, engine.rng).id
            for _ in range(200)
        }

        self.assertEqual(chosen, {"power", "normal", "quick"})

    def test_existing_grunts_keep_simple_role(self):
        engine = _engine()
        rat = engine.content.enemies["giant_rat"].create_enemy()
        undead = engine.content.enemies["undead"].create_enemy()

        for enemy in (rat, undead):
            action = combat.choose_enemy_action(enemy, engine.player, engine.content.actions, engine.rng)
            self.assertIn(action.id, {"power", "normal", "quick"})


if __name__ == "__main__":
    unittest.main()
