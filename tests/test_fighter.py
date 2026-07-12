import unittest

from rpg_game.core import combat
from rpg_game.core.entities import Enemy, EffectSpec
from rpg_game.core.game import GameEngine


class FighterClassTests(unittest.TestCase):
    def test_sunder_ignores_exactly_6_armor(self):
        engine = GameEngine(rng=SequenceRng([0.0, 0.99]))
        engine.start_new_game("Fighter", "fighter")
        target = make_enemy(hp=100, armor=6)

        result = combat.resolve_action(
            engine.player,
            target,
            engine.content.actions["sunder"],
            engine.rng,
            weapon=engine.content.weapons["knife"],
        )

        self.assertEqual(result.total_damage, 20)
        self.assertEqual(target.hp, 80)

    def test_combo_produces_2_hits_and_each_rolls_crit_independently(self):
        # hit, then per hit: [crit-check, crit-bonus]. Hit 1 crits (bonus floor 0.25),
        # hit 2 does not. Combo is a skill (fixed 0.8x, no range roll consumed).
        engine = GameEngine(rng=SequenceRng([0.0, 0.0, 0.0, 0.99]))
        engine.start_new_game("Fighter", "fighter")
        engine.player.crit_chance = 50
        target = make_enemy(hp=100)

        result = combat.resolve_action(
            engine.player,
            target,
            engine.content.actions["combo"],
            engine.rng,
            weapon=engine.content.weapons["knife"],
        )

        self.assertEqual(len([event for event in result.events if "dealt" in event]), 2)
        self.assertEqual(result.critical_hits, 1)
        # hit 1: 15 * (0.8 + 0.25) = 15.75 -> 16; hit 2: 15 * 0.8 = 12.
        self.assertEqual(result.total_damage, 28)

    def test_rage_stacks_refresh_together_cap_and_expire_after_3_missed_rounds(self):
        engine = GameEngine(rng=SequenceRng([0.0]))
        engine.start_new_game("Fighter", "fighter")
        engine.player.talent_points = 2
        engine.allocate_talent("fighter_berserker_b2_rage")
        enemy = make_enemy()

        for expected_power in (18, 21, 24):
            combat.resolve_action(enemy, engine.player, always_hit_action(), SequenceRng([0.0]))
            self.assertEqual(engine.player.base_damage, expected_power)

        for _ in range(2):
            combat.resolve_action(enemy, engine.player, always_hit_action(), SequenceRng([0.0]))
        self.assertEqual(engine.player.base_damage, 30)

        for _ in range(3):
            combat.resolve_action(enemy, engine.player, always_miss_action(), SequenceRng([0.99]))
            combat.tick_statuses(engine.player, "round_end")

        self.assertEqual(engine.player.base_damage, 15)

    def test_bloodlust_adds_30_percent_damage_at_or_below_40_percent_hp_only(self):
        engine = GameEngine(rng=SequenceRng([0.0, 0.99]))
        engine.start_new_game("Fighter", "fighter")
        engine.player.talent_points = 3
        engine.allocate_talent("fighter_berserker_b2_rage")
        engine.allocate_talent("fighter_berserker_b3_bloodlust")
        target = make_enemy(hp=100)

        # SequenceRng: [hit, multiplier-roll (0.0 -> floor 1.0x), crit-check].
        # Thresholds are relative to max HP (class-identity pass changed base HP).
        engine.player.hp = engine.player.max_hp          # full: above the 50% line
        normal = combat.resolve_action(
            engine.player,
            target,
            engine.content.actions["quick"],
            SequenceRng([0.0, 0.0, 0.99]),
            weapon=engine.content.weapons["knife"],
        )
        self.assertEqual(normal.total_damage, 15)

        target = make_enemy(hp=100)
        engine.player.hp = engine.player.max_hp // 2      # at/below 50%: bloodlust
        boosted = combat.resolve_action(
            engine.player,
            target,
            engine.content.actions["quick"],
            SequenceRng([0.0, 0.0, 0.99]),
            weapon=engine.content.weapons["knife"],
        )
        self.assertEqual(boosted.total_damage, 20)

    def test_reckless_adds_dealt_and_taken_damage_then_expires(self):
        engine = GameEngine(rng=SequenceRng([0.0]))
        engine.start_new_game("Fighter", "fighter")
        target = make_enemy(hp=100)

        combat.resolve_action(engine.player, target, engine.content.actions["reckless"], engine.rng)

        dealt = combat.resolve_action(
            engine.player,
            target,
            engine.content.actions["quick"],
            SequenceRng([0.0, 0.0, 0.99]),  # hit, multiplier floor 1.0x, no crit
            weapon=engine.content.weapons["knife"],
        )
        self.assertEqual(dealt.total_damage, 23)

        hp_before = engine.player.hp
        taken = combat.resolve_action(target, engine.player, always_hit_action(), SequenceRng([0.0]))
        self.assertEqual(taken.total_damage, 13)
        self.assertEqual(engine.player.hp, hp_before - 13)

        combat.tick_statuses(engine.player, "round_end")
        combat.tick_statuses(engine.player, "round_end")
        combat.tick_statuses(engine.player, "round_end")
        self.assertEqual(engine.player.damage_dealt_mod, 0)
        self.assertEqual(engine.player.damage_taken_mod, 0)


class SequenceRng:
    def __init__(self, values):
        self.values = list(values)

    def random(self):
        if self.values:
            return self.values.pop(0)
        return 0.99


def make_enemy(hp: int = 100, armor: int = 0) -> Enemy:
    return Enemy(
        id="dummy",
        name="Dummy",
        level=1,
        max_hp=hp,
        hp=hp,
        damage=1,
        armor=armor,
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


if __name__ == "__main__":
    unittest.main()
