import random
import unittest

from rpg_game.core import combat
from rpg_game.core.entities import Enemy
from rpg_game.core.game import GameEngine
from rpg_game.core.progression import round_half_up


def _dummy() -> Enemy:
    return Enemy(
        id="d", name="Dummy", level=1, max_hp=999, hp=999, damage=0, armor=0,
        speed=0, resistances={}, action_ids=(), xp_reward=0, gold_min=0, gold_max=0,
    )


class SeqRng:
    def __init__(self, values):
        self.values = list(values)

    def random(self):
        return self.values.pop(0) if self.values else 0.0


RANGES = {
    "quick": (1.0, 1.25),
    "normal": (1.1, 1.4),
    "power": (1.25, 1.7),
}


class AttackRangeTests(unittest.TestCase):
    def test_rolled_multiplier_stays_within_each_attacks_range(self):
        engine = GameEngine()
        engine.start_new_game("Fighter", "fighter")  # base_damage 15
        engine.player.crit_chance = 0  # isolate the range roll
        knife = engine.content.weapons["knife"]

        for attack_id, (lo, hi) in RANGES.items():
            effect = engine.content.actions[attack_id].effects[0]
            floor = round_half_up(15 * lo)
            ceiling = round_half_up(15 * hi)
            for seed in range(200):
                _components, total, _crit = combat.compute_damage_components(
                    engine.player, _dummy(), knife, effect, rng=random.Random(seed)
                )
                self.assertGreaterEqual(total, floor, attack_id)
                self.assertLessEqual(total, ceiling, attack_id)

    def test_seed_gives_known_outcome(self):
        engine = GameEngine()
        engine.start_new_game("Fighter", "fighter")
        engine.player.crit_chance = 0
        knife = engine.content.weapons["knife"]
        effect = engine.content.actions["quick"].effects[0]

        # Random(0).random() == 0.8444 -> 1.0 + 0.25*0.8444 = 1.2111 -> 15*1.2111 = 18.17 -> 18.
        _components, total, _crit = combat.compute_damage_components(
            engine.player, _dummy(), knife, effect, rng=random.Random(0)
        )
        self.assertEqual(total, 18)


class CritRangeTests(unittest.TestCase):
    def test_crit_extends_multiplier_additively_to_quick_ceiling(self):
        engine = GameEngine()
        engine.start_new_game("Fighter", "fighter")
        engine.player.crit_chance = 100
        knife = engine.content.weapons["knife"]
        effect = engine.content.actions["quick"].effects[0]

        # [multiplier-roll 1.0 -> 1.25x, crit-check, crit-bonus 1.0 -> +1.0] = 2.25x ceiling.
        _components, total, crit = combat.compute_damage_components(
            engine.player, _dummy(), knife, effect, rng=SeqRng([1.0, 0.0, 1.0]), result=combat.ActionResolution("", "", "", ""),
        )
        self.assertTrue(crit)
        self.assertEqual(total, round_half_up(15 * 2.25))  # 34, not a fixed x2 of the base roll

    def test_skill_crit_adds_bonus_without_a_range_roll(self):
        engine = GameEngine()
        engine.start_new_game("Rogue", "rogue")  # base_damage 13
        engine.player.crit_chance = 100
        dagger = engine.content.weapons["dagger"]
        backstab = engine.content.actions["backstab"].effects[0]  # fixed 1.6x skill

        # Skill consumes no multiplier roll: [crit-check, crit-bonus 0.0 -> +0.25].
        _components, total, crit = combat.compute_damage_components(
            engine.player, _dummy(), dagger, backstab, rng=SeqRng([0.0, 0.0]),
            result=combat.ActionResolution("", "", "", ""), weapon_scaled=True,
        )
        self.assertTrue(crit)
        self.assertEqual(total, round_half_up(13 * (1.6 + 0.25)))  # 24

    def test_no_crit_leaves_multiplier_unchanged(self):
        engine = GameEngine()
        engine.start_new_game("Rogue", "rogue")
        engine.player.crit_chance = 0  # backstab still carries +25 crit_bonus, so pick a non-crit roll
        dagger = engine.content.weapons["dagger"]
        backstab = engine.content.actions["backstab"].effects[0]

        _components, total, crit = combat.compute_damage_components(
            engine.player, _dummy(), dagger, backstab, rng=SeqRng([0.99]), weapon_scaled=True,
        )
        self.assertFalse(crit)
        self.assertEqual(total, round_half_up(13 * 1.6))  # 21


if __name__ == "__main__":
    unittest.main()
