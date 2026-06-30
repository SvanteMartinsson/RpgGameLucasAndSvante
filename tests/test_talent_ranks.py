"""B36: talent ranks 1-3. Owned talents can be upgraded instead of only learned.

Locks RELATIONS (rank 2 = 1.25x rank 1, rank 3 = 1.5x AND +1 round duration,
binary nodes cap at rank 1) and the deterministic node classification, not the
placeholder multiplier values themselves.
"""

import unittest

from rpg_game.core import combat, data_loader, persistence, progression
from rpg_game.core.game import GameEngine


DAMAGE_TYPES = {"physical", "fire", "frost", "holy", "poison"}


def _classify(node, actions):
    """The deterministic bucket rule (mirrors the data build)."""
    if node.node_type == "active":
        action = actions.get(node.action_id)
        if action is None:
            return "binary"
        for effect in action.effects:
            if effect.type in {"damage", "instant_damage", "drain", "instant_heal", "heal"}:
                return "active"
            if effect.type == "apply_status":
                st, tag = effect.status_type, effect.tag
                if st in DAMAGE_TYPES or tag in DAMAGE_TYPES or st in {"regen", "reflect"} or effect.scale == "spell":
                    return "active"
        return "binary"
    # passive: immunity-only is binary, any numeric magnitude is scalable
    if {effect.type for effect in node.effects} == {"immunity"}:
        return "binary"
    return "passive"


class TalentMaxRankDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = data_loader.load_content()

    def test_every_node_max_rank_matches_its_bucket(self):
        for node in self.content.talents.values():
            bucket = _classify(node, self.content.actions)
            expected = 1 if bucket == "binary" else 3
            self.assertEqual(node.max_rank, expected, f"{node.id} ({bucket}) max_rank {node.max_rank}")

    def test_bucket_distribution_is_24_active_17_passive_10_binary(self):
        buckets = [_classify(n, self.content.actions) for n in self.content.talents.values()]
        self.assertEqual(buckets.count("active"), 24)
        self.assertEqual(buckets.count("passive"), 17)
        self.assertEqual(buckets.count("binary"), 10)

    def test_binary_nodes_are_the_ten_pure_unlocks(self):
        binary = {n.id for n in self.content.talents.values() if n.max_rank == 1}
        self.assertEqual(binary, {
            "cleric_pest_p4_curse", "tank_guardian_g1_block", "tank_guardian_g4_taunt",
            "tank_sentinel_s3_resolve", "rogue_duelist_d1_evasion",
            "rogue_duelist_d4_deadly_precision", "fighter_berserker_b4_reckless",
            "mage_cryomancer_c2_freeze", "hunter_marksman_m2_hunters_mark",
            "hunter_trapper_t1_snare",
        })


class TalentRankStateTest(unittest.TestCase):
    def _engine(self, class_id="cleric"):
        engine = GameEngine()
        engine.start_new_game("Hero", class_id)
        return engine

    def test_new_game_grants_starter_actives_at_rank_1(self):
        player = self._engine().player
        self.assertTrue(player.talent_ranks)
        self.assertEqual(set(player.talent_ranks), player.learned_talent_ids)
        self.assertTrue(all(rank == 1 for rank in player.talent_ranks.values()))

    def test_persistence_round_trips_talent_ranks(self):
        player = self._engine().player
        player.talent_ranks["cleric_light_l3_devotion"] = 3
        player.learned_talent_ids.add("cleric_light_l3_devotion")
        data = persistence.serialize_player(player)
        restored = persistence.deserialize_player(data)
        self.assertEqual(restored.talent_ranks["cleric_light_l3_devotion"], 3)
        self.assertEqual(set(restored.talent_ranks), restored.learned_talent_ids)

    def test_old_save_without_ranks_migrates_each_learned_to_rank_1(self):
        legacy = {"learned_talent_ids": ["cleric_light_l1_smite", "cleric_light_l3_devotion"]}
        restored = persistence.deserialize_player(legacy)
        self.assertEqual(restored.talent_ranks,
                         {"cleric_light_l1_smite": 1, "cleric_light_l3_devotion": 1})
        self.assertEqual(restored.learned_talent_ids, set(restored.talent_ranks))


