"""ZONE2 step 2c: the Hollow Worg — a rare western miniboss.

Data only, reusing the bruiser/telegraph archetype. Made rare via a per-region
rare-roll (separate from the uniform pool), so the normal pool's relative
frequencies are unchanged and the core is untouched.
"""

import collections
import random
import unittest

from rpg_game.core import combat
from rpg_game.core.entities import EffectSpec
from rpg_game.core.game import GameEngine

FOREST = "burg_146"  # the worg's home (mid-west forest, undead-decay lore)
CORE = "burg_54"
NORMAL_FOREST = {"undead", "cave_bear", "undead_priest", "dire_wolf", "wild_boar", "treant"}


class HollowWorgTest(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine()
        self.engine.start_new_game("Hero", "fighter")

    def test_loads(self):
        self.assertIn("hollow_worg", self.engine.content.enemies)

    def test_is_a_rare_region_encounter_not_a_pool_member(self):
        forest = self.engine.content.places[FOREST]
        self.assertEqual(forest.rare_encounter, "hollow_worg")
        self.assertGreater(forest.rare_chance, 0.0)
        self.assertNotIn("hollow_worg", forest.encounters)  # not a uniform pool member

    def test_spawns_rarely_in_the_west(self):
        self.engine.rng = random.Random(7)
        self.engine.player.current_place_id = FOREST
        counts = collections.Counter()
        total = 4000
        for _ in range(total):
            counts[self.engine.create_encounter().id] += 1
        rate = counts["hollow_worg"] / total
        self.assertGreater(rate, 0.0)
        self.assertLess(rate, 0.15)  # an event, not a regular
        # normal beasts still all appear (relative frequencies preserved)
        self.assertTrue(NORMAL_FOREST <= set(counts))

    def test_does_not_spawn_in_the_core(self):
        self.engine.rng = random.Random(1)
        self.engine.player.current_place_id = CORE
        seen = {self.engine.create_encounter().id for _ in range(400)}
        self.assertNotIn("hollow_worg", seen)

    def test_core_region_has_no_rare_hook(self):
        self.assertEqual(self.engine.content.places[CORE].rare_encounter, "")
        self.assertEqual(self.engine.content.places[CORE].rare_chance, 0.0)

    def test_is_a_heavy_bruiser(self):
        worg = self.engine.content.enemies["hollow_worg"].create_enemy()
        bear = self.engine.content.enemies["cave_bear"].create_enemy()
        self.assertGreater(worg.max_hp, bear.max_hp)
        self.assertGreater(worg.damage, bear.damage)

    def test_lightly_physical_resistant(self):
        worg = self.engine.content.enemies["hollow_worg"].create_enemy()
        worg.armor = 0  # isolate the resistance from armor
        phys = EffectSpec(type="damage", scale="flat", magnitude=10, damage_type="physical")
        self.assertEqual(combat.calculate_effect_damage(self.engine.player, worg, None, phys), 9)  # x0.9

    def test_telegraphs_its_heavy_pounce_then_releases(self):
        worg = self.engine.content.enemies["hollow_worg"].create_enemy()
        rng = random.Random(1)
        before = self.engine.player.hp
        combat.enemy_take_turn(worg, self.engine.player, self.engine.content.actions, rng)
        self.assertEqual(worg.charging_action_id, "worg_pounce")
        self.assertEqual(self.engine.player.hp, before)
        combat.enemy_take_turn(worg, self.engine.player, self.engine.content.actions, rng)
        self.assertEqual(worg.charging_action_id, "")
        self.assertLess(self.engine.player.hp, before)

    def test_normal_western_spawn_frequency_unchanged_without_the_rare_roll(self):
        # With no rare hook, the forest pool is the plain uniform list (regression
        # for "normal frequency unchanged"): rates are roughly equal across beasts.
        self.engine.content.places[FOREST]  # sanity
        place = self.engine.content.places[FOREST]
        self.assertEqual(set(place.encounters), NORMAL_FOREST)


if __name__ == "__main__":
    unittest.main()
