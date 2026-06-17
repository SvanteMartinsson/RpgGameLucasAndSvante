import unittest

from rpg_game.core import combat
from rpg_game.core.entities import ActiveStatus, Enemy
from rpg_game.core.game import GameEngine


class MageClassTests(unittest.TestCase):
    def test_freeze_skip_turn_consumes_exactly_one_enemy_action(self):
        engine = GameEngine(rng=ChoiceRng([0.0, 0.0, 0.0]))
        engine.start_new_game("Mage", "mage")
        enemy = make_enemy(hp=200, damage=10, speed=1)

        first = engine.run_combat_turn(enemy, "freeze")
        self.assertTrue(any("loses the turn" in event for event in first.events))
        self.assertEqual(engine.player.hp, engine.player.max_hp)

        second = engine.run_combat_turn(enemy, "firebolt")
        self.assertFalse(any("loses the turn" in event for event in second.events))
        self.assertLess(engine.player.hp, engine.player.max_hp)

    def test_freeze_cooldown_blocks_chaining(self):
        engine = GameEngine(rng=ChoiceRng([0.0]))
        engine.start_new_game("Mage", "mage")
        enemy = make_enemy(hp=200, damage=1, speed=1)

        engine.run_combat_turn(enemy, "freeze")
        mana_after_freeze = engine.player.mana
        blocked = engine.run_combat_turn(enemy, "freeze")

        self.assertEqual(blocked.outcome, "blocked")
        self.assertIn("cannot use Freeze", blocked.events[0])
        self.assertEqual(engine.player.mana, mana_after_freeze)

    def test_combustion_bonus_applies_only_to_fire_damage_against_burning_targets(self):
        engine = GameEngine(rng=ChoiceRng([0.0]))
        engine.start_new_game("Mage", "mage")
        engine.player.talent_points = 3
        engine.allocate_talent("mage_pyromancer_y1_firebolt")
        engine.allocate_talent("mage_pyromancer_y2_ignite")
        engine.allocate_talent("mage_pyromancer_y3_combustion")

        plain = make_enemy(hp=100)
        weapon = engine.content.weapons["staff"]
        plain_result = combat.resolve_action(
            engine.player,
            plain,
            engine.content.actions["firebolt"],
            ChoiceRng([0.0]),
            weapon=weapon,
        )
        self.assertEqual(plain_result.total_damage, 19)

        burning = make_enemy(hp=100)
        burning.active_statuses.append(
            ActiveStatus(type="fire", magnitude=8, duration=3, tick_timing="round_end", tag="burn")
        )
        boosted = combat.resolve_action(
            engine.player,
            burning,
            engine.content.actions["firebolt"],
            ChoiceRng([0.0]),
            weapon=weapon,
        )
        self.assertEqual(boosted.total_damage, 23)

        chilled = make_enemy(hp=100)
        chilled.active_statuses.append(
            ActiveStatus(type="debuff", magnitude=-4, duration=2, tick_timing="round_end", stat="speed", tag="chill")
        )
        frost = combat.resolve_action(
            engine.player,
            chilled,
            engine.content.actions["frostbolt"],
            ChoiceRng([0.0]),
            weapon=weapon,
        )
        self.assertEqual(frost.total_damage, 17)

    def test_frostbite_bonus_applies_only_to_frost_damage_against_frozen_or_chilled_targets(self):
        engine = GameEngine(rng=ChoiceRng([0.0]))
        engine.start_new_game("Mage", "mage")
        engine.player.talent_points = 3
        engine.allocate_talent("mage_cryomancer_c1_frostbolt")
        engine.allocate_talent("mage_cryomancer_c2_freeze")
        engine.allocate_talent("mage_cryomancer_c3_frostbite")

        plain = make_enemy(hp=100)
        weapon = engine.content.weapons["staff"]
        plain_result = combat.resolve_action(
            engine.player,
            plain,
            engine.content.actions["frostbolt"],
            ChoiceRng([0.0]),
            weapon=weapon,
        )
        self.assertEqual(plain_result.total_damage, 17)

        chilled = make_enemy(hp=100)
        chilled.active_statuses.append(
            ActiveStatus(type="debuff", magnitude=-4, duration=2, tick_timing="round_end", stat="speed", tag="chill")
        )
        boosted = combat.resolve_action(
            engine.player,
            chilled,
            engine.content.actions["frostbolt"],
            ChoiceRng([0.0]),
            weapon=weapon,
        )
        self.assertEqual(boosted.total_damage, 21)

        fire = combat.resolve_action(
            engine.player,
            chilled,
            engine.content.actions["firebolt"],
            ChoiceRng([0.0]),
            weapon=weapon,
        )
        self.assertEqual(fire.total_damage, 19)

    def test_ice_lance_doubles_only_against_frozen_target(self):
        engine = GameEngine(rng=ChoiceRng([0.0]))
        engine.start_new_game("Mage", "mage")

        plain = make_enemy(hp=100)
        weapon = engine.content.weapons["staff"]
        plain_result = combat.resolve_action(
            engine.player,
            plain,
            engine.content.actions["ice_lance"],
            ChoiceRng([0.0]),
            weapon=weapon,
        )
        self.assertEqual(plain_result.total_damage, 18)

        frozen = make_enemy(hp=100)
        frozen.active_statuses.append(
            ActiveStatus(type="skip_turn", magnitude=0, duration=1, tick_timing="turn", tag="freeze")
        )
        boosted = combat.resolve_action(
            engine.player,
            frozen,
            engine.content.actions["ice_lance"],
            ChoiceRng([0.0]),
            weapon=weapon,
        )
        self.assertEqual(boosted.total_damage, 36)

    def test_frostbolt_chill_reduces_speed_for_2_rounds_then_restores(self):
        engine = GameEngine(rng=ChoiceRng([0.0]))
        engine.start_new_game("Mage", "mage")
        target = make_enemy(hp=100, speed=12)

        combat.resolve_action(
            engine.player,
            target,
            engine.content.actions["frostbolt"],
            ChoiceRng([0.0]),
            weapon=engine.content.weapons["staff"],
        )
        self.assertEqual(target.speed, 8)

        combat.tick_statuses(target, "round_end")
        self.assertEqual(target.speed, 8)
        combat.tick_statuses(target, "round_end")
        self.assertEqual(target.speed, 12)


class ChoiceRng:
    def __init__(self, values):
        self.values = list(values)

    def random(self):
        if self.values:
            return self.values.pop(0)
        return 0.0

    def choice(self, values):
        return values[0]


def make_enemy(hp: int = 100, damage: int = 1, speed: int = 1) -> Enemy:
    return Enemy(
        id="dummy",
        name="Dummy",
        level=1,
        max_hp=hp,
        hp=hp,
        damage=damage,
        armor=0,
        speed=speed,
        resistances={},
        action_ids=("quick",),
        xp_reward=0,
        gold_min=0,
        gold_max=0,
    )


if __name__ == "__main__":
    unittest.main()
