import os
import tempfile
import unittest

from rpg_game.core import combat
from rpg_game.core.entities import Enemy
from rpg_game.core.game import GameEngine


def _dummy() -> Enemy:
    return Enemy(
        id="d", name="Dummy", level=1, max_hp=999, hp=999, damage=0, armor=0,
        speed=0, resistances={}, action_ids=(), xp_reward=0, gold_min=0, gold_max=0,
    )


def _cleric_with_holy_strikes() -> GameEngine:
    engine = GameEngine()
    engine.start_new_game("Cle", "cleric")  # base_damage 10
    engine.player.talent_points = 2
    engine.allocate_talent("cleric_light_l1_smite")
    engine.allocate_talent("cleric_sanctified_strikes")
    return engine


def _components(engine, action_id, weapon_id):
    effect = engine.content.actions[action_id].effects[0]
    weapon = engine.content.weapons[weapon_id]
    weapon_scaled = combat.action_uses_weapon_scaling(engine.content.actions[action_id])
    components, _total, _crit = combat.compute_damage_components(
        engine.player, _dummy(), weapon, effect, weapon_scaled=weapon_scaled
    )
    return {c.damage_type: c.amount for c in components}, components


class ElementalTalentTests(unittest.TestCase):
    def test_prerequisite_requires_tier1_node(self):
        engine = GameEngine()
        engine.start_new_game("Cle", "cleric")
        engine.player.talent_points = 2
        available = {node.id for node in engine.available_talents()}
        self.assertNotIn("cleric_sanctified_strikes", available)  # locked until Smite

        engine.allocate_talent("cleric_light_l1_smite")
        available = {node.id for node in engine.available_talents()}
        self.assertIn("cleric_sanctified_strikes", available)

    def test_passive_records_the_elemental_mod(self):
        engine = _cleric_with_holy_strikes()
        self.assertEqual(engine.player.elemental_attack_mods, [{"damage_type": "holy", "mod_value": 4}])

    def test_adds_holy_component_to_basic_attacks(self):
        engine = _cleric_with_holy_strikes()
        by_type, _ = _components(engine, "quick", "holy_mace")  # mace is now physical

        self.assertEqual(set(by_type), {"physical", "holy"})
        self.assertEqual(by_type["holy"], 4)  # round_half_up(1.0 floor * 4)

    def test_component_persists_after_weapon_swap(self):
        engine = _cleric_with_holy_strikes()
        engine.player.owned_weapon_ids = ("holy_mace", "longsword")
        engine.player.equipped_weapon_id = "longsword"  # still physical

        by_type, _ = _components(engine, "quick", "longsword")
        self.assertIn("holy", by_type)

    def test_stacks_with_weapon_element(self):
        engine = _cleric_with_holy_strikes()
        engine.player.owned_weapon_ids = ("holy_mace", "emberwand")
        engine.player.equipped_weapon_id = "emberwand"  # fire weapon

        by_type, _ = _components(engine, "quick", "emberwand")
        self.assertEqual(set(by_type), {"fire", "holy"})  # weapon fire + talent holy
        self.assertEqual(by_type["holy"], 4)

    def test_does_not_affect_skills(self):
        engine = _cleric_with_holy_strikes()
        _by_type, components = _components(engine, "smite", "holy_mace")
        self.assertEqual(len(components), 1)  # only the skill's own component

    def test_mage_flametongue_and_rimeblade_use_their_branch_prereqs(self):
        engine = GameEngine()
        engine.start_new_game("Mage", "mage")
        engine.player.talent_points = 4
        engine.allocate_talent("mage_pyromancer_y1_firebolt")
        engine.allocate_talent("mage_flametongue")
        engine.allocate_talent("mage_cryomancer_c1_frostbolt")
        engine.allocate_talent("mage_rimeblade")

        types = {mod["damage_type"] for mod in engine.player.elemental_attack_mods}
        self.assertEqual(types, {"fire", "frost"})

    def test_elemental_mods_survive_save_load(self):
        engine = _cleric_with_holy_strikes()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "save.json")
            engine.save(path)
            loaded = GameEngine(content=engine.content)
            loaded.load(path)
        self.assertEqual(loaded.player.elemental_attack_mods, [{"damage_type": "holy", "mod_value": 4}])


if __name__ == "__main__":
    unittest.main()
