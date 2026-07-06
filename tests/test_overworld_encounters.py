"""Headless tests for wild encounters and the overworld<->battle loop.

Skips when pygame/pytmx are not installed.
"""

import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp
    from rpg_game.presentation.pygame_battle import BattleApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class OverworldEncounterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()

    def _into_wild(self):
        self.app.world.set_tile(14, 8)
        self.app.sync_location()

    # -- the roll -----------------------------------------------------------

    def test_no_encounter_in_town(self):
        self.app.world.set_tile(51, 52)  # Hordanita (new coords)
        self.app.sync_location()
        self.app.encounter_rate = 1.0
        self.assertIsNone(self.app.maybe_encounter())

    def test_encounter_in_wilderness_when_rolled(self):
        self._into_wild()
        self.app.encounter_rate = 1.0
        enemy = self.app.maybe_encounter()
        self.assertIsNotNone(enemy)

    def test_no_encounter_when_rate_zero(self):
        self._into_wild()
        self.app.encounter_rate = 0.0
        self.assertIsNone(self.app.maybe_encounter())

    def test_seeded_step_can_trigger(self):
        self.app.engine.rng = random.Random(12345)
        self.app.encounter_rate = 0.5
        triggered = False
        for _ in range(200):
            self._into_wild()
            if self.app.maybe_encounter() is not None:
                triggered = True
                break
        self.assertTrue(triggered)

    # -- B12 encounter heatmap (rate by distance + roads) -------------------

    def test_encounter_rate_zero_on_town_and_adjacent(self):
        self.app.encounter_rate = 0.06
        town = next(iter(self.app.world.town_tiles))
        self.assertEqual(self.app.encounter_rate_at(town), 0.0)
        self.assertEqual(self.app.encounter_rate_at((town[0] + 1, town[1])), 0.0)

    def test_encounter_rate_rises_with_distance_to_full(self):
        # Measured east of burg_117 (Yeblegali), a non-cluster pin town whose safe
        # zone is just the 1-tile radius — so the B12 ramp is visible. (burg_5 now
        # has a whole-cluster safe zone, B32, so its ramp starts farther out.)
        self.app.encounter_rate = 0.06
        rates = [self.app.encounter_rate_at((24 + d, 24)) for d in range(0, 8)]  # east of burg_117 (24,24)
        self.assertTrue(all(rates[i] <= rates[i + 1] for i in range(len(rates) - 1)))  # non-decreasing
        self.assertEqual(rates[0], 0.0)        # on the town
        self.assertAlmostEqual(rates[-1], 0.06)  # full base a few tiles out

    def test_road_tiles_reduce_the_rate(self):
        self.app.encounter_rate = 0.06
        far = (15, 8)  # well clear of any town safe zone
        # Measure the road FACTOR directly by toggling _on_path, so the result is
        # independent of whether this tile naturally carries path/flower ground.
        self.app._on_path = lambda tile: False
        base = self.app.encounter_rate_at(far)
        self.assertGreater(base, 0.0)
        self.app._on_path = lambda tile: True
        self.assertAlmostEqual(self.app.encounter_rate_at(far), base * 0.6)

    # -- B32: a whole town cluster + margin is encounter-free ----------------

    def test_no_encounters_on_any_cluster_tile_or_margin(self):
        from rpg_game.presentation import town_cluster
        self.app.encounter_rate = 0.06
        for pid, anchor in self.app.cluster_anchors.items():
            tmpl = self.app.cluster_templates[pid]
            cluster = town_cluster.cluster_footprints(anchor, tmpl) | {anchor}
            cluster |= set(town_cluster.cluster_entrances(anchor, tmpl).values())
            cluster |= {t for t, p in self.app.hub_interior.items() if p == pid}
            for (cx, cy) in cluster:
                for dx in range(-2, 3):       # SAFE_TILE_MARGIN
                    for dy in range(-2, 3):
                        tile = (cx + dx, cy + dy)
                        self.assertEqual(self.app.encounter_rate_at(tile), 0.0,
                                         f"{pid} not safe at {tile}")

    def test_sim_no_spawns_standing_on_cluster_streets(self):
        # N>=200 rolls on each walkable cluster (door/cobble) tile -> zero encounters.
        self.app.encounter_rate = 0.06
        self.app.engine.rng = random.Random(7)
        spawns = 0
        street_tiles = [t for t in self.app.hub_interior if t != self.app.cluster_anchor]
        for tile in street_tiles:
            self.app.world.set_tile(*tile)
            self.app.sync_location()
            for _ in range(220):
                if self.app.maybe_encounter() is not None:
                    spawns += 1
        self.assertEqual(spawns, 0, f"{spawns} ambushes on town streets across {len(street_tiles)} tiles")

    # -- battle handoff -----------------------------------------------------

    def test_single_battle_returns_outcome_without_quitting(self):
        self._into_wild()
        enemy = self.app.engine.create_encounter()
        battle = BattleApp(engine=self.app.engine, enemy=enemy, standalone=False)
        for _ in range(500):
            if battle.mode == "result" or not battle.running:
                break
            if battle.mode == "stat_choice":
                battle.apply_stat("hp")
            else:
                battle.issue_turn("attack")
                battle.flush_sequence()   # B75: drain the staged playback
        # Single battles pause on a result view; pressing continues and finishes.
        self.assertEqual(battle.mode, "result")
        battle._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE, unicode=" "))
        self.assertIn(battle.outcome, ("victory", "defeat", "fled"))
        self.assertTrue(pygame.get_init())  # must not pygame.quit() in single mode

    # -- post-battle resolution --------------------------------------------

    def test_victory_keeps_position(self):
        self._into_wild()
        enemy = self.app.engine.create_encounter()
        pos = self.app.world.player.center
        self.app.resolve_battle_outcome("victory", enemy)
        self.assertEqual(self.app.world.player.center, pos)
        self.assertEqual(self.app.engine.player.current_place_id, self.app.zone.wild_region_place_id)

    def test_defeat_respawns_to_hub(self):
        self._into_wild()
        enemy = self.app.engine.create_encounter()
        self.app.engine.player.current_place_id = "burg_5"  # engine respawn already happened
        self.app.resolve_battle_outcome("defeat", enemy)
        self.assertEqual(self.app.world.current_tile, (51, 52))
        self.assertEqual(self.app.engine.player.current_place_id, "burg_5")


if __name__ == "__main__":
    unittest.main()
