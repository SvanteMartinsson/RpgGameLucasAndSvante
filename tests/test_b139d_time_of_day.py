"""B139d: quests can require a time of day.

THE CHOICE, measured before building (reported in BACKLOG.md): the hour gates
being TAKEN, not being solved.

  * `accept()` is a single funnel that both the board's Accept button and a
    dialogue choice already pass through, so gating there is one check.
  * Gating PROGRESS would mean touching _push/_advance — the per-kill hot path,
    a second enforcement point — and would silently discard work done at the
    wrong hour. That is the worst of the three outcomes.
  * Turn-in was rejected for the same "lose your work" reason.

And because the quest must stay VISIBLE with its condition rather than vanish,
the hour lives in `accept_blocker`, deliberately NOT in `is_offerable`.

No quest content is authored here — mechanics plus a fixture.
"""

import dataclasses
import random
import unittest

from rpg_game.core import characters, daynight, dialogue, persistence, quests
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine


def _quest(qid="q", **kwargs):
    fields = dict(id=qid, title=qid.title(), text="...", giver_kind="board",
                  objective=quests.QuestObjective(kind="open_chests", count=1))
    fields.update(kwargs)
    return quests.Quest(**fields)


NIGHT_JOB = _quest("night_job", time_of_day="night")
DAY_JOB = _quest("day_job", time_of_day="day")
ANY_JOB = _quest("any_job")


class TimeOfDayTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = load_content()

    def _engine(self, quest_list=(NIGHT_JOB, DAY_JOB, ANY_JOB), phase="day", **extra):
        content = dataclasses.replace(self.content, quests=tuple(quest_list), **extra)
        engine = GameEngine(content=content, rng=random.Random(0))
        engine.start_new_game("Hero", "fighter")
        engine.set_world_phase(phase)
        return engine


class PhaseReadingTests(TimeOfDayTestBase):
    def test_the_hour_is_read_from_the_players_own_clock(self):
        engine = self._engine(phase="day")
        self.assertEqual(quests.quest_phase(engine.player), "day")
        engine.set_world_phase("night")
        self.assertEqual(quests.quest_phase(engine.player), "night")

    def test_dusk_counts_as_night_the_same_as_everywhere_else(self):
        # ONE definition of dark: spawns (B136e), ambience (B136d) and quests all
        # go through daynight.spawn_phase, so dusk is night for all three.
        engine = self._engine(phase="dusk")
        self.assertEqual(quests.quest_phase(engine.player), "night")
        self.assertEqual(quests.quest_phase(engine.player),
                         daynight.spawn_phase("dusk"))
        engine.set_world_phase("dawn")
        self.assertEqual(quests.quest_phase(engine.player), "day")

    def test_every_clock_phase_maps_to_a_quest_phase(self):
        engine = self._engine()
        for phase in daynight.PHASE_ORDER:
            engine.set_world_phase(phase)
            self.assertIn(quests.quest_phase(engine.player), ("day", "night"), phase)


class ConditionTests(TimeOfDayTestBase):
    def test_an_unconditioned_quest_is_takeable_at_any_hour(self):
        engine = self._engine()
        for phase in daynight.PHASE_ORDER:
            engine.set_world_phase(phase)
            self.assertTrue(quests.time_of_day_met(engine.player, ANY_JOB), phase)
            self.assertEqual(engine.quest_accept_blocker(ANY_JOB), "", phase)

    def test_a_night_quest_cannot_be_taken_by_day(self):
        engine = self._engine(phase="day")
        self.assertFalse(quests.time_of_day_met(engine.player, NIGHT_JOB))
        self.assertTrue(engine.quest_accept_blocker(NIGHT_JOB))
        self.assertFalse(engine.accept_quest("night_job"))
        self.assertEqual(engine.quest_status("night_job"), quests.AVAILABLE)

    def test_a_night_quest_can_be_taken_after_dark(self):
        engine = self._engine(phase="night")
        self.assertEqual(engine.quest_accept_blocker(NIGHT_JOB), "")
        self.assertTrue(engine.accept_quest("night_job"))
        self.assertEqual(engine.quest_status("night_job"), quests.ACTIVE)

    def test_a_day_quest_is_the_mirror_image(self):
        engine = self._engine(phase="night")
        self.assertFalse(engine.accept_quest("day_job"))
        engine.set_world_phase("day")
        self.assertTrue(engine.accept_quest("day_job"))

    def test_the_blocker_says_when_to_come_back(self):
        engine = self._engine(phase="day")
        self.assertIn("night", engine.quest_accept_blocker(NIGHT_JOB).lower())
        engine.set_world_phase("night")
        self.assertIn("day", engine.quest_accept_blocker(DAY_JOB).lower())

    def test_the_label_states_the_condition(self):
        self.assertEqual(quests.time_of_day_label(NIGHT_JOB), "Only at night")
        self.assertEqual(quests.time_of_day_label(DAY_JOB), "Only by day")
        self.assertEqual(quests.time_of_day_label(ANY_JOB), "")


