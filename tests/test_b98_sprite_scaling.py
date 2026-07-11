"""B98: battle-sprite downscale quality + tier-map coverage.

Heavy downscales (raw art is 500-1450px tall vs 150-250 canvas targets) use
smoothscale; upscales and mild downscales keep nearest-neighbor so pixel art
stays crisp. Every non-arena enemy with a sprite file must have an explicit
ENEMY_SPRITE_TIER entry so nothing silently falls back to medium.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

try:
    import pygame
except ImportError:  # pragma: no cover
    pygame = None

if pygame is not None:
    from rpg_game.presentation import pygame_battle
from rpg_game.core.data_loader import load_content


@unittest.skipIf(pygame is None, "pygame not installed")
class SpriteScaleModeTest(unittest.TestCase):
    def test_heavy_downscale_uses_smooth(self):
        # cursed_wight raw is 1432px tall, large tier target is 250 (~5.7x)
        self.assertEqual(pygame_battle.sprite_scale_mode(1432, 250), "smooth")

    def test_mild_downscale_keeps_nearest(self):
        self.assertEqual(pygame_battle.sprite_scale_mode(400, 250), "nearest")

    def test_upscale_keeps_nearest(self):
        self.assertEqual(pygame_battle.sprite_scale_mode(64, 200), "nearest")

    def test_threshold_boundary_is_nearest(self):
        self.assertEqual(pygame_battle.sprite_scale_mode(500, 250), "nearest")


@unittest.skipIf(pygame is None, "pygame not installed")
class SpriteTierCoverageTest(unittest.TestCase):
    def test_every_sprited_enemy_has_a_tier(self):
        content = load_content()
        missing = []
        for enemy_id in content.enemies:
            if enemy_id.startswith("arena_"):
                continue
            path = os.path.join(pygame_battle.SPRITE_DIR, f"{enemy_id}.png")
            if os.path.exists(path) and enemy_id not in pygame_battle.ENEMY_SPRITE_TIER:
                missing.append(enemy_id)
        self.assertEqual(missing, [], f"unmapped sprited enemies: {missing}")

    def test_new_elites_are_large(self):
        self.assertEqual(pygame_battle.ENEMY_SPRITE_TIER["cursed_wight"], "large")
        self.assertEqual(pygame_battle.ENEMY_SPRITE_TIER["skeleton_warrior"], "large")

    def test_scaled_sprite_matches_tier_height(self):
        pygame.init()
        pygame.display.set_mode((100, 100))
        pygame_battle._sprite_cache.clear()
        sprite = pygame_battle.enemy_sprite("cursed_wight")
        self.assertIsNotNone(sprite)
        self.assertEqual(sprite.get_height(), pygame_battle.TIER_HEIGHT["large"])
        pygame_battle._sprite_cache.clear()


if __name__ == "__main__":
    unittest.main()
