"""Battle layout rework: three zones rebalanced toward the fight.

STAGE biggest, COMBAT LOG slim, HUD compact. The YOU header is gone (level is
shown discreetly by the XP bar), all six actions stay clickable in a tighter
band, sprites share a groundline, and clicks still map through the transform.
Pure presentation — no game logic touched. Skips without pygame/pytmx.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import pygame_battle as pb
    from rpg_game.presentation.pygame_canvas import to_canvas

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class BattleLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _battle(self, enemy_id="cave_bear"):
        engine = GameEngine()
        engine.start_new_game("Hero", "hunter")
        enemy = engine.content.enemies[enemy_id].create_enemy()
        return engine, pb.BattleApp(engine=engine, enemy=enemy, standalone=False)

    def test_stage_is_the_biggest_zone_and_hud_the_smallest(self):
        self.assertGreater(pb.STAGE.height, pb.LOG_PANEL.height)
        self.assertGreater(pb.STAGE.height, pb.HUD.height)
        self.assertLessEqual(pb.HUD.height, pb.LOG_PANEL.height)
        # Three stacked, non-overlapping zones.
        self.assertLessEqual(pb.STAGE.bottom, pb.LOG_PANEL.top)
        self.assertLessEqual(pb.LOG_PANEL.bottom, pb.HUD.top)

    def test_all_six_actions_present_and_inside_the_compact_band(self):
        _engine, battle = self._battle()
        battle.set_mode("combat")
        battle.draw()
        labels = " ".join(b.label.lower() for b in battle.buttons)
        for word in ("attack", "skill", "item", "swap", "identify", "flee"):
            self.assertIn(word, labels)
        self.assertEqual(len(battle.buttons), 6)
        for b in battle.buttons:
            self.assertTrue(pb.ACTIONS.contains(b.rect), f"{b.label} escaped ACTIONS")
        # Tighter than the old 166px action band.
        span = max(b.rect.bottom for b in battle.buttons) - min(b.rect.top for b in battle.buttons)
        self.assertLess(span, 166)

    def test_enemy_and_hero_share_the_stage_groundline(self):
        _engine, battle = self._battle()
        enemy = battle._enemy_sprite_rect(*pb.enemy_sprite("cave_bear").get_size())
        hero = battle._hero_sprite_rect(60, 200)
        self.assertEqual(enemy.bottom, pb.GROUND_Y)
        self.assertEqual(hero.bottom, pb.GROUND_Y)
        self.assertLess(hero.left, enemy.left)        # hero left, enemy right
        self.assertLessEqual(pb.GROUND_Y, pb.STAGE.bottom)

    def test_fallback_box_drawn_for_spriteless_enemy(self):
        _engine, battle = self._battle("plague_acolyte")  # real enemy, no sprite art
        self.assertIsNone(pb.enemy_sprite("plague_acolyte"))
        battle.draw()  # must not raise; draws the fallback box on the stage

    def test_clicks_map_through_the_transform_to_the_right_button(self):
        _engine, battle = self._battle()
        battle.display = pygame.Surface((1400, 900))  # larger -> centered transform
        battle.set_mode("combat")
        battle.draw()
        ox, oy, scale = battle._transform
        for b in battle.buttons:
            display_point = (ox + b.rect.centerx * scale, oy + b.rect.centery * scale)
            self.assertTrue(b.rect.collidepoint(to_canvas(display_point, battle._transform)),
                            f"click missed {b.label}")

    def test_submenu_and_stat_choice_render_in_the_actions_region(self):
        _engine, battle = self._battle()
        battle.open_submenu("item")
        battle.draw()
        self.assertTrue(all(pb.ACTIONS.contains(b.rect) for b in battle.buttons))
        battle.set_mode("stat_choice")
        battle.draw()  # must not raise


if __name__ == "__main__":
    unittest.main()
