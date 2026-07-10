"""B67 S1: travel events — engine, outcomes, frequency, shell flow.

An event REPLACES a fired encounter slot with the authored chance (~10%), so
the total interruption frequency does not increase. Outcomes use existing
primitives only (gold, heal, next-battle buff, encounter). Seeded determinism
+ a >=1000-slot frequency sim. Shell parts skip without pygame/pytmx.
"""

import os
import random
import unittest

from rpg_game.core import events
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp

    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


class EventEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = load_content()

    def test_three_cainos_events_load(self):
        ids = [e.id for e in self.content.travel_events]
        self.assertEqual(ids, ["abandoned_cart", "wayside_altar", "wounded_trader"])
        self.assertTrue(all(e.zone == "cainos" for e in self.content.travel_events))

    def test_frequency_is_about_ten_percent_of_fired_slots(self):
        rng = random.Random(42)
        slots = 5000
        hits = sum(events.replaces_encounter(self.content.travel_event_slot_chance, rng)
                   for _ in range(slots))
        self.assertAlmostEqual(hits / slots, 0.10, delta=0.015)

    def test_pick_is_seeded_deterministic_and_zone_scoped(self):
        picks = [events.pick_event(self.content.travel_events, "cainos", random.Random(7)).id
                 for _ in range(5)]
        self.assertEqual(len(set(picks)), 1)
        self.assertIsNone(events.pick_event(self.content.travel_events, "mork_skog",
                                            random.Random(7)))

    def _player(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        return engine.player

    def _event(self, event_id):
        return next(e for e in self.content.travel_events if e.id == event_id)

    def test_gold_outcome_pays_out(self):
        player = self._player()
        before = player.gold
        result = events.resolve_choice(player, self._event("wounded_trader"), "help",
                                       random.Random(0))
        self.assertEqual(player.gold, before + 35)
        self.assertEqual(result.gold_delta, 35)

    def test_altar_buff_costs_gold_and_lasts_into_the_next_battle(self):
        player = self._player()
        player.gold = 50
        result = events.resolve_choice(player, self._event("wayside_altar"), "offer",
                                       random.Random(0))
        self.assertEqual(player.gold, 30)
        self.assertEqual(result.buff_stat, "damage_dealt_mod")
        buff = next(s for s in player.active_statuses if s.type == "buff")
        self.assertEqual(buff.duration, 3)
        self.assertEqual(player.damage_dealt_mod, 25)

    def test_altar_offer_is_refused_without_gold(self):
        player = self._player()
        player.gold = 5
        result = events.resolve_choice(player, self._event("wayside_altar"), "offer",
                                       random.Random(0))
        self.assertEqual(player.gold, 5)
        self.assertEqual(player.active_statuses, [])
        self.assertIn("cannot afford", result.text)

    def test_cart_search_rolls_gold_or_ambush_deterministically(self):
        outcomes = set()
        for seed in range(40):
            player = self._player()
            result = events.resolve_choice(player, self._event("abandoned_cart"), "search",
                                           random.Random(seed))
            outcomes.add("ambush" if result.start_encounter else "gold")
        self.assertEqual(outcomes, {"gold", "ambush"})


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class EventShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_event_screen_offers_one_button_per_choice(self):
        app = OverworldApp()
        app.screen = pygame.Surface((1024, 680))
        app.active_event = app.engine.content.travel_events[0]
        app.mode = "travel_event"
        app.buttons = []
        app.hover.begin()
        app._draw_travel_event()
        self.assertEqual(len(app.buttons), len(app.active_event.choices))

    def test_resolving_a_non_combat_choice_returns_to_walk(self):
        app = OverworldApp()
        app.screen = pygame.Surface((1024, 680))
        event = next(e for e in app.engine.content.travel_events if e.id == "wounded_trader")
        app.active_event = event
        app.mode = "travel_event"
        app._resolve_travel_event("help")
        self.assertEqual(app.mode, "walk")
        self.assertIsNone(app.active_event)


if __name__ == "__main__":
    unittest.main()
