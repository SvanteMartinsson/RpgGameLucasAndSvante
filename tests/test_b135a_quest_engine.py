"""B135a: the quest engine — data model, state, progress hooks, rewards.

Locks: each objective kind ticks on ITS hook and no other; a finished quest can be
handed in; rewards pay exactly ONCE; prerequisites are respected; a pre-quest save
loads with everything available (no SAVE_VERSION bump needed); and load-time
validation rejects unknown kinds/ids and broken prereq chains instead of failing
silently.

Content-free by design: quests are built inline here, so these tests lock the
ENGINE and stay valid whatever B135d authors.
"""

import random
import unittest

from rpg_game.core import inventory, persistence, quests, store
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine


def _quest(qid="q", kind="kill_enemy", target="giant_rat", count=1, rewards=(),
           prereqs=(), repeatable=False, giver="board", zone=""):
    return quests.Quest(
        id=qid, title=f"Title {qid}", text="Some flavour text.",
        giver_kind=giver,
        objective=quests.QuestObjective(kind=kind, target=target, count=count),
        rewards=tuple(rewards), zone=zone,
        prereq_quest_ids=tuple(prereqs), repeatable=repeatable,
    )


class QuestEngineTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = load_content()

    def _engine(self, quest_list, seed=0):
        """An engine whose content carries exactly `quest_list`."""
        import dataclasses
        content = dataclasses.replace(self.content, quests=tuple(quest_list))
        engine = GameEngine(content=content, rng=random.Random(seed))
        engine.start_new_game("Hero", "fighter")
        return engine


class StateAndAcceptTests(QuestEngineTestBase):
    def test_unknown_quest_reads_as_available_with_no_progress(self):
        engine = self._engine([_quest()])
        self.assertEqual(engine.player.quest_states, {})
        self.assertEqual(engine.quest_status("q"), quests.AVAILABLE)
        self.assertEqual(engine.board_quests(), list(engine.content.quests))

    def test_accept_then_abandon_returns_it_to_the_board(self):
        engine = self._engine([_quest()])
        self.assertTrue(engine.accept_quest("q"))
        self.assertEqual(engine.quest_status("q"), quests.ACTIVE)
        self.assertEqual(engine.board_quests(), [])          # no longer offered
        self.assertTrue(engine.abandon_quest("q"))
        self.assertEqual(engine.quest_status("q"), quests.AVAILABLE)
        self.assertEqual(len(engine.board_quests()), 1)

    def test_accepting_twice_fails(self):
        engine = self._engine([_quest()])
        self.assertTrue(engine.accept_quest("q"))
        self.assertFalse(engine.accept_quest("q"))

    def test_prereq_gates_the_offer_until_the_first_is_turned_in(self):
        first = _quest("first", count=1, rewards=({"kind": "gold", "amount": 5},))
        second = _quest("second", prereqs=("first",))
        engine = self._engine([first, second])
        self.assertEqual([q.id for q in engine.board_quests()], ["first"])
        engine.accept_quest("first")
        # merely completing it is not enough — it must be handed IN
        quests.note_kill(engine.player, engine.content, engine.content.quests,
                         "giant_rat")
        self.assertEqual(engine.quest_status("first"), quests.COMPLETED)
        self.assertEqual([q.id for q in engine.board_quests()], [])
        engine.turn_in_quest("first")
        self.assertEqual([q.id for q in engine.board_quests()], ["second"])


