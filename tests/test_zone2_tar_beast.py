"""ZONE2 step 2b addendum: the tar beast — a tanky, regenerating swamp bruiser
that slows the player. Data only, reusing existing regen/debuff effects.
"""

import random
import unittest

from rpg_game.core import combat
from rpg_game.core.entities import EffectSpec
from rpg_game.core.game import GameEngine

SWAMP = "burg_320"
CORE = "burg_54"
FOREST = "burg_146"


class TarBeastTest(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine()
        self.engine.start_new_game("Hero", "fighter")

    def _beast(self):
        return self.engine.content.enemies["tar_beast"].create_enemy()

    def test_loads_and_lives_in_the_swamp_only(self):
        self.assertIn("tar_beast", self.engine.content.enemies)
        self.assertIn("tar_beast", self.engine.content.places[SWAMP].encounters)
        self.assertNotIn("tar_beast", self.engine.content.places[CORE].encounters)
        self.assertNotIn("tar_beast", self.engine.content.places[FOREST].encounters)

    def test_spawns_in_the_swamp_within_the_regional_band(self):
        self.engine.rng = random.Random(5)
        self.engine.player.current_place_id = SWAMP
        seen, levels = set(), set()
        for _ in range(500):
            e = self.engine.create_encounter()
            seen.add(e.id)
            levels.add(e.level)
        self.assertIn("tar_beast", seen)
        self.assertGreaterEqual(min(levels), 5)
        self.assertLessEqual(max(levels), 10)

    def test_is_frost_weak_and_fire_resistant(self):
        # The tar beast is now [swamp]: cold-blooded ooze. Swamp makes it
        # frost-bane (+3 -> x2.0) and fire-resistant (-1 -> x0.65); the old
        # "burn the tar" fire-weakness is intentionally inverted.
        beast = self._beast()
        fire = EffectSpec(type="damage", scale="flat", magnitude=10, damage_type="fire")
        frost = EffectSpec(type="damage", scale="flat", magnitude=10, damage_type="frost")
        self.assertEqual(combat.calculate_effect_damage(self.engine.player, beast, None, fire), 7)    # x0.65
        self.assertEqual(combat.calculate_effect_damage(self.engine.player, beast, None, frost), 20)  # x2.0

    def test_regen_heals_each_round_and_caps_at_max_hp(self):
        beast = self._beast()
        beast.hp = beast.max_hp - 12
        combat.resolve_action(beast, self.engine.player, self.engine.content.actions["tar_regen"], random.Random(1))
        # Two ticks heal, but never above max_hp.
        first = beast.hp
        combat.tick_statuses(beast, "round_end")
        self.assertEqual(beast.hp, min(beast.max_hp, first + 5))
        beast.hp = beast.max_hp - 2
        combat.tick_statuses(beast, "round_end")
        self.assertEqual(beast.hp, beast.max_hp)  # capped

    def test_slow_lowers_player_speed_and_turn_order(self):
        beast = self._beast()
        beast.speed = 99  # ensure ordering flips purely from the slow, not base speed
        base_speed = self.engine.player.speed
        # Player normally acts first against a slow base-speed beast...
        slow_beast = self._beast()
        self.assertIs(combat.ordered_by_speed(self.engine.player, slow_beast)[0], self.engine.player)
        # ...the tar snare cuts the player's speed.
        combat.resolve_action(beast, self.engine.player, self.engine.content.actions["tar_ensnare"], random.Random(1))
        self.assertEqual(self.engine.player.speed, base_speed - 4)

    def test_long_fight_terminates_against_reasonable_damage(self):
        # Regen must not out-heal a normal damage output; the fight ends.
        engine = GameEngine(rng=random.Random(2))
        engine.start_new_game("Hero", "fighter")
        beast = engine.content.enemies["tar_beast"].create_enemy()
        rounds = 0
        while beast.is_alive and rounds < 300:
            beast.hp = max(0, beast.hp - 25)  # a reasonable per-round player hit
            if beast.is_alive:
                combat.enemy_take_turn(beast, engine.player, engine.content.actions, engine.rng)
                combat.tick_statuses(beast, "round_end")
            rounds += 1
        self.assertFalse(beast.is_alive)
        self.assertLess(rounds, 300)
        self.assertGreater(rounds, 3)  # but it IS a longer fight than a trash mob


if __name__ == "__main__":
    unittest.main()
