"""B54: load-time cross-reference validation — a typo in any content id fails at
load with a named ValueError instead of silently dropping behaviour.

Each test injects ONE broken reference into otherwise-valid content and asserts
the validator names the offender. The real shipped data loading cleanly is
locked by test_real_content_is_reference_clean.
"""

import dataclasses
import unittest

from rpg_game.core.data_loader import load_content, _validate_content_refs


def _args(content, **overrides):
    base = dict(
        classes=content.classes,
        weapons=content.weapons,
        gear_items=content.gear_items,
        items=content.items,
        actions=content.actions,
        talents=content.talents,
        enemies=content.enemies,
        places=content.places,
        rare_loot_table=content.rare_loot_table,
        upgrade_recipes=content.upgrade_recipes,
    )
    base.update(overrides)
    return base


class ContentValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = load_content()

    def _assert_rejects(self, pattern, **overrides):
        with self.assertRaisesRegex(ValueError, pattern):
            _validate_content_refs(**_args(self.content, **overrides))

    def test_real_content_is_reference_clean(self):
        _validate_content_refs(**_args(self.content))  # must not raise

    def test_class_with_unknown_starting_weapon(self):
        cls = dataclasses.replace(self.content.classes["fighter"], starting_weapon_id="no_such_sword")
        self._assert_rejects("fighter references unknown starting weapon no_such_sword",
                             classes={**self.content.classes, "fighter": cls})

    def test_class_with_unknown_starting_skill(self):
        cls = dataclasses.replace(self.content.classes["mage"], starting_skill_ids=("no_such_skill",))
        self._assert_rejects("mage references unknown starting skill no_such_skill",
                             classes={**self.content.classes, "mage": cls})

    def test_enemy_with_unknown_action(self):
        enemy = dataclasses.replace(self.content.enemies["giant_rat"], action_ids=("no_such_action",))
        self._assert_rejects("giant_rat references unknown action no_such_action",
                             enemies={**self.content.enemies, "giant_rat": enemy})

    def test_enemy_ai_with_unknown_action(self):
        enemy = dataclasses.replace(
            self.content.enemies["cave_bear"],
            ai=({"condition": {"always": True}, "action": "no_such_action"},))
        self._assert_rejects("cave_bear ai references unknown action no_such_action",
                             enemies={**self.content.enemies, "cave_bear": enemy})

    def test_enemy_loot_with_unknown_item(self):
        enemy = dataclasses.replace(
            self.content.enemies["giant_rat"],
            loot_table=({"item_id": "no_such_item", "weight": 1, "rarity_tier": 1},))
        self._assert_rejects("giant_rat loot_table references unknown item no_such_item",
                             enemies={**self.content.enemies, "giant_rat": enemy})

    def test_rare_table_with_unknown_item(self):
        self._assert_rejects("rare_table references unknown item no_such_item",
                             rare_loot_table=({"item_id": "no_such_item", "weight": 1},))

    def test_tome_teaching_unknown_action(self):
        tome = dataclasses.replace(self.content.items["tome_zap"], teaches="no_such_action")
        self._assert_rejects("tome tome_zap teaches unknown action no_such_action",
                             items={**self.content.items, "tome_zap": tome})

    def test_upgrade_recipe_with_unknown_target(self):
        recipe = self.content.upgrade_recipes["steel_greatsword"]
        broken = dataclasses.replace(recipe, item_id="no_such_item")
        self._assert_rejects("upgrade recipe targets unknown item no_such_item",
                             upgrade_recipes={**self.content.upgrade_recipes, "steel_greatsword": broken})

    def test_upgrade_variant_with_unknown_material(self):
        recipe = self.content.upgrade_recipes["steel_greatsword"]
        variant = dataclasses.replace(recipe.variants[0], materials=(("no_such_material", 1),))
        broken = dataclasses.replace(recipe, variants=(variant,))
        self._assert_rejects("references unknown material no_such_material",
                             upgrade_recipes={**self.content.upgrade_recipes, "steel_greatsword": broken})

    def test_talent_with_unknown_action(self):
        talent_id, talent = next((tid, t) for tid, t in self.content.talents.items()
                                 if t.node_type == "active" and t.action_id)
        broken = dataclasses.replace(talent, action_id="no_such_action")
        self._assert_rejects(f"talent {talent_id} references unknown action no_such_action",
                             talents={**self.content.talents, talent_id: broken})

    def test_place_with_unknown_encounter(self):
        place = dataclasses.replace(self.content.places["burg_54"], encounters=("no_such_enemy",))
        self._assert_rejects("burg_54 references unknown encounter no_such_enemy",
                             places={**self.content.places, "burg_54": place})

    def test_place_with_unknown_rare_encounter(self):
        place = dataclasses.replace(self.content.places["burg_146"], rare_encounter="no_such_enemy")
        self._assert_rejects("burg_146 references unknown rare encounter no_such_enemy",
                             places={**self.content.places, "burg_146": place})

    def test_place_store_with_unknown_item(self):
        place = dataclasses.replace(self.content.places["burg_5"], store_inventory=("no_such_item",))
        self._assert_rejects("burg_5 store references unknown item no_such_item",
                             places={**self.content.places, "burg_5": place})

    def test_place_connection_to_unknown_place(self):
        place = self.content.places["burg_5"]
        connection = dataclasses.replace(place.connections[0], to="no_such_place")
        broken = dataclasses.replace(place, connections=(connection,))
        self._assert_rejects("burg_5 connects to unknown place no_such_place",
                             places={**self.content.places, "burg_5": broken})


if __name__ == "__main__":
    unittest.main()
