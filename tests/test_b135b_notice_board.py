"""B135b: the notice board — accept, track and hand in quests.

The board hangs on the REST building (inn in a town/city/capital, cottage in a
village), measured in STEG 0 as the only building type present in all 17 towns.
Locks: the door menu offers it wherever you can sleep and nowhere else; the list
separates offers from quests you are on; a notice can be accepted, tracked with
progress, handed in for its reward and abandoned; keyboard nav and mouse both
work; and no quest RULE leaks into the shell (every action goes through the
engine).

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
    from rpg_game.presentation.overworld_buildings import BUILDING_FUNCTION
    from rpg_game.presentation.pygame_overworld import OverworldApp
    from rpg_game.presentation import town_cluster

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


def _key(key):
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="")


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class BoardHomeTests(unittest.TestCase):
    """The STEG 0 decision, locked: every town can reach a board."""

    def test_a_rest_building_exists_in_every_tier(self):
        for tier in ("capital", "city", "town", "village"):
            buildings = [b[0] for b in town_cluster.resolve_template(tier)]
            rest = [b for b in buildings if BUILDING_FUNCTION.get(b) == "rest"]
            self.assertEqual(len(rest), 1,
                             f"{tier} must have exactly one rest building, got {rest}")

    def test_villages_have_a_cottage_not_an_inn(self):
        # Why the board is on the REST FUNCTION rather than on "inn": villages
        # have no inn at all, so an inn-only board would miss every village.
        village = [b[0] for b in town_cluster.resolve_template("village")]
        self.assertIn("cottage", village)
        self.assertNotIn("inn", village)

    def test_town_hall_would_not_have_covered_the_map(self):
        # town_hall (the tournaments home) only appears with a tournament, so it
        # cannot be the board's home.
        without = [b[0] for b in town_cluster.resolve_template("town",
                                                               has_tournament=False)]
        self.assertNotIn("town_hall", without)


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class NoticeBoardTests(unittest.TestCase):
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

    def _open(self):
        self.app.open_overlay("notice_board")
        self.app.draw()

    def _button(self, label):
        return next((b for b in self.app.buttons if b.label == label), None)

    # -- the door offers it --------------------------------------------------

    def test_the_rest_building_menu_offers_the_board(self):
        place_id = self.eng.player.current_place_id
        self.app.building_menu = (place_id, "inn")
        self.app.mode = "building"
        self.app.draw()
        self.assertIsNotNone(self._button("Notice board"))

    def test_the_village_cottage_menu_offers_the_board_too(self):
        place_id = self.eng.player.current_place_id
        self.app.building_menu = (place_id, "cottage")
        self.app.mode = "building"
        self.app.draw()
        self.assertIsNotNone(self._button("Notice board"))

    def test_a_non_rest_building_does_not_offer_the_board(self):
        place_id = self.eng.player.current_place_id
        self.app.building_menu = (place_id, "blacksmith")
        self.app.mode = "building"
        self.app.draw()
        self.assertIsNone(self._button("Notice board"))

    def test_the_board_button_opens_the_overlay(self):
        place_id = self.eng.player.current_place_id
        self.app.building_menu = (place_id, "inn")
        self.app.mode = "building"
        self.app.draw()
        self._button("Notice board").on_click()
        self.assertEqual(self.app.overlay, "notice_board")
        self.assertIsNone(self.app.building_menu)

    # -- listing ------------------------------------------------------------

    def test_offers_are_listed_and_gated_quests_are_not(self):
        self._open()
        labels = " ".join(b.label for b in self.app.buttons)
        self.assertIn("The Fields Beyond Hordanita", labels)
        # side_hollow_worg needs its prereq handed in first
        self.assertNotIn("The Worg That Isn't There", labels)

    def test_rows_carry_a_full_title_tooltip(self):
        self._open()
        titles = [p.title for _r, p in self.app.hover._zones
                  if isinstance(p, ui.Tooltip)]
        self.assertIn("The Fields Beyond Hordanita", titles)

    def test_an_accepted_quest_moves_to_the_active_section_with_progress(self):
        self._open()
        self.app.accept_quest("spine_cainos")
        self.app.draw()
        sections = [name for name, _items in self.app.focus._sections]
        self.assertIn("board_active", sections)
        row = self._button("> The Fields Beyond Hordanita")
        self.assertIsNotNone(row)
        self.assertEqual(row.value, "0/6")

    def test_a_finished_quest_reads_as_ready(self):
        self._open()
        self.app.accept_quest("spine_cainos")
        for _ in range(6):
            core_quests.note_kill(self.eng.player, self.eng.content,
                                  self.eng.content.quests, "giant_rat", "cainos")
        self.app.draw()
        row = self._button("> The Fields Beyond Hordanita")
        self.assertEqual(row.value, "ready")

    def test_the_empty_board_says_so(self):
        # turn every offer into a taken quest, then check the message path
        self._open()
        # Turning one in can UNGATE another (side_hollow_worg), so drain until dry.
        for _ in range(20):
            offers = self.eng.board_quests()
            if not offers:
                break
            for quest in offers:
                self.eng.player.quest_states[quest.id] = {
                    "status": core_quests.TURNED_IN, "progress": 0}
        self.app.draw()
        self.assertEqual(self.app._notice_board_rows(), [])

    # -- the accept / hand-in / abandon loop ---------------------------------

    def test_accept_button_takes_the_quest_and_logs_it(self):
        self._open()
        self.app.board_selection = "spine_cainos"
        self.app.draw()
        self._button("Accept").on_click()
        self.assertEqual(self.eng.quest_status("spine_cainos"), core_quests.ACTIVE)
        lines = [chatlog.plain(payload) for payload, _c in self.app.event_log]
        self.assertTrue(any("Quest accepted" in line for line in lines), lines)

    def test_hand_in_pays_the_reward_once(self):
        self._open()
        self.app.accept_quest("spine_cainos")
        for _ in range(6):
            core_quests.note_kill(self.eng.player, self.eng.content,
                                  self.eng.content.quests, "giant_rat", "cainos")
        self.app.board_selection = "spine_cainos"
        self.app.draw()
        gold = self.eng.player.gold
        self._button("Hand in").on_click()
        self.assertEqual(self.eng.player.gold, gold + 40)
        self.assertEqual(self.eng.quest_status("spine_cainos"), core_quests.TURNED_IN)
        # the reward lines land on the QUEST channel, not combat/loot
        quest_lines = [chatlog.plain(payload) for payload, _c in self.app.event_log
                       if chatlog.channel_of(payload) == chatlog.CHANNEL_QUEST]
        self.assertTrue(any("Reward: 40 gold" in line for line in quest_lines),
                        quest_lines)

    def test_abandon_button_returns_it_to_the_offers(self):
        self._open()
        self.app.accept_quest("spine_cainos")
        self.app.board_selection = "spine_cainos"
        self.app.draw()
        self._button("Abandon").on_click()
        self.assertEqual(self.eng.quest_status("spine_cainos"), core_quests.AVAILABLE)

    def test_an_unfinished_quest_offers_abandon_not_hand_in(self):
        self._open()
        self.app.accept_quest("spine_cainos")
        self.app.board_selection = "spine_cainos"
        self.app.draw()
        self.assertIsNone(self._button("Hand in"))
        self.assertIsNotNone(self._button("Abandon"))

    # -- selection + navigation ---------------------------------------------

    def test_clicking_a_row_selects_it_for_the_detail_pane(self):
        self._open()
        first = self.app.board_selection
        row = next(b for b in self.app.buttons
                   if "The Water Turned" in b.label)
        row.on_click()
        self.assertNotEqual(self.app.board_selection, first)
        self.assertEqual(self.app.board_selection, "spine_cursed_mire")

    def test_keyboard_navigates_rows_selects_and_accepts(self):
        self._open()
        self.app._handle_key(_key(pygame.K_DOWN))
        self.app.draw()
        self.app._handle_key(_key(pygame.K_RETURN))     # select the focused row
        self.app.draw()
        selected = self.app.board_selection
        self.assertTrue(selected)
        self.app._handle_key(_key(pygame.K_RIGHT))      # jump to the action section
        self.app.draw()
        self.assertEqual(self.app.focus._sections[self.app.focus.section][0],
                         "board_action")
        self.app._handle_key(_key(pygame.K_RETURN))     # accept
        self.assertEqual(self.eng.quest_status(selected), core_quests.ACTIVE)

    def test_escape_closes_the_board(self):
        self._open()
        self.app._handle_key(_key(pygame.K_ESCAPE))
        self.assertEqual(self.app.overlay, "")

    def test_the_notice_list_scrolls_when_it_overflows(self):
        self._open()
        scroll = self.app._menu_scrolls["notice_board"]
        scroll.configure(2000, 300)                     # force an overflow
        self.assertTrue(scroll.scroll(46))
        self.assertGreater(scroll.offset, 0)
        self.assertIs(self.app._active_overflow_scroll(), scroll)

    # -- architecture -------------------------------------------------------

    def test_the_shell_holds_no_quest_rule(self):
        """Accepting through the shell and through the engine agree — the board is
        a thin wrapper, so there is no second quest implementation."""
        self._open()
        self.app.accept_quest("spine_cainos")
        via_shell = dict(self.eng.player.quest_states)
        self.eng.abandon_quest("spine_cainos")
        self.eng.accept_quest("spine_cainos")
        self.assertEqual(dict(self.eng.player.quest_states), via_shell)


if __name__ == "__main__":
    unittest.main()
