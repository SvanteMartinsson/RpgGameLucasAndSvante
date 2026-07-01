"""Menu-foundation Slice 1, Unit 2: hover timer + tooltip.

HoverTracker triggers a payload after ~1 s of dwell on one rect; draw_tooltip
renders a clamped panel. Both screens wire this in as a no-op (nothing registers
zones yet), so the assertions here exercise the primitives directly. Skips
without pygame.
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
class HoverTrackerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _tracker(self):
        t = ui.HoverTracker(delay_ms=1000)
        t.begin()
        t.add(pygame.Rect(0, 0, 50, 20), "A")
        t.add(pygame.Rect(0, 100, 50, 20), "B")
        return t

    def test_no_zone_under_mouse_stays_inactive(self):
        t = self._tracker()
        t.update((500, 500), 0)
        t.update((500, 500), 5000)
        self.assertIsNone(t.active)

    def test_dwell_must_exceed_the_delay(self):
        t = self._tracker()
        t.update((10, 10), 0)          # enter zone A
        t.update((10, 10), 999)        # still under the delay
        self.assertIsNone(t.active)
        t.update((10, 10), 1000)       # delay reached
        self.assertEqual(t.active, "A")

    def test_moving_to_another_zone_restarts_the_timer(self):
        t = self._tracker()
        t.update((10, 10), 0)
        t.update((10, 10), 1000)
        self.assertEqual(t.active, "A")
        t.update((10, 110), 1200)      # jump to zone B -> timer restarts
        self.assertIsNone(t.active)
        t.update((10, 110), 2200)      # dwell on B satisfied
        self.assertEqual(t.active, "B")

    def test_leaving_all_zones_clears_active(self):
        t = self._tracker()
        t.update((10, 10), 0)
        t.update((10, 10), 1000)
        self.assertEqual(t.active, "A")
        t.update((500, 500), 1100)
        self.assertIsNone(t.active)

    def test_add_ignores_none_payload(self):
        t = ui.HoverTracker()
        t.begin()
        t.add(pygame.Rect(0, 0, 10, 10), None)
        t.update((5, 5), 0)
        t.update((5, 5), 99999)
        self.assertIsNone(t.active)

    def test_begin_clears_previously_registered_zones(self):
        t = self._tracker()
        t.begin()                      # new frame, no zones re-added
        t.update((10, 10), 0)
        t.update((10, 10), 5000)
        self.assertIsNone(t.active)


@unittest.skipUnless(DEPS_OK, "pygame not installed")
class TooltipRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.title = pygame.font.SysFont("monospace", 15, bold=True)
        cls.body = pygame.font.SysFont("monospace", 12)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_tooltip_renders_and_stays_inside_the_screen(self):
        screen = pygame.Surface((400, 300))
        tip = ui.Tooltip("Iron Sword", ["Damage: 12", "Tier 3"],
                         "A dependable blade. Needs level 3 to equip.")
        rect = ui.draw_tooltip(screen, tip, (380, 290), self.title, self.body)
        self.assertTrue(screen.get_rect().contains(rect), "tooltip escaped the screen")
        # something actually drew (not a blank surface)
        self.assertGreater(rect.width, 0)

    def test_tooltip_handles_title_only(self):
        screen = pygame.Surface((400, 300))
        rect = ui.draw_tooltip(screen, ui.Tooltip("Just a title"), (10, 10),
                               self.title, self.body)
        self.assertTrue(screen.get_rect().contains(rect))


if __name__ == "__main__":
    unittest.main()
