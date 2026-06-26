import random
import unittest

from rpg_game.core import combat
from rpg_game.core.entities import EffectSpec, Enemy
from rpg_game.core.game import GameEngine


class WeaponGatingTests(unittest.TestCase):
    def test_all_weapons_have_expected_categories_and_gated_skills_are_classified(self):
        engine = GameEngine(rng=random.Random(1))
        expected_categories = {
            "knife": "melee",
            "sword": "melee",
            "axe": "melee",
            "longsword": "melee",
            "mace": "melee",
            "holy_mace": "magic",
            "dagger": "melee",
            "staff": "magic",
            "bow": "ranged",
            "steel_greatsword": "melee",
            "emberwand": "magic",
            "rimebrand": "magic",
            "consecrated_maul": "melee",
            "venomfang": "melee",
            "pyre_scepter": "magic",
            "gravewarden_blade": "melee",
            "worldsplitter": "melee",
            "worn_shortsword": "melee",
            "hunting_bow": "ranged",
            "iron_hatchet": "melee",
            "worgfang": "melee",
        }
        self.assertEqual(
            {weapon_id: weapon.category for weapon_id, weapon in engine.content.weapons.items()},
            expected_categories,
        )

        expected_requirements = {
            "counter": "melee",
            "backstab": "melee",
            "execute": "melee",
            "riposte": "melee",
            "frenzy": "melee",
            "precision": "melee",
            "sunder": "melee",
            "combo": "melee",
            "smite": "magic",
            "drain": "magic",
            "firebolt": "magic",
            "fireball": "magic",
            "frostbolt": "magic",
            "ice_lance": "magic",
            "aimed_shot": "ranged",
            "piercing_shot": "ranged",
        }
        actual = {
            action_id: action.requires_weapon_category
            for action_id, action in engine.content.actions.items()
            if action.requires_weapon_category
        }
        self.assertEqual(actual, expected_requirements)

    def test_gated_skill_with_correct_weapon_includes_weapon_bonus(self):
        engine = GameEngine(rng=NoCritRng([0.0, 0.99]))
        engine.start_new_game("Mage", "mage")
        target = make_enemy(hp=100)

        result = combat.resolve_action(
            engine.player,
            target,
            engine.content.actions["firebolt"],
            engine.rng,
            weapon=engine.content.weapons["emberwand"],
        )

        self.assertEqual(result.total_damage, 45)
        self.assertEqual(target.hp, 55)

    def test_wrong_weapon_category_blocks_without_spending_turn_or_mutating_state(self):
        engine = GameEngine(rng=NoCritRng([0.0]))
        engine.start_new_game("Mage", "mage")
        engine.player.owned_weapon_ids = (*engine.player.owned_weapon_ids, "steel_greatsword")
        engine.player.equipped_weapon_id = "steel_greatsword"
        engine.player.equipped_skill_ids = ("firebolt",)
        enemy = make_enemy(hp=100, damage=10)

        self.assertNotIn("firebolt", [action.id for action in engine.available_actions()])
        before = (
            engine.player.hp,
            engine.player.mana,
            dict(engine.player.cooldowns),
            enemy.hp,
            enemy.cooldowns.copy(),
        )

        result = engine.run_combat_turn(enemy, "firebolt")

        self.assertEqual(result.outcome, "blocked")
        self.assertIn("needs a magic weapon", result.events[0])
        self.assertEqual(
            (
                engine.player.hp,
                engine.player.mana,
                dict(engine.player.cooldowns),
                enemy.hp,
                enemy.cooldowns.copy(),
            ),
            before,
        )

    def test_free_skills_ignore_weapon_category_and_weapon_bonus(self):
        tank_engine = GameEngine(rng=random.Random(1))
        tank_engine.start_new_game("Tank", "tank")
        tank_target = make_enemy()
        combat.resolve_action(
            tank_engine.player,
            tank_target,
            tank_engine.content.actions["iron_stance"],
            tank_engine.rng,
            weapon=tank_engine.content.weapons["emberwand"],
        )
        self.assertEqual(tank_engine.player.active_statuses[0].magnitude, 6)

        mage_engine = GameEngine(rng=random.Random(1))
        mage_engine.start_new_game("Mage", "mage")
        mage_target = make_enemy()
        combat.resolve_action(
            mage_engine.player,
            mage_target,
            mage_engine.content.actions["ignite"],
            mage_engine.rng,
            weapon=mage_engine.content.weapons["worldsplitter"],
        )
        self.assertEqual(mage_target.active_statuses[0].magnitude, 8)

    def test_counter_and_riposte_reflect_scale_with_melee_weapon_bonus_and_require_melee(self):
        tank_engine = GameEngine(rng=NoCritRng([0.0]))
        tank_engine.start_new_game("Tank", "tank")
        enemy = make_enemy(hp=100)

        blocked = combat.resolve_action(
            tank_engine.player,
            enemy,
            tank_engine.content.actions["counter"],
            tank_engine.rng,
            weapon=tank_engine.content.weapons["staff"],
        )
        self.assertTrue(blocked.blocked)
        self.assertEqual(tank_engine.player.mana, tank_engine.player.max_mana)

        combat.resolve_action(
            tank_engine.player,
            enemy,
            tank_engine.content.actions["counter"],
            tank_engine.rng,
            weapon=tank_engine.content.weapons["steel_greatsword"],
        )
        hit = combat.resolve_action(enemy, tank_engine.player, always_hit_action(), NoCritRng([0.0]))
        self.assertEqual(hit.reflected_damage, 26)
        self.assertEqual(enemy.hp, 74)

        rogue_engine = GameEngine(rng=NoCritRng([0.0]))
        rogue_engine.start_new_game("Rogue", "rogue")
        rogue_enemy = make_enemy(hp=100)
        combat.resolve_action(
            rogue_engine.player,
            rogue_enemy,
            rogue_engine.content.actions["riposte"],
            rogue_engine.rng,
            weapon=rogue_engine.content.weapons["steel_greatsword"],
        )
        rogue_engine.player.evasion_chance = 100

        evade = combat.resolve_action(rogue_enemy, rogue_engine.player, always_hit_action(), NoCritRng([0.0]))

        self.assertEqual(evade.reflected_damage, 31)
        self.assertEqual(rogue_enemy.hp, 69)

    def test_base_attack_scales_with_power_plus_weapon_bonus(self):
        # [hit, multiplier-roll (0.0 -> normal floor 1.1x), no-crit]; worldsplitter +38 is included.
        engine = GameEngine(rng=NoCritRng([0.0, 0.0, 0.99]))
        engine.start_new_game("Fighter", "fighter")
        target = make_enemy(hp=100)

        result = combat.resolve_action(
            engine.player,
            target,
            engine.content.actions["normal"],
            engine.rng,
            weapon=engine.content.weapons["worldsplitter"],
        )

        # (15 power + 38 weapon) * 1.1 = 58.3 -> 58.
        self.assertEqual(result.total_damage, 58)


class NoCritRng:
    def __init__(self, values):
        self.values = list(values)

    def random(self):
        if self.values:
            return self.values.pop(0)
        return 0.99

    def randint(self, minimum, _maximum):
        return minimum

    def choice(self, values):
        return values[0]


def make_enemy(hp: int = 100, damage: int = 1) -> Enemy:
    return Enemy(
        id="dummy",
        name="Dummy",
        level=1,
        max_hp=hp,
        hp=hp,
        damage=damage,
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