class ProgressHookTests(QuestEngineTestBase):
    def test_kill_enemy_ticks_only_on_its_target(self):
        engine = self._engine([_quest(kind="kill_enemy", target="giant_rat", count=2)])
        engine.accept_quest("q")
        quest = engine.quest_by_id("q")
        quests.note_kill(engine.player, engine.content, engine.content.quests, "wild_dog")
        self.assertEqual(engine.quest_progress(quest), 0)     # wrong species
        quests.note_kill(engine.player, engine.content, engine.content.quests, "giant_rat")
        self.assertEqual(engine.quest_progress(quest), 1)
        quests.note_kill(engine.player, engine.content, engine.content.quests, "giant_rat")
        self.assertEqual(engine.quest_progress(quest), 2)
        self.assertEqual(engine.quest_status("q"), quests.COMPLETED)

    def test_kill_in_zone_ticks_on_the_shell_supplied_zone(self):
        engine = self._engine([_quest(kind="kill_in_zone", target="cainos", count=2)])
        engine.accept_quest("q")
        quest = engine.quest_by_id("q")
        quests.note_kill(engine.player, engine.content, engine.content.quests,
                         "giant_rat", "mork_skog")
        self.assertEqual(engine.quest_progress(quest), 0)     # wrong zone
        quests.note_kill(engine.player, engine.content, engine.content.quests,
                         "giant_rat", "cainos")
        self.assertEqual(engine.quest_progress(quest), 1)

    def test_progress_never_exceeds_the_target(self):
        engine = self._engine([_quest(count=2)])
        engine.accept_quest("q")
        for _ in range(5):
            quests.note_kill(engine.player, engine.content, engine.content.quests,
                             "giant_rat")
        self.assertEqual(engine.quest_progress(engine.quest_by_id("q")), 2)

    def test_an_unaccepted_quest_never_accrues_progress(self):
        engine = self._engine([_quest(count=2)])
        quests.note_kill(engine.player, engine.content, engine.content.quests,
                         "giant_rat")
        self.assertEqual(engine.quest_progress(engine.quest_by_id("q")), 0)
        self.assertEqual(engine.quest_status("q"), quests.AVAILABLE)

    def test_visit_place_ticks_via_enter_place(self):
        place_id = next(iter(self.content.places))
        engine = self._engine([_quest(kind="visit_place", target=place_id)])
        engine.accept_quest("q")
        engine.enter_place(place_id)
        self.assertEqual(engine.quest_status("q"), quests.COMPLETED)

    def test_open_chests_ticks_via_open_chest(self):
        chest_id = next(iter(self.content.chests))
        engine = self._engine([_quest(kind="open_chests", target="", count=1)])
        engine.accept_quest("q")
        result = engine.open_chest(chest_id)
        self.assertTrue(result.success)
        self.assertEqual(engine.quest_status("q"), quests.COMPLETED)

    def test_deliver_item_is_counted_from_the_inventory(self):
        engine = self._engine([_quest(kind="deliver_item", target="hp_potion", count=2)])
        engine.accept_quest("q")
        quest = engine.quest_by_id("q")
        self.assertEqual(engine.quest_progress(quest), 0)
        engine.player.inventory.add_consumable("hp_potion", 2)
        self.assertEqual(engine.quest_progress(quest), 2)
        quests.note_item_acquired(engine.player, engine.content, engine.content.quests)
        self.assertEqual(engine.quest_status("q"), quests.COMPLETED)

    def test_items_owned_before_accepting_still_count(self):
        engine = self._engine([_quest(kind="deliver_item", target="hp_potion", count=1)])
        engine.player.inventory.add_consumable("hp_potion")
        engine.accept_quest("q")           # accept AFTER already holding it
        self.assertEqual(engine.quest_status("q"), quests.COMPLETED)

    def test_kill_hook_rides_the_real_victory_flow(self):
        engine = self._engine([_quest(kind="kill_enemy", target="giant_rat", count=1)])
        engine.accept_quest("q")
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        enemy.hp = 1
        enemy.zone = "cainos"
        result = engine.run_combat_turn(enemy, "attack")
        while result.outcome == "ongoing" and enemy.is_alive:
            result = engine.run_combat_turn(enemy, "attack")
        self.assertEqual(result.outcome, "victory")
        self.assertEqual(engine.quest_status("q"), quests.COMPLETED)
        self.assertTrue(result.quest_events)     # carried on the Quest channel


