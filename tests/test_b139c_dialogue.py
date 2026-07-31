"""B139c: the dialogue screen — data model, cursor, geometry, keyboard, voice keys.

The core half (script shape, availability, the Conversation cursor) is tested
without pygame; the screen half needs it and skips without it.
"""

import dataclasses
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from rpg_game.core import characters, dialogue, quests
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine

try:
    import pygame

    from rpg_game.presentation import audio
    from rpg_game.presentation import pygame_battle as pb
    from rpg_game.presentation import pygame_dialogue as pd

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


def _line(lid, speaker=dialogue.NPC, text="Some words."):
    return dialogue.DialogueLine(id=lid, speaker=speaker, text=text)


def _choice(cid, **kwargs):
    fields = dict(id=cid, text=cid.replace("_", " ").title())
    fields.update(kwargs)
    return dialogue.DialogueChoice(**fields)


def _script(sid="s", character_id="mirr", state_id="", nodes=None, start="a"):
    if nodes is None:
        nodes = (dialogue.DialogueNode(id="a", lines=(_line("a1"),)),)
    return dialogue.DialogueScript(id=sid, character_id=character_id,
                                   state_id=state_id, start_node_id=start,
                                   nodes=tuple(nodes))


class DialogueTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = load_content()

    def _engine(self, **overrides):
        content = dataclasses.replace(self.content, **overrides)
        engine = GameEngine(content=content, rng=random.Random(0))
        engine.start_new_game("Hero", "fighter")
        return engine


class ScriptSelectionTests(DialogueTestBase):
    def test_the_state_picks_the_script(self):
        engine = self._engine()
        mirr = engine.character_at("burg_5", "inn")
        self.assertEqual(engine.dialogue_script_for(mirr).state_id, "warm")
        engine.player.quest_flags.add("mirr_bereaved")
        self.assertEqual(engine.dialogue_script_for(mirr).state_id, "cold")

    def test_a_stateless_script_is_the_fallback_for_every_state(self):
        scripts = (_script("any", state_id=""),)
        self.assertEqual(dialogue.script_for(scripts, "mirr", "warm").id, "any")
        self.assertEqual(dialogue.script_for(scripts, "mirr", "cold").id, "any")

    def test_an_exact_state_match_beats_the_fallback(self):
        scripts = (_script("any", state_id=""), _script("warm_only", state_id="warm"))
        self.assertEqual(dialogue.script_for(scripts, "mirr", "warm").id, "warm_only")
        self.assertEqual(dialogue.script_for(scripts, "mirr", "cold").id, "any")

    def test_a_character_with_nothing_written_has_no_script(self):
        self.assertIsNone(dialogue.script_for((), "mirr", "warm"))
        engine = self._engine(dialogue=())
        self.assertIsNone(engine.start_conversation(engine.character_at("burg_5", "inn")))


