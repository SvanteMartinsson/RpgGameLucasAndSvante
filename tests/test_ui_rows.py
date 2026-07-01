"""Menu-foundation Slice 1, Unit 3: the shared list/row helper.

draw_menu_row renders one menu line — label (left), optional right-aligned value
(cost), a dim/restricted look — and registers the row for tooltip hover. This is
the reusable piece the inventory/shop/character apply-slices adopt. Skips without
pygame.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation import ui

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame not installed")
class MenuRowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.font = pygame.font.SysFont("monospace", 14)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _style(self):
        return ui.RowStyle(font=self.font)

    def test_row_defaults(self):
        row = ui.MenuRow("Iron Sword")
        self.assertEqual((row.value, row.enabled, row.restricted, row.tooltip, row.on_click),
                         ("", True, False, None, None))

    def test_draw_returns_rect_and_registers_hover_with_tooltip(self):
        screen = pygame.Surface((300, 60))
        rect = pygame.Rect(10, 10, 260, 36)
        tip = ui.Tooltip("Iron Sword", ["Damage: 12"], "A dependable blade.")
        row = ui.MenuRow("Iron Sword", value="45g", tooltip=tip)
        hover = ui.HoverTracker()
        hover.begin()
        out = ui.draw_menu_row(screen, rect, row, self._style(), mouse=rect.center, hover=hover)
        self.assertEqual(out, rect)
        hover.update(rect.center, 0)
        hover.update(rect.center, ui.HOVER_DELAY_MS)
        self.assertIs(hover.active, tip)

    def test_no_tooltip_registers_no_hover_zone(self):
        screen = pygame.Surface((300, 60))
        rect = pygame.Rect(10, 10, 260, 36)
        row = ui.MenuRow("Plain", value="1g")            # tooltip=None
        hover = ui.HoverTracker()
        hover.begin()
        ui.draw_menu_row(screen, rect, row, self._style(), mouse=rect.center, hover=hover)
        hover.update(rect.center, 0)
        hover.update(rect.center, 10 * ui.HOVER_DELAY_MS)
        self.assertIsNone(hover.active)

    def test_disabled_row_still_registers_tooltip(self):
        # a level-locked / unaffordable row should still explain itself on hover
        screen = pygame.Surface((300, 60))
        rect = pygame.Rect(0, 0, 260, 36)
        tip = ui.Tooltip("Locked", body="Needs level 5.")
        row = ui.MenuRow("Great Axe", value="200g", enabled=False, tooltip=tip)
        hover = ui.HoverTracker()
        hover.begin()
        ui.draw_menu_row(screen, rect, row, self._style(), mouse=rect.center, hover=hover)
        hover.update(rect.center, 0)
        hover.update(rect.center, ui.HOVER_DELAY_MS)
        self.assertIs(hover.active, tip)

    def test_right_aligned_value_is_drawn_on_the_right(self):
        screen = pygame.Surface((300, 60))
        screen.fill((0, 0, 0))
        rect = pygame.Rect(0, 10, 260, 36)
        row = ui.MenuRow("A", value="999g")
        style = ui.RowStyle(font=self.font, bg=(0, 0, 0), edge=(0, 0, 0),
                            value=(255, 0, 0))
        ui.draw_menu_row(screen, rect, row, style)
        # some red value pixel lands in the right third of the row
        right = pygame.Rect(rect.right - 90, rect.y, 90, rect.height)
        found = any(screen.get_at((x, y))[0] > 120
                    for x in range(right.left, right.right, 2)
                    for y in range(right.top, right.bottom, 2))
        self.assertTrue(found, "right-aligned value not drawn on the right")

    def test_label_color_paints_the_name_and_survives_dim(self):
        from rpg_game.presentation import chatlog
        legendary = chatlog.rarity_color("legendary")
        screen = pygame.Surface((300, 60))
        screen.fill((0, 0, 0))
        rect = pygame.Rect(0, 10, 260, 36)
        row = ui.MenuRow("Dragon Blade", value="999g", enabled=False, label_color=legendary)
        style = ui.RowStyle(font=self.font, bg=(0, 0, 0), edge=(0, 0, 0),
                            disabled=(0, 0, 0))
        ui.draw_menu_row(screen, rect, row, style)
        # the NAME is drawn in the rarity colour even though the row is disabled
        found = any(tuple(screen.get_at((x, y))[:3]) == legendary
                    for x in range(rect.x, rect.x + 140)
                    for y in range(rect.top, rect.bottom))
        self.assertTrue(found, "rarity colour not applied to the item name")

    def test_no_label_color_uses_style_text(self):
        row = ui.MenuRow("Plain")
        self.assertIsNone(row.label_color)   # default: fall back to style.text

    def test_fit_callback_is_applied_to_the_label(self):
        screen = pygame.Surface((300, 60))
        rect = pygame.Rect(0, 0, 120, 36)
        calls = []

        def fit(text, max_w, font):
            calls.append((text, max_w))
            return text[:3]

        row = ui.MenuRow("A Very Long Label", value="9g")
        ui.draw_menu_row(screen, rect, row, self._style(), fit=fit)
        self.assertEqual(len(calls), 1)
        # the label was fitted against the width LEFT of the value, not the full row
        self.assertLess(calls[0][1], rect.width)


if __name__ == "__main__":
    unittest.main()
