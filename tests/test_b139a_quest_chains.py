"""B139a: quest chains — chain_id, part numbering, recommended level, and the
VISIBLE offer of the next part.

Lucas's model: a story is a chain of SEPARATE quests, not stages inside one, so
the player walks back to the giver between parts and that walking back is the
relationship. Two things therefore have to be true and are tested here: the next
part must be announced rather than quietly appear, and no chain may ever gate
where the player is allowed to go.
"""

import dataclasses
import random
import unittest

from rpg_game.core import persistence, quests
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine


def _quest(qid="q", **kwargs):
    fields = dict(
        id=qid, title=qid.replace("_", " ").title(), text="...",
        giver_kind="board",
        objective=quests.QuestObjective(kind="open_chests", count=1),
    )
    fields.update(kwargs)
    return quests.Quest(**fields)


def _chain(chain_id="mirr", parts=3, **extra):
    """A straight chain of `parts` quests, each unlocking the next."""
    out = []
    for index in range(1, parts + 1):
        out.append(_quest(
            f"{chain_id}_{index}",
            chain_id=chain_id,
            chain_index=index,
            next_quest_id=f"{chain_id}_{index + 1}" if index < parts else "",
            **extra,
        ))
    return out


class ChainTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = load_content()

    def _engine(self, quest_list, seed=0):
        content = dataclasses.replace(self.content, quests=tuple(quest_list))
        engine = GameEngine(content=content, rng=random.Random(seed))
        engine.start_new_game("Hero", "fighter")
        return engine

    def _finish(self, engine, quest_id):
        """Accept, satisfy the open_chests objective, hand in."""
        self.assertTrue(engine.accept_quest(quest_id))
        quests.note_chest_opened(engine.player, engine.content, engine.all_quests())
        result = engine.turn_in_quest(quest_id)
        self.assertTrue(result.ok, result.text)
        return result


class ChainShapeTests(ChainTestBase):
    def test_a_standalone_quest_has_no_chain_fields(self):
        quest = _quest()
        self.assertEqual(quest.chain_id, "")
        self.assertEqual(quest.chain_index, 0)
        self.assertEqual(quest.next_quest_id, "")
        self.assertEqual(quest.recommended_level, 0)

    def test_part_numbering_reads_position_out_of_length(self):
        chain = _chain(parts=4)
        for index, quest in enumerate(chain, start=1):
            self.assertEqual(quests.chain_part_text(chain, quest), f"Part {index} of 4")

    def test_a_standalone_quest_shows_no_part_text(self):
        self.assertEqual(quests.chain_part_text([_quest()], _quest()), "")

    def test_chain_parts_come_back_in_story_order(self):
        chain = list(reversed(_chain(parts=3)))
        ordered = quests.chain_parts(chain, "mirr")
        self.assertEqual([q.chain_index for q in ordered], [1, 2, 3])

    def test_predecessor_and_next_walk_the_chain_both_ways(self):
        chain = _chain(parts=3)
        first, second, third = chain
        self.assertIsNone(quests.chain_predecessor(chain, first))
        self.assertEqual(quests.chain_predecessor(chain, second).id, first.id)
        self.assertEqual(quests.chain_next(chain, second).id, third.id)
        self.assertIsNone(quests.chain_next(chain, third))


