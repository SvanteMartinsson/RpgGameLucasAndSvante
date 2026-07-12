"""B71: save slots + autosave + death flow.

Core: slot summaries read the picker metadata straight from the JSON, legacy
root saves migrate into slot 1 exactly once, playtime persists and formats.
UI (pygame): a fresh run claims the first free slot, entering a town and
winning a battle autosave, defeat opens the death screen with load choices,
and loading a save resyncs the sprite. All file IO is patched into a tempdir.
"""

import os
import random
import tempfile
import unittest
from unittest import mock

from rpg_game.core import persistence, saveslots
from rpg_game.core.game import GameEngine

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def _engine():
    engine = GameEngine(rng=random.Random(0))
    engine.start_new_game("Slotty", "mage")
    engine.player.level = 4
    engine.player.playtime_seconds = 3725      # 1h 02m
    return engine


class SlotSummaryTests(unittest.TestCase):
    def test_summary_reads_the_picker_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "slot1.json")
            _engine().save(path)
            summary = saveslots.slot_summary(path)
            self.assertEqual(summary.name, "Slotty")
            self.assertEqual(summary.player_class, "mage")
            self.assertEqual(summary.level, 4)
            self.assertEqual(summary.playtime_seconds, 3725)
            self.assertEqual(summary.playtime_label(), "1h 02m")

    def test_missing_and_corrupt_files_yield_none(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(saveslots.slot_summary(os.path.join(folder, "nope.json")))
            bad = os.path.join(folder, "bad.json")
            open(bad, "w").write("{not json")
            self.assertIsNone(saveslots.slot_summary(bad))

    def test_short_playtime_label(self):
        summary = saveslots.SlotSummary("p", "X", "mage", 1, "", 240)
        self.assertEqual(summary.playtime_label(), "4m")


class LegacyMigrationTests(unittest.TestCase):
    def test_root_save_moves_into_slot_1_once(self):
        with tempfile.TemporaryDirectory() as folder:
            legacy = os.path.join(folder, "savegame.json")
            slot1 = os.path.join(folder, "slot1.json")
            _engine().save(legacy)
            with mock.patch.object(saveslots, "SAVES_DIR", folder), \
                 mock.patch.object(saveslots, "SLOT_PATHS", (slot1,)):
                self.assertTrue(saveslots.migrate_legacy(legacy))
                self.assertTrue(os.path.exists(slot1))
                self.assertFalse(os.path.exists(legacy))
                _engine().save(legacy)                       # a NEW legacy file
                self.assertFalse(saveslots.migrate_legacy(legacy))  # slot1 occupied

    def test_playtime_round_trips(self):
        restored = persistence.deserialize_player(
            persistence.serialize_player(_engine().player))
        self.assertEqual(restored.playtime_seconds, 3725)


try:
    import pygame
    from rpg_game.presentation.pygame_overworld import OverworldApp
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class SaveSlotUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        folder = self._tmp.name
        slots = tuple(os.path.join(folder, f"slot{i}.json") for i in (1, 2, 3))
        auto = os.path.join(folder, "autosave.json")
        patchers = [
            mock.patch.object(saveslots, "SAVES_DIR", folder),
            mock.patch.object(saveslots, "SLOT_PATHS", slots),
            mock.patch.object(saveslots, "AUTOSAVE_PATH", auto),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)
        self.app = OverworldApp()
        self.app.screen = pygame.Surface((1024, 680))

    def test_fresh_run_claims_the_first_free_slot(self):
        self.assertEqual(self.app.save_path, saveslots.SLOT_PATHS[0])

    def test_entering_a_town_autosaves(self):
        self.app.world.set_tile(60, 70)                     # wilderness
        self.app.sync_location()
        self.assertFalse(os.path.exists(saveslots.AUTOSAVE_PATH))
        start = self.app.town_tile_by_place[self.app.engine.content.start_place_id]
        self.app.world.set_tile(*start)
        self.app.sync_location()
        self.assertTrue(os.path.exists(saveslots.AUTOSAVE_PATH))

    def test_victory_autosaves_and_defeat_returns_directly_to_town(self):
        enemy = self.app.engine.content.enemies["giant_rat"].create_enemy()
        self.app.resolve_battle_outcome("victory", enemy)
        self.assertTrue(os.path.exists(saveslots.AUTOSAVE_PATH))
        self.app.resolve_battle_outcome("defeat", enemy)
        self.assertEqual(self.app.mode, "walk")
        self.assertEqual(self.app.world.current_tile,
                         self.app.town_tile_by_place[self.app.engine.player.current_place_id])
        self.assertIn("You fell. You wake at", self.app.event_log[-1][0])

    def test_load_save_resyncs_and_returns_to_walk(self):
        self.app.save_game()
        self.app.mode = "store"
        self.app._load_save(self.app.save_path)
        self.assertEqual(self.app.mode, "walk")


if __name__ == "__main__":
    unittest.main()
