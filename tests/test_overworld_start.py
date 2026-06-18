"""The overworld starts from the created character, not a default Hero.

Skips when pygame/pytmx are not installed.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation.pygame_overworld import OverworldApp
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


if __name__ == "__main__":
    unittest.main()
