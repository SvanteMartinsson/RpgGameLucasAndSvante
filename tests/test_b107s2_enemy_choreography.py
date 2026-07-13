"""B107 S2: enemy attack choreography — the mirror of S1's hero swing.

An enemy DAMAGE action runs the same weighted timeline as the hero (quick/
normal/power), but mirrored by the presentation: the enemy dashes LEFT toward
the hero, the fx sheet + weighted damage number land on the HERO, and the enemy
idle holds still during the swing. Non-damage enemy actions get no choreography.
It is pure presentation — no engine RNG is drawn (fx on/off is identical). An
enemy with no idle sheet uses its static still and must not crash.

Skips without pygame.
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
    from rpg_game.presentation import battle_choreo
    from rpg_game.presentation import pygame_battle as pb

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


def _enemy_res(amount=10, crit=0, damage=True, actor="Cave Bear"):
    """A synthetic ENEMY resolution: no rolled style (enemies never roll one),
    so action_weight takes the effect branch — a plain damage hit maps to
    'normal'. `damage=False` gives a non-damage action (should get no choreo)."""
    res = combat.ActionResolution(action_id="", action_name="Claw",
                                  actor_name=actor, target_name="Hero")
    res.critical_hits = crit
    if damage:
        res.damage_components = [combat.DamageComponent(amount, "physical")]
    return res


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class EnemyChoreographyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _battle(self, enemy_id="cave_bear", fx=True, seed=0):
        engine = GameEngine(rng=random.Random(seed))
        engine.start_new_game("Hero", "fighter")
        enemy = engine.content.enemies[enemy_id].create_enemy()
        battle = pb.BattleApp(engine=engine, enemy=enemy, standalone=False,
                              event_log=collections.deque())
        battle._combat_fx = fx
        return battle

    # -- weight mapping (mirror of S1's table) ------------------------------

    def test_enemy_damage_maps_to_a_weight_and_non_damage_maps_to_none(self):
        self.assertEqual(battle_choreo.action_weight(_enemy_res(), None), "normal")
        self.assertIsNone(battle_choreo.action_weight(_enemy_res(damage=False), None))

    # -- the mirrored choreography ------------------------------------------

    def test_enemy_damage_action_starts_an_enemy_side_choreography(self):
        battle = self._battle()
        battle._spawn_resolution_fx(_enemy_res(amount=8))
        self.assertIsNotNone(battle._choreo)
        self.assertEqual(battle._choreo_attacker, "enemy")

    def test_enemy_non_damage_action_starts_no_choreography(self):
        battle = self._battle()
        battle._spawn_resolution_fx(_enemy_res(damage=False))
        self.assertIsNone(battle._choreo)

    def test_impact_number_lands_on_the_hero_side_not_the_enemy(self):
        battle = self._battle()
        battle._spawn_resolution_fx(_enemy_res(amount=13))
        guard = 0
        while (battle._choreo is not None and not battle._choreo.impact_done
               and guard < 600):
            battle.draw()
            guard += 1
        self.assertTrue(battle._floaters, "no damage number spawned at impact")
        hero_x, _ = battle._fx_anchor(over_enemy=False)
        enemy_x, _ = battle._fx_anchor(over_enemy=True)
        fx_x = battle._floaters[-1][0]
        self.assertLess(abs(fx_x - hero_x), abs(fx_x - enemy_x))

    def test_enemy_idle_holds_still_during_the_swing(self):
        # find an enemy that actually has an animated idle sheet
        battle = self._battle()
        animated = None
        for enemy_id in battle.engine.content.enemies:
            if pb.enemy_idle_frames(enemy_id):
                animated = enemy_id
                break
        if animated is None:
            self.skipTest("no animated enemy idle sheets available")
        battle = self._battle(enemy_id=animated)
        span = pb.ENEMY_IDLE_PERIOD  # a full idle period apart
        # WITHOUT a swing the idle animates across the period...
        battle._anim_tick = 0
        a0 = battle._enemy_stage_sprite(battle.enemy)
        battle._anim_tick = span // 2
        a1 = battle._enemy_stage_sprite(battle.enemy)
        self.assertIsNot(a0, a1, "idle should animate when not swinging")
        # ...but WHILE the enemy swings it is frozen to the swing-start frame.
        battle._anim_tick = 0
        battle._spawn_resolution_fx(_enemy_res(amount=5))   # freezes at tick 0
        s0 = battle._enemy_stage_sprite(battle.enemy)
        battle._anim_tick = span // 2
        s1 = battle._enemy_stage_sprite(battle.enemy)
        self.assertIs(s0, s1, "idle should hold still mid-swing")

    # -- determinism: pure presentation, no engine RNG ----------------------

    def test_live_enemy_choreography_draws_no_engine_rng(self):
        battle = self._battle(seed=7)
        before = battle.engine.rng.getstate()
        battle._spawn_resolution_fx(_enemy_res(amount=9))
        self.assertIsNotNone(battle._choreo)
        for _ in range(160):        # run the whole timeline dry
            battle.draw()
        self.assertIsNone(battle._choreo)                        # it completed
        self.assertEqual(battle.engine.rng.getstate(), before)   # nothing drawn

    def test_fx_on_and_off_reach_the_same_engine_state(self):
        states = []
        for fx in (True, False):
            battle = self._battle(seed=21, fx=fx)
            battle.issue_turn("attack")     # a full round incl. the enemy reply
            battle.flush_sequence()
            for _ in range(60):
                battle.draw()
            states.append(battle.engine.rng.getstate())
        self.assertEqual(states[0], states[1])

    # -- still-frame fallback for sheet-less enemies ------------------------

    def test_sheetless_enemy_does_not_crash_during_swing(self):
        battle = self._battle()
        checked = 0
        for enemy_id in ("shade", "skeleton_warrior", "strangling_vine",
                         "witchlight", "plague_acolyte"):
            if enemy_id not in battle.engine.content.enemies:
                continue
            if pb.enemy_idle_frames(enemy_id):
                continue                    # this one has a sheet; not the case under test
            b = self._battle(enemy_id=enemy_id)
            b._spawn_resolution_fx(_enemy_res(amount=6))
            for _ in range(40):
                b.draw()                    # static still + swing must not crash
            checked += 1
        self.assertGreater(checked, 0, "no sheet-less enemy was available to test")


if __name__ == "__main__":
    unittest.main()