class ConversationCursorTests(DialogueTestBase):
    def _three_line_script(self):
        return _script(nodes=(
            dialogue.DialogueNode(id="a", lines=(_line("a1"), _line("a2"), _line("a3")),
                                  choices=(_choice("go", next_node_id="b"),)),
            dialogue.DialogueNode(id="b", lines=(_line("b1"),)),
        ))

    def test_lines_are_walked_in_order_then_the_choices_appear(self):
        conv = dialogue.Conversation(self._three_line_script())
        self.assertEqual(conv.current_line().id, "a1")
        self.assertFalse(conv.awaiting_choice())
        self.assertTrue(conv.advance())
        self.assertEqual(conv.current_line().id, "a2")
        self.assertTrue(conv.advance())
        self.assertEqual(conv.current_line().id, "a3")
        self.assertFalse(conv.advance())          # out of lines
        self.assertTrue(conv.awaiting_choice())
        self.assertEqual([c.id for c in conv.pending_choices()], ["go"])

    def test_choices_are_hidden_while_lines_remain(self):
        conv = dialogue.Conversation(self._three_line_script())
        self.assertEqual(conv.pending_choices(), ())

    def test_a_choice_moves_to_its_node(self):
        conv = dialogue.Conversation(self._three_line_script())
        while conv.advance():
            pass
        conv.choose(conv.pending_choices()[0])
        self.assertEqual(conv.node_id, "b")
        self.assertEqual(conv.current_line().id, "b1")

    def test_a_node_with_no_choices_ends_the_conversation(self):
        conv = dialogue.Conversation(_script(nodes=(
            dialogue.DialogueNode(id="a", lines=(_line("a1"),)),)))
        self.assertFalse(conv.over)
        self.assertFalse(conv.advance())
        self.assertTrue(conv.over)

    def test_an_end_action_closes_the_conversation_immediately(self):
        conv = dialogue.Conversation(_script(nodes=(
            dialogue.DialogueNode(id="a", lines=(_line("a1"),),
                                  choices=(_choice("bye", action=dialogue.ACTION_END),)),)))
        conv.advance()
        conv.choose(conv.pending_choices()[0])
        self.assertTrue(conv.over)

    def test_history_accumulates_every_line_heard(self):
        conv = dialogue.Conversation(self._three_line_script())
        while conv.advance():
            pass
        conv.choose(conv.pending_choices()[0])
        self.assertEqual([line.id for line in conv.history], ["a1", "a2", "a3", "b1"])

    def test_a_choice_leading_nowhere_ends_the_conversation(self):
        conv = dialogue.Conversation(_script(nodes=(
            dialogue.DialogueNode(id="a", lines=(_line("a1"),),
                                  choices=(_choice("nowhere"),)),)))
        conv.advance()
        conv.choose(conv.pending_choices()[0])
        self.assertTrue(conv.over)

    def test_advancing_a_finished_conversation_is_a_no_op(self):
        conv = dialogue.Conversation(_script())
        conv.advance()
        self.assertTrue(conv.over)
        self.assertFalse(conv.advance())
        self.assertIsNone(conv.current_line())