class TurnInAndRewardTests(QuestEngineTestBase):
    def test_cannot_hand_in_an_unfinished_quest(self):
        engine = self._engine([_quest(count=2, rewards=({"kind": "gold", "amount": 50},))])
        engine.accept_quest("q")
        gold = engine.player.gold
        result = engine.turn_in_quest("q")
        self.assertFalse(result.ok)
        self.assertEqual(engine.player.gold, gold)          # no payout

    def test_rewards_pay_exactly_once(self):
        engine = self._engine([_quest(rewards=({"kind": "gold", "amount": 50},
                                               {"kind": "xp", "amount": 10}))])
        engine.accept_quest("q")
        quests.note_kill(engine.player, engine.content, engine.content.quests, "giant_rat")
        gold_before, xp_before = engine.player.gold, engine.player.xp
        first = engine.turn_in_quest("q")
        self.assertTrue(first.ok)
        self.assertEqual(engine.player.gold, gold_before + 50)
        self.assertEqual(engine.quest_status("q"), quests.TURNED_IN)
        # a second hand-in is refused and pays nothing
        gold_after = engine.player.gold
        second = engine.turn_in_quest("q")
        self.assertFalse(second.ok)
        self.assertEqual(engine.player.gold, gold_after)

    def test_item_reward_uses_the_shared_grant_path(self):
        engine = self._engine([_quest(rewards=({"kind": "item", "item_id": "hp_potion"},))])
        engine.accept_quest("q")
        quests.note_kill(engine.player, engine.content, engine.content.quests, "giant_rat")
        engine.turn_in_quest("q")
        self.assertGreaterEqual(engine.player.inventory.count("hp_potion"), 1)

    def test_weapon_reward_lands_in_owned_weapons(self):
        weapon_id = next(iter(self.content.weapons))
        engine = self._engine([_quest(rewards=({"kind": "item", "item_id": weapon_id},))])
        engine.accept_quest("q")
        quests.note_kill(engine.player, engine.content, engine.content.quests, "giant_rat")
        engine.turn_in_quest("q")
        self.assertIn(weapon_id, engine.player.owned_weapon_ids)

    def test_deliver_item_reward_consumes_the_delivered_items(self):
        engine = self._engine([_quest(kind="deliver_item", target="hp_potion", count=2,
                                      rewards=({"kind": "gold", "amount": 10},))])
        engine.accept_quest("q")
        engine.player.inventory.add_consumable("hp_potion", 3)
        result = engine.turn_in_quest("q")
        self.assertTrue(result.ok)
        self.assertEqual(engine.player.inventory.count("hp_potion"), 1)   # 3 - 2

    def test_shop_discount_reward_is_persistent_and_applied_to_prices(self):
        engine = self._engine([_quest(rewards=({"kind": "shop_discount", "percent": 20},))])
        engine.accept_quest("q")
        quests.note_kill(engine.player, engine.content, engine.content.quests, "giant_rat")
        engine.turn_in_quest("q")
        self.assertEqual(engine.player.shop_discount_pct, 20)
        self.assertEqual(store.buy_price(engine.player, 100), 80)
        # and it caps at 50% however many discounts stack
        engine.player.shop_discount_pct = 90
        self.assertEqual(store.buy_price(engine.player, 100), 50)

    def test_discounted_price_shown_equals_price_charged(self):
        engine = self._engine([])
        engine.player.shop_discount_pct = 25
        place_id = next((pid for pid, p in self.content.places.items()
                         if p.has_store and p.store_inventory), None)
        self.assertIsNotNone(place_id)
        engine.player.current_place_id = place_id
        entry = store.get_store_entries(self.content, place_id,
                                        player=engine.player)[0]
        engine.player.gold = entry.price          # exactly the shown price
        result = store.buy_item(engine.player, self.content, entry.id)
        self.assertTrue(result.success, result.message)
        self.assertEqual(engine.player.gold, 0)   # charged exactly what was shown

    def test_flag_reward_records_a_flag(self):
        engine = self._engine([_quest(rewards=({"kind": "flag", "flag": "met_warden"},))])
        engine.accept_quest("q")
        quests.note_kill(engine.player, engine.content, engine.content.quests, "giant_rat")
        engine.turn_in_quest("q")
        self.assertIn("met_warden", engine.player.quest_flags)

    def test_repeatable_quest_can_be_taken_again_after_turn_in(self):
        engine = self._engine([_quest(rewards=({"kind": "gold", "amount": 5},),
                                      repeatable=True)])
        engine.accept_quest("q")
        quests.note_kill(engine.player, engine.content, engine.content.quests, "giant_rat")
        engine.turn_in_quest("q")
        self.assertEqual(len(engine.board_quests()), 1)       # offered again
        self.assertTrue(engine.accept_quest("q"))
        self.assertEqual(engine.quest_progress(engine.quest_by_id("q")), 0)  # reset


