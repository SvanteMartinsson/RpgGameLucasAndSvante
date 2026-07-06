"""B57: ONE text wrap. Locks the superset behaviours (word-wrap, character-break
of over-long words, ellipsis fit) and that chatlog + the overworld delegate to
the shared ui implementation. Skips without pygame."""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation import chatlog, ui
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


@unittest.skipUnless(HAVE_PYGAME, "pygame not installed")
class WrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.font = pygame.font.Font(None, 18)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_word_wrap_keeps_words_within_width(self):
        lines = ui.wrap("the quick brown fox jumps over the lazy dog", self.font, 90)
        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertLessEqual(self.font.size(line)[0], 90)
        self.assertEqual(" ".join(lines), "the quick brown fox jumps over the lazy dog")

    def test_over_long_word_breaks_by_character_without_empty_fragments(self):
        lines = ui.wrap("w" * 80, self.font, 60)
        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertTrue(line)                                   # no empty fragments
            self.assertLessEqual(self.font.size(line)[0], 60)
        self.assertEqual("".join(lines), "w" * 80)                  # nothing lost

    def test_zero_width_and_empty_text_are_safe(self):
        self.assertEqual(ui.wrap("hello", self.font, 0), ["hello"])
        self.assertEqual(ui.wrap("", self.font, 100), [""])

    def test_fit_returns_text_unchanged_when_it_fits(self):
        self.assertEqual(ui.fit("hi", self.font, 500), "hi")

    def test_fit_truncates_with_ellipsis_inside_the_width(self):
        fitted = ui.fit("a very long label that cannot possibly fit", self.font, 80)
        self.assertTrue(fitted.endswith("..."))
        self.assertLessEqual(self.font.size(fitted)[0], 80)

    def test_chatlog_delegates_to_the_shared_wrap(self):
        text = "the quick brown fox jumps over the lazy dog " + "x" * 60
        self.assertEqual(chatlog.wrap_lines(text, 90, self.font), ui.wrap(text, self.font, 90))

    def test_overworld_delegates_to_the_shared_wrap_and_fit(self):
        from rpg_game.presentation.pygame_overworld import OverworldApp
        app = OverworldApp()
        text = "a fairly long line of ui text that will need wrapping " + "y" * 50
        self.assertEqual(app._wrapped_lines_pixels(text, 90, self.font),
                         ui.wrap(text, self.font, 90))
        self.assertEqual(app._fit_text(text, 90, self.font), ui.fit(text, self.font, 90))


if __name__ == "__main__":
    unittest.main()