class ChainProgressionTests(ChainTestBase):
    def test_only_the_first_part_is_offered_at_the_start(self):
        engine = self._engine(_chain(parts=3))
        offered = {q.id for q in engine.board_quests()}
        self.assertEqual(offered, {"mirr_1"})

    def test_handing_in_a_part_unlocks_exactly_the_next_one(self):
        engine = self._engine(_chain(parts=3))
        self._finish(engine, "mirr_1")
        self.assertEqual({q.id for q in engine.board_quests()}, {"mirr_2"})
        self._finish(engine, "mirr_2")
        self.assertEqual({q.id for q in engine.board_quests()}, {"mirr_3"})
        self._finish(engine, "mirr_3")
        self.assertEqual({q.id for q in engine.board_quests()}, set())

    def test_the_next_part_is_ANNOUNCED_not_quietly_added(self):
        engine = self._engine(_chain(parts=3))
        result = self._finish(engine, "mirr_1")
        # a dedicated result field the shell can act on...
        self.assertEqual(result.next_quest_id, "mirr_2")
        # ...and a log line the player actually reads
        self.assertTrue(any("Mirr 2" in line for line in result.events), result.events)
        self.assertTrue(any("story continues" in line for line in result.events),
                        result.events)

    def test_the_final_part_announces_nothing(self):
        engine = self._engine(_chain(parts=2))
        self._finish(engine, "mirr_1")
        result = self._finish(engine, "mirr_2")
        self.assertEqual(result.next_quest_id, "")
        self.assertFalse(any("story continues" in line for line in result.events))

    def test_a_waiting_continuation_is_flagged_for_the_ui(self):
        engine = self._engine(_chain(parts=3))
        self.assertEqual(engine.chain_offers(), [])       # nothing waiting yet
        self._finish(engine, "mirr_1")
        waiting = engine.chain_offers()
        self.assertEqual([q.id for q in waiting], ["mirr_2"])
        self.assertTrue(engine.quest_is_new_chain_offer(waiting[0]))
        # accepting it clears the announcement
        engine.accept_quest("mirr_2")
        self.assertEqual(engine.chain_offers(), [])

    def test_a_first_part_is_never_a_chain_offer(self):
        # It has no predecessor, so it is an ordinary notice, not a continuation.
        engine = self._engine(_chain(parts=3))
        first = engine.quest_by_id("mirr_1")
        self.assertFalse(engine.quest_is_new_chain_offer(first))

    def test_an_unfinished_part_does_not_unlock_the_next(self):
        engine = self._engine(_chain(parts=3))
        engine.accept_quest("mirr_1")            # accepted but not handed in
        self.assertEqual({q.id for q in engine.board_quests()}, set())
        self.assertEqual(engine.chain_offers(), [])


class RecommendedLevelTests(ChainTestBase):
    def test_the_recommended_level_is_a_hint_and_never_a_gate(self):
        engine = self._engine([_quest("hard", recommended_level=20)])
        quest = engine.quest_by_id("hard")
        self.assertEqual(engine.player.level, 1)
        self.assertTrue(engine.quest_below_recommended_level(quest))
        # It is OFFERED and can be ACCEPTED anyway — that is the whole point.
        self.assertIn("hard", {q.id for q in engine.board_quests()})
        self.assertTrue(engine.accept_quest("hard"))
        self.assertEqual(engine.quest_status("hard"), quests.ACTIVE)

    def test_the_hint_text_renders_only_when_set(self):
        self.assertEqual(quests.recommended_level_text(_quest("a", recommended_level=7)),
                         "Recommended level 7")
        self.assertEqual(quests.recommended_level_text(_quest("b")), "")

    def test_the_warning_clears_once_the_player_catches_up(self):
        engine = self._engine([_quest("q", recommended_level=5)])
        quest = engine.quest_by_id("q")
        self.assertTrue(engine.quest_below_recommended_level(quest))
        engine.player.level = 5
        self.assertFalse(engine.quest_below_recommended_level(quest))

    def test_a_chain_part_can_carry_a_recommendation(self):
        chain = _chain(parts=2, recommended_level=6)
        engine = self._engine(chain)
        self.assertTrue(engine.quest_below_recommended_level(engine.quest_by_id("mirr_1")))
        self.assertTrue(engine.accept_quest("mirr_1"))   # still not gated


class ChainValidationTests(ChainTestBase):
    def _validate(self, quest_list):
        quests.validate_quests(tuple(quest_list), self.content)

    def test_a_well_formed_chain_validates(self):
        self._validate(_chain(parts=4))

    def test_a_chain_to_an_unknown_quest_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown quest"):
            self._validate([_quest("a", next_quest_id="nope")])

    def test_a_quest_chaining_to_itself_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "chains to itself"):
            self._validate([_quest("a", next_quest_id="a")])

    def test_a_chain_cycle_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "chain cycle"):
            self._validate([_quest("a", chain_id="c", chain_index=1, next_quest_id="b"),
                            _quest("b", chain_id="c", chain_index=2, next_quest_id="a")])

    def test_crossing_into_another_chain_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "chain"):
            self._validate([_quest("a", chain_id="one", chain_index=1, next_quest_id="b"),
                            _quest("b", chain_id="two", chain_index=1)])

    def test_two_quests_unlocking_the_same_part_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "both chain to"):
            self._validate([_quest("a", next_quest_id="c"),
                            _quest("b", next_quest_id="c"),
                            _quest("c")])

    def test_duplicate_part_numbers_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "two part"):
            self._validate([_quest("a", chain_id="c", chain_index=1),
                            _quest("b", chain_id="c", chain_index=1)])

    def test_a_chain_id_without_a_part_number_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "1-based chain_index"):
            self._validate([_quest("a", chain_id="c")])

    def test_a_part_number_without_a_chain_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no chain_id"):
            self._validate([_quest("a", chain_index=2)])

    def test_a_repeatable_story_part_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "cannot repeat"):
            self._validate([_quest("a", next_quest_id="b", repeatable=True),
                            _quest("b")])


