"""The overworld starts from the created character, not a default Hero.

Skips when pygame/pytmx are not installed.
"""

import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation.pygame_overworld import (
        OverworldApp,
        engine_from_start_choice,
        start_menu,
        start_menu_options,
    )
    from rpg_game.presentation.pygame_battle import character_creation

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class OverworldStartTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_overworld_uses_the_provided_created_character(self):
        engine = GameEngine()
        engine.start_new_game("Svante", "tank")
        app = OverworldApp(engine=engine)
        self.assertEqual(app.engine.player.name, "Svante")
        self.assertEqual(app.engine.player.player_class, "tank")

    def test_creation_flow_feeds_overworld(self):
        engine = GameEngine()
        pygame.display.set_mode((1024, 680))
        for ch in "Greta":
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=ord(ch), unicode=ch))
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r"))
        name, class_id = character_creation(engine)
        engine.start_new_game(name, class_id)
        app = OverworldApp(engine=engine)
        self.assertEqual(app.engine.player.name, "Greta")
        self.assertIn(class_id, engine.content.classes)

    def test_start_menu_opens_window_and_returns_choice(self):
        # Exercises the real set_mode((WIDTH, HEIGHT)) + button-build path that
        # crashed with NameError; only start_menu_options was covered before.
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=ord("n"), unicode="n"))
        self.assertEqual(start_menu(save_path="/tmp/no_such_save_file.json"), "new")

    def test_start_menu_hides_load_without_save_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "savegame.json")

            options = start_menu_options(path)

        self.assertEqual([choice for choice, _label in options], ["new", "quit"])

    def test_start_menu_shows_load_and_loads_saved_character(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "savegame.json")
            saved = GameEngine()
            saved.start_new_game("Loaded", "mage")
            saved.player.current_place_id = "burg_117"
            saved.save(path)

            options = start_menu_options(path)
            loaded = engine_from_start_choice("load", save_path=path)
            app = OverworldApp(engine=loaded)

        self.assertEqual([choice for choice, _label in options], ["new", "load", "quit"])
        self.assertEqual(app.engine.player.name, "Loaded")
        self.assertEqual(app.engine.player.player_class, "mage")
        self.assertEqual(app.engine.player.current_place_id, "burg_117")

    def test_new_game_start_choice_uses_character_creation_path(self):
        calls = []

        def fake_creation(engine):
            calls.append(engine)
            return ("Newbie", "hunter")

        engine = engine_from_start_choice("new", creation_fn=fake_creation)

        self.assertEqual(len(calls), 1)
        self.assertEqual(engine.player.name, "Newbie")
        self.assertEqual(engine.player.player_class, "hunter")


if __name__ == "__main__":
    unittest.main()
