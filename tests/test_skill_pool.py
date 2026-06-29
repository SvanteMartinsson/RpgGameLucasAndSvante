"""B27: a reusable POOL of data-only skills (elemental + utility).

These exist in actions.json but are attached to NO class and NO talent, so they
don't touch class balance — a future mage-tower purchase or tournament reward can
grant them. The tests lock: they load and are well-formed, they stay unattached,
and their power sits within the established skill band (no deliberate spike).
"""

import json
import os
import random
import statistics
import unittest

from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine

POOL = ["zap", "thunder_strike", "incineration", "holy_strike",
        "frost_shard", "earthen_smash", "plague_ooze", "immolate"]


class SkillPoolTests(unittest.TestCase):
    def setUp(self):
        self.content = load_content()

    def test_pool_skills_load_and_are_well_formed(self):
        for sid in POOL:
            action = self.content.actions[sid]
            self.assertEqual(action.kind, "skill", sid)
            self.assertTrue(action.effects, f"{sid} has no effects")
            for eff in action.effects:
                self.assertIn(eff.type, ("instant_damage", "apply_status", "drain", "instant_heal"), sid)

    def test_pool_is_attached_to_no_class_and_no_talent(self):
        class_skills = set()
        for cls in self.content.classes.values():
            class_skills |= set(cls.starting_skill_ids)
        here = os.path.join(os.path.dirname(__file__), "..", "rpg_game", "data", "talents.json")
        talent_skills = {node.get("action_id") for node in json.load(open(here))}
        for sid in POOL:
            self.assertNotIn(sid, class_skills, f"{sid} leaked into a class loadout")
            self.assertNotIn(sid, talent_skills, f"{sid} leaked into a talent tree")

    def test_no_pool_skill_exceeds_the_established_power_ceiling(self):
        # Damage multipliers stay at/under fireball's 2.4; DoT total (magnitude x
        # duration) stays at/under the existing venom_trap (9x3=27).
        ceiling = self.content.actions["fireball"].effects[0].multiplier
        for sid in POOL:
            for eff in self.content.actions[sid].effects:
                if eff.type == "instant_damage":
                    self.assertLessEqual(eff.multiplier, ceiling, f"{sid} multiplier too high")
                if eff.type == "apply_status" and eff.status_type in ("poison", "fire", "bleed"):
                    self.assertLessEqual(eff.magnitude * eff.duration, 27, f"{sid} DoT too high")

    def test_pool_damage_skills_are_in_band_in_sim(self):
        # A single cast lands within the firebolt..fireball band — present but not a
        # spike. (Magic skills cast on a mage; earthen_smash on a melee fighter.)
        fireball = self._avg_cast("mage", "fireball")
        for sid in ("zap", "thunder_strike", "incineration", "holy_strike", "frost_shard"):
            dmg = self._avg_cast("mage", sid)
            self.assertGreater(dmg, 0, sid)
            self.assertLessEqual(dmg, fireball + 1, f"{sid} hits harder than fireball")
        self.assertGreater(self._avg_cast("fighter", "earthen_smash"), 0)

    def _avg_cast(self, class_id, skill, trials=150):
        out = []
        for s in range(trials):
            engine = GameEngine(rng=random.Random(s))
            engine.start_new_game("Sim", class_id)
            engine.player.mana = 999
            enemy = engine.content.enemies["giant_rat"].create_enemy()
            enemy.hp = enemy.max_hp = 99999
            before = enemy.hp
            result = engine.run_combat_turn(enemy, skill)
            self.assertNotEqual(result.outcome, "blocked", f"{class_id} could not cast {skill}")
            out.append(before - enemy.hp)
        return statistics.mean(out)


if __name__ == "__main__":
    unittest.main()