class VisibilityTests(TimeOfDayTestBase):
    """The quest must be SHOWN with its condition, never silently missing."""

    def test_an_out_of_hours_quest_still_appears_on_the_board(self):
        engine = self._engine(phase="day")
        listed = {q.id for q in engine.board_quests()}
        self.assertIn("night_job", listed)      # visible...
        self.assertTrue(engine.quest_accept_blocker(NIGHT_JOB))   # ...but not takeable

    def test_the_hour_is_not_folded_into_is_offerable(self):
        # If it were, the quest would vanish from the board instead of explaining
        # itself — that is the whole reason accept_blocker exists separately.
        engine = self._engine(phase="day")
        self.assertTrue(quests.is_offerable(engine.player, NIGHT_JOB,
                                            engine.all_quests()))

    def test_the_board_shows_the_label_and_dims_accept(self):
        engine = self._engine(phase="day")
        self.assertEqual(engine.quest_time_of_day_label(NIGHT_JOB), "Only at night")
        self.assertTrue(engine.quest_accept_blocker(NIGHT_JOB))


class NoLostProgressTests(TimeOfDayTestBase):
    """The reason taking is gated instead of solving."""

    def test_progress_keeps_counting_when_the_hour_turns(self):
        engine = self._engine(phase="night", quest_list=(
            _quest("night_hunt", time_of_day="night",
                   objective=quests.QuestObjective(kind="open_chests", count=2)),))
        self.assertTrue(engine.accept_quest("night_hunt"))
        quests.note_chest_opened(engine.player, engine.content, engine.all_quests())
        engine.set_world_phase("day")           # dawn comes mid-quest
        quests.note_chest_opened(engine.player, engine.content, engine.all_quests())
        quest = engine.quest_by_id("night_hunt")
        self.assertEqual(engine.quest_progress(quest), 2)
        self.assertTrue(engine.quest_is_ready(quest))

    def test_it_can_still_be_handed_in_after_sunrise(self):
        engine = self._engine(phase="night", quest_list=(
            _quest("night_hunt", time_of_day="night",
                   rewards=({"kind": "gold", "amount": 10},)),))
        engine.accept_quest("night_hunt")
        quests.note_chest_opened(engine.player, engine.content, engine.all_quests())
        engine.set_world_phase("day")
        result = engine.turn_in_quest("night_hunt")
        self.assertTrue(result.ok, result.text)
        self.assertEqual(engine.quest_status("night_hunt"), quests.TURNED_IN)

    def test_the_progress_hooks_never_consult_the_hour(self):
        # Structural: if _advance or _push read the clock, work could be silently
        # discarded. Assert they do not.
        import inspect
        for function in (quests._advance, quests._push, quests.refresh):
            source = inspect.getsource(function)
            self.assertNotIn("time_of_day", source, function.__name__)
            self.assertNotIn("quest_phase", source, function.__name__)


class DialogueParityTests(TimeOfDayTestBase):
    def test_a_character_offer_is_gated_by_the_same_hour(self):
        person = characters.Character(
            id="mirr", name="Mirr", home_place_id="burg_5", home_building="inn",
            states=(characters.CharacterState(id="warm"),))
        quest = _quest("mirr_night", giver_kind=characters.GIVER_CHARACTER,
                       giver_character_id="mirr", time_of_day="night")
        engine = self._engine(quest_list=(quest,), phase="day", characters=(person,),
                              dialogue=())
        choice = dialogue.DialogueChoice(id="take", text="Take it",
                                         action=dialogue.ACTION_ACCEPT,
                                         quest_id="mirr_night")
        self.assertIn("night", engine.dialogue_choice_blocker(choice).lower())
        self.assertEqual(engine.apply_dialogue_choice(choice), [])
        self.assertEqual(engine.quest_status("mirr_night"), quests.AVAILABLE)
        engine.set_world_phase("night")
        self.assertEqual(engine.dialogue_choice_blocker(choice), "")
        engine.apply_dialogue_choice(choice)
        self.assertEqual(engine.quest_status("mirr_night"), quests.ACTIVE)


class ValidationAndCompatibilityTests(TimeOfDayTestBase):
    def test_an_unknown_time_of_day_is_rejected_at_load(self):
        with self.assertRaisesRegex(ValueError, "unknown time_of_day"):
            quests.validate_quests((_quest("q", time_of_day="midnight"),), self.content)

    def test_day_and_night_and_empty_all_validate(self):
        for value in ("", "day", "night"):
            quests.validate_quests((_quest("q", time_of_day=value),), self.content)

    def test_the_shipped_quests_have_no_hour_condition_yet(self):
        # No content is authored in this batch — only the mechanism.
        for quest in self.content.quests:
            self.assertEqual(quest.time_of_day, "", quest.id)

    def test_parse_defaults_the_field(self):
        parsed = quests.parse_quests({"quests": [{
            "id": "old", "title": "Old", "text": "t",
            "objective": {"kind": "open_chests", "count": 1}}]})
        self.assertEqual(parsed[0].time_of_day, "")

    def test_parse_reads_the_field(self):
        parsed = quests.parse_quests({"quests": [{
            "id": "n", "title": "N", "text": "t", "time_of_day": "night",
            "objective": {"kind": "open_chests", "count": 1}}]})
        self.assertEqual(parsed[0].time_of_day, "night")

    def test_no_save_bump_the_hour_is_read_from_the_existing_clock(self):
        # world_time_seconds (B136a) already persists; nothing new is stored.
        engine = self._engine(phase="night")
        data = persistence.serialize_player(engine.player)
        restored = persistence.deserialize_player(data, default_place_id="burg_5")
        self.assertEqual(quests.quest_phase(restored), "night")
        self.assertEqual(persistence.SAVE_VERSION, 2)


if __name__ == "__main__":
    unittest.main()
