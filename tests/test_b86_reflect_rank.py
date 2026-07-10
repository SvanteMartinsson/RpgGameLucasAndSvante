"""B86: talent ranks must scale power-scaled reflects (Counter/Riposte).

Before the fix, the B36 rank multiplier was applied only to `magnitude`, which
power-scaled reflect statuses ignore (they read `status.multiplier` at trigger
time) — so ranking Counter/Riposte to rank 2 was a complete no-op. Locks that
the stored multiplier scales with rank and that the reflected damage follows.
"""

import random
import unittest

from rpg_game.core import combat
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine
from rpg_game.core.progression import round_half_up


def _cast_counter(rank: int):
    engine = GameEngine()
    engine.start_new_game("Hero", "tank")
    player = engine.player
    if rank:
        player.talent_skill_ranks["counter"] = rank
    action = engine.content.actions["counter"]
    weapon = engine.content.weapons[player.equipped_weapon_id]
    combat.resolve_action(player, player, action, weapon=weapon, rng=random.Random(1))
    status = next(s for s in player.active_statuses if s.type == "reflect")
    return engine, player, status


class ReflectRankScalingTest(unittest.TestCase):
    def test_rank_two_counter_stores_a_scaled_multiplier(self):
        _engine, _player, rank1 = _cast_counter(1)
        _engine, _player, rank2 = _cast_counter(2)
        self.assertEqual(rank1.multiplier, 1.0)
        self.assertEqual(rank2.multiplier, 1.25)

    def test_rank_two_counter_reflects_more_damage(self):
        reflected = {}
        for rank in (1, 2):
            engine, player, status = _cast_counter(rank)
            enemy = engine.content.enemies["cave_bear"].create_enemy()
            result = combat.ActionResolution("x", "X", enemy.name, player.name)
            combat.apply_reflects(player, enemy, result)
            reflected[rank] = result.reflected_damage
            expected_raw = round_half_up(
                (combat.effective_stat(player, "damage") + status.weapon_bonus) * status.multiplier
            )
            self.assertEqual(
                reflected[rank],
                combat.apply_damage_mitigation(expected_raw, enemy, status.damage_type),
            )
        self.assertGreater(reflected[2], reflected[1])

    def test_flat_reflects_are_unchanged_by_the_multiplier_path(self):
        # Thorns is magnitude-based; its rank scaling flows through magnitude
        # and its stored multiplier is irrelevant to apply_reflects.
        engine = GameEngine()
        engine.start_new_game("Hero", "tank")
        player = engine.player
        action = engine.content.actions["thorns"]
        weapon = engine.content.weapons[player.equipped_weapon_id]
        combat.resolve_action(player, player, action, weapon=weapon, rng=random.Random(1))
        status = next(s for s in player.active_statuses if s.type == "reflect")
        self.assertEqual(status.scale, "flat")
        self.assertEqual(status.magnitude, 5)


if __name__ == "__main__":
    unittest.main()