class ZoneProgressionGuardTests(ChainTestBase):
    """THE guard: chains are side content and must never gate exploration."""

    def test_the_shipped_spine_quests_have_no_prerequisites(self):
        spine = [q for q in self.content.quests if q.id.startswith("spine_")]
        self.assertEqual(len(spine), 4)
        for quest in spine:
            self.assertEqual(quest.prereq_quest_ids, (), quest.id)
            self.assertEqual(quest.chain_id, "", quest.id)
            self.assertEqual(quest.next_quest_id, "", quest.id)

    def test_every_shipped_spine_quest_is_offered_from_a_fresh_save(self):
        engine = GameEngine(content=self.content, rng=random.Random(0))
        engine.start_new_game("Hero", "fighter")
        offered = {q.id for q in engine.board_quests()}
        for quest in self.content.quests:
            if quest.id.startswith("spine_"):
                self.assertIn(quest.id, offered, quest.id)

    def test_a_chain_never_locks_a_place_or_a_zone(self):
        # A chain expresses ORDER between its own parts and nothing else: no chain
        # field can make a place unreachable, because travel does not consult
        # quests at all. Assert the seam: world.travel/enter_place take no quest.
        import inspect
        from rpg_game.core import world
        for function in (world.travel, world.enter_place, world.available_destinations):
            source = inspect.getsource(function)
            self.assertNotIn("quest", source, function.__name__)

    def test_an_unfinished_chain_leaves_every_zone_reachable(self):
        engine = self._engine(_chain(parts=3))
        engine.accept_quest("mirr_1")            # mid-story
        reachable = {place.id for place in engine.content.places.values()
                     if not place.locked}
        self.assertGreater(len(reachable), 1)
        # entering any of them is refused only by the place's own `locked` flag
        for place_id in sorted(reachable)[:5]:
            engine.enter_place(place_id)
            self.assertEqual(engine.player.current_place_id, place_id)


class BackwardCompatibilityTests(ChainTestBase):
    def test_the_shipped_quests_json_parses_with_no_chain_fields(self):
        for quest in self.content.quests:
            self.assertIsInstance(quest.chain_id, str)
            self.assertIsInstance(quest.chain_index, int)
            self.assertIsInstance(quest.recommended_level, int)

    def test_parse_quests_defaults_every_chain_field(self):
        parsed = quests.parse_quests({"quests": [{
            "id": "old", "title": "Old", "text": "t",
            "objective": {"kind": "open_chests", "count": 1},
        }]})
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].chain_id, "")
        self.assertEqual(parsed[0].chain_index, 0)
        self.assertEqual(parsed[0].next_quest_id, "")
        self.assertEqual(parsed[0].recommended_level, 0)

    def test_chains_need_no_save_version_bump(self):
        # Chain progress IS quest status, which already round-trips (B135a).
        engine = self._engine(_chain(parts=3))
        self._finish(engine, "mirr_1")
        data = persistence.serialize_player(engine.player)
        restored = persistence.deserialize_player(data, default_place_id="hordanita")
        self.assertEqual(quests.status_of(restored, "mirr_1"), quests.TURNED_IN)
        self.assertEqual(quests.status_of(restored, "mirr_2"), quests.AVAILABLE)
        self.assertEqual(persistence.SAVE_VERSION, 2)

    def test_a_pre_chain_save_resumes_a_chain_correctly(self):
        engine = self._engine(_chain(parts=3))
        self._finish(engine, "mirr_1")
        data = persistence.serialize_player(engine.player)
        restored = persistence.deserialize_player(data, default_place_id="hordanita")
        chain = list(engine.all_quests())
        waiting = quests.new_chain_offers(restored, chain)
        self.assertEqual([q.id for q in waiting], ["mirr_2"])


if __name__ == "__main__":
    unittest.main()
