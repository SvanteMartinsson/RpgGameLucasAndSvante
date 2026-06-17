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


class BruiserArchetypeTests(unittest.TestCase):
    def test_bruiser_uses_heavy_attack(self):
        engine = _engine()
        bear = engine.content.enemies["cave_bear"].create_enemy()

        action = combat.choose_enemy_action(bear, engine.player, engine.content.actions, engine.rng)

        self.assertEqual(action.id, "bear_maul")

    def test_faster_player_acts_before_bruiser(self):
        engine = _engine()  # fighter speed 11
        bear = engine.content.enemies["cave_bear"].create_enemy()  # speed 6

        order = combat.ordered_by_speed(engine.player, bear)

        self.assertEqual(order, [engine.player, bear])

    def test_heavy_attack_deals_its_stated_damage(self):
        engine = _engine()
        bear = engine.content.enemies["cave_bear"].create_enemy()

        # damage 10 * 2.0 multiplier = 20 physical, 0 armor.
        damage = combat.calculate_enemy_damage(bear, engine.content.actions["bear_maul"], target_armor=0)

        self.assertEqual(damage, 20)

    def test_bruiser_deals_damage_after_player_in_a_full_turn(self):
        engine = _engine()
        bear = engine.content.enemies["cave_bear"].create_enemy()

        result = engine.run_combat_turn(bear, "quick")

        # Player (speed 11) acts first, then the bear mauls for 20 (hit_chance 1.0).
        self.assertEqual(engine.player.hp, 80)
        self.assertEqual(result.outcome, "ongoing")


class CasterArchetypeTests(unittest.TestCase):
    def test_telegraph_charge_deals_no_damage_and_announces(self):
        engine = _engine()
        acolyte = engine.content.enemies["plague_acolyte"].create_enemy()

        result = combat.enemy_take_turn(acolyte, engine.player, engine.content.actions, engine.rng)

        self.assertEqual(engine.player.hp, engine.player.max_hp)
        self.assertEqual(acolyte.charging_action_id, "acolyte_nuke")
        self.assertEqual(acolyte.mana, 30)  # mana paid on release, not on charge
        self.assertTrue(any("charges" in event for event in result.events))

    def test_nuke_releases_next_round(self):
        engine = _engine()
        acolyte = engine.content.enemies["plague_acolyte"].create_enemy()

        combat.enemy_take_turn(acolyte, engine.player, engine.content.actions, engine.rng)  # charge
        combat.enemy_take_turn(acolyte, engine.player, engine.content.actions, engine.rng)  # release

        # damage 7 * 3.0 = 21 fire, no resistance.
        self.assertEqual(engine.player.hp, engine.player.max_hp - 21)
        self.assertEqual(acolyte.charging_action_id, "")
        self.assertEqual(acolyte.cooldowns.get("acolyte_nuke", 0), 2)

    def test_caster_killed_during_charge_never_fires_nuke(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Cleric", "cleric")  # speed 10 < acolyte 14
        acolyte = engine.content.enemies["plague_acolyte"].create_enemy()
        acolyte.hp = 1

        # Acolyte acts first (charges), then the cleric's smite kills it the same round.
        result = engine.run_combat_turn(acolyte, "smite")

        self.assertEqual(result.outcome, "victory")
        self.assertEqual(engine.player.hp, engine.player.max_hp)  # nuke never fired

    def test_nuke_on_cooldown_falls_back_to_bolt(self):
        engine = _engine()
        acolyte = engine.content.enemies["plague_acolyte"].create_enemy()

        combat.enemy_take_turn(acolyte, engine.player, engine.content.actions, engine.rng)  # charge
        combat.enemy_take_turn(acolyte, engine.player, engine.content.actions, engine.rng)  # release (sets cooldown)

        action = combat.choose_enemy_action(acolyte, engine.player, engine.content.actions, engine.rng)

        self.assertEqual(action.id, "acolyte_bolt")


if __name__ == "__main__":
    unittest.main()
