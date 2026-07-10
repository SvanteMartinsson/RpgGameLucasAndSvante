"""B88: a DoT landing writes exactly one flavoured line with source + type.

Enemy DoTs name the caster possessively ("... by Boss Rotfang's Plague Leap!"),
player DoTs name the skill ("... was set ablaze by Immolate!"), the verb keys
the tick damage type, and non-DoT statuses keep the generic B77 wording.
The battle log colours the line by damage type (pygame part skips without it).
"""

import os
import random
import unittest

from rpg_game.core import combat
from rpg_game.core.game import GameEngine

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.presentation import pygame_battle as pb

    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


def _resolve(engine, actor, target, action_id, weapon=None):
    return combat.resolve_action(
        actor, target, engine.content.actions[action_id],
        weapon=weapon, rng=random.Random(0),
    )


class DotApplyLineTests(unittest.TestCase):
    def setUp(self):
        self.engine = GameEngine()
        self.engine.start_new_game("Hero", "mage")

    def test_enemy_dot_line_names_caster_and_type(self):
        spider = self.engine.content.enemies["giant_spider"].create_enemy()
        result = _resolve(self.engine, spider, self.engine.player, "poison_sting")
        lines = [e for e in result.events if "was poisoned by" in e]
        self.assertEqual(len(lines), 1, result.events)
        self.assertEqual(lines[0], f"Hero was poisoned by {spider.name}'s Poison Sting!")
        self.assertFalse(any("is affected by poison" in e for e in result.events))

    def test_player_fire_dot_line_names_the_skill(self):
        enemy = self.engine.content.enemies["cave_bear"].create_enemy()
        weapon = self.engine.content.weapons[self.engine.player.equipped_weapon_id]
        result = _resolve(self.engine, self.engine.player, enemy, "immolate", weapon)
        lines = [e for e in result.events if "was set ablaze by" in e]
        self.assertEqual(len(lines), 1, result.events)
        self.assertEqual(lines[0], f"{enemy.name} was set ablaze by Immolate!")

    def test_non_dot_status_keeps_the_generic_wording(self):
        enemy = self.engine.content.enemies["cave_bear"].create_enemy()
        weapon = self.engine.content.weapons[self.engine.player.equipped_weapon_id]
        result = _resolve(self.engine, self.engine.player, self.engine.player, "block", weapon)
        self.assertTrue(any("is affected by mitigation" in e for e in result.events), result.events)
        self.assertFalse(any(" was " in e and e.endswith("!") for e in result.events))


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class DotApplyColourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_line_is_coloured_by_damage_type(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        enemy = engine.content.enemies["cave_bear"].create_enemy()
        battle = pb.BattleApp(engine=engine, enemy=enemy, standalone=False)
        battle.event_log.clear()
        battle._push_combat_event("Hero was poisoned by Giant Spider's Poison Sting!")
        self.assertEqual(battle.event_log[-1][1], pb.BattleApp.FX_TYPE_COLORS["poison"])
        battle._push_combat_event("Undead Priest was set ablaze by Immolate!")
        self.assertEqual(battle.event_log[-1][1], pb.BattleApp.FX_TYPE_COLORS["fire"])


if __name__ == "__main__":
    unittest.main()