class TalentAllocationTest(unittest.TestCase):
    def _cleric(self, points=10):
        engine = GameEngine()
        engine.start_new_game("Hero", "cleric")
        engine.player.talent_points = points
        return engine

    def test_learning_then_upgrading_spends_one_point_per_step(self):
        engine = self._cleric(points=5)
        engine.allocate_talent("cleric_light_l2_mend")              # learn -> rank 1
        self.assertEqual(engine.player.talent_points, 4)
        self.assertEqual(engine.player.talent_ranks["cleric_light_l2_mend"], 1)
        msg = engine.allocate_talent("cleric_light_l2_mend")        # upgrade -> rank 2
        self.assertEqual(engine.player.talent_points, 3)
        self.assertEqual(engine.player.talent_ranks["cleric_light_l2_mend"], 2)
        self.assertIn("rank 2/3", msg)

    def test_cannot_upgrade_a_binary_node_past_rank_1(self):
        # Curse (max_rank 1) learns once, then refuses further points.
        engine = self._cleric()
        engine.allocate_talent("cleric_pest_p1_plague_bolt")
        engine.allocate_talent("cleric_pest_p2_drain")
        engine.allocate_talent("cleric_pest_p3_virulence")
        engine.allocate_talent("cleric_pest_p4_curse")
        self.assertEqual(engine.player.talent_ranks["cleric_pest_p4_curse"], 1)
        points = engine.player.talent_points
        with self.assertRaises(ValueError):
            engine.allocate_talent("cleric_pest_p4_curse")
        self.assertEqual(engine.player.talent_points, points)

    def test_cannot_upgrade_past_max_rank_3(self):
        engine = self._cleric()
        for _ in range(3):
            engine.allocate_talent("cleric_light_l2_mend")
        self.assertEqual(engine.player.talent_ranks["cleric_light_l2_mend"], 3)
        with self.assertRaises(ValueError):
            engine.allocate_talent("cleric_light_l2_mend")


class TalentPassiveRankTest(unittest.TestCase):
    def _cleric(self, points=10):
        engine = GameEngine()
        engine.start_new_game("Hero", "cleric")
        engine.player.talent_points = points
        return engine

    def test_devotion_stat_bonus_scales_125_then_150(self):
        engine = self._cleric()
        engine.allocate_talent("cleric_light_l2_mend")     # prereq
        engine.allocate_talent("cleric_light_l3_devotion")  # rank 1
        base = engine.player.stat_bonuses["max_mana"]
        self.assertEqual(base, 15)
        engine.allocate_talent("cleric_light_l3_devotion")  # rank 2
        rank2 = engine.player.stat_bonuses["max_mana"]
        engine.allocate_talent("cleric_light_l3_devotion")  # rank 3
        rank3 = engine.player.stat_bonuses["max_mana"]
        # Lock the RELATION, not the placeholder numbers.
        self.assertEqual(rank2, progression.round_half_up(base * combat.TALENT_RANK_MULT[2]))
        self.assertEqual(rank3, progression.round_half_up(base * combat.TALENT_RANK_MULT[3]))

    def test_elemental_attack_mod_scales_with_rank(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "mage")
        engine.player.talent_points = 5
        engine.allocate_talent("mage_flametongue")          # requires firebolt (starter), rank 1
        base = engine.player.elemental_attack_mods[0]["mod_value"]
        engine.allocate_talent("mage_flametongue")          # rank 2
        rank2 = engine.player.elemental_attack_mods[0]["mod_value"]
        self.assertEqual(rank2, progression.round_half_up(base * combat.TALENT_RANK_MULT[2]))

    def test_conditional_multiplier_delta_scales_with_rank(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        engine.player.talent_points = 5
        engine.allocate_talent("fighter_berserker_b1_frenzy")
        engine.allocate_talent("fighter_berserker_b2_rage")
        engine.allocate_talent("fighter_berserker_b3_bloodlust")   # rank 1: multiplier 1.3
        base = engine.player.conditional_damage_mods[-1]["multiplier"]
        engine.allocate_talent("fighter_berserker_b3_bloodlust")   # rank 2
        rank2 = engine.player.conditional_damage_mods[-1]["multiplier"]
        # delta above 1.0 scales linearly: 1 + (base-1)*1.25
        self.assertAlmostEqual(rank2, 1.0 + (base - 1.0) * combat.TALENT_RANK_MULT[2])

    def test_recompute_is_idempotent_for_unchanged_ranks(self):
        engine = self._cleric()
        engine.allocate_talent("cleric_light_l2_mend")
        engine.allocate_talent("cleric_light_l3_devotion")
        engine.allocate_talent("cleric_light_l3_devotion")  # rank 2
        before = dict(engine.player.stat_bonuses)
        from rpg_game.core import talents
        talents.sync_runtime(engine.player, engine.content)
        talents.sync_runtime(engine.player, engine.content)
        self.assertEqual(engine.player.stat_bonuses, before)


if __name__ == "__main__":
    unittest.main()
