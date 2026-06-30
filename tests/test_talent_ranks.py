"""B36: talent ranks 1-3. Owned talents can be upgraded instead of only learned.

Locks RELATIONS (rank 2 = 1.25x rank 1, rank 3 = 1.5x AND +1 round duration,
binary nodes cap at rank 1) and the deterministic node classification, not the
placeholder multiplier values themselves.
"""

import unittest

from rpg_game.core import combat, data_loader, progression
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


if __name__ == "__main__":
    unittest.main()
