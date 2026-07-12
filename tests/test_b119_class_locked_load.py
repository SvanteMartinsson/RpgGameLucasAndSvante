"""B119: save loading is locked to a persistent profile class.

Rule (Lucas): the first game (new or loaded) anchors a profile class in
settings.json. From then on the start menu greys out — and the engine refuses
to load — any save whose class differs from that profile. Starting a new game
re-anchors the profile to the freshly chosen class.

Skips when pygame/pytmx are not installed (the flow lives in pygame_overworld).
"""

import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame  # noqa: F401
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import pygame_overworld
    from rpg_game.presentation import settings as user_settings
    from rpg_game.presentation.pygame_overworld import (
        engine_from_start_choice,
        start_menu_slot_options,
    )

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class ClassLockedLoadTest(unittest.TestCase):
    def setUp(self):
        # Isolated saves + settings so nothing touches the real files.
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.settings_path = os.path.join(self._dir.name, "settings.json")
        for module in (user_settings, pygame_overworld.user_settings):
            p = patch.object(module, "SETTINGS_PATH", self.settings_path)
            p.start()
            self.addCleanup(p.stop)

    def _make_save(self, name, class_id):
        path = os.path.join(self._dir.name, f"{class_id}.json")
        engine = GameEngine()
        engine.start_new_game(name, class_id)
        engine.save(path)
        return path

    # --- settings helpers ---------------------------------------------------
    def test_profile_starts_empty_and_round_trips(self):
        self.assertEqual(user_settings.profile_class(), "")
        user_settings.set_profile_class("rogue")
        self.assertEqual(user_settings.profile_class(), "rogue")

    # --- engine-level guard -------------------------------------------------
    def test_new_game_anchors_profile_to_chosen_class(self):
        engine_from_start_choice("new", creation_fn=lambda e: ("Sly", "rogue"))
        self.assertEqual(user_settings.profile_class(), "rogue")

    def test_matching_class_save_loads_and_keeps_profile(self):
        user_settings.set_profile_class("rogue")
        path = self._make_save("Sly", "rogue")
        engine = engine_from_start_choice(f"load:{path}")
        self.assertEqual(engine.player.player_class, "rogue")
        self.assertEqual(user_settings.profile_class(), "rogue")

    def test_mismatched_class_save_is_refused(self):
        user_settings.set_profile_class("rogue")
        path = self._make_save("Merlin", "mage")
        with self.assertRaises(ValueError) as ctx:
            engine_from_start_choice(f"load:{path}")
        self.assertIn("mage", str(ctx.exception))
        # profile untouched by a refused load
        self.assertEqual(user_settings.profile_class(), "rogue")

    def test_empty_profile_allows_any_load_then_anchors(self):
        self.assertEqual(user_settings.profile_class(), "")
        path = self._make_save("Merlin", "mage")
        engine = engine_from_start_choice(f"load:{path}")
        self.assertEqual(engine.player.player_class, "mage")
        self.assertEqual(user_settings.profile_class(), "mage")

    def test_new_game_reanchors_to_switch_class(self):
        user_settings.set_profile_class("rogue")
        engine_from_start_choice("new", creation_fn=lambda e: ("Merlin", "mage"))
        self.assertEqual(user_settings.profile_class(), "mage")

    # --- menu row enable/disable -------------------------------------------
    def test_menu_disables_only_other_class_slots(self):
        user_settings.set_profile_class("rogue")
        rogue_save = self._make_save("Sly", "rogue")
        mage_save = self._make_save("Merlin", "mage")
        # slot paths are fixed by saveslots; write our saves there so the menu sees them
        with patch.object(pygame_overworld.saveslots, "SLOT_PATHS", (rogue_save, mage_save)), \
             patch.object(pygame_overworld.saveslots, "AUTOSAVE_PATH",
                          os.path.join(self._dir.name, "none.json")):
            rows = start_menu_slot_options()
        by_choice = {choice: (label, enabled) for choice, label, enabled in rows}
        self.assertTrue(by_choice["new"][1])                       # New game always on
        self.assertTrue(by_choice[f"load:{rogue_save}"][1])        # matching class on
        self.assertFalse(by_choice[f"load:{mage_save}"][1])        # other class locked
        self.assertIn("(locked)", by_choice[f"load:{mage_save}"][0])

    def test_menu_all_enabled_when_profile_empty(self):
        rogue_save = self._make_save("Sly", "rogue")
        mage_save = self._make_save("Merlin", "mage")
        with patch.object(pygame_overworld.saveslots, "SLOT_PATHS", (rogue_save, mage_save)), \
             patch.object(pygame_overworld.saveslots, "AUTOSAVE_PATH",
                          os.path.join(self._dir.name, "none.json")):
            rows = start_menu_slot_options()
        for choice, label, enabled in rows:
            self.assertTrue(enabled, f"{choice} should be loadable with an empty profile")


if __name__ == "__main__":
    unittest.main()
