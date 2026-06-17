import random
import unittest

from rpg_game.core import combat
from rpg_game.core.entities import ActiveStatus, EffectSpec
from rpg_game.core.game import GameEngine


class TankClassTests(unittest.TestCase):
    def test_block_reduces_all_incoming_damage_by_8_min_1_and_expires(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Tank", "tank")
        enemy = engine.content.enemies["giant_rat"].create_enemy()

        combat.resolve_action(engine.player, enemy, engine.content.actions["block"], engine.rng)

        self.assertEqual(combat.apply_damage_mitigation(10, engine.player, "fire"), 2)
        self.assertEqual(combat.apply_damage_mitigation(5, engine.player, "fire"), 1)
        combat.tick_statuses(engine.player, "round_end")
        self.assertEqual(combat.apply_damage_mitigation(10, engine.player, "fire"), 10)

    def test_block_cooldown_blocks_until_counted_down(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Tank", "tank")
        engine.player.equipped_skill_ids = ("block",)
        enemy = engine.content.enemies["cave_bear"].create_enemy()
        enemy.action_ids = ("quick",)

        first = engine.run_combat_turn(enemy, "block")

        self.assertEqual(first.outcome, "ongoing")
        self.assertNotIn("block", [action.id for action in engine.available_actions()])

        before = (engine.player.hp, engine.player.mana, dict(engine.player.cooldowns), list(engine.player.active_statuses))
        blocked = engine.run_combat_turn(enemy, "block")

        self.assertEqual(blocked.outcome, "blocked")
        self.assertEqual((engine.player.hp, engine.player.mana, dict(engine.player.cooldowns), list(engine.player.active_statuses)), before)

        engine.run_combat_turn(enemy, "quick")

        self.assertNotIn("block", [action.id for action in engine.available_actions()])

        engine.run_combat_turn(enemy, "quick")

        self.assertIn("block", [action.id for action in engine.available_actions()])

    def test_thorns_reflects_5_on_hit_no_retrigger_and_none_on_miss(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Tank", "tank")
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        enemy.hp = 20

        combat.resolve_action(engine.player, enemy, engine.content.actions["thorns"], engine.rng)
        hit = combat.resolve_action(enemy, engine.player, always_hit_action(), engine.rng)

        self.assertEqual(hit.reflected_damage, 5)
        self.assertEqual(enemy.hp, 15)

        enemy.hp = 20
        miss = combat.resolve_action(enemy, engine.player, always_miss_action(), engine.rng)

        self.assertEqual(miss.reflected_damage, 0)
        self.assertEqual(enemy.hp, 20)

        enemy.active_statuses.append(
            ActiveStatus(type="reflect", magnitude=99, duration=1, tick_timing="round_end")
        )
        enemy.hp = 20
        combat.resolve_action(enemy, engine.player, always_hit_action(), engine.rng)

        self.assertEqual(enemy.hp, 15)

    def test_taunt_accuracy_minus_20_for_2_rounds_then_restores(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Tank", "tank")
        enemy = engine.content.enemies["giant_rat"].create_enemy()

        combat.resolve_action(engine.player, enemy, engine.content.actions["taunt"], engine.rng)

        self.assertEqual(enemy.accuracy_mod, -20)
        # Normal hit% is now 80; -20 accuracy -> 0.60.
        self.assertEqual(combat.effective_hit_chance(engine.content.actions["normal"], enemy.accuracy_mod), 0.60)
        combat.tick_statuses(enemy, "round_end")
        self.assertEqual(enemy.accuracy_mod, -20)
        combat.tick_statuses(enemy, "round_end")
        self.assertEqual(enemy.accuracy_mod, 0)

    def test_counter_reflects_round_half_up_power_only_on_hit(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Tank", "tank")
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        enemy.hp = 30

        combat.resolve_action(
            engine.player,
            enemy,
            engine.content.actions["counter"],
            engine.rng,
            weapon=engine.content.weapons["mace"],
        )
        hit = combat.resolve_action(enemy, engine.player, always_hit_action(), engine.rng)

        self.assertEqual(hit.reflected_damage, 8)
        self.assertEqual(enemy.hp, 22)

        enemy.hp = 30
        miss = combat.resolve_action(enemy, engine.player, always_miss_action(), engine.rng)

        self.assertEqual(miss.reflected_damage, 0)
        self.assertEqual(enemy.hp, 30)

    def test_iron_stance_regens_for_exactly_3_rounds(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Tank", "tank")
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        engine.player.hp = 80

        combat.resolve_action(engine.player, enemy, engine.content.actions["iron_stance"], engine.rng)

        combat.tick_statuses(engine.player, "round_end")
        self.assertEqual(engine.player.hp, 86)
        combat.tick_statuses(engine.player, "round_end")
        self.assertEqual(engine.player.hp, 92)
        combat.tick_statuses(engine.player, "round_end")
        self.assertEqual(engine.player.hp, 98)
        combat.tick_statuses(engine.player, "round_end")
        self.assertEqual(engine.player.hp, 98)

    def test_resolve_immunity_blocks_debuff_and_flee_force(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Tank", "tank")
        engine.player.talent_points = 3
        engine.allocate_talent("tank_sentinel_s1_iron_stance")
        engine.allocate_talent("tank_sentinel_s2_counter")
        engine.allocate_talent("tank_sentinel_s3_resolve")
        enemy = engine.content.enemies["giant_rat"].create_enemy()

        combat.resolve_action(enemy, engine.player, engine.content.actions["taunt"], engine.rng)

        self.assertEqual(engine.player.accuracy_mod, 0)
        self.assertEqual(engine.player.active_statuses, [])

        result = combat.ActionResolution("flee_test", "Flee Test", enemy.name, engine.player.name)
        combat.apply_effect(
            enemy,
            engine.player,
            EffectSpec(type="apply_status", status_type="debuff", tag="flee_force", duration=1),
            result,
            weapon=None,
        )

        self.assertEqual(engine.player.active_statuses, [])

    def test_bulwark_and_fortitude_stat_bonuses_persist(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Tank", "tank")
        engine.player.talent_points = 7
        engine.allocate_talent("tank_guardian_g1_block")
        engine.allocate_talent("tank_guardian_g2_thorns")
        engine.allocate_talent("tank_guardian_g3_bulwark")
        engine.allocate_talent("tank_sentinel_s1_iron_stance")
        engine.allocate_talent("tank_sentinel_s2_counter")
        engine.allocate_talent("tank_sentinel_s3_resolve")
        engine.allocate_talent("tank_sentinel_s4_fortitude")

        self.assertEqual(engine.player.armor, 12)
        self.assertEqual(engine.player.max_hp, 170)
        self.assertEqual(engine.player.hp, 170)

    def test_cooldown_and_mana_gating_do_not_mutate_state_on_rejection(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Tank", "tank")
        enemy = engine.content.enemies["cave_bear"].create_enemy()
        enemy.action_ids = ("quick",)
        engine.player.equipped_skill_ids = ("counter",)
        engine.player.mana = 0

        before = snapshot(engine)
        no_mana = engine.run_combat_turn(enemy, "counter")

        self.assertEqual(no_mana.outcome, "blocked")
        self.assertEqual(snapshot(engine), before)

        engine.player.mana = engine.player.max_mana
        engine.player.equipped_skill_ids = ("block",)
        engine.run_combat_turn(enemy, "block")
        before_cooldown_reject = snapshot(engine)
        on_cooldown = engine.run_combat_turn(enemy, "block")

        self.assertEqual(on_cooldown.outcome, "blocked")
        self.assertEqual(snapshot(engine), before_cooldown_reject)


def always_hit_action():
    return combat.CombatAction(
        id="always_hit",
        name="Always Hit",
        kind="test",
        hit_chance=1.0,
        effects=(
            EffectSpec(type="instant_damage", scale="flat", magnitude=10, damage_type="physical"),
        ),
    )


def always_miss_action():
    return combat.CombatAction(
        id="always_miss",
        name="Always Miss",
        kind="test",
        hit_chance=0.0,
        effects=(
            EffectSpec(type="instant_damage", scale="flat", magnitude=10, damage_type="physical"),
        ),
    )


def snapshot(engine: GameEngine):
    player = engine.player
    return (
        player.hp,
        player.mana,
        tuple(sorted(player.cooldowns.items())),
        tuple((status.type, status.magnitude, status.duration) for status in player.active_statuses),
    )


if __name__ == "__main__":
    unittest.main()
