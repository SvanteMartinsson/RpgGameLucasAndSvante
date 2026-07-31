"""B139b: the character model with STATES, and Mirr as the first character.

Lucas's locked design: a character is someone with a CONDITION, and that
condition drives portrait, tone and lines together. So the tests care most about
two things — that state selection is right (including the fallback), and that a
character quest is offered at the CHARACTER and never on the notice board.
"""

import dataclasses
import os
import random
import unittest

from rpg_game.core import characters, persistence, quests
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine

PORTRAIT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                            "rpg_game", "assets", "sprites", "generated", "characters")


def _state(sid, flag="", **kwargs):
    return characters.CharacterState(id=sid, requires_quest_flag=flag, **kwargs)


def _character(cid="who", states=None, **kwargs):
    fields = dict(id=cid, name=cid.title(), home_place_id="burg_5",
                  home_building="inn",
                  states=tuple(states if states is not None else [_state("only")]))
    fields.update(kwargs)
    return characters.Character(**fields)


def _quest(qid="q", **kwargs):
    fields = dict(id=qid, title=qid.title(), text="...", giver_kind="board",
                  objective=quests.QuestObjective(kind="open_chests", count=1))
    fields.update(kwargs)
    return quests.Quest(**fields)


class CharacterTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = load_content()

    def _engine(self, quest_list=None, character_list=None, seed=0):
        content = dataclasses.replace(
            self.content,
            quests=tuple(quest_list) if quest_list is not None else self.content.quests,
            characters=(tuple(character_list) if character_list is not None
                        else self.content.characters),
        )
        engine = GameEngine(content=content, rng=random.Random(seed))
        engine.start_new_game("Hero", "fighter")
        return engine


class StateSelectionTests(CharacterTestBase):
    def test_a_single_state_character_is_always_in_it(self):
        engine = self._engine(character_list=[_character()])
        who = engine.character_by_id("who")
        self.assertEqual(engine.character_state(who).id, "only")

    def test_without_a_matching_flag_the_first_state_holds(self):
        person = _character(states=[_state("warm"), _state("cold", "bereaved")])
        engine = self._engine(character_list=[person])
        self.assertEqual(engine.player.quest_flags, set())
        self.assertEqual(engine.character_state(person).id, "warm")

    def test_the_flag_switches_the_state(self):
        person = _character(states=[_state("warm"), _state("cold", "bereaved")])
        engine = self._engine(character_list=[person])
        engine.player.quest_flags.add("bereaved")
        self.assertEqual(engine.character_state(person).id, "cold")

    def test_the_last_matching_state_wins_so_authored_order_is_story_order(self):
        person = _character(states=[_state("a"), _state("b", "f1"), _state("c", "f2")])
        engine = self._engine(character_list=[person])
        self.assertEqual(engine.character_state(person).id, "a")
        engine.player.quest_flags.add("f1")
        self.assertEqual(engine.character_state(person).id, "b")
        engine.player.quest_flags.add("f2")      # a later beat overrides an earlier
        self.assertEqual(engine.character_state(person).id, "c")
        engine.player.quest_flags.discard("f1")  # out-of-order flags still resolve
        self.assertEqual(engine.character_state(person).id, "c")

    def test_state_selection_is_pure_and_reads_only_the_player(self):
        person = _character(states=[_state("warm"), _state("cold", "bereaved")])
        engine = self._engine(character_list=[person])
        before = engine.character_state(person).id
        self.assertEqual(engine.character_state(person).id, before)   # no mutation
        self.assertEqual(engine.player.quest_flags, set())

    def test_a_character_with_no_states_resolves_to_nothing_rather_than_crashing(self):
        bare = characters.Character(id="x", name="X", home_place_id="burg_5",
                                    home_building="inn", states=())
        self.assertIsNone(bare.state_for(self._engine().player))

    def test_the_state_carries_the_writers_tone_note_and_its_sheets(self):
        state = _state("warm", portrait_idle_sheet="i.png",
                       portrait_talk_sheet="t.png", voice_in_text="Warm and busy.")
        self.assertEqual(state.portrait_idle_sheet, "i.png")
        self.assertEqual(state.portrait_talk_sheet, "t.png")
        self.assertEqual(state.voice_in_text, "Warm and busy.")


class CharacterLookupTests(CharacterTestBase):
    def test_a_character_is_found_behind_their_own_door_only(self):
        engine = self._engine()
        self.assertEqual(engine.character_at("burg_5", "inn").id, "mirr")
        self.assertIsNone(engine.character_at("burg_5", "blacksmith"))
        self.assertIsNone(engine.character_at("burg_146", "inn"))

    def test_an_unknown_id_resolves_to_none(self):
        self.assertIsNone(self._engine().character_by_id("nobody"))


