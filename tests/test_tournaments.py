import unittest
import os
import tempfile

from rpg_game.core import view
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine


class TournamentContentTests(unittest.TestCase):
    def test_tournaments_load_with_human_named_opponents(self):
        content = load_content()
        tournament = content.tournaments["hordanita_imperial_ten"]

        self.assertEqual(tournament.place_id, "burg_5")
        self.assertEqual(len(tournament.opponent_ids), 10)
        for opponent_id in tournament.opponent_ids:
            enemy = content.enemies[opponent_id]
            self.assertIn("human", enemy.tags)
            self.assertTrue(enemy.name)
            self.assertGreater(len(enemy.action_ids), 0)

    def test_start_place_exposes_hordanita_tournaments(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")

        available = {tournament.id for tournament in engine.available_tournaments()}

        self.assertIn("hordanita_novice_cup", available)
        self.assertIn("hordanita_imperial_ten", available)


class TournamentProgressionTests(unittest.TestCase):
    def test_start_rejects_tournament_in_another_place(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")

        result = engine.start_tournament("fongorinos_iron_ring")

        self.assertFalse(result.success)
        self.assertIn("not held here", result.message)

    def test_complete_tournament_awards_reward_and_marks_cleared(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        tournament = engine.content.tournaments["fongorinos_iron_ring"]
        start_gold = engine.player.gold

        result = engine.complete_tournament(tournament)

        self.assertTrue(result.success)
        self.assertEqual(engine.player.gold, start_gold + 250)
        self.assertIn("steel_greatsword", engine.player.owned_weapon_ids)
        self.assertIn(tournament.id, engine.player.completed_tournament_ids)

    def test_completing_a_tournament_restores_full_hp_and_mana(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        engine.player.hp, engine.player.mana = 1, 0
        engine.complete_tournament(engine.content.tournaments["fongorinos_iron_ring"])
        self.assertEqual(engine.player.hp, engine.effective_stat("max_hp"))
        self.assertEqual(engine.player.mana, engine.effective_stat("max_mana"))

    def test_completed_non_repeatable_tournament_cannot_start_again(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        tournament = engine.content.tournaments["hordanita_novice_cup"]
        engine.complete_tournament(tournament)

        result = engine.start_tournament(tournament.id)

        self.assertFalse(result.success)
        self.assertIn("already been cleared", result.message)

    def test_between_tournament_matches_recovers_hp_and_mana(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "cleric")
        engine.player.hp = 1
        engine.player.mana = 0

        result = engine.recover_between_tournament_matches()

        self.assertEqual(engine.player.hp, engine.player.max_hp)
        self.assertEqual(engine.player.mana, engine.player.max_mana)
        self.assertEqual(result.player_hp, engine.player.max_hp)
        self.assertEqual(result.player_mana, engine.player.max_mana)

    def test_tournament_completion_survives_save_load(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        tournament = engine.content.tournaments["hordanita_novice_cup"]
        engine.complete_tournament(tournament)

        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "save.json")
            engine.save(path)
            loaded = GameEngine(content=engine.content)
            loaded.load(path)

        self.assertIn(tournament.id, loaded.player.completed_tournament_ids)


class TournamentSnapshotTests(unittest.TestCase):
    def test_snapshot_lists_tournaments_for_current_place(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")

        snapshot = view.build_snapshot(engine)
        ids = {tournament.id for tournament in snapshot.tournaments}

        self.assertIn("hordanita_novice_cup", ids)
        self.assertTrue(all(tournament.opponent_count > 0 for tournament in snapshot.tournaments))


if __name__ == "__main__":
    unittest.main()
