import random
import unittest

from rpg_game.core import combat
from rpg_game.core.entities import Enemy, EffectSpec
from rpg_game.core.game import GameEngine


class RogueClassTests(unittest.TestCase):
    def test_crit_forced_roll_doubles_damage_and_backstab_bonus_adds(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Rogue", "rogue")
        target = make_enemy(hp=100)
        backstab = engine.content.actions["backstab"]
        effect = backstab.effects[0]

        self.assertEqual(combat.effective_crit_chance(engine.player, effect), 35)

        weapon = engine.content.weapons["dagger"]
        engine.player.crit_chance = 100
        crit = combat.resolve_action(engine.player, target, backstab, random.Random(1), weapon=weapon)

        # Crit is now an additive range-extension, not a fixed x2: 13 * (1.6 + rolled bonus).
        self.assertEqual(crit.total_damage, 31)
        self.assertEqual(crit.critical_hits, 1)

        target = make_enemy(hp=100)
        engine.player.crit_chance = 0
        no_crit = combat.resolve_action(engine.player, target, backstab, random.Random(1), weapon=weapon)

        self.assertEqual(no_crit.total_damage, 21)
        self.assertEqual(no_crit.critical_hits, 0)

    def test_execute_conditional_applies_only_at_30_percent_or_lower(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Rogue", "rogue")
        engine.player.crit_chance = 0
        execute = engine.content.actions["execute"]

        healthy = make_enemy(hp=100)
        healthy.hp = 31
        normal = combat.resolve_action(
            engine.player,
            healthy,
            execute,
            random.Random(1),
            weapon=engine.content.weapons["dagger"],
        )

        self.assertEqual(normal.total_damage, 18)

        wounded = make_enemy(hp=100)
        wounded.hp = 30
        boosted = combat.resolve_action(
            engine.player,
            wounded,
            execute,
            random.Random(1),
            weapon=engine.content.weapons["dagger"],
        )

        self.assertEqual(boosted.total_damage, 45)

    def test_lethality_and_deadly_precision_modify_crit_chance_and_expire(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Rogue", "rogue")
        engine.player.talent_points = 3
        engine.allocate_talent("rogue_assassin_a2_rupture")
        engine.allocate_talent("rogue_assassin_a3_lethality")

        self.assertEqual(engine.player.crit_chance, 25)

        target = make_enemy()
        combat.resolve_action(engine.player, target, engine.content.actions["deadly_precision"], engine.rng)

        self.assertEqual(engine.player.crit_chance, 55)
        combat.tick_statuses(engine.player, "round_end")
        self.assertEqual(engine.player.crit_chance, 55)
        combat.tick_statuses(engine.player, "round_end")
        self.assertEqual(engine.player.crit_chance, 55)
        combat.tick_statuses(engine.player, "round_end")
        self.assertEqual(engine.player.crit_chance, 25)

    def test_evasion_can_make_incoming_attack_deal_zero_damage(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Rogue", "rogue")
        target = make_enemy()
        combat.resolve_action(engine.player, target, engine.content.actions["evasion"], engine.rng)
        hp_before = engine.player.hp

        result = combat.resolve_action(target, engine.player, always_hit_action(), random.Random(4))

        self.assertTrue(result.evaded)
        self.assertEqual(result.total_damage, 0)
        self.assertEqual(engine.player.hp, hp_before)

    def test_riposte_reflects_on_evade_only(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Rogue", "rogue")
        enemy = make_enemy(hp=50)
        combat.resolve_action(
            engine.player,
            enemy,
            engine.content.actions["riposte"],
            engine.rng,
            weapon=engine.content.weapons["dagger"],
        )
        engine.player.evasion_chance = 100

        evade = combat.resolve_action(enemy, engine.player, always_hit_action(), random.Random(1))

        self.assertTrue(evade.evaded)
        self.assertEqual(evade.reflected_damage, 13)
        self.assertEqual(enemy.hp, 37)

        enemy.hp = 50
        engine.player.evasion_chance = 0
        hit = combat.resolve_action(enemy, engine.player, always_hit_action(), random.Random(1))

        self.assertFalse(hit.evaded)
        self.assertEqual(hit.reflected_damage, 0)
        self.assertEqual(enemy.hp, 50)

    def test_rupture_bleed_ticks_14_for_3_rounds(self):
        # B94: bleed raised 7 -> 14/tick so the total tracks a same-cost nuke.
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Rogue", "rogue")
        target = make_enemy(hp=50)

        combat.resolve_action(engine.player, target, engine.content.actions["rupture"], engine.rng)

        combat.tick_statuses(target, "round_end")
        self.assertEqual(target.hp, 36)
        combat.tick_statuses(target, "round_end")
        self.assertEqual(target.hp, 22)
        combat.tick_statuses(target, "round_end")
        self.assertEqual(target.hp, 8)
        combat.tick_statuses(target, "round_end")
        self.assertEqual(target.hp, 8)


def make_enemy(hp: int = 100) -> Enemy:
    return Enemy(
        id="dummy",
        name="Dummy",
        level=1,
        max_hp=hp,
        hp=hp,
        damage=1,
        armor=0,
        speed=1,
        resistances={},
        action_ids=("quick",),
        xp_reward=0,
        gold_min=0,
        gold_max=0,
    )


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


if __name__ == "__main__":
    unittest.main()
