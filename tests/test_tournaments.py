import unittest
import os
import tempfile

from rpg_game.core import combat, view
from rpg_game.core.data_loader import load_content
from rpg_game.core.entities import ActiveStatus
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


class TournamentDifficultyTests(unittest.TestCase):
    """B13: diversified per-instance opponent buffs. Small/mid tournaments (<=4
    opponents, incl. iron_ring): x1.6 max HP, then alternating roles — even index
    TANKY (+armour, +damage), odd index BURST (+crit, +damage). Big finale (>=10):
    per-index escalation, also split tanky/burst."""

    def setUp(self):
        from rpg_game.core import game
        from rpg_game.core.progression import round_half_up
        self.G = game
        self.round = round_half_up
        self.engine = GameEngine()
        self.engine.start_new_game("Hero", "fighter")
        self.t = self.engine.content.tournaments

    def _raw(self, tour, i):
        return self.engine.content.enemies[tour.opponent_ids[i]].create_enemy()

    def _check_small(self, tour):
        for i in range(len(tour.opponent_ids)):
            raw, buf = self._raw(tour, i), self.engine.create_tournament_opponent(tour, i)
            self.assertEqual(buf.max_hp, self.round(raw.max_hp * self.G.TOURNEY_SMALL_HP_MULT))
            if i % 2 == 0:  # tanky
                self.assertEqual(buf.armor, raw.armor + self.G.TOURNEY_TANKY_ARMOR)
                self.assertEqual(buf.damage, raw.damage + self.G.TOURNEY_TANKY_DMG)
            else:           # burst
                self.assertEqual(buf.crit_chance, raw.crit_chance + self.G.TOURNEY_BURST_CRIT)
                self.assertEqual(buf.damage, raw.damage + self.G.TOURNEY_BURST_DMG)

    def test_small_and_mid_tournaments_split_tanky_and_burst(self):
        for tid in ("hordanita_novice_cup", "alherralba_market_trials", "fongorinos_iron_ring"):
            tour = self.t[tid]
            self.assertLessEqual(len(tour.opponent_ids), 4)
            self._check_small(tour)

    def test_zone2_wildblood_pit_is_a_late_zone_beast_bracket(self):
        # B26: a frontier beast tournament in a zone-2 city (Rotequero). Opponents are
        # drawn from the zone-2 wild pool (NOT the arena humans), it sits in a later
        # zone (not the start town), gets the small-bracket diversified buff, and pays
        # a NON-strong consumable reward (no gold, no signature item / power spike).
        tour = self.t["rotequero_wildblood_pit"]
        self.assertEqual(tour.place_id, "burg_146")
        self.assertLessEqual(len(tour.opponent_ids), 4)
        rotequero_pool = set(self.engine.content.places["burg_146"].encounters)
        parguillas_pool = set(self.engine.content.places["burg_320"].encounters)
        zone2_pool = rotequero_pool | parguillas_pool
        for eid in tour.opponent_ids:
            enemy = self.engine.content.enemies[eid]
            self.assertIn(eid, zone2_pool)            # from the zone-2 wild pool
            self.assertNotIn("human", enemy.tags)     # beasts, not arena humans
            self.assertGreaterEqual(enemy.level, 5)   # zone-level band, not L1 fodder
        # Reward: no gold; a neutral item + one mana + one hp potion, all consumables
        # (no weapon/gear power spike).
        self.assertEqual(tour.reward.gold, 0)
        self.assertEqual(tour.reward.item_ids, ("antidote", "mana_potion", "hp_potion"))
        for item_id in tour.reward.item_ids:
            self.assertIn(item_id, self.engine.content.items)   # consumables, not weapons/gear
        self._check_small(tour)                       # diversified buff applies

    def test_wildblood_pit_reward_grants_consumables_no_gold(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        tour = engine.content.tournaments["rotequero_wildblood_pit"]
        start_gold = engine.player.gold
        before = {i: engine.player.inventory.count(i) for i in tour.reward.item_ids}

        result = engine.complete_tournament(tour)

        self.assertTrue(result.success)
        self.assertEqual(engine.player.gold, start_gold)        # no gold awarded
        for item_id in tour.reward.item_ids:
            self.assertEqual(engine.player.inventory.count(item_id), before[item_id] + 1)

    def test_big_finale_is_diversified_per_index(self):
        tour = self.t["hordanita_imperial_ten"]
        self.assertEqual(len(tour.opponent_ids), 10)
        for i in range(10):
            raw, buf = self._raw(tour, i), self.engine.create_tournament_opponent(tour, i)
            if i % 2 == 0:  # tanky: +armour, scaling HP
                self.assertEqual(buf.armor, raw.armor + self.G.TOURNEY_FINALE_TANKY_ARMOR)
                self.assertEqual(buf.max_hp, raw.max_hp + self.G.TOURNEY_FINALE_HP + i)
            else:           # burst: +crit, per-index damage
                self.assertEqual(buf.crit_chance, raw.crit_chance + 50)
                self.assertEqual(buf.damage, raw.damage + (i + 1) * 2)


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
        self.assertEqual(engine.player.mana, engine.effective_stat('max_mana'))
        self.assertEqual(result.player_hp, engine.player.max_hp)
        self.assertEqual(result.player_mana, engine.effective_stat('max_mana'))

    def test_between_tournament_matches_clears_battle_statuses(self):
        # B85: a DoT applied by opponent 1 must not tick during match 2.
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        engine.player.active_statuses.append(
            ActiveStatus(type="poison", magnitude=5, duration=3, tick_timing="round_end")
        )

        engine.recover_between_tournament_matches()
        hp_before = engine.player.hp
        combat.tick_statuses(engine.player, "round_end")

        self.assertEqual(engine.player.active_statuses, [])
        self.assertEqual(engine.player.hp, hp_before)

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
