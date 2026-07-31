"""B135e: the repeatable bounty board.

Bounties are GENERATED, not authored: each of MAX_BOUNTY_SLOTS slots rolls a
species from the player's current zone and asks for N of them, scaled to the
zone's level band. Handing one in rerolls THAT slot.

Locks:
- determinism: the board is a pure function of the save (same state -> same board,
  survives a save/load round trip) and rolling one consumes NO engine rng draw,
  so encounter/loot/map streams are untouched (the CLAUDE.md rule).
- the rails: at most MAX_BOUNTY_SLOTS at a time, distinct species, a slot never
  re-posts what it just paid out, and targets/zones are real.
- the B62 ECONOMY rail: bounty gold is a bonus on grinding, never the optimal
  income. Asserted numerically per zone.
- bounties ride the SAME pipeline as authored quests (progress hooks, turn-in,
  rewards) — no parallel path.
"""

import random
import unittest

from rpg_game.core import persistence, quests
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine
from rpg_game.tools import check_bounty_economy


class BountyTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = load_content()

    def _engine(self, seed=0, level=1):
        engine = GameEngine(content=self.content, rng=random.Random(seed))
        engine.start_new_game("Hero", "fighter")
        engine.player.level = level
        return engine

    def _complete(self, engine, bounty):
        for _ in range(bounty.objective.count):
            quests.note_kill(engine.player, engine.content, engine.all_quests(),
                             bounty.objective.target, bounty.zone)


class BountyGenerationTests(BountyTestBase):
    def test_the_board_offers_exactly_the_slot_count(self):
        engine = self._engine()
        self.assertEqual(len(engine.bounty_quests()), quests.MAX_BOUNTY_SLOTS)

    def test_slots_post_distinct_species(self):
        engine = self._engine()
        targets = [q.objective.target for q in engine.bounty_quests()]
        self.assertEqual(len(set(targets)), len(targets))

    def test_bounties_are_marked_repeatable_and_bounty_given(self):
        engine = self._engine()
        for bounty in engine.bounty_quests():
            self.assertTrue(bounty.repeatable)
            self.assertEqual(bounty.giver_kind, "bounty")

    def test_targets_really_spawn_in_the_bounty_zone(self):
        for level in (1, 5, 8, 12):
            engine = self._engine(level=level)
            for bounty in engine.bounty_quests():
                roster = self.content.zone_enemies[bounty.zone]
                self.assertIn(bounty.objective.target, roster)

    def test_no_bounty_ever_targets_a_boss(self):
        for level in (1, 4, 6, 9, 12, 20):
            engine = self._engine(level=level)
            for bounty in engine.bounty_quests():
                self.assertFalse(self.content.enemies[bounty.objective.target].boss)

    def test_the_zone_follows_the_players_level_band(self):
        for level, expected in ((1, "cainos"), (6, "mork_skog")):
            engine = self._engine(level=level)
            self.assertEqual(quests.bounty_zone_for(engine.player, self.content),
                             expected)

    def test_a_high_level_player_still_gets_the_toughest_zone(self):
        engine = self._engine(level=40)
        zone = quests.bounty_zone_for(engine.player, self.content)
        self.assertEqual(zone, "grave_heath")
        self.assertEqual(len(engine.bounty_quests()), quests.MAX_BOUNTY_SLOTS)

    def test_counts_stay_inside_the_authored_range(self):
        for level in (1, 5, 8, 12):
            engine = self._engine(level=level)
            for bounty in engine.bounty_quests():
                self.assertGreaterEqual(bounty.objective.count, quests.BOUNTY_MIN_COUNT)
                self.assertLessEqual(bounty.objective.count, quests.BOUNTY_MAX_COUNT)

    def test_the_board_is_offered_via_the_engine_board_api(self):
        engine = self._engine()
        ids = {q.id for q in engine.board_quests("bounty")}
        self.assertEqual(ids, {q.id for q in engine.bounty_quests()})
        # ... and the authored notices are a DIFFERENT set
        self.assertFalse(ids & {q.id for q in engine.board_quests("board")})


