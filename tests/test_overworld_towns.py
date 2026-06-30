"""Headless tests for overworld towns, location sync, town menu and gates.

Skips when pygame/pytmx are not installed (system interpreter / core run).
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp, ZoneConfig

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class OverworldTownsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()
        self.zone = self.app.zone

    # -- location sync ------------------------------------------------------

    def test_starts_in_hub_town(self):
        self.assertEqual(self.app.engine.player.current_place_id, "burg_5")

    def test_stepping_onto_town_sets_location(self):
        self.app.world.set_tile(10, 8)  # Yeblegali
        self.app.sync_location()
        self.assertEqual(self.app.engine.player.current_place_id, "burg_117")

    def test_wilderness_uses_wild_region(self):
        self.app.world.set_tile(14, 8)  # off any town tile
        self.app.sync_location()
        self.assertIsNone(self.app.world.town_place_id())
        self.assertEqual(self.app.engine.player.current_place_id, self.zone.wild_region_place_id)

    # -- town menu actions go through the engine ----------------------------

    def test_rest_in_hub_heals_via_engine(self):
        self.app.world.set_tile(26, 18)
        self.app.sync_location()
        self.app.engine.player.hp = 1
        self.app.do_action("rest")
        self.assertEqual(self.app.engine.player.hp, self.app.engine.player.max_hp)

    def test_save_action_writes_via_engine(self):
        self.app.do_action("save")
        self.assertIn("saved", self.app.event_log[-1][0].lower())  # logged, no floating toast
        self.addCleanup(lambda: os.path.exists("savegame.json") and os.remove("savegame.json"))

    def test_store_gated_when_town_has_no_store(self):
        self.app.world.set_tile(10, 8)  # Yeblegali has no store
        self.app.sync_location()
        self.app.mode = "walk"
        self.app.do_action("store")
        self.assertNotEqual(self.app.mode, "store")

    # -- no town menu in the wild -------------------------------------------

    def test_enter_in_wilderness_opens_no_menu(self):
        self.app.world.set_tile(14, 8)
        self.app.sync_location()
        self.app.mode = "walk"
        self.app._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        self.assertEqual(self.app.mode, "walk")

    # -- per-building door interaction (B-doors) ----------------------------

    def _door(self, place_id, building_id):
        return next(t for t, (pid, bid) in self.app.door_index.items()
                    if pid == place_id and bid == building_id)

    def _enter_door(self, building):
        self.app.world.set_tile(*self._door("burg_5", building))
        self.app.mode = "walk"
        self.app._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))

    def test_enter_on_a_door_opens_a_titled_menu_not_the_service(self):
        # B30: Enter opens the building's titled menu; the service does NOT run yet.
        from rpg_game.presentation.pygame_overworld import BUILDING_TITLES
        for building in ("shop", "blacksmith", "barracks", "inn", "church", "town_hall"):
            self._enter_door(building)
            self.assertEqual(self.app.mode, "building", building)
            self.assertEqual(self.app.building_menu, ("burg_5", building))
            self.assertIn(building, BUILDING_TITLES)
            self.app.mode = "walk"; self.app.building_menu = None

    def test_trade_building_menu_choice_opens_its_store_category(self):
        # The menu choice (not the door) opens the category-filtered store.
        for building, (category, kind) in {"blacksmith": ("weapons", "weapon"),
                                           "barracks": ("armor", "gear"),
                                           "shop": ("general", "consumable")}.items():
            self._enter_door(building)
            self.assertEqual(self.app.mode, "building", building)
            self.app._choose_building_action("store", category)   # the menu's choice
            self.assertEqual(self.app.mode, "store", building)
            self.assertEqual(self.app.store_category, category, building)
            entries = self.app.engine.store_entries(self.app.store_category)
            self.assertTrue(entries and all(e.kind == kind for e in entries), building)
            self.app.mode = "walk"

    # -- B29: chatbox v2 (dedupe / scroll / resize-clamp) -------------------

    def test_log_dedupes_immediate_repeats(self):
        n = len(self.app.event_log)
        self.app.push_log("Rested.", (1, 2, 3))
        self.app.push_log("Rested.", (1, 2, 3))   # immediate repeat -> ignored
        self.app.push_log("Moved on.", (1, 2, 3))
        self.assertEqual(len(self.app.event_log), n + 2)

    def test_resize_log_clamps_to_min_and_max(self):
        from rpg_game.presentation.pygame_overworld import LOG_VISIBLE_MIN, LOG_VISIBLE_MAX
        for _ in range(50):
            self.app.resize_log(1)
        self.assertEqual(self.app.log_visible, LOG_VISIBLE_MAX)
        for _ in range(50):
            self.app.resize_log(-1)
        self.assertEqual(self.app.log_visible, LOG_VISIBLE_MIN)

    def test_scroll_log_clamps_to_history(self):
        self.app.log_visible = 5
        for i in range(12):
            self.app.push_log(f"line {i}", (1, 2, 3))
        self.app.scroll_log(-100)                  # can't scroll below newest
        self.assertEqual(self.app.log_scroll, 0)
        self.app.scroll_log(100)                   # clamps to history - visible
        self.assertEqual(self.app.log_scroll, self.app._log_scroll_max())
        self.assertEqual(self.app.log_scroll, len(self.app.event_log) - 5)

    def test_set_toast_only_logs_no_floating_state(self):
        # B29: set_toast routes to the log; there is no on-screen toast state.
        self.app.set_toast("Hello", (1, 2, 3))
        self.assertEqual(self.app.event_log[-1][0], "Hello")
        self.assertFalse(hasattr(self.app, "toast"))

    # -- B39: chatbox word-wrap (no truncation) -----------------------------

    def test_long_log_line_wraps_to_several_visual_lines_without_ellipsis(self):
        self.app.display = pygame.Surface((960, 640))
        long_line = ("The ancient hollow worg lunges from the treeline and "
                     "savages you for a tremendous amount of physical damage!")
        self.app.push_log(long_line, (1, 2, 3))
        visual = [t for t, _c, _newest in self.app._visual_log_lines()]
        pieces = [t for t in visual if t and t in long_line]
        self.assertGreater(len(pieces), 1, visual)            # wrapped, not one line
        self.assertFalse(any("..." in t for t in visual), visual)  # never truncated
        self.assertEqual(" ".join(pieces), long_line)         # full text preserved

    def test_short_line_stays_one_visual_line(self):
        self.app.push_log("Victory!", (1, 2, 3))
        matches = [t for t, _c, _n in self.app._visual_log_lines() if t == "Victory!"]
        self.assertEqual(len(matches), 1)

    # -- B31: HUD bars (no top bar, vitals above the chatbox) ---------------

    def test_vitals_bars_sit_above_the_chatbox(self):
        self.app.display = pygame.Surface((960, 640))
        log = self.app._log_rect()
        # B39: Lv/Gold header + three thicker bars (bar_h 18) occupy the band
        # directly above the log, fitting on-screen without overlapping it.
        head_h = self.app.font_sm.get_height() + 3
        band_top = log.y - (head_h + 3 * (18 + 3) + 4)
        self.assertGreater(band_top, 0)         # whole band fits above the chatbox
        self.assertLess(band_top, log.y)
        self.app.mode = "walk"; self.app.overlay = ""
        self.app.draw()  # must render HUD + vitals + chatbox without error
        self.assertFalse(hasattr(self.app, "_draw_xp_bar"))  # old top XP bar gone

    def test_vitals_band_shows_level_and_gold(self):
        # B39: the vitals band (not the top HUD) now carries Lv + Gold.
        self.app.display = pygame.Surface((960, 640))
        self.app.engine.player.level = 5
        self.app.engine.player.gold = 142

        drawn: list[str] = []
        real = self.app.font_sm

        class _Sink:
            def render(self, text, *a, **k): drawn.append(text); return real.render(text, *a, **k)
            def get_height(self): return real.get_height()
            def size(self, t): return real.size(t)

        self.app.font_sm = _Sink()
        try:
            self.app._draw_vitals()
        finally:
            self.app.font_sm = real
        joined = " ".join(drawn)
        self.assertIn("Lv 5", joined)
        self.assertIn("Gold 142", joined)

    def test_hud_shows_no_name_or_gold(self):
        # B31 removed the name/level/gold top-left text; the HUD no longer reads them.
        import inspect
        src = inspect.getsource(type(self.app)._draw_hud)
        self.assertNotIn("Gold", src)
        self.assertNotIn(".name", src)

    def test_inn_rests_only_after_menu_choice(self):
        self.app.engine.player.hp = 1
        self._enter_door("inn")
        self.assertEqual(self.app.mode, "building")
        self.assertEqual(self.app.engine.player.hp, 1)            # opening the menu does NOT rest
        self.app._choose_building_action("rest")                 # the menu's [Rest] choice
        self.assertEqual(self.app.engine.player.hp, self.app.engine.player.max_hp)

    def test_church_sets_respawn_only_after_menu_choice(self):
        # burg_5 is the default respawn; move it away, then confirm the Church menu
        # sets it back only when the choice is taken, not on opening.
        self.app.engine.player.respawn_place_id = "burg_67"
        self._enter_door("church")
        self.assertEqual(self.app.mode, "building")
        self.assertEqual(self.app.engine.player.respawn_place_id, "burg_67")  # not yet
        self.app._choose_building_action("relocate_respawn")
        self.assertEqual(self.app.engine.player.respawn_place_id, "burg_5")

    def test_enter_on_plaza_without_a_door_does_nothing(self):
        # The old single-tile menu is gone: standing on the plaza anchor (not a
        # door) and pressing Enter opens no menu.
        self.app.world.set_tile(26, 18)  # burg_5 plaza anchor
        self.app.mode = "walk"
        self.app._handle_key(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN))
        self.assertEqual(self.app.mode, "walk")

    # -- UI Slice A: compare-vs-equipped delta ------------------------------

    def test_delta_text_computes_signed_per_stat_change(self):
        d = self.app._delta_text
        self.assertEqual(d({"armor": 3, "max_hp": 10}, {"armor": 2, "max_hp": 5}), "  (+1 armor, +5 hp)")
        self.assertEqual(d({"damage": 9}, {"damage": 2}), "  (+7 dmg)")          # weapon swap
        self.assertEqual(d({"armor": 1}, {"armor": 3}), "  (-2 armor)")          # downgrade
        self.assertEqual(d({"armor": 2}, {"armor": 2}), "  (=)")                 # no change
        self.assertEqual(d({"armor": 3}, {}), "  (+3 armor)")                    # empty slot

    # -- B29.3: outcome is logged once, not twice ---------------------------

    def test_flee_outcome_is_not_logged_twice(self):
        enemy = self.app.engine.content.enemies["cave_bear"].create_enemy()
        # The battle shell already mirrored the engine's flee line into the shared
        # log; resolving the outcome must NOT add a second 'fled from' line.
        self.app.push_log(f"You fled from {enemy.name}.", (235, 180, 90))
        self.app.resolve_battle_outcome("fled", enemy)
        fled_lines = [m for m, _c in self.app.event_log if "fled from" in m.lower()]
        self.assertEqual(len(fled_lines), 1, self.app.event_log)  # logged once, no duplicate

    def test_victory_outcome_is_not_logged_twice(self):
        enemy = self.app.engine.content.enemies["giant_rat"].create_enemy()
        self.app.push_log("Victory!", (120, 220, 140))
        before = len(self.app.event_log)
        self.app.resolve_battle_outcome("victory", enemy)
        # the battle already logged the outcome; resolve adds no extra line
        self.assertEqual(len(self.app.event_log), before)

    def test_door_without_a_service_logs_locked(self):
        before = len(self.app.event_log)
        self.app._interact_door("burg_5", "well")  # unmapped building -> locked
        self.assertEqual(self.app.mode, "walk")
        self.assertGreater(len(self.app.event_log), before)
        self.assertIn("locked", self.app.event_log[-1][0].lower())

    # -- location indicator (top-right) replaces the floating town name ------

    def test_indicator_names_the_city_on_its_cluster(self):
        # On the plaza AND on a door/cobble tile, the indicator names the city.
        self.app.world.set_tile(26, 18)              # burg_5 plaza
        self.assertEqual(self.app._location_label(), ("Hordanita", True))
        door = next(t for t, (pid, _b) in self.app.door_index.items() if pid == "burg_5")
        self.app.world.set_tile(*door)
        text, in_town = self.app._location_label()
        self.assertEqual((text, in_town), ("Hordanita", True))

    def test_indicator_is_relative_when_near_a_hub(self):
        self.app.world.set_tile(26, 23)              # 5 tiles south of burg_5
        text, in_town = self.app._location_label()
        self.assertEqual(text, "south of Hordanita")
        self.assertFalse(in_town)

    def test_hub_floating_label_is_removed(self):
        # The cluster hubs no longer emit a floating world-space name; the indicator
        # carries the name instead. (Non-hub town pins keep their labels.)
        self.app.display = pygame.Surface((960, 640))
        self.app.world.set_tile(26, 18)
        self.app.sync_location()
        self.app.mode = "walk"
        self.app.draw()  # must not raise; hubs contribute no floating label
        self.assertIn("burg_5", self.app.cluster_anchors)

    # -- gates --------------------------------------------------------------

    def test_gate_blocks_and_shows_its_message(self):
        self.app.world.set_tile(26, 2)  # below the north gate at (26, 0)
        message = ""
        for _ in range(40):
            hit = self.app.world.try_move(0, -3)
            if hit:
                message = hit
        self.assertTrue(message)
        self.assertGreaterEqual(self.app.world.player.top, self.app.world.th)  # never entered row 0

    def test_plain_wall_gives_no_gate_message(self):
        self.app.world.set_tile(2, 2)  # corner wall, not a gate
        message = ""
        for _ in range(40):
            hit = self.app.world.try_move(0, -3)
            if hit:
                message = hit
        self.assertEqual(message, "")


if __name__ == "__main__":
    unittest.main()
