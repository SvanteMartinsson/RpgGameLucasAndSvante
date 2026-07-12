"""B90: talent detail spells out every rank with COMPUTED values from data.

No more 'x1.25 magnitude' steps: each rank line carries the actual numbers the
engine would use (round_half_up on integers, the B86 multiplier path for power
reflects, +1 round duration at rank 3 for actives only). Current rank marked.
"""

import unittest

from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine
from rpg_game.presentation.talent_text import talent_detail, talent_rank_lines


class RankLinesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = load_content()

    def _node_for_action(self, action_id):
        return next(n for n in self.content.talents.values() if n.action_id == action_id)

    def test_active_drain_skill_lines_are_computed(self):
        node = self._node_for_action("frenzy")
        mult = next(e.multiplier for e in self.content.actions["frenzy"].effects
                    if e.type in ("instant_damage", "drain"))
        lines = talent_rank_lines(self.content, node, current_rank=1)
        self.assertEqual(len(lines), 3)
        self.assertIn(f"{mult}x", lines[0])
        self.assertIn("<- current", lines[0])
        self.assertIn(f"{round(mult * 1.25, 2)}x", lines[1])
        self.assertIn(f"{round(mult * 1.5, 2)}x", lines[2])
        self.assertNotIn("magnitude", " ".join(lines))

    def test_active_dot_scales_ticks_and_duration(self):
        node = self._node_for_action("ignite")
        lines = talent_rank_lines(self.content, node)
        self.assertIn("8 fire/round for 3 rounds", lines[0])
        self.assertIn("10 fire/round for 3 rounds", lines[1])   # round_half_up(8*1.25)
        self.assertIn("12 fire/round for 4 rounds", lines[2])   # rank 3: +1 round

    def test_power_reflect_rank_lines_follow_the_b86_multiplier(self):
        node = self._node_for_action("counter")
        lines = talent_rank_lines(self.content, node)
        self.assertIn("1.0x Power", lines[0])
        self.assertIn("1.25x Power", lines[1])
        self.assertIn("1.5x Power", lines[2])

    def test_passive_node_scales_magnitudes_without_duration_bonus(self):
        node = next(n for n in self.content.talents.values()
                    if n.node_type == "passive" and n.max_rank > 1
                    and any(e.type == "stat_bonus" for e in n.effects))
        lines = talent_rank_lines(self.content, node)
        self.assertEqual(len(lines), node.max_rank)
        self.assertNotIn("magnitude", " ".join(lines))

    def test_talent_detail_lines_carry_rank_lines_and_no_raw_steps(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        node = self._node_for_action("frenzy")
        detail = talent_detail(engine, node)
        self.assertEqual(len(detail.rank_lines), 3)
        self.assertNotIn("magnitude", " ".join(detail.rank_lines))


if __name__ == "__main__":
    unittest.main()