class BountyDeterminismTests(BountyTestBase):
    def test_the_same_state_yields_the_same_board(self):
        engine = self._engine()
        first = [(q.id, q.title, q.objective.count) for q in engine.bounty_quests()]
        second = [(q.id, q.title, q.objective.count) for q in engine.bounty_quests()]
        self.assertEqual(first, second)

    def test_two_engines_with_different_rng_seeds_agree(self):
        """The board must not depend on the engine rng at all."""
        a = self._engine(seed=1)
        b = self._engine(seed=99999)
        self.assertEqual([q.title for q in a.bounty_quests()],
                         [q.title for q in b.bounty_quests()])

    def test_rolling_the_board_consumes_no_engine_rng_draw(self):
        engine = self._engine(seed=7)
        before = engine.rng.getstate()
        for _ in range(5):
            engine.bounty_quests()
        self.assertEqual(engine.rng.getstate(), before)

    def test_the_board_survives_a_save_load_round_trip(self):
        engine = self._engine()
        bounty = engine.bounty_quests()[0]
        engine.accept_quest(bounty.id)
        self._complete(engine, bounty)
        engine.turn_in_quest(bounty.id)
        expected = [q.title for q in engine.bounty_quests()]

        data = persistence.serialize_player(engine.player)
        restored = persistence.deserialize_player(data)
        other = self._engine()
        other.state.player = restored
        self.assertEqual([q.title for q in other.bounty_quests()], expected)
        self.assertEqual(restored.bounty_rolls, engine.player.bounty_rolls)

    def test_a_pre_bounty_save_loads_with_a_fresh_board(self):
        engine = self._engine()
        data = persistence.serialize_player(engine.player)
        data.pop("bounty_rolls", None)          # an old file has no such key
        restored = persistence.deserialize_player(data)
        self.assertEqual(restored.bounty_rolls, {})
        engine.state.player = restored
        self.assertEqual(len(engine.bounty_quests()), quests.MAX_BOUNTY_SLOTS)


class BountyLifecycleTests(BountyTestBase):
    def test_a_bounty_progresses_and_pays_through_the_normal_pipeline(self):
        engine = self._engine()
        bounty = engine.bounty_quests()[0]
        self.assertTrue(engine.accept_quest(bounty.id))
        # partial progress ticks on the shared kill hook
        quests.note_kill(engine.player, engine.content, engine.all_quests(),
                         bounty.objective.target, bounty.zone)
        self.assertEqual(engine.quest_progress(engine.quest_by_id(bounty.id)), 1)
        self._complete(engine, bounty)
        gold = engine.player.gold
        result = engine.turn_in_quest(bounty.id)
        self.assertTrue(result.ok)
        expected = sum(int(r["amount"]) for r in bounty.rewards if r["kind"] == "gold")
        self.assertEqual(engine.player.gold, gold + expected)

    def test_handing_in_rerolls_only_that_slot(self):
        engine = self._engine()
        before = [q.objective.target for q in engine.bounty_quests()]
        bounty = engine.bounty_quests()[1]
        engine.accept_quest(bounty.id)
        self._complete(engine, bounty)
        engine.turn_in_quest(bounty.id)
        after = [q.objective.target for q in engine.bounty_quests()]
        self.assertEqual(before[0], after[0])          # untouched slots stay
        self.assertEqual(before[2], after[2])
        self.assertNotEqual(before[1], after[1])       # the handed-in one rerolled

    def test_a_slot_never_reposts_the_species_it_just_paid_out(self):
        engine = self._engine()
        previous = None
        for _ in range(8):
            bounty = engine.bounty_quests()[0]
            self.assertNotEqual(bounty.objective.target, previous)
            previous = bounty.objective.target
            engine.accept_quest(bounty.id)
            self._complete(engine, bounty)
            engine.turn_in_quest(bounty.id)

    def test_a_rerolled_slot_starts_with_clean_progress(self):
        engine = self._engine()
        bounty = engine.bounty_quests()[0]
        engine.accept_quest(bounty.id)
        self._complete(engine, bounty)
        engine.turn_in_quest(bounty.id)
        fresh = engine.bounty_quests()[0]
        self.assertEqual(engine.quest_status(fresh.id), quests.AVAILABLE)
        self.assertEqual(engine.quest_progress(fresh), 0)

    def test_at_most_the_slot_count_can_be_active_at_once(self):
        engine = self._engine()
        for bounty in engine.bounty_quests():
            engine.accept_quest(bounty.id)
        active = [q for q in engine.tracked_quests() if q.giver_kind == "bounty"]
        self.assertLessEqual(len(active), quests.MAX_BOUNTY_SLOTS)
        # and no fourth bounty is on offer while all slots are taken
        self.assertEqual(engine.bounty_quests(), [])

    def test_an_accepted_bounty_keeps_its_species_while_you_work_on_it(self):
        engine = self._engine()
        bounty = engine.bounty_quests()[0]
        engine.accept_quest(bounty.id)
        tracked = next(q for q in engine.tracked_quests() if q.id == bounty.id)
        self.assertEqual(tracked.objective.target, bounty.objective.target)
        self.assertEqual(tracked.objective.count, bounty.objective.count)

    def test_a_bounty_kill_of_the_wrong_species_does_not_count(self):
        engine = self._engine()
        bounty = engine.bounty_quests()[0]
        other = next(e for e in self.content.zone_enemies[bounty.zone]
                     if e != bounty.objective.target)
        engine.accept_quest(bounty.id)
        quests.note_kill(engine.player, engine.content, engine.all_quests(),
                         other, bounty.zone)
        self.assertEqual(engine.quest_progress(engine.quest_by_id(bounty.id)), 0)