class CharacterQuestTests(CharacterTestBase):
    def _setup(self):
        person = _character("mirr", states=[_state("warm")])
        given = _quest("mirr_1", giver_kind=characters.GIVER_CHARACTER,
                       giver_character_id="mirr")
        board = _quest("board_job")
        return self._engine([given, board], [person])

    def test_a_character_quest_is_offered_by_the_character(self):
        engine = self._setup()
        self.assertEqual([q.id for q in engine.character_quests("mirr")], ["mirr_1"])

    def test_a_character_quest_never_appears_on_the_notice_board(self):
        # The design split: the board keeps the impersonal work.
        engine = self._setup()
        self.assertEqual([q.id for q in engine.board_quests()], ["board_job"])
        self.assertNotIn("mirr_1", {q.id for q in engine.board_quests("")})

    def test_a_character_quest_still_runs_the_ordinary_pipeline(self):
        engine = self._setup()
        self.assertTrue(engine.accept_quest("mirr_1"))
        quests.note_chest_opened(engine.player, engine.content, engine.all_quests())
        self.assertTrue(engine.quest_is_ready(engine.quest_by_id("mirr_1")))
        self.assertTrue(engine.turn_in_quest("mirr_1").ok)
        self.assertEqual(engine.quest_status("mirr_1"), quests.TURNED_IN)

    def test_an_accepted_character_quest_stops_being_offered(self):
        engine = self._setup()
        engine.accept_quest("mirr_1")
        self.assertEqual(engine.character_quests("mirr"), [])

    def test_finished_character_quests_are_listed_for_hand_in(self):
        engine = self._setup()
        engine.accept_quest("mirr_1")
        self.assertEqual(engine.character_turn_ins("mirr"), [])
        quests.note_chest_opened(engine.player, engine.content, engine.all_quests())
        self.assertEqual([q.id for q in engine.character_turn_ins("mirr")], ["mirr_1"])

    def test_a_character_chain_is_offered_one_part_at_a_time(self):
        person = _character("mirr", states=[_state("warm")])
        chain = [
            _quest("m1", giver_kind=characters.GIVER_CHARACTER, giver_character_id="mirr",
                   chain_id="mirr_story", chain_index=1, next_quest_id="m2"),
            _quest("m2", giver_kind=characters.GIVER_CHARACTER, giver_character_id="mirr",
                   chain_id="mirr_story", chain_index=2),
        ]
        engine = self._engine(chain, [person])
        self.assertEqual([q.id for q in engine.character_quests("mirr")], ["m1"])
        engine.accept_quest("m1")
        quests.note_chest_opened(engine.player, engine.content, engine.all_quests())
        engine.turn_in_quest("m1")
        self.assertEqual([q.id for q in engine.character_quests("mirr")], ["m2"])


class ValidationTests(CharacterTestBase):
    def _validate(self, character_list, quest_list=None):
        content = dataclasses.replace(
            self.content,
            quests=tuple(quest_list) if quest_list is not None else ())
        characters.validate_characters(tuple(character_list), content)

    def test_the_shipped_characters_validate(self):
        characters.validate_characters(self.content.characters, self.content)

    def test_a_character_in_an_unknown_place_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown place"):
            self._validate([_character(home_place_id="nowhere")])

    def test_a_character_with_no_states_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no states"):
            self._validate([_character(states=[])])

    def test_a_character_with_no_home_building_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no home_building"):
            self._validate([_character(home_building="")])

    def test_duplicate_character_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate character"):
            self._validate([_character("a"), _character("a")])

    def test_duplicate_state_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "two states"):
            self._validate([_character(states=[_state("s"), _state("s", "f")])])

    def test_a_later_unconditional_state_is_rejected(self):
        # It would always win under last-match-wins and silently kill the others.
        with self.assertRaisesRegex(ValueError, "only the first state"):
            self._validate([_character(states=[_state("a"), _state("b")])])

    def test_a_conditional_first_state_is_rejected(self):
        # The first state is the fallback, so it must always hold.
        with self.assertRaisesRegex(ValueError, "first state"):
            self._validate([_character(states=[_state("a", "f")])])

    def test_a_quest_naming_an_unknown_character_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown character"):
            self._validate([_character("mirr")],
                           [_quest("q", giver_kind=characters.GIVER_CHARACTER,
                                   giver_character_id="ghost")])

    def test_a_mismatched_giver_kind_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "giver_kind"):
            self._validate([_character("mirr")],
                           [_quest("q", giver_character_id="mirr")])   # kind stayed "board"

    def test_a_character_giver_kind_with_no_character_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "names no character"):
            self._validate([_character("mirr")],
                           [_quest("q", giver_kind=characters.GIVER_CHARACTER)])


