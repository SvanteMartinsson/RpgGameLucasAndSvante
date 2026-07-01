"""B42: the four-zone wild roster.

Locks the 6 new forest enemies, the trait-derived weaknesses from the design
screenshot, the four wild-region pools + rare_encounter + level bands, the loot
policy (trash/standard have no shared-rare access, elites do; every enemy has a
drop pool), and the engine invariant that every enemy owns at least one mana-free
non-telegraph fallback action (else it would hesitate forever).
"""

import os
import random
import unittest

from rpg_game.core import combat
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine

NEW_FOREST = ["goblin_raider", "thornling", "razortusk_boar", "goblin_shaman",
              "broodmother_spider", "strangling_vine"]
SPRITE_DIR = os.path.join(os.path.dirname(__file__), "..", "rpg_game",
                          "assets", "sprites", "generated")

HUB_POOLS = {
    "burg_54":  (0, 0, None,   # CAINOS: no region band -> per-enemy level bands
                 {"wild_dog", "goblin_scrapper", "giant_spider", "wild_stag", "giant_rat", "undead"}),
    "burg_146": (4, 9, "strangling_vine",
                 {"goblin_raider", "thornling", "razortusk_boar", "cave_bear", "dire_wolf",
                  "treant", "broodmother_spider", "goblin_shaman"}),
    "burg_320": (5, 10, "bog_hag",
                 {"bog_leech", "mire_lurker", "rotting_fiend", "mutated_mudcrab", "tar_beast",
                  "bog_wraith", "witchlight"}),
    "burg_121": (6, 12, "cursed_wight",
                 {"skeleton_warrior", "ghoul", "grave_hound", "undead", "undead_priest",
                  "shade", "hollow_worg"}),
}


class NewForestEnemyTests(unittest.TestCase):
    def setUp(self):
        self.content = load_content()

    def test_six_new_enemies_load_with_a_sprite(self):
        for eid in NEW_FOREST:
            self.assertIn(eid, self.content.enemies, eid)
            self.assertTrue(os.path.exists(os.path.join(SPRITE_DIR, f"{eid}.png")),
                            f"{eid}.png missing (placeholder expected)")

    def test_new_enemy_weaknesses_match_the_design(self):
        def r(eid, t):
            return self.content.enemies[eid].resistances.get(t, 1.0)
        expected = {
            "thornling": {"fire": 2.0, "frost": 0.65},
            "razortusk_boar": {"fire": 2.0, "poison": 1.25, "frost": 0.65},
            "goblin_shaman": {"holy": 1.5, "physical": 0.65},
            "broodmother_spider": {"fire": 1.25, "poison": 0.65},
            "strangling_vine": {"fire": 2.0, "frost": 0.65},
            "goblin_raider": {},  # no trait -> neutral
        }
        for eid, exp in expected.items():
            for t, v in exp.items():
                self.assertAlmostEqual(r(eid, t), v, places=9, msg=f"{eid}/{t}")


class ZonePoolTests(unittest.TestCase):
    def setUp(self):
        self.content = load_content()

    def test_hub_pools_bands_and_rare(self):
        for pid, (lmin, lmax, rare, roster) in HUB_POOLS.items():
            place = self.content.places[pid]
            self.assertEqual(place.level_min, lmin, pid)
            self.assertEqual(place.level_max, lmax, pid)
            self.assertEqual(set(place.encounters), roster, pid)
            self.assertEqual(getattr(place, "rare_encounter", None) or None, rare, pid)

    def test_every_encounter_id_creates_a_valid_enemy(self):
        for pid, (_lmin, _lmax, rare, roster) in HUB_POOLS.items():
            for eid in roster | ({rare} if rare else set()):
                enemy = self.content.enemies[eid].create_enemy()
                self.assertGreater(enemy.max_hp, 0, f"{pid}:{eid}")


class LootPolicyTests(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine(rng=random.Random(0))
        self.engine.start_new_game("Hero", "fighter")
        self.content = self.engine.content

    def test_trash_and_standard_have_no_shared_rare_access_elites_do(self):
        no_rare = ["goblin_raider", "thornling", "razortusk_boar", "bog_leech",
                   "mire_lurker", "rotting_fiend", "ghoul", "grave_hound"]
        with_rare = ["goblin_shaman", "broodmother_spider", "strangling_vine",
                     "witchlight", "bog_hag", "shade", "cursed_wight", "skeleton_warrior"]
        for eid in no_rare:
            self.assertFalse(self.content.enemies[eid].rare_table_access, eid)
        for eid in with_rare:
            self.assertTrue(self.content.enemies[eid].rare_table_access, eid)

    def test_every_new_enemy_has_a_non_empty_drop_pool(self):
        for eid in NEW_FOREST:
            enemy = self.content.enemies[eid].create_enemy()
            self.assertTrue(self.engine.loot_pool(enemy), f"{eid} has empty loot pool")

    def test_low_level_wild_cannot_drop_top_tier_shared_rares(self):
        # a level-4 forest elite may reach the shared rare table but is tier-capped
        shaman = self.content.enemies["goblin_shaman"].create_enemy()
        ids = {e["item_id"] for e in self.engine.loot_pool(shaman)}
        self.assertNotIn("worldsplitter", ids)   # tier 6, gated far above L5


class FallbackActionInvariantTests(unittest.TestCase):
    """Every enemy must own >=1 ready, mana-free, non-telegraph action, else
    choose_enemy_action returns None and the enemy hesitates every turn."""

    def setUp(self):
        self.content = load_content()

    def test_every_enemy_has_a_mana_free_non_telegraph_action(self):
        actions = self.content.actions
        for eid, enemy in self.content.enemies.items():
            fallbacks = [
                actions[aid] for aid in enemy.action_ids
                if aid in actions and not actions[aid].telegraph and actions[aid].mana_cost == 0
            ]
            self.assertTrue(fallbacks, f"{eid} has no mana-free non-telegraph fallback")

    def test_new_casters_pick_an_action_without_hesitating(self):
        engine = GameEngine(rng=random.Random(3))
        engine.start_new_game("Hero", "mage")
        for eid in ["goblin_shaman", "bog_hag", "witchlight", "broodmother_spider",
                    "strangling_vine", "cursed_wight"]:
            enemy = engine.content.enemies[eid].create_enemy()
            action = combat.choose_enemy_action(enemy, engine.player, engine.content.actions,
                                                 random.Random(1))
            self.assertIsNotNone(action, f"{eid} hesitated (no ready action)")


if __name__ == "__main__":
    unittest.main()
