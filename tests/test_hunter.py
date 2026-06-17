import unittest

from rpg_game.core import combat
from rpg_game.core.entities import Enemy, EffectSpec
from rpg_game.core.game import GameEngine


class HunterClassTests(unittest.TestCase):
    def test_hunters_mark_adds_25_percent_damage_from_all_sources_then_expires(self):
        engine = GameEngine(rng=SequenceRng([0.0]))
        engine.start_new_game("Hunter", "hunter")
        target = make_enemy(hp=100)

        combat.resolve_action(engine.player, target, engine.content.actions["hunters_mark"], SequenceRng([0.0]))
        self.assertEqual(target.damage_taken_mod, 25)

        hunter_hit = combat.resolve_action(
            engine.player,
            target,
            engine.content.actions["aimed_shot"],
            SequenceRng([0.0, 0.99]),
        )
        self.assertEqual(hunter_hit.total_damage, 28)

        target.hp = target.max_hp
        outside_attacker = make_enemy(hp=100, damage=1)
        outside_hit = combat.resolve_action(outside_attacker, target, always_hit_action(), SequenceRng([0.0]))
        self.assertEqual(outside_hit.total_damage, 13)

        combat.tick_statuses(target, "round_end")
        combat.tick_statuses(target, "round_end")
        combat.tick_statuses(target, "round_end")
        self.assertEqual(target.damage_taken_mod, 0)

        normal = combat.resolve_action(
            engine.player,
            target,
            engine.content.actions["aimed_shot"],
            SequenceRng([0.0, 0.99]),
        )
        self.assertEqual(normal.total_damage, 22)

    def test_piercing_shot_ignores_8_armor(self):
        engine = GameEngine(rng=SequenceRng([0.0, 0.99]))
        engine.start_new_game("Hunter", "hunter")
        target = make_enemy(hp=100, armor=8)

        result = combat.resolve_action(engine.player, target, engine.content.actions["piercing_shot"], engine.rng)

        self.assertEqual(result.total_damage, 20)
        self.assertEqual(target.hp, 80)

    def test_exploit_weakness_adds_30_percent_only_when_damage_type_is_weakness(self):
        engine = GameEngine(rng=SequenceRng([0.0]))
        engine.start_new_game("Hunter", "hunter")
        engine.player.talent_points = 3
        engine.allocate_talent("hunter_trapper_t1_snare")
        engine.allocate_talent("hunter_trapper_t2_venom_trap")
        engine.allocate_talent("hunter_trapper_t3_exploit_weakness")

        normal = make_enemy(hp=100, resistances={"physical": 1.0})
        normal_result = combat.resolve_action(
            engine.player,
            normal,
            engine.content.actions["aimed_shot"],
            SequenceRng([0.0, 0.99]),
        )
        self.assertEqual(normal_result.total_damage, 22)

        weak = make_enemy(hp=100, resistances={"physical": 2.0})
        boosted = combat.resolve_action(
            engine.player,
            weak,
            engine.content.actions["aimed_shot"],
            SequenceRng([0.0, 0.99]),
        )
        self.assertEqual(boosted.total_damage, 58)

    def test_beast_slayer_adds_25_percent_only_against_beast_tag(self):
        engine = GameEngine(rng=SequenceRng([0.0]))
        engine.start_new_game("Hunter", "hunter")
        engine.player.talent_points = 4
        engine.allocate_talent("hunter_trapper_t1_snare")
        engine.allocate_talent("hunter_trapper_t2_venom_trap")
        engine.allocate_talent("hunter_trapper_t3_exploit_weakness")
        engine.allocate_talent("hunter_trapper_t4_beast_slayer")

        humanoid = make_enemy(hp=100)
        humanoid_result = combat.resolve_action(
            engine.player,
            humanoid,
            engine.content.actions["aimed_shot"],
            SequenceRng([0.0, 0.99]),
        )
        self.assertEqual(humanoid_result.total_damage, 22)

        beast = make_enemy(hp=100, tags={"beast"})
        beast_result = combat.resolve_action(
            engine.player,
            beast,
            engine.content.actions["aimed_shot"],
            SequenceRng([0.0, 0.99]),
        )
        self.assertEqual(beast_result.total_damage, 28)

    def test_snare_reduces_speed_and_accuracy_for_2_rounds_then_restores(self):
        engine = GameEngine(rng=SequenceRng([0.0]))
        engine.start_new_game("Hunter", "hunter")
        target = make_enemy(hp=100, speed=12)

        combat.resolve_action(engine.player, target, engine.content.actions["snare"], SequenceRng([0.0]))

        self.assertEqual(target.speed, 6)
        self.assertEqual(target.accuracy_mod, -10)
        combat.tick_statuses(target, "round_end")
        self.assertEqual(target.speed, 6)
        self.assertEqual(target.accuracy_mod, -10)
        combat.tick_statuses(target, "round_end")
        self.assertEqual(target.speed, 12)
        self.assertEqual(target.accuracy_mod, 0)


class SequenceRng:
    def __init__(self, values):
        self.values = list(values)

    def random(self):
        if self.values:
            return self.values.pop(0)
        return 0.99


def make_enemy(
    hp: int = 100,
    damage: int = 1,
    armor: int = 0,
    speed: int = 1,
    resistances: dict[str, float] | None = None,
    tags: set[str] | None = None,
) -> Enemy:
    return Enemy(
        id="dummy",
        name="Dummy",
        level=1,
        max_hp=hp,
        hp=hp,
        damage=damage,
        armor=armor,
        speed=speed,
        resistances=resistances or {},
        action_ids=("quick",),
        xp_reward=0,
        gold_min=0,
        gold_max=0,
        tags=tags or set(),
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
