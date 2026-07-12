import unittest

from rpg_game.core import simulation


class CombatSimulationTests(unittest.TestCase):
    def test_single_fight_is_seed_deterministic(self):
        first = simulation.simulate_fight("fighter", "giant_rat", seed=12)
        second = simulation.simulate_fight("fighter", "giant_rat", seed=12)

        self.assertEqual(first, second)
        self.assertIn(first.outcome, {"victory", "defeat", "timeout"})
        self.assertGreater(first.turns, 0)

    def test_matchup_reports_bounded_rates_and_counts(self):
        result = simulation.simulate_matchup("fighter", "giant_rat", trials=10, seed=1)

        self.assertEqual(result.trials, 10)
        self.assertEqual(result.victories + result.defeats + result.timeouts, 10)
        self.assertGreaterEqual(result.win_rate, 0.0)
        self.assertLessEqual(result.win_rate, 1.0)
        self.assertGreater(result.average_turns, 0.0)

    def test_matrix_uses_requested_classes_and_enemies(self):
        results = simulation.simulate_matrix(["fighter", "rogue"], ["giant_rat"], trials=2)

        self.assertEqual([(row.class_id, row.enemy_id, row.trials) for row in results], [
            ("fighter", "giant_rat", 2),
            ("rogue", "giant_rat", 2),
        ])


if __name__ == "__main__":
    unittest.main()


class SmartSelfBuffOncePerFightTests(unittest.TestCase):
    """Class-identity pass (2026-07-12): the smart skill policy opens with a
    self-buff at most ONCE per fight instead of re-casting it on every expiry.
    Without this the rogue's short-duration `evasion` was cast every other turn,
    burning ~half its turns and making DPS regress after L5 (a sim-policy
    artefact, not a game rule)."""

    def _casts(self, engine, enemy, turns):
        import rpg_game.core.simulation as sim
        seen = []
        for _ in range(turns):
            skill = sim._choose_skill(engine, enemy, smart=True)
            seen.append(skill.id if skill else "attack")
            sim._take_turn(engine, enemy, use_skills=True)
            engine.player.hp = engine.effective_stat("max_hp")
            engine.player.mana = engine.effective_stat("max_mana")
        return seen

    def test_rogue_evasion_cast_at_most_once(self):
        import random
        from rpg_game.core.game import GameEngine
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("R", "rogue")
        # give the rogue the evasion self-buff + a damage skill, smart policy on
        engine.player.talent_points += 4
        for node in engine.content.talents.values():
            if node.class_id == "rogue" and node.action_id == "evasion":
                engine.allocate_talent(node.id)
                break
        engine._sim_smart_skills = True
        dummy = engine.content.enemies["giant_rat"].create_enemy()
        dummy.max_hp = dummy.hp = 10 ** 6
        dummy.damage = 0
        casts = self._casts(engine, dummy, 8)
        self.assertLessEqual(casts.count("evasion"), 1, casts)
