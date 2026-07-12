"""B106: menu text style rules as shared ui helpers.

Locks: (a) no parenthetical help text in button labels — hotkeys are badge
chips, costs right-aligned values; (b) settings say "Combat animations" and
render a Controls table instead of the Keys prose (no hotkey suffix on rows);
(c) truncated labels always carry their full text as a tooltip; (d) talent
status prefixes render as compact markers, not [LEARNED]-style text. Shell
tests skip without pygame/pytmx.
"""

import os
import re
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import settings as user_settings
    from rpg_game.presentation import ui
    from rpg_game.presentation import ui_text as T
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False

# Parenthetical help text: "(Esc)", "(20g)", "(free)", "(1 point)", "(need ...)".
# Data-ish parens like a weapon's "(1h sword)" type are allowed; the guard
# targets the known help patterns so labels can still carry item data.
_HELP_PAREN = re.compile(r"\((Esc|Enter|F11|[A-Z]|free|here|\d+ ?g(old)?|\d+ point[s]?|need[^)]*)\)")


def _labels(app):
    return [b.label for b in app.buttons]


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class TextStyleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1280, 800))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "mage")
        self.app = OverworldApp(engine=engine)

    def _assert_no_help_parens(self, surface):
        self.app.draw()
        for label in _labels(self.app):
            self.assertIsNone(_HELP_PAREN.search(label),
                              f"{surface}: help-paren in label {label!r}")

    def test_back_button_is_label_plus_badge(self):
        self.app.open_overlay("system")
        self.app.draw()
        back = next(b for b in self.app.buttons if b.label == "Back")
        self.assertEqual(back.hotkey, "Esc")    # badge column, not "(Esc)"

    def test_no_help_parens_on_overlays(self):
        for overlay in ("system", "settings", "character", "inventory",
                        "skills_talents"):
            self.app.open_overlay(overlay)
            self._assert_no_help_parens(overlay)

    def test_no_help_parens_on_menu_modes(self):
        events = list(self.app.engine.content.travel_events)
        if events:
            self.app.mode = "travel_event"
            self.app.active_event = events[0]
            self._assert_no_help_parens("travel_event")

    def test_event_cost_is_a_right_aligned_value(self):
        priced = next((e for e in self.app.engine.content.travel_events
                       if any(c.cost_gold for c in e.choices)), None)
        if priced is None:
            self.skipTest("no priced travel event in content")
        self.app.mode = "travel_event"
        self.app.active_event = priced
        self.app.draw()
        values = [b.value for b in self.app.buttons if b.value]
        self.assertTrue(any(v.endswith("g") for v in values), values)

    def test_settings_rows_renamed_and_unsuffixed(self):
        labels = [option["label"] for option in user_settings.OPTIONS]
        self.assertIn("Combat animations", labels)
        self.assertNotIn("Combat FX", labels)
        self.app.open_overlay("settings")
        self.app.draw()
        for label in _labels(self.app):
            self.assertNotIn("(F11)", label)
            self.assertNotIn("(N)", label)

    def test_controls_table_data_covers_the_old_keys_prose(self):
        actions = {action for action, _ in T.CONTROLS}
        for expected in ("Move", "Interact", "Fullscreen", "Menu / back"):
            self.assertIn(expected, actions)

    def test_talent_rows_use_markers_not_bracket_prefixes(self):
        self.app.open_overlay("skills_talents")
        self.app.draw()
        for label in _labels(self.app):
            self.assertNotIn("[LEARNED]", label)
            self.assertNotIn("[LOCKED]", label)
            self.assertNotIn("[CAN LEARN]", label)
        glyphs = {g for g, _ in ui.STATUS_MARKERS.values()}
        self.assertTrue(any(any(g in l for g in glyphs) for l in _labels(self.app)))

    def test_truncated_row_label_gets_full_text_tooltip(self):
        font = pygame.font.SysFont("menlo,consolas,monospace", 16)
        style = ui.RowStyle(font=font)
        hover = ui.HoverTracker()
        hover.begin()
        screen = pygame.Surface((200, 40))
        long_label = "An extremely long menu row label that cannot possibly fit"
        row = ui.MenuRow(label=long_label)
        ui.draw_menu_row(screen, pygame.Rect(0, 0, 120, 28), row, style,
                         fit=lambda t, w, f: ui.fit(t, f, w), hover=hover)
        # The registered tooltip payload carries the FULL label.
        payloads = [payload for _, payload in hover._zones]
        self.assertTrue(any(getattr(p, "title", "") == long_label for p in payloads),
                        "truncated label did not register a full-text tooltip")

    def test_status_marker_mapping(self):
        self.assertEqual(ui.status_marker("[LEARNED]")[1], "good")
        self.assertEqual(ui.status_marker("[CAN LEARN]")[1], "accent")
        self.assertEqual(ui.status_marker("[LOCKED]")[1], "dim")


if __name__ == "__main__":
    unittest.main()
