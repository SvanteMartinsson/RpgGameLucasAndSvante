"""Global enemy HP multiplier: a single tunable scalar on every enemy's max_hp
at creation (wild and arena), preserving ratios and stacking with level scaling.
"""

import unittest
from unittest.mock import patch

from rpg_game.core import progression, world
from rpg_game.core.game import GameEngine
from rpg_game.core.progression import round_half_up


def _template(engine, enemy_id):
    return engine.content.enemies[enemy_id]


class EnemyHpMultiplierTest(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine()
        self.engine.start_new_game("Hero", "fighter")

    def _base_hp(self, enemy_id):
        return _template(self.engine, enemy_id).max_hp

    def test_each_enemy_max_hp_is_base_times_multiplier(self):
        mult = progression.ENEMY_HP_MULTIPLIER
        for enemy_id in ("giant_rat", "undead", "cave_bear", "undead_priest"):
            enemy = _template(self.engine, enemy_id).create_enemy()
            self.assertEqual(enemy.max_hp, round_half_up(self._base_hp(enemy_id) * mult))
            self.assertEqual(enemy.hp, enemy.max_hp)  # current set to (new) max

    def test_default_multiplier_is_two(self):
        self.assertEqual(progression.ENEMY_HP_MULTIPLIER, 2.0)

    def test_ratios_between_enemies_are_preserved(self):
        rat = _template(self.engine, "giant_rat").create_enemy()
        bear = _template(self.engine, "cave_bear").create_enemy()
        # base ratio == scaled ratio (integer base * 2.0 is exact)
        self.assertEqual(bear.max_hp * self._base_hp("giant_rat"),
                         rat.max_hp * self._base_hp("cave_bear"))

    def test_only_hp_changes_not_power_xp_gold(self):
        rat_t = _template(self.engine, "giant_rat")
        rat = rat_t.create_enemy()
        self.assertEqual(rat.damage, rat_t.damage)
        self.assertEqual(rat.xp_reward, rat_t.xp_reward)
        self.assertEqual((rat.gold_min, rat.gold_max), (rat_t.gold_min, rat_t.gold_max))
        self.assertEqual(rat.drop_chance, rat_t.drop_chance)

    def test_arena_opponents_are_multiplied_but_keep_their_order(self):
        # The hand-built arena ladder doubles but its HP ordering is unchanged.
        # iron_ring's size (4) is outside the B13 per-instance buff, so the HP
        # multiplier is observable on its own here.
        tournament = self.engine.content.tournaments["fongorinos_iron_ring"]
        for index, enemy_id in enumerate(tournament.opponent_ids):
            opp = self.engine.create_tournament_opponent(tournament, index)
            self.assertEqual(opp.max_hp, round_half_up(self._base_hp(enemy_id) * progression.ENEMY_HP_MULTIPLIER))
        order = [self._base_hp(eid) for eid in tournament.opponent_ids]
        scaled = [self.engine.create_tournament_opponent(tournament, i).max_hp
                  for i in range(len(tournament.opponent_ids))]
        self.assertEqual([a < b for a, b in zip(order, order[1:])],
                         [a < b for a, b in zip(scaled, scaled[1:])])

    def test_multiplier_stacks_with_level_scaling(self):
        # Order: multiplier at creation, then per-level scaling, each round_half_up.
        base = self._base_hp("giant_rat")  # 20
        enemy = _template(self.engine, "giant_rat").create_enemy()
        self.assertEqual(enemy.max_hp, round_half_up(base * progression.ENEMY_HP_MULTIPLIER))  # 40
        world.scale_enemy_to_level(enemy, base_level=1, target_level=5)
        expected = round_half_up(round_half_up(base * progression.ENEMY_HP_MULTIPLIER)
                                 * (1 + world.HP_GROWTH_PER_LEVEL * 4))
        self.assertEqual(enemy.max_hp, expected)  # 72

    def test_multiplier_one_reproduces_old_values(self):
        with patch("rpg_game.core.progression.ENEMY_HP_MULTIPLIER", 1.0):
            rat = _template(self.engine, "giant_rat").create_enemy()
            self.assertEqual((rat.max_hp, rat.hp), (20, 20))
            world.scale_enemy_to_level(rat, 1, 5)
            self.assertEqual(rat.max_hp, 36)  # pre-multiplier scaled value


if __name__ == "__main__":
    unittest.main()
