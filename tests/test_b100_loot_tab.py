"""B100: the Loot log tab — every item/gold acquisition lands on the loot
channel with a source-typed line. One test per acquisition path (enemy drop
and battle gold are locked in test_chatbox_dedup). Skips without pygame/pytmx.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame

    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import chatlog
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class LootTabTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _app(self, class_id="fighter"):
        engine = GameEngine()
        engine.start_new_game("Hero", class_id)
        app = OverworldApp(engine=engine)
        app.event_log.clear()
        return app

    def _loot_lines(self, app):
        return [chatlog.plain(payload) for payload, _color in app.event_log
                if chatlog.channel_of(payload) == chatlog.CHANNEL_LOOT]

    def test_loot_tab_filters_on_loot_channel(self):
        app = self._app()
        self.assertIsNone(app._log_channel())          # All
        app._set_log_tab("combat")
        self.assertEqual(app._log_channel(), chatlog.CHANNEL_COMBAT)
        app._set_log_tab("loot")
        self.assertEqual(app._log_channel(), chatlog.CHANNEL_LOOT)

    def test_chest_opening_logs_on_loot_channel(self):
        app = self._app()
        (cx, cy), chest_id = next(iter(app.chest_tiles.items()))
        app.world.set_tile(cx + 1, cy)
        self.assertTrue(app._try_open_chest())
        lines = self._loot_lines(app)
        self.assertTrue(any(l.startswith("Opened chest: ") for l in lines), lines)

    def test_shop_purchase_logs_on_loot_channel(self):
        app = self._app()
        app.engine.player.gold = 1000
        # Any store item the engine will sell to the player.
        entries = app.engine.store_entries()
        self.assertTrue(entries)
        app.buy(entries[0].id)
        lines = self._loot_lines(app)
        self.assertEqual(len(lines), 1, list(app.event_log))

    def test_shop_sale_logs_on_loot_channel(self):
        app = self._app()
        app.engine.player.inventory.add_consumable("rat_pelt")   # miscellaneous: sellable
        app.sell("rat_pelt")
        lines = self._loot_lines(app)
        self.assertEqual(len(lines), 1, list(app.event_log))

    def test_tome_study_logs_on_loot_channel(self):
        app = self._app("mage")
        player = app.engine.player
        tome_id = next(item_id for item_id, item in app.engine.content.items.items()
                       if item.kind == "tome")
        player.inventory.add_consumable(tome_id)
        player.level = 20   # clear any level gate on the taught skill
        app.use_inventory_item(tome_id)
        lines = self._loot_lines(app)
        self.assertEqual(len(lines), 1, list(app.event_log))

    def test_brew_logs_on_loot_channel(self):
        app = self._app()
        recipes = app.engine.brew_recipes()
        self.assertTrue(recipes)
        recipe = recipes[0]
        app.engine.player.gold = 1000
        for material_id, count in recipe.materials:
            for _ in range(count):
                app.engine.player.inventory.add_consumable(material_id)
        app._brew(recipe.id)
        lines = self._loot_lines(app)
        self.assertEqual(len(lines), 1, list(app.event_log))

    def test_travel_event_gold_logs_on_loot_channel(self):
        app = self._app()
        event = next(e for e in app.engine.content.travel_events
                     if e.id == "wounded_trader")
        app.active_event = event
        app.mode = "travel_event"
        app._resolve_travel_event("help")   # +35 gold, chance 1.0
        lines = self._loot_lines(app)
        self.assertEqual(len(lines), 1, list(app.event_log))

    def test_tournament_reward_logs_on_loot_channel(self):
        from rpg_game.presentation.pygame_overworld import TournamentRun
        app = self._app()
        tournament = next(iter(app.engine.content.tournaments.values()))
        # Stub the battle itself: the last match was just won.
        app.run_tournament_battle = lambda enemy: "victory"
        app.tournament_run = TournamentRun(tournament,
                                           next_index=len(tournament.opponent_ids) - 1)
        app._start_next_tournament_match()
        lines = self._loot_lines(app)
        self.assertEqual(len(lines), 1, list(app.event_log))

    def test_failed_purchase_stays_off_the_loot_tab(self):
        app = self._app()
        app.engine.player.gold = 0
        entries = app.engine.store_entries()
        app.buy(entries[0].id)
        self.assertEqual(self._loot_lines(app), [])


if __name__ == "__main__":
    unittest.main()