class ChoiceAvailabilityTests(DialogueTestBase):
    def _blocker(self, engine, choice):
        return engine.dialogue_choice_blocker(choice)

    def test_a_plain_choice_is_available(self):
        engine = self._engine()
        self.assertEqual(self._blocker(engine, _choice("plain")), "")

    def test_a_level_gate_says_the_level(self):
        engine = self._engine()
        blocker = self._blocker(engine, _choice("hard", requires_level=5))
        self.assertIn("level 5", blocker)

    def test_a_flag_gate_blocks_until_the_flag_lands(self):
        engine = self._engine()
        choice = _choice("secret", requires_quest_flag="knows")
        self.assertTrue(self._blocker(engine, choice))
        engine.player.quest_flags.add("knows")
        self.assertEqual(self._blocker(engine, choice), "")

    def test_an_authored_reason_wins_over_the_generated_one(self):
        engine = self._engine()
        choice = _choice("hard", requires_level=9,
                         unavailable_reason="You'd go straight through it.")
        self.assertEqual(self._blocker(engine, choice), "You'd go straight through it.")

    def test_every_blocked_choice_gives_a_reason(self):
        # B112: a dimmed row that does not say why is worse than no row.
        engine = self._engine()
        for choice in (_choice("a", requires_level=99),
                       _choice("b", requires_quest_flag="nope"),
                       _choice("c", action=dialogue.ACTION_ACCEPT, quest_id="ghost"),
                       _choice("d", action=dialogue.ACTION_TURN_IN, quest_id="ghost")):
            self.assertTrue(self._blocker(engine, choice).strip(), choice.id)

    def test_accept_is_blocked_once_the_quest_is_taken(self):
        quest = quests.Quest(id="job", title="Job", text="t",
                             giver_kind=characters.GIVER_CHARACTER,
                             giver_character_id="mirr",
                             objective=quests.QuestObjective(kind="open_chests", count=1))
        engine = self._engine(quests=(quest,))
        choice = _choice("take", action=dialogue.ACTION_ACCEPT, quest_id="job")
        self.assertEqual(self._blocker(engine, choice), "")
        engine.accept_quest("job")
        self.assertIn("already", self._blocker(engine, choice).lower())

    def test_turn_in_is_blocked_until_the_objective_is_met(self):
        quest = quests.Quest(id="job", title="Job", text="t",
                             giver_kind=characters.GIVER_CHARACTER,
                             giver_character_id="mirr",
                             objective=quests.QuestObjective(kind="open_chests", count=1))
        engine = self._engine(quests=(quest,))
        choice = _choice("hand", action=dialogue.ACTION_TURN_IN, quest_id="job")
        self.assertIn("not on that", self._blocker(engine, choice).lower())
        engine.accept_quest("job")
        self.assertIn("not finished", self._blocker(engine, choice).lower())
        quests.note_chest_opened(engine.player, engine.content, engine.all_quests())
        self.assertEqual(self._blocker(engine, choice), "")

    def test_a_quest_action_runs_the_ordinary_pipeline(self):
        quest = quests.Quest(id="job", title="Job", text="t",
                             giver_kind=characters.GIVER_CHARACTER,
                             giver_character_id="mirr",
                             objective=quests.QuestObjective(kind="open_chests", count=1),
                             rewards=({"kind": "gold", "amount": 25},))
        engine = self._engine(quests=(quest,))
        gold = engine.player.gold
        engine.apply_dialogue_choice(_choice("take", action=dialogue.ACTION_ACCEPT,
                                             quest_id="job"))
        self.assertEqual(engine.quest_status("job"), quests.ACTIVE)
        quests.note_chest_opened(engine.player, engine.content, engine.all_quests())
        engine.apply_dialogue_choice(_choice("hand", action=dialogue.ACTION_TURN_IN,
                                             quest_id="job"))
        self.assertEqual(engine.quest_status("job"), quests.TURNED_IN)
        self.assertEqual(engine.player.gold, gold + 25)

    def test_a_blocked_choice_does_nothing_at_all(self):
        quest = quests.Quest(id="job", title="Job", text="t",
                             giver_kind=characters.GIVER_CHARACTER,
                             giver_character_id="mirr",
                             objective=quests.QuestObjective(kind="open_chests", count=1))
        engine = self._engine(quests=(quest,))
        events = engine.apply_dialogue_choice(
            _choice("hand", action=dialogue.ACTION_TURN_IN, quest_id="job"))
        self.assertEqual(events, [])
        self.assertEqual(engine.quest_status("job"), quests.AVAILABLE)


class VoiceKeyTests(DialogueTestBase):
    def test_the_key_is_built_from_ids_only(self):
        script = _script("mirr_warm")
        self.assertEqual(dialogue.voice_key(script, _line("greet_1")),
                         "mirr_warm__greet_1")

    def test_the_key_does_not_move_when_a_line_is_inserted_above(self):
        # THE point of an id-derived key: a new line must not repoint recorded audio.
        script = _script("s")
        before = dialogue.voice_key(script, _line("greet_1"))
        _bigger = _script("s", nodes=(dialogue.DialogueNode(
            id="a", lines=(_line("brand_new"), _line("greet_1"))),))
        self.assertEqual(dialogue.voice_key(_bigger, _line("greet_1")), before)

    def test_every_shipped_line_has_a_unique_key(self):
        keys = [dialogue.voice_key(script, line)
                for script in self.content.dialogue
                for node in script.nodes for line in node.lines]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(keys)

    @unittest.skipUnless(DEPS_OK, "pygame not installed")
    def test_playback_is_silent_when_nothing_is_recorded(self):
        # No voice is authored yet: every lookup misses, and that is not an error.
        for script in self.content.dialogue:
            for node in script.nodes:
                for line in node.lines:
                    key = dialogue.voice_key(script, line)
                    self.assertIsNone(audio.voice_path(key))
                    self.assertFalse(audio.play_voice(key))
        audio.stop_voice()      # safe with nothing playing


