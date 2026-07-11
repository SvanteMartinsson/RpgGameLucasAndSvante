"""B96: the reflect log line names its source skill.

"Hero's Counter reflected 6 damage to Dire Wolf." instead of the generic
"Hero reflected 6 damage to Dire Wolf." — derived from the status's
originating action (ActiveStatus.source_action), not hardcoded. Statuses
without a recorded source keep the generic wording, and the source survives
save/load.
"""

import random
import unittest

from rpg_game.core import combat
from rpg_game.core.entities import ActiveStatus
from rpg_game.core.game import GameEngine
from rpg_game.core.persistence import deserialize_status, serialize_status


def _tank_with_status(action_id: str):
    engine = GameEngine()
    engine.start_new_game("Hero", "tank")
    player = engine.player
    action = engine.content.actions[action_id]
    weapon = engine.content.weapons[player.equipped_weapon_id]
    combat.resolve_action(player, player, action, weapon=weapon, rng=random.Random(1))
    status = next(s for s in player.active_statuses if s.type == "reflect")
    return engine, player, status


class ReflectSourceLineTest(unittest.TestCase):
    def test_counter_reflect_line_names_the_skill(self):
        engine, player, status = _tank_with_status("counter")
        self.assertEqual(status.source_action, "Counter")
        enemy = engine.content.enemies["cave_bear"].create_enemy()
        result = combat.ActionResolution("x", "X", enemy.name, player.name)
        combat.apply_reflects(player, enemy, result)
        line = next(e for e in result.events if "reflected" in e)
        self.assertTrue(line.startswith("Hero's Counter reflected "), line)
        self.assertTrue(line.endswith(f"damage to {enemy.name}."), line)

    def test_thorns_reflect_line_names_the_skill(self):
        engine, player, status = _tank_with_status("thorns")
        self.assertEqual(status.source_action, "Thorns")
        enemy = engine.content.enemies["cave_bear"].create_enemy()
        result = combat.ActionResolution("x", "X", enemy.name, player.name)
        combat.apply_reflects(player, enemy, result)
        line = next(e for e in result.events if "reflected" in e)
        self.assertTrue(line.startswith("Hero's Thorns reflected "), line)

    def test_sourceless_reflect_keeps_generic_wording(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "tank")
        player = engine.player
        player.active_statuses.append(ActiveStatus(
            type="reflect", magnitude=5, duration=2, tick_timing="round_end",
        ))
        enemy = engine.content.enemies["cave_bear"].create_enemy()
        result = combat.ActionResolution("x", "X", enemy.name, player.name)
        combat.apply_reflects(player, enemy, result)
        line = next(e for e in result.events if "reflected" in e)
        self.assertTrue(line.startswith("Hero reflected "), line)

    def test_source_action_survives_save_load(self):
        _engine, _player, status = _tank_with_status("counter")
        restored = deserialize_status(serialize_status(status))
        self.assertEqual(restored.source_action, "Counter")


if __name__ == "__main__":
    unittest.main()