class SoftDegradationTests(CharacterTestBase):
    """Validate, but degrade: absent art must never take the game down."""

    def test_mirrs_portraits_are_declared_but_not_yet_on_disk(self):
        # The placeholder era, asserted rather than assumed. When Lucas's four
        # sheets land this list empties and the screen picks them up automatically.
        missing = characters.missing_portrait_sheets(self.content.characters,
                                                     PORTRAIT_DIR)
        self.assertEqual(sorted(missing), [
            "mirr_cold_idle_sheet.png", "mirr_cold_talk_sheet.png",
            "mirr_warm_idle_sheet.png", "mirr_warm_talk_sheet.png",
        ])

    def test_missing_art_does_not_stop_the_content_loading(self):
        # load_content() already ran in setUpClass with every sheet absent.
        self.assertTrue(self.content.characters)
        mirr = characters.character_by_id(self.content, "mirr")
        self.assertEqual(mirr.name, "Mirr")

    def test_a_state_flag_no_quest_grants_is_reported_not_raised(self):
        # Mirr's `cold` state waits on the chain text Lucas still owes; that is a
        # known gap, so it is REPORTED here instead of failing the load.
        unwired = characters.unwired_state_flags(self.content.characters, self.content)
        self.assertIn(("mirr", "cold", "mirr_bereaved"), unwired)

    def test_a_wired_flag_drops_off_the_unwired_report(self):
        content = dataclasses.replace(self.content, quests=(
            _quest("grants", rewards=({"kind": "flag", "flag": "mirr_bereaved"},)),
        ))
        unwired = characters.unwired_state_flags(self.content.characters, content)
        self.assertEqual(unwired, ())


class MirrDataTests(CharacterTestBase):
    def test_mirr_is_the_innkeeper_of_hordanita(self):
        mirr = characters.character_by_id(self.content, "mirr")
        self.assertIsNotNone(mirr)
        self.assertEqual(mirr.name, "Mirr")
        self.assertEqual(mirr.full_name, "Miranda")
        self.assertEqual(mirr.home_place_id, "burg_5")
        self.assertEqual(self.content.places["burg_5"].name, "Hordanita")

    def test_she_lives_on_the_rest_building_where_the_board_already_hangs(self):
        from rpg_game.presentation import overworld_buildings as ob
        mirr = characters.character_by_id(self.content, "mirr")
        # Same building type the notice board hangs on (B135b), and Hordanita is a
        # capital so that door really exists there.
        self.assertEqual(ob.BUILDING_FUNCTION[mirr.home_building], "rest")
        # ...and it is one of the doors the night does NOT shut (B136c), so she is
        # reachable at any hour.
        self.assertNotIn(mirr.home_building, ob.NIGHT_CLOSED_BUILDINGS)

    def test_she_has_a_warm_and_a_cold_state_in_that_order(self):
        mirr = characters.character_by_id(self.content, "mirr")
        self.assertEqual([s.id for s in mirr.states], ["warm", "cold"])
        self.assertEqual(mirr.states[0].requires_quest_flag, "")
        self.assertEqual(mirr.states[1].requires_quest_flag, "mirr_bereaved")

    def test_every_state_carries_a_tone_note_for_the_writer(self):
        for character in self.content.characters:
            for state in character.states:
                self.assertTrue(state.voice_in_text.strip(),
                                f"{character.id}/{state.id} has no voice_in_text")

    def test_she_gives_no_quests_yet(self):
        # Her chain text is explicitly out of this batch; the machinery is what
        # ships. This test documents that and will be updated when it lands.
        engine = self._engine()
        self.assertEqual(engine.character_quests("mirr"), [])

    def test_her_state_survives_a_save_round_trip(self):
        # Character state rides quest_flags, which already persists — no new field.
        engine = self._engine()
        engine.player.quest_flags.add("mirr_bereaved")
        data = persistence.serialize_player(engine.player)
        restored = persistence.deserialize_player(data, default_place_id="burg_5")
        mirr = characters.character_by_id(self.content, "mirr")
        self.assertEqual(mirr.state_for(restored).id, "cold")
        self.assertEqual(persistence.SAVE_VERSION, 2)


if __name__ == "__main__":
    unittest.main()
