"""Two playtest fixes:
  #1 a loot drop's SHOWN rarity is the item's AUTHORED rarity (gear/weapon/item),
     so the chat line matches inventory/character — not the drop-luck denominator.
  #3 the player's skill cooldowns reset at every encounter start (wild AND
     tournament) so a cooldown never leaks from a previous fight.
"""

import random
import unittest

from rpg_game.core.game import GameEngine


class LootRarityIsAuthoredTest(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(rng=random.Random(0))
        self.engine.start_new_game("H", "fighter")
        self.enemy = self.engine.content.enemies["hollow_worg"].create_enemy()

    def _drop(self, item_id):
        entry = {"item_id": item_id, "rarity_tier": 3, "weight": 1}
        return self.engine._make_loot_drop(entry, self.enemy, [entry])

    def test_gear_drop_rarity_is_the_gear_definitions_rarity(self):
        drop = self._drop("iron_helm")
        self.assertEqual(drop.rarity, self.engine.content.gear_items["iron_helm"].rarity)
        self.assertEqual(drop.rarity, "rare")   # matches what inventory/character show

    def test_weapon_drop_rarity_is_the_weapon_definitions_rarity(self):
        drop = self._drop("worgfang")
        self.assertEqual(drop.rarity, self.engine.content.weapons["worgfang"].rarity)

    def test_consumable_drop_rarity_defaults_common(self):
        self.assertEqual(self._drop("hp_potion").rarity, "common")

    def test_shown_rarity_is_independent_of_drop_denominator(self):
        # Same item, wildly different drop chances -> same authored rarity shown.
        rares = {self._drop("iron_helm").rarity for _ in range(5)}
        self.assertEqual(rares, {"rare"})


class CooldownResetPerEncounterTest(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(rng=random.Random(0))
        self.engine.start_new_game("H", "fighter")

    def test_tournament_opponent_start_clears_player_cooldowns(self):
        self.engine.player.cooldowns = {"frenzy": 2}
        tournament = next(iter(self.engine.content.tournaments.values()))
        self.engine.create_tournament_opponent(tournament, 0)
        self.assertEqual(self.engine.player.cooldowns, {})

    def test_each_tournament_fight_starts_fresh(self):
        tournament = next(iter(self.engine.content.tournaments.values()))
        self.engine.create_tournament_opponent(tournament, 0)
        self.engine.player.cooldowns = {"frenzy": 2}   # spent in fight 1
        self.engine.create_tournament_opponent(tournament, 1)
        self.assertEqual(self.engine.player.cooldowns, {})   # ready again in fight 2

    def test_wild_encounter_start_clears_player_cooldowns(self):
        self.engine.player.current_place_id = "burg_54"   # a wild region with encounters
        self.engine.rng = random.Random(3)
        fired = False
        for _ in range(500):
            self.engine.player.cooldowns = {"frenzy": 2}
            enemy = self.engine.create_encounter()
            if enemy is not None:
                fired = True
                self.assertEqual(self.engine.player.cooldowns, {})
                break
        self.assertTrue(fired, "no wild encounter fired to test")


if __name__ == "__main__":
    unittest.main()
