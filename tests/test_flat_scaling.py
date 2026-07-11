"""Lever d (progression pass 2026-07-12): an enemy's FLAT skill-effect
magnitudes (DoT/debuff/regen) scale with its rolled level, mirroring the
damage growth — so B94's "a tick should be felt" band holds across the level
band instead of eroding as the player levels."""

import random
import unittest

from rpg_game.core import combat, world
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine
from rpg_game.core.progression import round_half_up

CONTENT = load_content()


class _AlwaysHit(random.Random):
    def random(self):
        return 0.0


def _status(target, status_type):
    return next(s for s in target.active_statuses if s.type == status_type)


class FlatScaleFieldTests(unittest.TestCase):
    def test_scale_enemy_sets_flat_scale_with_damage_growth(self):
        enemy = CONTENT.enemies["giant_spider"].create_enemy()
        world.scale_enemy_to_level(enemy, enemy.level, enemy.level + 4)
        self.assertAlmostEqual(enemy.flat_scale,
                               1 + world.DAMAGE_GROWTH_PER_LEVEL * 4)

    def test_at_template_level_flat_scale_is_one(self):
        enemy = CONTENT.enemies["giant_spider"].create_enemy()
        world.scale_enemy_to_level(enemy, enemy.level, enemy.level)
        self.assertEqual(enemy.flat_scale, 1.0)


class ScaledMagnitudeTests(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine()
        self.engine.start_new_game("Hero", "fighter")
        self.player = self.engine.player

    def _cast(self, enemy_id, action_id, levels_up):
        enemy = CONTENT.enemies[enemy_id].create_enemy()
        world.scale_enemy_to_level(enemy, enemy.level, enemy.level + levels_up)
        action = CONTENT.actions[action_id]
        combat.resolve_action(enemy, self.player, action, _AlwaysHit())
        return enemy

    def test_enemy_dot_tick_scales_with_rolled_level(self):
        base = CONTENT.actions["poison_sting"]
        base_mag = next(e for e in base.effects if e.type == "apply_status").magnitude
        enemy = self._cast("giant_spider", "poison_sting", 4)
        tick = _status(self.player, "poison").magnitude
        self.assertEqual(tick, round_half_up(base_mag * enemy.flat_scale))
        self.assertGreater(tick, base_mag)

    def test_enemy_dot_unchanged_at_template_level(self):
        base = CONTENT.actions["poison_sting"]
        base_mag = next(e for e in base.effects if e.type == "apply_status").magnitude
        self._cast("giant_spider", "poison_sting", 0)
        self.assertEqual(_status(self.player, "poison").magnitude, base_mag)

    def test_player_flat_dots_are_untouched(self):
        # A player-cast flat DoT ignores flat_scale (players have none).
        engine = GameEngine()
        engine.start_new_game("R", "rogue")
        enemy = CONTENT.enemies["cave_bear"].create_enemy()
        action = CONTENT.actions["rupture"]
        dot = next(e for e in action.effects if e.type == "apply_status"
                   and (e.status_type in combat.DAMAGE_TYPES or e.tag in combat.DAMAGE_TYPES))
        status_type = dot.status_type or dot.damage_type
        result = combat.resolve_action(
            engine.player, enemy, action, _AlwaysHit(),
            weapon=engine.content.weapons[engine.player.equipped_weapon_id])
        self.assertFalse(result.blocked, result.events)
        self.assertEqual(_status(enemy, status_type).magnitude, dot.magnitude)


if __name__ == "__main__":
    unittest.main()
