"""New-enemy data slice: the 14 registered enemies load with sprites + derived
resistances, and the skeleton_warrior elite uses frostfire_strike via its AI.
Stats/magnitudes are placeholders (balance = B37); this locks the DATA + the
frostfire_strike effect resolution (fire+frost hit, burn DoT, armor sunder).
"""

import os
import random
import unittest

from rpg_game.core import combat
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine

NEW = ["wild_dog", "wild_stag", "giant_spider", "goblin_scrapper", "mire_lurker",
       "bog_leech", "rotting_fiend", "witchlight", "bog_hag", "ghoul",
       "grave_hound", "shade", "cursed_wight", "skeleton_warrior"]
SPRITE_DIR = os.path.join(os.path.dirname(__file__), "..", "rpg_game", "assets", "sprites", "generated")


class NewEnemyDataTests(unittest.TestCase):
    def setUp(self):
        self.content = load_content()

    def test_all_14_load_with_a_sprite_file(self):
        for eid in NEW:
            self.assertIn(eid, self.content.enemies, eid)
            self.assertTrue(os.path.exists(os.path.join(SPRITE_DIR, f"{eid}.png")), f"{eid}.png missing")

    def test_derived_resistances_match_targets(self):
        def r(eid, t):
            return self.content.enemies[eid].resistances.get(t, 1.0)
        cases = {
            "cursed_wight": {"holy": 2.0, "physical": 0.65, "poison": 0.0, "frost": 0.65},
            # B42: grave_hound is now beast+cursed (was undead,beast)
            "grave_hound": {"fire": 2.0, "holy": 1.5, "physical": 0.65, "poison": 1.25},
            "mire_lurker": {"frost": 2.0, "fire": 0.65, "poison": 0.65},
            "giant_spider": {"fire": 1.25, "poison": 0.65},
            # B42: shade gained the undead trait -> holy stacks spirit+undead to ×2
            "shade": {"holy": 2.0, "physical": 0.65, "poison": 0.0},
        }
        for eid, exp in cases.items():
            for t, v in exp.items():
                self.assertAlmostEqual(r(eid, t), v, places=9, msg=f"{eid}/{t}")

    def test_skeleton_warrior_is_a_physical_bruiser(self):
        # B97 variant B (2026-07-12): the skeleton trades frostfire_strike for
        # shield_slam (sword+board art = physical bruiser); the wight casts
        # frostfire now. Mana funds the slam (cost 8, cd 3).
        sw = self.content.enemies["skeleton_warrior"]
        self.assertEqual(sw.action_ids, ("shield_slam", "power", "normal"))
        self.assertGreaterEqual(sw.mana, 16)           # at least two casts
        self.assertEqual(sw.ai[0]["action"], "shield_slam")
        self.assertTrue(sw.rare_table_access)
        self.assertTrue(sw.unique_table)               # B42: real loot table now assigned
        self.assertEqual(len(sw.ai), 2)

    def test_cursed_wight_carries_the_frostfire_kit(self):
        # B97 variant B: wight = frostfire_strike + wight_curse + power.
        cw = self.content.enemies["cursed_wight"]
        self.assertEqual(cw.action_ids, ("frostfire_strike", "wight_curse", "power"))
        self.assertEqual(cw.ai[0]["action"], "frostfire_strike")


class FrostfireStrikeTests(unittest.TestCase):
    # B97 variant B: the frostfire kit lives on the cursed_wight now.
    def setUp(self):
        self.engine = GameEngine(rng=random.Random(1))
        self.engine.start_new_game("Hero", "fighter")
        self.player = self.engine.player
        self.skel = self.engine.content.enemies["cursed_wight"].create_enemy()
        self.action = self.engine.content.actions["frostfire_strike"]

    def test_deals_fire_and_frost_and_applies_burn_and_armor_sunder(self):
        armor_before = combat.effective_stat(self.player, "armor")
        result = combat.resolve_action(self.skel, self.player, self.action, self.engine.rng)

        types = {c.damage_type for c in result.damage_components}
        self.assertIn("fire", types)
        self.assertIn("frost", types)

        burn = [s for s in self.player.active_statuses if s.tag == "burn"]
        self.assertEqual(len(burn), 1)
        self.assertEqual(burn[0].duration, 3)
        self.assertEqual(burn[0].tick_timing, "round_end")

        # armor sunder reduces EFFECTIVE armor by 6 immediately
        self.assertEqual(combat.effective_stat(self.player, "armor"), armor_before - 6)

        # ...for exactly two round_end ticks, then restored
        combat.tick_statuses(self.player, "round_end")
        self.assertEqual(combat.effective_stat(self.player, "armor"), armor_before - 6)  # still down after 1
        combat.tick_statuses(self.player, "round_end")
        self.assertEqual(combat.effective_stat(self.player, "armor"), armor_before)      # restored after 2

    def test_skeleton_ai_casts_shield_slam_with_its_mana(self):
        skel = self.engine.content.enemies["skeleton_warrior"].create_enemy()
        result = combat.enemy_take_turn(skel, self.player, self.engine.content.actions,
                                        random.Random(3))
        self.assertEqual(result.action_id, "shield_slam")
        self.assertEqual(skel.mana, skel.max_mana - 8)

    def test_ai_uses_frostfire_when_ready_else_power(self):
        actions = self.engine.content.actions
        rng = random.Random(2)
        # telegraphed: ready -> charges frostfire_strike
        combat.enemy_take_turn(self.skel, self.player, actions, rng)
        self.assertEqual(self.skel.charging_action_id, "frostfire_strike")
        combat.enemy_take_turn(self.skel, self.player, actions, rng)   # release
        self.assertEqual(self.skel.charging_action_id, "")
        # now on cooldown -> AI falls through to power (no crash, not frostfire)
        self.skel.cooldowns["frostfire_strike"] = 3
        combat.enemy_take_turn(self.skel, self.player, actions, rng)
        self.assertNotEqual(self.skel.charging_action_id, "frostfire_strike")


if __name__ == "__main__":
    unittest.main()