class BountyEconomyTests(BountyTestBase):
    """The B62 rail: bounties give grinding MEANING, not income."""

    def test_the_economy_check_passes_for_every_zone(self):
        rows = check_bounty_economy.rows(self.content)
        self.assertTrue(rows)
        zones = {row[0] for row in rows}
        self.assertEqual(zones, set(self.content.zone_bands))
        for zone, _band, bounty, _count, _gold, up_kill, up_fight in rows:
            self.assertLess(up_kill, check_bounty_economy.FAIL_UPLIFT,
                            f"{zone}/{bounty.objective.target}: bounty gold would "
                            f"beat grinding ({up_kill:.0%} per target kill)")
            self.assertLess(up_fight, check_bounty_economy.FAIL_UPLIFT,
                            f"{zone}/{bounty.objective.target}: {up_fight:.0%} per fight")

    def test_the_uplift_stays_within_the_design_target(self):
        rows = check_bounty_economy.rows(self.content)
        worst = max(row[5] for row in rows)
        self.assertLessEqual(worst, check_bounty_economy.TARGET_UPLIFT,
                             f"worst per-kill uplift {worst:.0%} exceeds the "
                             f"{check_bounty_economy.TARGET_UPLIFT:.0%} design target")

    def test_the_bonus_fraction_is_well_under_one(self):
        # The rail itself: the reward is a FRACTION of what the kills already pay.
        self.assertLess(quests.BOUNTY_BONUS_FRACTION, 0.5)
        self.assertLess(quests.BOUNTY_XP_FRACTION, 0.5)

    def test_a_repeatable_bounty_pays_less_per_kill_than_a_one_shot_quest(self):
        """One-shot authored quests may be rich because they cannot be farmed; a
        repeatable bounty must be leaner per kill than the zone's spine quest."""
        engine = self._engine()
        spine = engine.quest_by_id("spine_cainos")
        spine_gold = sum(int(r["amount"]) for r in spine.rewards if r["kind"] == "gold")
        spine_per_kill = spine_gold / spine.objective.count
        for bounty in engine.bounty_quests():
            gold = sum(int(r["amount"]) for r in bounty.rewards if r["kind"] == "gold")
            self.assertLess(gold / bounty.objective.count, spine_per_kill,
                            f"{bounty.title} out-pays the one-shot spine quest")

    def test_bounty_rewards_are_only_gold_and_xp(self):
        # No repeatable source of items/tomes/discounts — those stay one-shot.
        for level in (1, 6, 9, 12):
            engine = self._engine(level=level)
            for bounty in engine.bounty_quests():
                kinds = {r["kind"] for r in bounty.rewards}
                self.assertEqual(kinds, {"gold", "xp"}, bounty.title)


if __name__ == "__main__":
    unittest.main()
