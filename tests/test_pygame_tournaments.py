"""Headless tests for Pygame tournament presentation.

Skips when pygame/pytmx are not installed.
"""

import os
import unittest
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame

    from rpg_game.core.game import GameEngine
    from rpg_game.presentation.pygame_battle import BattleApp
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class PygameTournamentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()

    def test_town_hall_menu_opens_tournaments_only_where_available(self):
        # B30: the town_hall door opens the "Town Hall" menu where tournaments are
        # held (burg_5); its choice opens the list. Where none are (burg_117) the
        # door reads as locked and no menu opens.
        th_door = next(t for t, (pid, bid) in self.app.door_index.items()
                       if pid == "burg_5" and bid == "town_hall")
        self.app.world.set_tile(*th_door)
        self.app.mode = "walk"
        self.app._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        self.assertEqual(self.app.mode, "building")          # titled menu, not the list yet
        self.assertEqual(self.app.building_menu, ("burg_5", "town_hall"))
        self.app._choose_building_action("tournaments")      # the menu's [Tournaments] choice
        self.assertEqual(self.app.mode, "tournaments")

        self.app.mode = "walk"
        self.app._interact_door("burg_117", "town_hall")  # Yeblegali: no tournaments
        self.assertEqual(self.app.mode, "walk")
        self.assertIn("locked", self.app.event_log[-1][0].lower())

    def test_victory_series_runs_all_opponents_and_awards_reward(self):
        fought = []
        self.app.run_tournament_battle = lambda enemy: fought.append(enemy.id) or "victory"
        start_gold = self.app.engine.player.gold

        self.app.start_tournament_series("hordanita_novice_cup")
        while self.app.tournament_run is not None:
            self.app.continue_tournament()

        self.assertEqual(
            fought,
            ["arena_ralla_quickstep", "arena_borin_shieldhand", "arena_tomas_reed"],
        )
        self.assertEqual(self.app.engine.player.gold, start_gold + 120)
        self.assertIn("hordanita_novice_cup", self.app.engine.player.completed_tournament_ids)

    def test_defeat_mid_series_gives_no_reward_and_can_restart_cleanly(self):
        outcomes = iter(["victory", "defeat"])
        self.app.run_tournament_battle = lambda enemy: next(outcomes)
        start_gold = self.app.engine.player.gold

        self.app.start_tournament_series("hordanita_novice_cup")
        self.app.continue_tournament()

        self.assertIsNone(self.app.tournament_run)
        self.assertEqual(self.app.engine.player.gold, start_gold)
        self.assertNotIn("hordanita_novice_cup", self.app.engine.player.completed_tournament_ids)

        outcomes = iter(["victory", "victory", "victory"])
        self.app.run_tournament_battle = lambda enemy: next(outcomes)
        self.app.start_tournament_series("hordanita_novice_cup")
        while self.app.tournament_run is not None:
            self.app.continue_tournament()

        self.assertIn("hordanita_novice_cup", self.app.engine.player.completed_tournament_ids)

    def test_tournament_intermission_heals_player(self):
        self.app.engine.player.hp = 1
        self.app.engine.player.mana = 0
        self.app.run_tournament_battle = lambda enemy: "victory"

        self.app.start_tournament_series("hordanita_novice_cup")

        self.assertEqual(self.app.mode, "tournament_intermission")
        self.assertEqual(self.app.engine.player.hp, self.app.engine.player.max_hp)
        self.assertEqual(self.app.engine.player.mana, self.app.engine.effective_stat('max_mana'))

    def test_tournament_battle_hides_flee_and_swap(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        enemy = engine.content.enemies["arena_ralla_quickstep"].create_enemy()
        battle = BattleApp(engine=engine, enemy=enemy, standalone=False, allow_flee=False, allow_swap=False)

        battle.draw()
        labels = [button.label for button in battle.buttons]

        self.assertFalse(any("Flee" in label for label in labels))
        self.assertFalse(any("Swap" in label for label in labels))

    def test_tournament_battle_reuses_overworld_battle_log(self):
        enemy = self.app.engine.content.enemies["arena_ralla_quickstep"].create_enemy()
        with mock.patch("rpg_game.presentation.pygame_overworld.BattleApp") as battle_cls:
            battle_cls.return_value.run.return_value = "victory"
            self.assertEqual(self.app.run_tournament_battle(enemy), "victory")
        kwargs = battle_cls.call_args.kwargs
        self.assertIs(kwargs["event_log"], self.app.event_log)
        self.assertFalse(kwargs["allow_flee"])
        self.assertFalse(kwargs["allow_swap"])


if __name__ == "__main__":
    unittest.main()
