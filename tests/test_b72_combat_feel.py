"""B72: combat feel — floating damage numbers + hit feedback.

Locks: a consumed result spawns one floater per damage component (type colour,
crits big + shake), heals float green over the healer, the hit side blinks,
a kill triggers the hit-pause, floaters age out, and the combat_fx setting
turns the whole layer off. Skips without pygame.
"""

import collections
import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.core import combat
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation.pygame_battle import BattleApp
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


def _result(actor="Hero", components=(), crit=0, healing=0, outcome="ongoing"):
    resolution = combat.ActionResolution("a", "A", actor, "T")
    resolution.damage_components = [combat.DamageComponent(a, t) for a, t in components]
    resolution.critical_hits = crit
    resolution.total_healing = healing
    return combat.CombatTurnResult(outcome=outcome, action_resolutions=[resolution])


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class CombatFeelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _battle(self):
        engine = GameEngine(rng=random.Random(0))
        engine.start_new_game("Hero", "fighter")
        enemy = engine.content.enemies["cave_bear"].create_enemy()
        return BattleApp(engine=engine, enemy=enemy, standalone=False,
                         event_log=collections.deque())

    def test_damage_components_become_floaters_at_impact(self):
        # B107 S1: a PLAYER damage action routes through the choreography —
        # the weighted numbers spawn at the impact frame, not at cast.
        battle = self._battle()
        battle._spawn_combat_fx(_result(components=((12, "fire"), (4, "frost"))))
        self.assertIsNotNone(battle._choreo)
        self.assertEqual(len(battle._choreo_pending), 2)
        self.assertEqual(battle._floaters, [])
        for _ in range(battle._choreo.total):
            battle._tick_choreo()
            if not battle._choreo:
                break
        self.assertEqual(len(battle._floaters), 2)
        self.assertEqual(battle._blink_hero, 0)

    def test_enemy_attack_routes_through_mirrored_choreography(self):
        # B107 S2: an ENEMY damage action now routes through the choreography too
        # (mirror of S1) — the hero is the defender and flashes via the choreo,
        # so the old instant white blink is gone.
        battle = self._battle()
        battle._spawn_combat_fx(_result(actor="Cave Bear", components=((9, "physical"),)))
        self.assertIsNotNone(battle._choreo)
        self.assertEqual(battle._choreo_attacker, "enemy")
        self.assertEqual(battle._blink_enemy, 0)

    def test_crit_shakes_the_screen(self):
        battle = self._battle()
        battle._spawn_combat_fx(_result(components=((20, "physical"),), crit=1))
        self.assertGreater(battle._shake, 0)

    def test_heal_floats_over_the_healer(self):
        battle = self._battle()
        battle._spawn_combat_fx(_result(healing=15))
        self.assertEqual(len(battle._floaters), 1)

    def test_kill_triggers_the_hit_pause(self):
        battle = self._battle()
        battle._spawn_combat_fx(_result(components=((30, "physical"),), outcome="victory"))
        self.assertGreater(battle._freeze, 0)

    def test_floaters_age_out(self):
        battle = self._battle()
        battle.display = pygame.display.get_surface()
        battle._spawn_combat_fx(_result(components=((12, "fire"),)))
        for _ in range(60):
            battle._draw_combat_fx()
        self.assertEqual(battle._floaters, [])

    def test_setting_turns_the_layer_off(self):
        battle = self._battle()
        battle._combat_fx = False
        battle._spawn_combat_fx(_result(components=((12, "fire"),), crit=1))
        self.assertEqual(battle._floaters, [])
        self.assertEqual(battle._shake, 0)


if __name__ == "__main__":
    unittest.main()
