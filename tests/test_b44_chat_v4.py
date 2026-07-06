"""B44 + B16.1: chat log v4 — segment colours, red vs-you damage, channels/tabs.

Locks: ChannelText stays str-compatible, Segments wrap across colours, push
dedupe covers both payloads, the battle colourizer (damage against the PLAYER
red / heals green / enemy-directed damage plain), the one-row loot and reward
segments, the chest gold+loot row, and the overworld [All][Combat] tabs.
Skips without pygame.
"""

import collections
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.core import combat
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import chatlog
    from rpg_game.presentation import ui_text as T
    from rpg_game.presentation.pygame_battle import BattleApp
    from rpg_game.presentation.pygame_overworld import OverworldApp
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class PayloadModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.font = pygame.font.SysFont("menlo,consolas,monospace", 13)

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_channel_text_is_still_a_str(self):
        line = chatlog.ChannelText("You fled.", chatlog.CHANNEL_COMBAT)
        self.assertEqual(line, "You fled.")
        self.assertIn("fled", line.lower())
        self.assertEqual(chatlog.channel_of(line), "combat")
        self.assertEqual(chatlog.channel_of("plain"), "world")

    def test_push_tags_the_channel_and_still_dedupes(self):
        log = collections.deque()
        self.assertTrue(chatlog.push(log, "hit", channel=chatlog.CHANNEL_COMBAT))
        self.assertFalse(chatlog.push(log, "hit", channel=chatlog.CHANNEL_COMBAT))
        self.assertEqual(len(log), 1)
        self.assertEqual(chatlog.channel_of(log[-1][0]), "combat")

    def test_push_rich_dedupes_and_exposes_plain_text(self):
        log = collections.deque()
        parts = [("Loot: ", (1, 1, 1)), ("Rimebrand", (2, 2, 2))]
        self.assertTrue(chatlog.push_rich(log, parts))
        self.assertFalse(chatlog.push_rich(log, parts))
        self.assertEqual(chatlog.plain(log[-1][0]), "Loot: Rimebrand")

    def test_segments_wrap_preserves_each_words_colour(self):
        red, white = (200, 0, 0), (250, 250, 250)
        parts = [("a long opening piece of text ", white),
                 ("then a red tail that must wrap onward", red)]
        lines = chatlog.wrap_segments(parts, 120, self.font)
        self.assertGreater(len(lines), 1)
        colors_seen = {color for chunks in lines for _t, color in chunks}
        self.assertEqual(colors_seen, {red, white})
        joined = " ".join(" ".join(t for t, _c in chunks) for chunks in lines)
        self.assertEqual(" ".join(joined.split()),
                         "a long opening piece of text then a red tail that must wrap onward")

    def test_visual_lines_filters_by_channel(self):
        log = collections.deque()
        chatlog.push(log, "world line")
        chatlog.push(log, "combat line", channel=chatlog.CHANNEL_COMBAT)
        all_lines = chatlog.visual_lines(log, 400, self.font)
        combat_only = chatlog.visual_lines(log, 400, self.font,
                                           channel=chatlog.CHANNEL_COMBAT)
        self.assertEqual(len(all_lines), 2)
        self.assertEqual([t for t, _c, _n in combat_only], ["combat line"])

    def test_draw_renders_rich_lines_without_crashing(self):
        log = collections.deque()
        chatlog.push_rich(log, [("+5 XP", chatlog.XP), ("  +7 gold", chatlog.GOLD)])
        screen = pygame.Surface((400, 200))
        scroll = chatlog.draw(screen, pygame.Rect(0, 0, 380, 180), log, self.font,
                              visible=8, scroll=0, interactive=False,
                              edge=(80, 80, 80), accent=(120, 170, 255))
        self.assertEqual(scroll, 0)


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class BattleColourizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _battle(self):
        engine = GameEngine(rng=random.Random(0))
        engine.start_new_game("Hero", "fighter")
        enemy = engine.content.enemies["cave_bear"].create_enemy()
        return BattleApp(engine=engine, enemy=enemy, standalone=False,
                         event_log=collections.deque())

    def test_damage_against_the_player_renders_red_segments(self):
        battle = self._battle()
        battle.event_log.clear()
        battle._push_combat_event("Cave Bear's Maul dealt 12 physical to Hero.")
        payload = battle.event_log[-1][0]
        self.assertIsInstance(payload, chatlog.Segments)
        self.assertEqual(dict(payload)["12 physical"], chatlog.DAMAGE)
        self.assertEqual(chatlog.plain(payload),
                         "Cave Bear's Maul dealt 12 physical to Hero.")

    def test_damage_against_the_enemy_stays_plain(self):
        battle = self._battle()
        battle.event_log.clear()
        battle._push_combat_event("Hero's Attack dealt 9 physical to Cave Bear.")
        payload = battle.event_log[-1][0]
        self.assertNotIsInstance(payload, chatlog.Segments)

    def test_heal_lines_render_green(self):
        battle = self._battle()
        battle.event_log.clear()
        battle._push_combat_event("Undead Priest healed 18 HP.")
        self.assertEqual(battle.event_log[-1][1], chatlog.HEAL)

    def test_every_battle_line_is_combat_channel(self):
        battle = self._battle()
        battle.event_log.clear()
        battle.push_log("anything")
        battle.push_rich([("a", (1, 1, 1))])
        for payload, _color in battle.event_log:
            self.assertEqual(chatlog.channel_of(payload), chatlog.CHANNEL_COMBAT)


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class OverworldTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.app = OverworldApp()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app.event_log.clear()
        self.app.log_tab = "all"
        self.app.log_scroll = 0

    def test_combat_tab_filters_world_lines(self):
        chatlog.push(self.app.event_log, "You travel east.")
        chatlog.push(self.app.event_log, "You take a hit.",
                     channel=chatlog.CHANNEL_COMBAT)
        self.app._set_log_tab("combat")
        lines = chatlog.visual_lines(self.app.event_log, 400, self.app.font_sm,
                                     channel=self.app._log_channel())
        self.assertEqual([t for t, _c, _n in lines], ["You take a hit."])
        self.app._set_log_tab("all")
        lines = chatlog.visual_lines(self.app.event_log, 400, self.app.font_sm,
                                     channel=self.app._log_channel())
        self.assertEqual(len(lines), 2)

    def test_draw_log_registers_the_tab_chips(self):
        self.app.screen = pygame.Surface((1024, 680))
        self.app.buttons = []
        self.app.hover.begin()
        self.app._draw_log()
        self.assertGreaterEqual(len(self.app.buttons), 2)   # All + Combat chips
        self.app.buttons[-1].on_click()                     # the Combat chip
        self.assertEqual(self.app.log_tab, "combat")
        self.assertEqual(self.app.log_scroll, 0)

    def test_switching_tab_resets_scroll(self):
        self.app.log_scroll = 7
        self.app._set_log_tab("combat")
        self.assertEqual(self.app.log_scroll, 0)


if __name__ == "__main__":
    unittest.main()
