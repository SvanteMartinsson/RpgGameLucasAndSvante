import unittest

from rpg_game.core import combat
from rpg_game.core.entities import Enemy
from rpg_game.core.game import GameEngine


def _enemy(resistances=None, armor=0, hp=100) -> Enemy:
    return Enemy(
        id="t", name="Target", level=1, max_hp=hp, hp=hp, damage=0, armor=armor,
        speed=0, resistances=resistances or {}, action_ids=(), xp_reward=0,
        gold_min=0, gold_max=0,
    )


class StartWeaponTests(unittest.TestCase):
    def test_caster_start_weapons_are_physical_but_keep_magic_category(self):
        engine = GameEngine()
        for weapon_id in ("holy_mace", "staff"):
            weapon = engine.content.weapons[weapon_id]
            self.assertEqual(weapon.damage_type, "physical")
            self.assertEqual(weapon.category, "magic")

    def test_cleric_basic_attack_is_physical(self):
        engine = GameEngine()
        engine.start_new_game("Cle", "cleric")
        weapon = engine.content.weapons[engine.player.equipped_weapon_id]
        power = engine.content.actions["power"].effects[0]

        components, _total, _crit = combat.compute_damage_components(
            engine.player, _enemy(), weapon, power
        )
        self.assertEqual([c.damage_type for c in components], ["physical"])


class MultiComponentTests(unittest.TestCase):
    def test_each_component_uses_its_own_resistance_and_only_physical_is_armored(self):
        engine = GameEngine()
        engine.start_new_game("Cle", "cleric")  # base_damage 10, mace physical +0
        engine.player.elemental_attack_mods = [{"damage_type": "holy", "mod_value": 4}]
        weapon = engine.content.weapons["holy_mace"]
        power = engine.content.actions["power"].effects[0]  # x2.0 basic attack
        target = _enemy(resistances={"holy": 2.0, "physical": 1.0}, armor=3)

        components, total, _crit = combat.compute_damage_components(
            engine.player, target, weapon, power
        )

        by_type = {c.damage_type: c for c in components}
        self.assertEqual(set(by_type), {"physical", "holy"})
        self.assertEqual(by_type["physical"].amount, 17)  # 10*2=20, -3 armor
        self.assertEqual(by_type["holy"].amount, 16)      # 4*2=8, *2.0 weakness, no armor
        self.assertEqual(by_type["holy"].effectiveness, "super effective")
        self.assertEqual(by_type["physical"].effectiveness, "")
        self.assertEqual(total, 33)

    def test_total_is_floored_at_one(self):
        engine = GameEngine()
        engine.start_new_game("Cle", "cleric")
        weapon = engine.content.weapons["holy_mace"]
        power = engine.content.actions["power"].effects[0]
        target = _enemy(armor=999)  # armor wipes the physical component

        _components, total, _crit = combat.compute_damage_components(
            engine.player, target, weapon, power
        )
        self.assertEqual(total, 1)


class EffectivenessOutputTests(unittest.TestCase):
    def test_super_effective_flag_in_event(self):
        engine = GameEngine(rng=__import__("random").Random(1))
        engine.start_new_game("Cle", "cleric")
        undead = engine.content.enemies["undead"].create_enemy()  # holy 2.0

        result = combat.resolve_action(
            engine.player, undead, engine.content.actions["smite"], engine.rng,
            weapon=engine.content.weapons["holy_mace"],
        )
        self.assertTrue(any("holy super effective" in event for event in result.events))

    def test_resisted_flag_in_event(self):
        engine = GameEngine(rng=__import__("random").Random(1))
        engine.start_new_game("Fighter", "fighter")
        bear = engine.content.enemies["cave_bear"].create_enemy()  # physical 0.9
        bear.evasion_chance = 0

        result = combat.resolve_action(
            engine.player, bear, engine.content.actions["quick"], engine.rng,
            weapon=engine.content.weapons["sword"],
        )
        self.assertTrue(any("physical resisted" in event for event in result.events))


if __name__ == "__main__":
    unittest.main()
