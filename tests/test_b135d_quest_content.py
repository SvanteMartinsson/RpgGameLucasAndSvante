"""B135d: the authored quest content — 4 zone-intro "spine" quests + 5 side
quests with mixed rewards.

Locks the CONTENT rules (the engine itself is locked by test_b135a):
- four spine quests, one per zone, and none of them has a prerequisite, so no
  zone's introduction can ever be locked behind another zone. Quests are side
  content: they must not gate zone progression.
- every objective kind is exercised, and the reward mix includes the two unique
  kinds Lucas asked for (an unlock_tome and a shop_discount).
- level/zone appropriateness: a quest's target must actually be obtainable in the
  zone the quest advertises, so no objective sends the player somewhere their
  level cannot survive.
- reward value rises with zone difficulty.

The zone->tile rule is READ from core_zone.json's ground_themes here rather than
hardcoded, so this test re-measures if Lucas redraws the map.
"""

import json
import os
import unittest

from rpg_game.core import quests
from rpg_game.core.data_loader import load_content

_ZONE_ORDER = ("cainos", "mork_skog", "cursed_mire", "grave_heath")
_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "rpg_game", "data", "maps", "core_zone.json")


def _theme_rules():
    with open(_DATA, encoding="utf-8") as handle:
        return json.load(handle)["ground_themes"]


def _theme_for(rules, x, y):
    """core_zone's ground-theme rule: a y-band wins over the x-bands (the heath
    runs along the south edge across every column)."""
    for rule in rules:
        if "min_tile_y" in rule and y >= rule["min_tile_y"]:
            return rule["theme"]
    for rule in rules:
        if "min_tile_y" in rule:
            continue
        if (("min_tile_x" not in rule or x >= rule["min_tile_x"])
                and ("max_tile_x" not in rule or x <= rule["max_tile_x"])):
            return rule["theme"]
    return ""


class QuestContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = load_content()
        cls.quests = cls.content.quests
        rules = _theme_rules()
        # zone -> the enemy ids that spawn there, and the zone's level band
        cls.zone_enemies = {zone: set() for zone in _ZONE_ORDER}
        cls.zone_band = {zone: [] for zone in _ZONE_ORDER}
        for area in cls.content.spawn_areas:
            x0, y0, x1, y1 = area.rect
            zone = _theme_for(rules, (x0 + x1) // 2, (y0 + y1) // 2)
            if zone not in cls.zone_enemies:
                continue
            for enemy_id, _weight in area.enemies:
                cls.zone_enemies[zone].add(enemy_id)
            if area.level_min or area.level_max:
                cls.zone_band[zone].append(area.level_min or area.level_max)

    def _by_id(self, quest_id):
        return next(q for q in self.quests if q.id == quest_id)

    def _spine(self):
        return [q for q in self.quests if q.id.startswith("spine_")]

    def _side(self):
        return [q for q in self.quests if q.id.startswith("side_")]

    # -- shape ---------------------------------------------------------------

    def test_nine_quests_four_spine_five_side(self):
        self.assertEqual(len(self.quests), 9)
        self.assertEqual(len(self._spine()), 4)
        self.assertEqual(len(self._side()), 5)

    def test_one_spine_quest_per_zone(self):
        zones = [q.objective.target for q in self._spine()]
        self.assertEqual(sorted(zones), sorted(_ZONE_ORDER))
        for quest in self._spine():
            self.assertEqual(quest.objective.kind, "kill_in_zone")

    def test_every_quest_has_authored_title_and_text(self):
        for quest in self.quests:
            self.assertTrue(quest.title.strip(), quest.id)
            self.assertGreater(len(quest.text.strip()), 40,
                               f"{quest.id} text reads like a stub")

    def test_all_quests_come_from_the_board_in_s1(self):
        # S1 has no NPC givers (that needs art) — everything is board-given.
        for quest in self.quests:
            self.assertEqual(quest.giver_kind, "board", quest.id)

    # -- "quests never gate zone progression" --------------------------------

    def test_no_spine_quest_has_a_prerequisite(self):
        # The concrete guarantee: every zone's introduction is offered on its own,
        # so no zone's content can sit behind another zone's quest.
        for quest in self._spine():
            self.assertEqual(quest.prereq_quest_ids, (), quest.id)

    def test_prereqs_point_at_real_quests_and_stay_shallow(self):
        ids = {q.id for q in self.quests}
        for quest in self.quests:
            for required in quest.prereq_quest_ids:
                self.assertIn(required, ids)
            self.assertLessEqual(len(quest.prereq_quest_ids), 1,
                                 f"{quest.id}: S1 has no quest chains")

    # -- coverage ------------------------------------------------------------

    def test_every_objective_kind_is_exercised(self):
        used = {q.objective.kind for q in self.quests}
        self.assertEqual(used, set(quests.OBJECTIVE_KINDS))

    def test_reward_mix_includes_the_unique_kinds(self):
        kinds = {r["kind"] for q in self.quests for r in q.rewards}
        self.assertIn("unlock_tome", kinds)
        self.assertIn("shop_discount", kinds)
        # ... and the ordinary ones are still the backbone
        self.assertIn("gold", kinds)
        self.assertIn("xp", kinds)
        self.assertIn("item", kinds)

    def test_every_quest_pays_something(self):
        for quest in self.quests:
            self.assertTrue(quest.rewards, quest.id)

    def test_the_tome_reward_is_a_real_tome(self):
        quest = self._by_id("side_hollow_worg")
        reward = next(r for r in quest.rewards if r["kind"] == "unlock_tome")
        self.assertIn(reward["item_id"], self.content.items)

    def test_tome_rewards_are_not_class_locked(self):
        """A board quest is offered to every class, so a class-gated tome would be
        a dud reward for five of six classes (tome_power_slash is rogue-only —
        measured: it is the only class-gated tome of the twelve). Any unlock_tome
        reward must therefore be learnable by any class."""
        for quest in self.quests:
            for reward in quest.rewards:
                if reward["kind"] != "unlock_tome":
                    continue
                tome = self.content.items[reward["item_id"]]
                self.assertFalse(tome.class_req,
                                 f"{quest.id} rewards a {tome.class_req}-only tome")
                self.assertFalse(tome.weapon_category_req,
                                 f"{quest.id} rewards a weapon-gated tome")

    def test_tome_reward_level_fits_the_quest_zone(self):
        quest = self._by_id("side_hollow_worg")
        reward = next(r for r in quest.rewards if r["kind"] == "unlock_tome")
        tome = self.content.items[reward["item_id"]]
        band = min(self.zone_band[quest.zone])
        self.assertLessEqual(tome.level_req, max(band, 1) + 4,
                             "tome is far above the zone's level band")

    # -- level / zone appropriateness ----------------------------------------

    def test_kill_targets_spawn_in_the_zone_the_quest_advertises(self):
        for quest in self.quests:
            if quest.objective.kind != "kill_enemy":
                continue
            self.assertIn(quest.objective.target,
                          self.zone_enemies[quest.zone],
                          f"{quest.id} targets an enemy that does not spawn in "
                          f"{quest.zone}")

    def test_delivery_items_drop_from_enemies_in_the_advertised_zone(self):
        for quest in self.quests:
            if quest.objective.kind != "deliver_item":
                continue
            droppers = {enemy.id for enemy in self.content.enemies.values()
                        if any(row["item_id"] == quest.objective.target
                               for row in enemy.loot_table)}
            in_zone = droppers & self.zone_enemies[quest.zone]
            self.assertTrue(in_zone,
                            f"{quest.id}: nothing in {quest.zone} drops "
                            f"{quest.objective.target}")

    def test_kill_in_zone_targets_are_real_zones(self):
        for quest in self.quests:
            if quest.objective.kind == "kill_in_zone":
                self.assertIn(quest.objective.target, self.content.zone_names)

    def test_zone_hints_are_real_zones(self):
        for quest in self.quests:
            if quest.zone:
                self.assertIn(quest.zone, self.content.zone_names, quest.id)

    def test_spine_rewards_rise_with_zone_difficulty(self):
        """A later zone's introduction must pay more than an earlier one's."""
        def value(quest):
            gold = sum(int(r.get("amount", 0)) for r in quest.rewards
                       if r["kind"] == "gold")
            xp = sum(int(r.get("amount", 0)) for r in quest.rewards
                     if r["kind"] == "xp")
            return gold + xp
        spine_by_zone = {q.objective.target: q for q in self._spine()}
        values = [value(spine_by_zone[zone]) for zone in _ZONE_ORDER]
        self.assertEqual(values, sorted(values), f"spine payouts not ordered: {values}")
        # and the zones themselves really are ordered by level
        bands = [min(self.zone_band[zone]) for zone in _ZONE_ORDER]
        self.assertEqual(bands, sorted(bands), f"zone level bands not ordered: {bands}")

    def test_no_quest_objective_asks_for_a_boss(self):
        for quest in self.quests:
            if quest.objective.kind == "kill_enemy":
                enemy = self.content.enemies[quest.objective.target]
                self.assertFalse(enemy.boss,
                                 f"{quest.id} sends the player at a boss")


class QuestContentPlayableTests(unittest.TestCase):
    """The authored content works through the real engine, not just the schema."""

    @classmethod
    def setUpClass(cls):
        cls.content = load_content()

    def _engine(self):
        import random
        from rpg_game.core.game import GameEngine
        engine = GameEngine(content=self.content, rng=random.Random(3))
        engine.start_new_game("Hero", "fighter")
        return engine

    def test_the_starting_board_offers_the_spine_quests_but_not_the_gated_one(self):
        engine = self._engine()
        offered = {q.id for q in engine.board_quests()}
        self.assertIn("spine_cainos", offered)
        self.assertIn("spine_grave_heath", offered)      # never gated
        self.assertNotIn("side_hollow_worg", offered)    # needs its prereq

    def test_a_zone_intro_quest_can_be_completed_and_handed_in(self):
        engine = self._engine()
        self.assertTrue(engine.accept_quest("spine_cainos"))
        quest = engine.quest_by_id("spine_cainos")
        for _ in range(quest.objective.count):
            quests.note_kill(engine.player, self.content, self.content.quests,
                             "giant_rat", "cainos")
        self.assertTrue(engine.quest_is_ready(quest))
        gold = engine.player.gold
        result = engine.turn_in_quest("spine_cainos")
        self.assertTrue(result.ok)
        self.assertEqual(engine.player.gold, gold + 40)

    def test_the_discount_quest_actually_cheapens_the_shop(self):
        from rpg_game.core import store
        engine = self._engine()
        engine.accept_quest("side_goblin_scrap")
        engine.player.inventory.add_consumable("iron_scrap", 4)
        result = engine.turn_in_quest("side_goblin_scrap")
        self.assertTrue(result.ok)
        self.assertEqual(engine.player.shop_discount_pct, 10)
        self.assertEqual(store.buy_price(engine.player, 200), 180)

    def _clear_heath_prereq(self, engine):
        engine.accept_quest("spine_grave_heath")
        for _ in range(8):
            quests.note_kill(engine.player, self.content, self.content.quests,
                             "ghoul", "grave_heath")
        engine.turn_in_quest("spine_grave_heath")

    def test_the_tome_quest_teaches_the_skill_to_any_class(self):
        quest_reward = next(r for r in self.content.quests
                            if r.id == "side_hollow_worg").rewards
        tome_id = next(r["item_id"] for r in quest_reward
                       if r["kind"] == "unlock_tome")
        tome = self.content.items[tome_id]
        for player_class in ("fighter", "mage", "cleric"):
            import random
            from rpg_game.core.game import GameEngine
            engine = GameEngine(content=self.content, rng=random.Random(3))
            engine.start_new_game("Hero", player_class)
            self._clear_heath_prereq(engine)
            self.assertIn("side_hollow_worg", {q.id for q in engine.board_quests()})
            engine.accept_quest("side_hollow_worg")
            engine.player.level = max(engine.player.level, tome.level_req)
            quests.note_kill(engine.player, self.content, self.content.quests,
                             "hollow_worg", "grave_heath")
            result = engine.turn_in_quest("side_hollow_worg")
            self.assertTrue(result.ok)
            self.assertTrue(any("learned" in line for line in result.events),
                            f"{player_class}: {result.events}")
            self.assertIn(tome.teaches, engine.player.learned_skill_ids)

    def test_an_ineligible_player_is_handed_the_tome_instead_of_losing_it(self):
        # Below the tome's level requirement the reward must not evaporate.
        import random
        from rpg_game.core.game import GameEngine
        engine = GameEngine(content=self.content, rng=random.Random(3))
        engine.start_new_game("Hero", "fighter")
        self._clear_heath_prereq(engine)
        engine.accept_quest("side_hollow_worg")
        engine.player.level = 1                     # too low to read it
        quests.note_kill(engine.player, self.content, self.content.quests,
                         "hollow_worg", "grave_heath")
        result = engine.turn_in_quest("side_hollow_worg")
        self.assertTrue(result.ok)
        tome_id = next(r["item_id"] for r in engine.quest_by_id("side_hollow_worg").rewards
                       if r["kind"] == "unlock_tome")
        self.assertGreaterEqual(engine.player.inventory.count(tome_id), 1)


if __name__ == "__main__":
    unittest.main()
