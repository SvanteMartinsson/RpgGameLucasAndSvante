"""B136c: the towns shut at night, and the two safety valves back to morning.

The gate is one check in `_interact_door`, so these tests drive that entry point
rather than the drawing code. The valves (rest, respawn) live in CORE so the
terminal shell cannot diverge from the pygame one.

Skips the door tests without pygame; the core valves are tested unconditionally.
"""

import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from rpg_game.core import daynight
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine

try:
    import pygame

    from rpg_game.presentation import overworld_buildings as ob
    from rpg_game.presentation import ui_text as T
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


_CONTENT = None


def _engine(class_id="fighter", seed=0):
    global _CONTENT
    if _CONTENT is None:
        _CONTENT = load_content()
    engine = GameEngine(content=_CONTENT, rng=random.Random(seed))
    engine.start_new_game("Hero", class_id)
    return engine


class SafetyValveTests(unittest.TestCase):
    """Neither valve may ever leave the player inside a closed night."""

    def test_resting_brings_the_morning(self):
        engine = _engine()
        engine.set_world_phase("night")
        self.assertTrue(engine.towns_closed())
        engine.player.gold = 500
        result = engine.rest(zone=1)
        self.assertEqual(result.outcome, "rested")
        self.assertEqual(engine.world_phase(), daynight.MORNING_PHASE)
        self.assertFalse(engine.towns_closed())

    def test_a_refused_rest_does_not_move_the_clock(self):
        engine = _engine()
        engine.set_world_phase("night")
        engine.player.gold = 0
        # The starting kit carries a Rest Voucher, which would make it free.
        engine.player.inventory.remove_consumable(engine.REST_VOUCHER_ID)
        before = engine.world_time()
        result = engine.rest(zone=4)          # expensive zone, no gold
        self.assertEqual(result.outcome, "not_allowed")
        self.assertEqual(engine.world_time(), before)
        self.assertTrue(engine.towns_closed())

    def test_dying_brings_the_morning(self):
        engine = _engine()
        engine.set_world_phase("night")
        engine._respawn_player()
        self.assertEqual(engine.world_phase(), daynight.MORNING_PHASE)
        self.assertFalse(engine.towns_closed())

    def test_a_full_defeat_through_combat_also_wakes_at_dawn(self):
        engine = _engine()
        engine.set_world_phase("night")
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        engine.player.hp = 0
        result = engine._defeat(enemy, [])
        self.assertEqual(result.outcome, "defeat")
        self.assertEqual(engine.world_phase(), daynight.MORNING_PHASE)

    def test_resting_by_day_is_harmless(self):
        engine = _engine()
        engine.advance_world_time(200.0)      # mid-day
        self.assertEqual(engine.world_phase(), "day")
        engine.player.gold = 500
        engine.rest(zone=1)
        self.assertEqual(engine.world_phase(), daynight.MORNING_PHASE)


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class ClosedDoorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.app = OverworldApp()
        cls.app.screen = pygame.Surface((320, 200))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _door(self, building_id, phase):
        """Open `building_id` in the starting town during `phase`; return
        (menu_opened, last_log_line)."""
        app = self.app
        app.engine.set_world_phase(phase)
        app.building_menu = None
        app.mode = "walk"
        app.event_log.clear()
        place_id = app.engine.player.respawn_place_id
        app._interact_door(place_id, building_id)
        tail = app.event_log[-1] if app.event_log else None
        text = getattr(tail, "text", tail if isinstance(tail, str) else str(tail))
        return app.building_menu is not None, text

    def test_the_shop_is_shut_at_night_with_a_message_not_an_empty_menu(self):
        opened, message = self._door("shop", "night")
        self.assertFalse(opened)
        self.assertEqual(self.app.mode, "walk")
        self.assertIn(T.BUILDING_CLOSED_FOR_NIGHT, message)

    def test_every_closed_building_is_shut_at_night(self):
        for building_id in sorted(ob.NIGHT_CLOSED_BUILDINGS):
            opened, message = self._door(building_id, "night")
            self.assertFalse(opened, building_id)
            self.assertIn(T.BUILDING_CLOSED_FOR_NIGHT, message, building_id)

    def test_the_rest_building_stays_open_at_night(self):
        # The valve itself: if this ever closes, a night in town is a dead end.
        for building_id in ("inn", "cottage"):
            self.assertNotIn(building_id, ob.NIGHT_CLOSED_BUILDINGS)
            opened, _message = self._door(building_id, "night")
            self.assertTrue(opened, building_id)
            self.assertEqual(self.app.mode, "building")

    def test_the_shrine_and_church_stay_open_at_night(self):
        for building_id in ("church", "shrine"):
            self.assertNotIn(building_id, ob.NIGHT_CLOSED_BUILDINGS)
            opened, _message = self._door(building_id, "night")
            self.assertTrue(opened, building_id)

    def test_the_notice_board_is_reachable_at_night(self):
        # B135b hangs the board inside the REST building's menu, and rest stays
        # open — so the board needs no gate of its own. Prove the whole path:
        # the door opens, and the board's own screen still opens from it.
        opened, _message = self._door("inn", "night")
        self.assertTrue(opened)
        self.app._open_notice_board()
        self.assertEqual(self.app.overlay, "notice_board")
        self.assertIsNone(self.app.building_menu)
        self.app.close_overlay()

    def test_dusk_is_a_warning_only_the_doors_are_still_open(self):
        for building_id in ("shop", "blacksmith", "town_hall"):
            opened, _message = self._door(building_id, "dusk")
            self.assertTrue(opened, f"{building_id} must not close before night")

    def test_the_shop_opens_normally_by_day(self):
        opened, _message = self._door("shop", "day")
        self.assertTrue(opened)
        self.assertEqual(self.app.mode, "building")

    def test_the_closed_set_never_swallows_a_safety_valve(self):
        for building_id, func in ob.BUILDING_FUNCTION.items():
            if func in ("rest", "relocate_respawn"):
                self.assertNotIn(building_id, ob.NIGHT_CLOSED_BUILDINGS, building_id)


if __name__ == "__main__":
    unittest.main()
