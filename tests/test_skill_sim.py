"""Skill-aware balance sim: simulated players can cast skills (mana + cooldown
aware) instead of attack-only, so caster classes (mana-mage) are measured fairly.
Pure sim infrastructure — no game-logic change; attack-only stays the default.
"""

import unittest

from rpg_game.core import simulation as S


class SkillSimTests(unittest.TestCase):
    def test_attack_only_default_is_unchanged_and_deterministic(self):
        a = S.simulate_matchup("fighter", "giant_rat", trials=40, seed=1)
        b = S.simulate_matchup("fighter", "giant_rat", trials=40, seed=1)
        self.assertEqual(a.victories, b.victories)          # seeded, repeatable
        self.assertGreater(a.win_rate, 0.9)                  # fighter trounces a rat

    def test_skill_policy_runs_for_all_six_classes(self):
        for class_id in ("fighter", "tank", "rogue", "mage", "cleric", "hunter"):
            result = S.simulate_matchup(class_id, "giant_rat", trials=20, level=3, use_skills=True)
            self.assertEqual(result.trials, 20, class_id)     # completes without error

    def test_skills_make_the_mana_mage_viable_where_attack_only_fails(self):
        # The whole point: at L5 vs dire_wolf the attack-only mage flounders, the
        # skill-using mage (Mana main, casts firebolt) wins clearly.
        attack = S.simulate_matchup("mage", "dire_wolf", trials=80, level=5, use_skills=False)
        skills = S.simulate_matchup("mage", "dire_wolf", trials=80, level=5, use_skills=True)
        self.assertGreater(skills.win_rate, attack.win_rate + 0.4)

    def test_choose_skill_respects_mana_and_offence(self):
        from rpg_game.core.game import GameEngine
        engine = GameEngine(); engine.start_new_game("M", "mage")
        self.assertIsNotNone(S._choose_skill(engine))         # has mana -> picks a skill
        engine.player.mana = 0
        self.assertIsNone(S._choose_skill(engine))            # broke -> no skill, will attack

    def test_default_main_stat_makes_casters_take_mana(self):
        self.assertEqual(S._DEFAULT_MAIN["mage"], "wisdom")
        self.assertEqual(S._DEFAULT_MAIN["fighter"], "damage")


if __name__ == "__main__":
    unittest.main()