class ValidationTests(DialogueTestBase):
    def _validate(self, scripts, **overrides):
        content = dataclasses.replace(self.content, **overrides)
        dialogue.validate_dialogue(tuple(scripts), content)

    def test_the_shipped_dialogue_validates(self):
        dialogue.validate_dialogue(self.content.dialogue, self.content)

    def test_an_unknown_start_node_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown node"):
            self._validate([_script(start="nope")])

    def test_a_choice_leading_to_an_unknown_node_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown node"):
            self._validate([_script(nodes=(dialogue.DialogueNode(
                id="a", lines=(_line("a1"),),
                choices=(_choice("go", next_node_id="ghost"),)),))])

    def test_a_reused_line_id_is_rejected_because_it_is_a_voice_key(self):
        with self.assertRaisesRegex(ValueError, "voice key"):
            self._validate([_script(nodes=(
                dialogue.DialogueNode(id="a", lines=(_line("dup"),),
                                      choices=(_choice("go", next_node_id="b"),)),
                dialogue.DialogueNode(id="b", lines=(_line("dup"),)),))])

    def test_an_unknown_speaker_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown speaker"):
            self._validate([_script(nodes=(dialogue.DialogueNode(
                id="a", lines=(_line("a1", speaker="narrator"),)),))])

    def test_an_empty_line_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "is empty"):
            self._validate([_script(nodes=(dialogue.DialogueNode(
                id="a", lines=(_line("a1", text="   "),)),))])

    def test_an_unknown_character_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown character"):
            self._validate([_script(character_id="ghost")])

    def test_an_unknown_state_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown state"):
            self._validate([_script(state_id="furious")])

    def test_an_empty_node_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "is empty"):
            self._validate([_script(nodes=(dialogue.DialogueNode(id="a"),))])

    def test_an_unknown_action_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown action"):
            self._validate([_script(nodes=(dialogue.DialogueNode(
                id="a", lines=(_line("a1"),),
                choices=(_choice("go", action="explode"),)),))])

    def test_a_quest_action_with_no_quest_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no quest_id"):
            self._validate([_script(nodes=(dialogue.DialogueNode(
                id="a", lines=(_line("a1"),),
                choices=(_choice("go", action=dialogue.ACTION_ACCEPT),)),))])

    def test_a_quest_id_with_no_quest_action_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no quest action"):
            self._validate([_script(nodes=(dialogue.DialogueNode(
                id="a", lines=(_line("a1"),),
                choices=(_choice("go", quest_id="job"),)),))])


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class ScreenTests(DialogueTestBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _app(self, flags=()):
        engine = self._engine()
        engine.player.quest_flags |= set(flags)
        mirr = engine.character_at("burg_5", "inn")
        return pd.DialogueApp(engine, mirr)

    def _to_choices(self, app, limit=40):
        for _ in range(limit):
            if app.conversation.awaiting_choice() or not app.running:
                return
            app.skip_typing()
            app.advance()

    def _key(self, app, key):
        app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=""))

    # -- geometry mirrors the battle screen ---------------------------------

    def test_the_zones_are_the_battle_screens_zones(self):
        self.assertEqual(tuple(pd.STAGE), (16, 16, 992, 360))
        self.assertEqual(tuple(pd.TALK_PANEL), (16, 392, 460, 272))
        self.assertEqual(tuple(pd.CHOICES), (492, 392, 516, 272))

    def test_the_rects_are_imported_not_retyped(self):
        # They must be the SAME objects the battle screen uses, or they can drift.
        self.assertIs(pd.STAGE, pb.STAGE)
        self.assertIs(pd.TALK_PANEL, pb.LOG_PANEL)
        self.assertEqual(pd.CHOICES.x, pb.VITALS.x)
        self.assertEqual(pd.CHOICES.width, pb.VITALS.width)
        self.assertEqual(pd.CHOICES.bottom, pb.ACTIONS.bottom)

    def test_the_choice_grid_is_two_columns_plus_an_esc_cell(self):
        rects = self.pd_rects(4)          # 3 choices + Esc
        self.assertEqual(len(rects), 4)
        columns = sorted({r.x for r in rects[:3]})
        self.assertEqual(len(columns), 2)
        self.assertGreater(rects[3].x, columns[-1])       # Esc in its own column
        for rect in rects:
            self.assertTrue(pd.CHOICES.contains(rect), rect)

    def pd_rects(self, count):
        return self._app().choice_grid_rects(count)

    def test_the_grid_keeps_the_canonical_two_rows_up_to_four_choices(self):
        for count in (1, 2, 3, 4):
            rects = self.pd_rects(count + 1)
            self.assertEqual(len(rects), count + 1)
            self.assertLessEqual(len({r.y for r in rects[:count]}), 2, count)

    def test_the_grid_grows_rows_beyond_four_choices(self):
        rects = self.pd_rects(7)          # 6 choices + Esc
        self.assertEqual(len({r.y for r in rects[:6]}), 3)
        for rect in rects:
            self.assertTrue(pd.CHOICES.contains(rect), rect)

    # -- portraits ----------------------------------------------------------

    def test_a_missing_sheet_gives_no_frames_so_the_placeholder_draws(self):
        pd._reset_portrait_cache()
        self.assertIsNone(pd.portrait_frames("mirr_warm_idle_sheet.png"))
        self.assertIsNone(pd.portrait_frames(""))

    def test_the_talk_sheet_is_used_while_typing_and_idle_when_still(self):
        app = self._app()
        self.assertTrue(app.is_typing)
        self.assertEqual(app.current_portrait_sheet(), app.state.portrait_talk_sheet)
        app.skip_typing()
        self.assertFalse(app.is_typing)
        self.assertEqual(app.current_portrait_sheet(), app.state.portrait_idle_sheet)

    def test_the_portrait_frame_cycles_through_all_four(self):
        app = self._app()
        seen = set()
        for _ in range(240):
            app.update()
            seen.add(app.portrait_frame_index())
        self.assertEqual(seen, {0, 1, 2, 3})

    def test_a_corrupt_sheet_degrades_to_the_placeholder(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            name = "broken_sheet.png"
            with open(os.path.join(folder, name), "wb") as handle:
                handle.write(b"not a png")
            original = pd.PORTRAIT_DIR
            pd.PORTRAIT_DIR = folder
            try:
                pd._reset_portrait_cache()
                self.assertIsNone(pd.portrait_frames(name))
            finally:
                pd.PORTRAIT_DIR = original
                pd._reset_portrait_cache()

    # -- typing + drawing ---------------------------------------------------

    def test_text_types_out_and_a_press_skips_to_the_full_line(self):
        app = self._app()
        self.assertEqual(app._visible_text(), "")
        for _ in range(10):
            app.update()
        partial = app._visible_text()
        self.assertTrue(0 < len(partial) < len(app._full_text()))
        app.advance()                     # first press = reveal
        self.assertEqual(app._visible_text(), app._full_text())
        self.assertFalse(app.is_typing)

    def test_a_second_press_moves_to_the_next_line(self):
        app = self._app()
        first = app.conversation.current_line().id
        app.advance()                     # reveal
        app.advance()                     # move on
        self.assertNotEqual(app.conversation.current_line().id, first)

    def test_every_state_renders_both_moments(self):
        for flags in ((), ("mirr_bereaved",)):
            app = self._app(flags)
            app.update()
            app.draw()                    # typing
            self._to_choices(app)
            app.draw()                    # choices
            self.assertTrue(pygame.image.tostring(app.screen, "RGB"))

    def test_the_speaker_colours_are_gold_for_npc_and_blue_for_the_player(self):
        self.assertEqual(pd.SPEAKER_COLORS[dialogue.NPC], pd.NPC_COLOR)
        self.assertEqual(pd.SPEAKER_COLORS[dialogue.PLAYER], pd.PLAYER_COLOR)
        self.assertNotEqual(pd.NPC_COLOR, pd.PLAYER_COLOR)

    def test_a_block_is_a_name_row_then_the_wrapped_line(self):
        app = self._app()
        app.skip_typing()
        blocks = app._talk_blocks(400)
        self.assertTrue(blocks)
        name_row, *body = blocks[0]
        self.assertIn(app.character.name, name_row[0])
        self.assertEqual(name_row[1], pd.NPC_COLOR)
        self.assertTrue(body)

    def test_the_player_name_is_used_for_player_lines(self):
        app = self._app()
        self._to_choices(app)
        rows = [row for block in app._talk_blocks(400) for row in block]
        self.assertTrue(any(app.engine.player.name in text and color == pd.PLAYER_COLOR
                            for text, color in rows))

    # -- keyboard -----------------------------------------------------------

    def test_space_and_enter_advance_the_text(self):
        for key in (pygame.K_SPACE, pygame.K_RETURN):
            app = self._app()
            app.skip_typing()
            first = app.conversation.current_line().id
            self._key(app, key)
            self.assertNotEqual(app.conversation.current_line().id, first, key)

    def test_arrows_move_the_choice_focus_by_geometry(self):
        app = self._app()
        self._to_choices(app)
        app.draw()
        first = app.focus.focused().label
        self._key(app, pygame.K_RIGHT)
        app.draw()
        self.assertNotEqual(app.focus.focused().label, first)

    def test_enter_takes_the_focused_choice(self):
        app = self._app()
        self._to_choices(app)
        app.draw()
        app.focus.reset()
        node_before = app.conversation.node_id
        self._key(app, pygame.K_RETURN)
        self.assertNotEqual(app.conversation.node_id, node_before)

    def test_esc_ends_the_conversation(self):
        app = self._app()
        self.assertTrue(app.running)
        self._key(app, pygame.K_ESCAPE)
        self.assertFalse(app.running)

    def test_the_whole_screen_is_reachable_without_a_mouse(self):
        """B99/B126: EVERY cell, Leave included, can be reached with arrows alone.

        Flooded over all four directions rather than walked in a fixed pattern —
        geometric nav is a graph, and a fixed walk can cycle between two cells
        without proving anything about the rest.
        """
        app = self._app()
        self._to_choices(app)
        app.draw()
        keys = (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN)
        start = (app.focus.section, app.focus.index)
        reached = {start}
        frontier = [start]
        while frontier:
            position = frontier.pop()
            for key in keys:
                app.focus.section, app.focus.index = position
                self._key(app, key)
                landed = (app.focus.section, app.focus.index)
                if landed not in reached:
                    reached.add(landed)
                    frontier.append(landed)
        labels = {app.focus._sections[s][1][i].label for s, i in reached}
        self.assertIn("Leave", labels)
        self.assertEqual(len(reached), len(app.buttons),
                         f"unreachable cells; reached {sorted(labels)}")

    def test_a_blocked_choice_stays_focusable_and_explains_itself(self):
        app = self._app()
        self._to_choices(app)
        app.draw()
        blocked = [b for b in app.buttons if b.restricted]
        self.assertTrue(blocked, "the placeholder script should carry a gated choice")
        for button in blocked:
            self.assertTrue(button.sublabel.strip())      # the reason is on the cell
            self.assertIsNotNone(button.tooltip)          # and never truncated away
        node_before = app.conversation.node_id
        blocked[0].on_click()                             # taking it does nothing...
        self.assertEqual(app.conversation.node_id, node_before)
        self.assertTrue(any(blocked[0].label in line for line in app.log_lines))

    def test_scrolling_the_history_does_not_disturb_the_conversation(self):
        app = self._app()
        self._to_choices(app)
        node = app.conversation.node_id
        self._key(app, pygame.K_PAGEUP)
        self._key(app, pygame.K_PAGEDOWN)
        self.assertEqual(app.conversation.node_id, node)


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class DoorWiringTests(DialogueTestBase):
    def test_the_inn_door_offers_a_talk_row_for_mirr(self):
        from rpg_game.presentation import ui_text as T
        engine = self._engine()
        mirr = engine.character_at("burg_5", "inn")
        self.assertIsNotNone(mirr)
        self.assertIsNotNone(engine.dialogue_script_for(mirr))
        self.assertEqual(T.talk_to(mirr.name), "Talk to Mirr")

    def test_the_talk_row_is_keyed_on_the_character_not_the_building(self):
        import inspect
        from rpg_game.presentation import overworld_buildings as ob
        source = inspect.getsource(ob.BuildingMenusMixin._draw_building_menu)
        self.assertIn("character_at(place_id, building_id)", source)


if __name__ == "__main__":
    unittest.main()
