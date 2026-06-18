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
        self.app.world.set_tile(14, 10)  # Hordanita
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

    # -- battle handoff -----------------------------------------------------

    def test_single_battle_returns_outcome_without_quitting(self):
        self._into_wild()
        enemy = self.app.engine.create_encounter()
        battle = BattleApp(engine=self.app.engine, enemy=enemy, standalone=False)
        for _ in range(500):
            if not battle.running:
                break
            if battle.mode == "stat_choice":
                battle.apply_stat("hp")
            else:
                battle.issue_turn("attack")
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
        self.assertEqual(self.app.world.current_tile, (14, 10))
        self.assertEqual(self.app.engine.player.current_place_id, "burg_5")


if __name__ == "__main__":
    unittest.main()
