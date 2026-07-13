"""B133: the hero idle is gated behind the same "Combat animations" toggle as
the enemy idle (B109). Toggle OFF -> hero holds still frame 0 no matter how the
anim clock advances; toggle ON -> the hero cycles A-B-C-B. This makes the two
combatants symmetric (before B133 the hero animated while the enemy froze).

Skips without pygame.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame

    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import pygame_battle as pb

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class HeroIdleToggleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _battle(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        return pb.BattleApp(engine=engine, enemy=enemy, standalone=False)

    def test_toggle_off_freezes_hero_to_frame_zero(self):
        battle = self._battle()
        battle._combat_fx = False
        # advance the anim clock across a full idle period; the frame never moves
        for tick in range(pb.HERO_IDLE_PERIOD * 2 + 3):
            battle._anim_tick = tick
            self.assertEqual(battle._hero_idle_frame_index(), 0)

    def test_toggle_on_animates_hero(self):
        battle = self._battle()
        battle._combat_fx = True
        seen = set()
        for tick in range(pb.HERO_IDLE_PERIOD):
            battle._anim_tick = tick
            seen.add(battle._hero_idle_frame_index())
        self.assertGreater(len(seen), 1, "hero idle did not animate with the toggle on")

    def test_hero_gate_matches_enemy_gate(self):
        # Symmetry: both idles read the same flag. With it off, the enemy stage
        # sprite is the static still and the hero index is 0; with it on, both
        # animate. We assert the shared gate rather than duplicate the enemy path.
        battle = self._battle()
        battle._combat_fx = False
        battle._anim_tick = 7                       # a tick that WOULD animate
        self.assertEqual(battle._hero_idle_frame_index(), 0)
        battle._combat_fx = True
        self.assertEqual(battle._hero_idle_frame_index(),
                         pb.hero_idle_index(battle._anim_tick))


if __name__ == "__main__":
    unittest.main()
