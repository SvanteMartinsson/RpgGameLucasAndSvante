"""B27 content batch: 9 new skills (6 t5 talent nodes + 3 class-agnostic tomes)
and 7 new weapons (2 common ones in tier-correct shops, 6 low-weight rare-table
entries). Locks the acquisition paths — referential integrity is covered by
the B54 validator."""

import random
import unittest

from rpg_game.core import combat
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine

NEW_T5 = {
    "fighter": ("fighter_weaponmaster_w5_executioners_swing", "executioners_swing",
                ["fighter_weaponmaster_w1_precision", "fighter_weaponmaster_w2_sunder",
                 "fighter_weaponmaster_w3_mastery", "fighter_weaponmaster_w4_combo"]),
    "tank": ("tank_guardian_g5_shield_slam", "shield_slam",
             ["tank_guardian_g2_thorns", "tank_guardian_g3_bulwark",
              "tank_guardian_g4_taunt"]),
    "rogue": ("rogue_duelist_d5_flurry", "flurry",
              ["rogue_duelist_d1_evasion", "rogue_duelist_d2_riposte",
               "rogue_duelist_d3_finesse", "rogue_duelist_d4_deadly_precision"]),
    "mage": ("mage_cryomancer_c5_glacial_spike", "glacial_spike",
             ["mage_cryomancer_c1_frostbolt", "mage_cryomancer_c2_freeze",
              "mage_cryomancer_c3_frostbite", "mage_cryomancer_c4_ice_lance"]),
    "cleric": ("cleric_pest_p5_pestilent_burst", "pestilent_burst",
               ["cleric_pest_p1_plague_bolt", "cleric_pest_p2_drain",
                "cleric_pest_p3_virulence", "cleric_pest_p4_curse"]),
    "hunter": ("hunter_trapper_t5_serrated_bolt", "serrated_bolt",
               ["hunter_trapper_t1_snare", "hunter_trapper_t2_venom_trap",
                "hunter_trapper_t3_exploit_weakness", "hunter_trapper_t4_beast_slayer"]),
}


class NewTalentNodeTests(unittest.TestCase):
    def test_t5_nodes_chain_off_their_branch_and_unlock_their_skill(self):
        for class_id, (node_id, action_id, prereqs) in NEW_T5.items():
            engine = GameEngine(rng=random.Random(0))
            engine.start_new_game("Hero", class_id)
            engine.player.talent_points = len(prereqs) + 1
            for prereq in prereqs:
                engine.allocate_talent(prereq)
            # stay under the 4-equipped cap before learning the t5 active
            for skill_id in list(engine.player.equipped_skill_ids)[1:]:
                engine.unequip_skill(skill_id)
            message = engine.allocate_talent(node_id)
            self.assertIn("Learned", message)
            self.assertIn(action_id, engine.content.actions)


class NewTomeTests(unittest.TestCase):
    def test_new_tomes_buy_and_learn(self):
        engine = GameEngine(rng=random.Random(0))
        engine.start_new_game("Hero", "fighter")
        engine.player.level = 8
        engine.player.gold = 2000
        for tome_id, skill_id in (("tome_stone_ward", "stone_ward"),
                                  ("tome_venom_lash", "venom_lash"),
                                  ("tome_sun_flare", "sun_flare")):
            self.assertTrue(engine.buy_tome("tower", tome_id).success, tome_id)
            engine.use_consumable(tome_id)
            self.assertIn(skill_id, engine.player.learned_skill_ids)

    def test_new_tome_skills_have_no_weapon_gate(self):
        # The B84 lesson: a tome anyone can buy must be usable by anyone.
        content = load_content()
        for skill_id in ("stone_ward", "venom_lash", "sun_flare"):
            self.assertEqual(content.actions[skill_id].requires_weapon_category, "")


class NewWeaponTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = load_content()

    def test_new_weapons_fill_the_tier_gaps(self):
        tiers = {wid: combat.weapon_tier_from_damage(w.damage_bonus)
                 for wid, w in self.content.weapons.items()}
        self.assertEqual(tiers["oak_charm"], 1)        # magic finally has a t1
        self.assertEqual(tiers["duskrender"], 7)       # melee t7 gap
        self.assertEqual(tiers["stormpiercer"], 7)     # ranged t7 gap
        self.assertEqual(tiers["frostveil_staff"], 7)  # magic t7 gap
        self.assertEqual(tiers["hexfire_rod"], 5)      # magic t5 gap
        self.assertEqual(tiers["plaguebrand_scepter"], 5)
        self.assertEqual(tiers["adderfang_bow"], 4)

    def test_shops_carry_the_commons_and_loot_carries_the_rares(self):
        self.assertIn("oak_charm", self.content.places["burg_117"].store_inventory)
        self.assertIn("hexfire_rod", self.content.places["burg_149"].store_inventory)
        rare_ids = {entry["item_id"] for entry in self.content.rare_loot_table}
        for wid in ("adderfang_bow", "hexfire_rod", "plaguebrand_scepter",
                    "duskrender", "stormpiercer", "frostveil_staff"):
            self.assertIn(wid, rare_ids)


if __name__ == "__main__":
    unittest.main()