class SaveCompatTests(QuestEngineTestBase):
    def test_quest_state_round_trips(self):
        engine = self._engine([_quest(count=3)])
        engine.accept_quest("q")
        quests.note_kill(engine.player, engine.content, engine.content.quests, "giant_rat")
        engine.player.shop_discount_pct = 15
        engine.player.quest_flags.add("f")
        data = persistence.serialize_player(engine.player)
        restored = persistence.deserialize_player(data)
        self.assertEqual(restored.quest_states["q"],
                         {"status": quests.ACTIVE, "progress": 1})
        self.assertEqual(restored.shop_discount_pct, 15)
        self.assertIn("f", restored.quest_flags)

    def test_pre_quest_save_loads_with_everything_available(self):
        # A save written BEFORE quests existed: drop the three new keys entirely,
        # exactly as an old file on disk would look. No SAVE_VERSION bump needed
        # because each from_json applies its own default for a missing key.
        engine = self._engine([_quest()])
        data = persistence.serialize_player(engine.player)
        for key in ("quest_states", "shop_discount_pct", "quest_flags"):
            data.pop(key, None)
        restored = persistence.deserialize_player(data)
        self.assertEqual(restored.quest_states, {})
        self.assertEqual(restored.shop_discount_pct, 0)
        self.assertEqual(restored.quest_flags, set())
        # ... and the engine treats that as "every quest available"
        engine.state.player = restored
        self.assertEqual(engine.quest_status("q"), quests.AVAILABLE)
        self.assertEqual(len(engine.board_quests()), 1)

    def test_legacy_save_still_migrates_through_the_version_path(self):
        engine = self._engine([_quest()])
        data = persistence.serialize_player(engine.player)
        data.pop("quest_states", None)
        migrated = persistence.migrate_player_data(dict(data), 1)
        restored = persistence.deserialize_player(migrated)
        self.assertEqual(restored.quest_states, {})


