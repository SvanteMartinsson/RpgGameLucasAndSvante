"""B66: the bestiary codex.

Locks the unlock rules (Identify once OR KILL_UNLOCK kills), the engine hooks
(encounter -> seen, victory -> kill count, Identify -> identified), persistence
of all three fields, the arena exclusion, and the codex screen wiring (pygame).
"""

import os
import random
import unittest

from rpg_game.core import bestiary, persistence
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def _engine(seed=0):
    engine = GameEngine(rng=random.Random(seed))
    engine.start_new_game("Hero", "fighter")
    return engine


class UnlockRuleTests(unittest.TestCase):
    def test_identify_unlocks_immediately(self):
        engine = _engine()
        bestiary.mark_identified(engine.player, "cave_bear")
        self.assertTrue(bestiary.is_unlocked(engine.player, "cave_bear"))

    def test_kills_unlock_at_the_threshold(self):
        engine = _engine()
        for n in range(bestiary.KILL_UNLOCK):
            self.assertFalse(bestiary.is_unlocked(engine.player, "wild_dog"))
            bestiary.record_kill(engine.player, "wild_dog")
        self.assertTrue(bestiary.is_unlocked(engine.player, "wild_dog"))

    def test_arena_duelists_stay_out_of_the_codex(self):
        engine = _engine()
        bestiary.mark_seen(engine.player, "arena_ralla_quickstep")
        bestiary.record_kill(engine.player, "arena_ralla_quickstep")
        self.assertNotIn("arena_ralla_quickstep", engine.player.bestiary_seen)
        self.assertNotIn("arena_ralla_quickstep",
                         bestiary.codex_enemy_ids(engine.content))

    def test_codex_covers_every_wild_enemy(self):
        content = load_content()
        ids = bestiary.codex_enemy_ids(content)
        wild = {eid for eid in content.enemies if not eid.startswith("arena_")}
        self.assertEqual(set(ids), wild)


class EngineHookTests(unittest.TestCase):
    def test_victory_records_the_kill_and_marks_seen(self):
        engine = _engine()
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        enemy.hp = 1
        for _ in range(20):                      # attack until one actually lands
            result = engine.run_combat_turn(enemy, "attack")
            if result.outcome == "victory":
                break
        self.assertEqual(engine.player.bestiary_kills.get("giant_rat"), 1)
        self.assertIn("giant_rat", engine.player.bestiary_seen)

    def test_identify_marks_identified(self):
        engine = _engine()
        enemy = engine.content.enemies["cave_bear"].create_enemy()
        engine.run_combat_turn(enemy, "identify")
        self.assertIn("cave_bear", engine.player.bestiary_identified)
        self.assertTrue(bestiary.is_unlocked(engine.player, "cave_bear"))

    def test_wild_encounter_marks_seen(self):
        engine = _engine(seed=3)
        engine.player.current_place_id = "burg_54"
        enemy = engine.create_encounter()
        self.assertIn(enemy.id, engine.player.bestiary_seen)


class PersistenceTests(unittest.TestCase):
    def test_all_three_fields_round_trip(self):
        engine = _engine()
        bestiary.mark_identified(engine.player, "cave_bear")
        bestiary.record_kill(engine.player, "wild_dog")
        restored = persistence.deserialize_player(
            persistence.serialize_player(engine.player))
        self.assertIn("cave_bear", restored.bestiary_identified)
        self.assertEqual(restored.bestiary_kills.get("wild_dog"), 1)
        self.assertIn("wild_dog", restored.bestiary_seen)


try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class CodexScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.app = OverworldApp()
        self.app.screen = pygame.Surface((1024, 680))

    def test_selection_wraps_over_the_roster(self):
        total = len(bestiary.codex_enemy_ids(self.app.engine.content))
        self.app.bestiary_index = total - 1
        self.app.move_bestiary_selection(1)
        self.assertEqual(self.app.bestiary_index, 0)
        self.app.move_bestiary_selection(-1)
        self.assertEqual(self.app.bestiary_index, total - 1)

    def test_codex_renders_rows_and_details_without_error(self):
        player = self.app.engine.player
        bestiary.mark_identified(player, "cave_bear")
        self.app.overlay = "bestiary"
        self.app.bestiary_index = bestiary.codex_enemy_ids(
            self.app.engine.content).index("cave_bear")
        self.app.buttons = []
        self.app.hover.begin()
        self.app._draw_overlay_screen()          # must not raise
        labels = [b.label for b in self.app.buttons]
        self.assertTrue(any("Cave Bear" in l for l in labels))
        self.assertTrue(any("???" in l for l in labels))   # unseen rows masked

    def test_thumbnails_exist_for_unlocked_enemies(self):
        thumb, shadow = self.app._bestiary_thumb("cave_bear")
        self.assertIsNotNone(thumb)
        self.assertIsNotNone(shadow)


if __name__ == "__main__":
    unittest.main()
