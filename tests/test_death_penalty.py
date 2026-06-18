"""Death penalty applied on respawn (half HP/mana, lost XP, gold loss)."""

import unittest

from rpg_game.core import progression
from rpg_game.core.game import GameEngine


def _engine():
    engine = GameEngine()
    engine.start_new_game("Hero", "fighter")
    return engine


class DeathPenaltyTest(unittest.TestCase):
    def test_half_hp_and_mana_round_half_up(self):
        engine = _engine()
        p = engine.player
        p.max_hp, p.max_mana, p.gold, p.xp, p.level = 101, 51, 0, 0, 1
        result = progression.apply_death_penalty(p)
        self.assertEqual(p.hp, 51)    # round_half_up(50.5) == 51
        self.assertEqual(p.mana, 26)  # round_half_up(25.5) == 26
        self.assertEqual((result.hp, result.mana), (51, 26))

    def test_even_max_halves_cleanly(self):
        engine = _engine()
        p = engine.player
        p.max_hp, p.max_mana = 100, 40
        progression.apply_death_penalty(p)
        self.assertEqual((p.hp, p.mana), (50, 20))

    def test_xp_resets_to_floor_level_unchanged(self):
        engine = _engine()
        p = engine.player
        p.level, p.xp, p.gold = 4, 137, 0
        result = progression.apply_death_penalty(p)
        self.assertEqual(p.xp, 0)
        self.assertEqual(p.level, 4)          # never drop a level
        self.assertEqual(result.xp_lost, 137)

    def test_gold_loss_scales_with_level(self):
        engine = _engine()
        p = engine.player
        p.level, p.gold = 3, 200
        result = progression.apply_death_penalty(p)
        self.assertEqual(result.gold_lost, 3 * progression.GOLD_LOSS_PER_LEVEL)  # 75
        self.assertEqual(p.gold, 125)

    def test_gold_clamped_at_zero_never_negative(self):
        engine = _engine()
        p = engine.player
        p.level, p.gold = 5, 10  # would lose 125, only has 10
        result = progression.apply_death_penalty(p)
        self.assertEqual(result.gold_lost, 10)
        self.assertEqual(p.gold, 0)

    def test_respawn_sets_location_and_returns_penalty(self):
        engine = _engine()
        p = engine.player
        p.gold, p.xp = 100, 30
        result = engine._respawn_player()
        self.assertEqual(p.current_place_id, p.respawn_place_id)
        self.assertEqual(p.hp, progression.round_half_up(p.max_hp / 2))
        self.assertIsInstance(result, progression.RespawnResult)

    def test_defeat_result_carries_structured_respawn(self):
        engine = _engine()
        engine.player.gold = 100
        enemy = next(iter(engine.content.enemies.values())).create_enemy()
        result = engine._defeat(enemy, [])
        self.assertEqual(result.outcome, "defeat")
        self.assertIsNotNone(result.respawn)
        self.assertTrue(any("respawned" in event for event in result.events))


if __name__ == "__main__":
    unittest.main()