class ValidationTests(QuestEngineTestBase):
    def _validate(self, row):
        parsed = quests.parse_quests({"quests": [row]})
        quests.validate_quests(parsed, self.content)

    def _row(self, **over):
        row = {"id": "v", "title": "T", "text": "x", "giver_kind": "board",
               "objective": {"kind": "kill_enemy", "target": "giant_rat", "count": 1},
               "rewards": [{"kind": "gold", "amount": 5}]}
        row.update(over)
        return row

    def test_a_valid_row_passes(self):
        self._validate(self._row())

    def test_unknown_objective_kind_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown objective kind"):
            self._validate(self._row(objective={"kind": "befriend", "target": "x"}))

    def test_unknown_enemy_target_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown kill_enemy"):
            self._validate(self._row(objective={"kind": "kill_enemy",
                                                "target": "no_such_beast", "count": 1}))

    def test_unknown_place_target_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown visit_place"):
            self._validate(self._row(objective={"kind": "visit_place",
                                                "target": "nowhere", "count": 1}))

    def test_unknown_item_target_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown deliver_item"):
            self._validate(self._row(objective={"kind": "deliver_item",
                                                "target": "no_such_item", "count": 1}))

    def test_unknown_zone_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown zone"):
            self._validate(self._row(objective={"kind": "kill_in_zone",
                                                "target": "atlantis", "count": 1}))

    def test_unknown_reward_kind_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown reward kind"):
            self._validate(self._row(rewards=[{"kind": "kingdom"}]))

    def test_unknown_reward_item_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown item"):
            self._validate(self._row(rewards=[{"kind": "item", "item_id": "nope"}]))

    def test_non_tome_unlock_tome_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-tome"):
            self._validate(self._row(rewards=[{"kind": "unlock_tome",
                                               "item_id": "hp_potion"}]))

    def test_out_of_range_discount_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "shop_discount must be"):
            self._validate(self._row(rewards=[{"kind": "shop_discount", "percent": 90}]))

    def test_zero_count_objective_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "count must be"):
            self._validate(self._row(objective={"kind": "kill_enemy",
                                                "target": "giant_rat", "count": 0}))

    def test_unknown_prereq_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "requires unknown quest"):
            self._validate(self._row(prereq_quest_ids=["ghost_quest"]))

    def test_duplicate_ids_are_rejected(self):
        parsed = quests.parse_quests({"quests": [self._row(), self._row()]})
        with self.assertRaisesRegex(ValueError, "duplicate quest id"):
            quests.validate_quests(parsed, self.content)

    def test_prereq_cycle_is_rejected(self):
        rows = [self._row(id="a", prereq_quest_ids=["b"]),
                self._row(id="b", prereq_quest_ids=["a"])]
        parsed = quests.parse_quests({"quests": rows})
        with self.assertRaisesRegex(ValueError, "cycle"):
            quests.validate_quests(parsed, self.content)

    def test_shipped_quest_data_is_valid(self):
        # load_content() validates quests.json; this asserts the real file passes.
        quests.validate_quests(self.content.quests, self.content)

    def test_zone_vocabulary_is_the_ground_themes_not_spawn_area_ids(self):
        # STEG 0 correction: spawn-AREA ids are sub-areas ("skog_beast_1"), while
        # the shell tags a spawn with a GROUND THEME. Validating against the wrong
        # one would accept a kill_in_zone target the hook could never match.
        self.assertEqual(set(self.content.zone_names),
                         {"cainos", "mork_skog", "cursed_mire", "grave_heath"})
        self.assertEqual(quests._known_zones(self.content),
                         set(self.content.zone_names))
        for zone in self.content.zone_names:
            self._validate(self._row(objective={"kind": "kill_in_zone",
                                                "target": zone, "count": 3}))
        # a sub-area id is NOT a valid zone
        with self.assertRaisesRegex(ValueError, "unknown zone"):
            self._validate(self._row(objective={"kind": "kill_in_zone",
                                                "target": "skog_beast", "count": 3}))


class GrantItemTests(QuestEngineTestBase):
    def test_grant_item_picks_the_right_bucket(self):
        engine = self._engine([])
        player = engine.player
        weapon_id = next(iter(self.content.weapons))
        gear_id = next(iter(self.content.gear_items))
        self.assertEqual(inventory.grant_item(player, self.content, weapon_id), "weapon")
        self.assertEqual(inventory.grant_item(player, self.content, gear_id), "gear")
        self.assertEqual(inventory.grant_item(player, self.content, "hp_potion"),
                         "consumable")
        self.assertIn(weapon_id, player.owned_weapon_ids)
        self.assertIn(gear_id, player.owned_gear_ids)
        self.assertGreaterEqual(player.inventory.count("hp_potion"), 1)

    def test_owned_items_are_not_duplicated(self):
        engine = self._engine([])
        weapon_id = next(iter(self.content.weapons))
        inventory.grant_item(engine.player, self.content, weapon_id)
        before = engine.player.owned_weapon_ids
        inventory.grant_item(engine.player, self.content, weapon_id)
        self.assertEqual(engine.player.owned_weapon_ids, before)


if __name__ == "__main__":
    unittest.main()
