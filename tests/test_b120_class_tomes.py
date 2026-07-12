"""B120: class- and weapon-gated offensive tomes."""

import unittest

from rpg_game.core.game import GameEngine
from rpg_game.presentation import item_text


class ClassTomeTest(unittest.TestCase):
    def _engine(self, class_id):
        engine = GameEngine()
        engine.start_new_game(class_id.title(), class_id)
        engine.player.gold = 500
        return engine

    def test_power_slash_template_data(self):
        engine = self._engine("rogue")
        tome = engine.content.items["tome_power_slash"]
        action = engine.content.actions["power_slash"]
        self.assertEqual((tome.price, tome.class_req, tome.weapon_category_req),
                         (200, "rogue", "melee"))
        self.assertEqual(action.requires_weapon_category, "melee")
        self.assertTrue(any(effect.type == "instant_damage" for effect in action.effects))

    def test_tower_filters_class_tome_by_class_and_current_weapon(self):
        rogue = self._engine("rogue")
        mage = self._engine("mage")
        self.assertIn("tome_power_slash", {t.id for t in rogue.tomes_for_sale("tower")})
        self.assertNotIn("tome_power_slash", {t.id for t in mage.tomes_for_sale("tower")})
        rogue.player.equipped_weapon_id = "bow"
        self.assertNotIn("tome_power_slash", {t.id for t in rogue.tomes_for_sale("tower")})

    def test_matching_rogue_can_buy_and_learn_power_slash(self):
        rogue = self._engine("rogue")
        self.assertTrue(rogue.buy_tome("tower", "tome_power_slash").success)
        learned = rogue.use_consumable("tome_power_slash")
        self.assertTrue(learned.success, learned.message)
        self.assertIn("power_slash", rogue.player.learned_skill_ids)

    def test_mismatch_blocks_use_without_consuming(self):
        mage = self._engine("mage")
        mage.player.inventory.add_consumable("tome_power_slash")
        result = mage.use_consumable("tome_power_slash")
        self.assertFalse(result.success)
        self.assertIn("Rogue", result.message)
        self.assertEqual(mage.player.inventory.count("tome_power_slash"), 1)

    def test_tooltip_documents_both_gates(self):
        engine = self._engine("rogue")
        tip = item_text.consumable_tooltip(
            engine.content.items["tome_power_slash"], engine.content)
        self.assertIn("Class: Rogue", tip.lines)
        self.assertIn("Requires a melee weapon", tip.lines)


if __name__ == "__main__":
    unittest.main()
