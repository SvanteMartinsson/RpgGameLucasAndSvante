"""Enemy battle sprites: load + per-enemy sizing + shared baseline + fallback.
Presentation/assets only. Skips when pygame/pytmx are not installed.
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

SPRITED = [
    "giant_rat", "undead", "cave_bear", "undead_priest", "dire_wolf",
    "wild_boar", "treant", "mutated_mudcrab", "bog_wraith", "tar_beast",
]


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class EnemyBattleSpriteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        pb._sprite_cache.clear()  # don't leak cached surfaces between tests
        self.engine = GameEngine()
        self.engine.start_new_game("Hero", "fighter")

    def _battle(self, enemy_id):
        enemy = self.engine.content.enemies[enemy_id].create_enemy()
        return pb.BattleApp(engine=self.engine, enemy=enemy, standalone=False)

    def test_all_ten_sprites_load(self):
        for enemy_id in SPRITED:
            self.assertIsNotNone(pb.enemy_sprite(enemy_id), enemy_id)

    def test_each_sprited_enemy_renders_in_battle(self):
        for enemy_id in SPRITED:
            battle = self._battle(enemy_id)
            battle.draw()  # must not raise

    def test_per_enemy_sizing_small_vs_large(self):
        small = pb.enemy_sprite("giant_rat").get_height()
        large = pb.enemy_sprite("cave_bear").get_height()
        self.assertEqual(small, pb.TIER_HEIGHT["small"])
        self.assertEqual(large, pb.TIER_HEIGHT["large"])
        self.assertLess(small, large)

    def test_sprites_share_a_common_baseline(self):
        battle = self._battle("giant_rat")
        rat = battle._enemy_sprite_rect(*pb.enemy_sprite("giant_rat").get_size())
        bear = battle._enemy_sprite_rect(*pb.enemy_sprite("cave_bear").get_size())
        self.assertEqual(rat.bottom, bear.bottom)      # same ground line
        self.assertNotEqual(rat.height, bear.height)   # but different heights

    def test_aspect_ratio_preserved_on_scale(self):
        raw = pygame.image.load(os.path.join(pb.SPRITE_DIR, "dire_wolf.png"))
        scaled = pb.enemy_sprite("dire_wolf")
        self.assertAlmostEqual(scaled.get_width() / scaled.get_height(),
                               raw.get_width() / raw.get_height(), places=1)

    def test_missing_sprite_falls_back_without_crashing(self):
        self.assertIsNone(pb.enemy_sprite("hollow_worg"))  # sprite intentionally absent
        battle = self._battle("hollow_worg")
        battle.draw()  # fallback box, no crash

    def test_unknown_enemy_without_sprite_also_falls_back(self):
        self.assertIsNone(pb.enemy_sprite("arena_ralla_quickstep"))
        battle = self._battle("arena_ralla_quickstep")
        battle.draw()

    def test_sprite_dir_is_cwd_independent(self):
        self.assertTrue(os.path.isabs(pb.SPRITE_DIR))
        cwd = os.getcwd()
        import tempfile
        with tempfile.TemporaryDirectory() as other:
            os.chdir(other)
            try:
                pb._sprite_cache.clear()
                self.assertIsNotNone(pb.enemy_sprite("giant_rat"))
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
