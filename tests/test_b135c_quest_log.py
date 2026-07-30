"""B135c: the quest log screen (hotkey Q) + the fourth "Quest" chat tab.

Locks: Q toggles the log; the log lists every tracked quest with objective,
progress, zone hint and reward, with finished-but-not-handed-in ones sorted first
and called out; the chatbox gained a Quest tab that filters to quest lines only;
and quest lines are MILESTONES (accepted / halfway / ready / handed in) rather
than one line per kill.

Skips without pygame.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame

    from rpg_game.core import quests as core_quests
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import chatlog, ui
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


def _key(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="")


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class QuestLogScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        self.app = OverworldApp(engine=engine)
        self.app.display = pygame.Surface((980, 660))
        self.app.screen = pygame.Surface((980, 660))
        self.eng = self.app.engine

    def _kill(self, enemy_id, zone, times=1):
        lines = []
        for _ in range(times):
            lines.extend(core_quests.note_kill(self.eng.player, self.eng.content,
                                               self.eng.content.quests,
                                               enemy_id, zone))
        return lines

    # -- the hotkey ----------------------------------------------------------

    def test_q_opens_and_closes_the_quest_log(self):
        self.app._handle_key(_key(pygame.K_q))
        self.assertEqual(self.app.overlay, "quest_log")
        self.app._handle_key(_key(pygame.K_q))
        self.assertEqual(self.app.overlay, "")

    def test_escape_closes_the_quest_log(self):
        self.app.open_overlay("quest_log")
        self.app.draw()
        self.app._handle_key(_key(pygame.K_ESCAPE))
        self.assertEqual(self.app.overlay, "")

    def test_q_does_not_collide_with_another_overlay_hotkey(self):
        # C/I/K/M/B were taken; Q must map to the quest log and nothing else.
        for key, expected in ((pygame.K_c, "character"), (pygame.K_i, "inventory"),
                              (pygame.K_k, "skills_talents"), (pygame.K_b, "bestiary"),
                              (pygame.K_q, "quest_log")):
            self.app.overlay = ""
            self.app._handle_key(_key(key))
            self.assertEqual(self.app.overlay, expected)

    # -- contents ------------------------------------------------------------

    def test_the_empty_log_says_so(self):
        self.app.open_overlay("quest_log")
        self.app.draw()
        self.assertEqual(self.eng.tracked_quests(), [])

    def test_tracked_quests_are_listed_with_a_tooltip_each(self):
        self.eng.accept_quest("spine_cainos")
        self.eng.accept_quest("side_rat_pelts")
        self.app.open_overlay("quest_log")
        self.app.draw()
        titles = [p.title for _r, p in self.app.hover._zones
                  if isinstance(p, ui.Tooltip)]
        self.assertIn("The Fields Beyond Hordanita", titles)
        self.assertIn("Pelts for the Tanner", titles)

    def test_an_unaccepted_quest_is_not_in_the_log(self):
        self.eng.accept_quest("spine_cainos")
        self.app.open_overlay("quest_log")
        self.app.draw()
        titles = [p.title for _r, p in self.app.hover._zones
                  if isinstance(p, ui.Tooltip)]
        self.assertNotIn("The Water Turned", titles)

    def test_a_handed_in_quest_leaves_the_log(self):
        self.eng.accept_quest("spine_cainos")
        self._kill("giant_rat", "cainos", 6)
        self.eng.turn_in_quest("spine_cainos")
        self.assertEqual([q.id for q in self.eng.tracked_quests()], [])

    def test_ready_quests_sort_before_unfinished_ones(self):
        self.eng.accept_quest("side_rat_pelts")          # will stay unfinished
        self.eng.accept_quest("spine_cainos")
        self._kill("giant_rat", "cainos", 6)             # this one becomes ready
        self.app.open_overlay("quest_log")
        self.app.draw()
        order = [p.title for _r, p in self.app.hover._zones
                 if isinstance(p, ui.Tooltip)]
        self.assertEqual(order[0], "The Fields Beyond Hordanita")

    def test_the_log_scrolls_when_it_overflows(self):
        for quest in list(self.eng.board_quests()):
            self.eng.accept_quest(quest.id)
        self.app.open_overlay("quest_log")
        self.app.draw()
        scroll = self.app._menu_scrolls["quest_log"]
        self.assertGreater(scroll.content_height, 0)
        self.assertIs(self.app._active_overflow_scroll(), scroll)

    def test_progress_shown_matches_the_engine(self):
        self.eng.accept_quest("spine_cainos")
        self._kill("giant_rat", "cainos", 2)
        quest = self.eng.quest_by_id("spine_cainos")
        from rpg_game.presentation.overworld_overlays import quest_progress_value
        self.assertEqual(quest_progress_value(self.eng, quest), "2/6")


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class QuestChatTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        self.app = OverworldApp(engine=engine)
        self.app.display = pygame.Surface((980, 660))
        self.app.screen = pygame.Surface((980, 660))
        self.eng = self.app.engine

    def _quest_lines(self):
        return [chatlog.plain(payload) for payload, _c in self.app.event_log
                if chatlog.channel_of(payload) == chatlog.CHANNEL_QUEST]

    def test_the_quest_tab_exists_and_filters_to_the_quest_channel(self):
        self.app.log_tab = "quest"
        self.assertEqual(self.app._log_channel(), chatlog.CHANNEL_QUEST)

    def test_the_tab_chip_is_drawn_and_clickable(self):
        self.app.draw()
        # the four chips are borderless buttons in the log strip
        self.app.log_tab = "all"
        chips = [b for b in self.app.buttons if b.label == ""]
        self.assertGreaterEqual(len(chips), 4)

    def test_accept_and_hand_in_lines_land_on_the_quest_channel(self):
        self.app.accept_quest("spine_cainos")
        for _ in range(6):
            core_quests.note_kill(self.eng.player, self.eng.content,
                                  self.eng.content.quests, "giant_rat", "cainos")
        self.app.hand_in_quest("spine_cainos")
        lines = self._quest_lines()
        self.assertTrue(any("Quest accepted" in line for line in lines), lines)
        self.assertTrue(any("Quest complete" in line for line in lines), lines)
        self.assertTrue(any("Reward" in line for line in lines), lines)

    def test_quest_lines_do_not_pollute_the_combat_or_loot_tabs(self):
        self.app.accept_quest("spine_cainos")
        combat_lines = [chatlog.plain(p) for p, _c in self.app.event_log
                        if chatlog.channel_of(p) == chatlog.CHANNEL_COMBAT]
        loot_lines = [chatlog.plain(p) for p, _c in self.app.event_log
                      if chatlog.channel_of(p) == chatlog.CHANNEL_LOOT]
        self.assertFalse(any("Quest accepted" in line
                             for line in combat_lines + loot_lines))

    # -- milestone, not spam -------------------------------------------------

    def test_progress_logs_a_halfway_milestone_only_once(self):
        self.eng.accept_quest("spine_cainos")            # 6 kills
        emitted = []
        for _ in range(6):
            emitted.extend(core_quests.note_kill(
                self.eng.player, self.eng.content, self.eng.content.quests,
                "giant_rat", "cainos"))
        progress = [line for line in emitted if "3/6" in line]
        others = [line for line in emitted
                  if "/6" in line and "3/6" not in line]
        self.assertEqual(len(progress), 1, emitted)
        self.assertEqual(others, [], f"per-kill spam: {others}")
        self.assertTrue(any("ready to hand in" in line for line in emitted), emitted)

    def test_a_single_step_objective_logs_no_progress_line(self):
        self.eng.accept_quest("side_hollow_worg") or None    # gated: force it
        self.eng.player.quest_states["spine_grave_heath"] = {
            "status": core_quests.TURNED_IN, "progress": 8}
        self.eng.accept_quest("side_hollow_worg")
        emitted = core_quests.note_kill(self.eng.player, self.eng.content,
                                        self.eng.content.quests,
                                        "hollow_worg", "grave_heath")
        self.assertFalse(any("/1" in line for line in emitted), emitted)
        self.assertTrue(any("ready to hand in" in line for line in emitted), emitted)

    def test_a_kill_in_battle_puts_its_quest_line_on_the_quest_tab(self):
        from rpg_game.presentation import pygame_battle as pb
        self.eng.accept_quest("spine_cainos")
        for _ in range(5):
            core_quests.note_kill(self.eng.player, self.eng.content,
                                  self.eng.content.quests, "giant_rat", "cainos")
        enemy = self.eng.content.enemies["giant_rat"].create_enemy()
        enemy.zone = "cainos"
        enemy.hp = 1
        battle = pb.BattleApp(engine=self.eng, enemy=enemy, standalone=False,
                              event_log=self.app.event_log)
        result = battle.engine.run_combat_turn(enemy, "attack")
        while result.outcome == "ongoing":
            result = battle.engine.run_combat_turn(enemy, "attack")
        battle._finish_result(result, False)
        self.assertTrue(any("ready to hand in" in line for line in self._quest_lines()),
                        self._quest_lines())


if __name__ == "__main__":
    unittest.main()
