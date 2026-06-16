import unittest

from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine


class WorldLoadingTests(unittest.TestCase):
    def test_player_starts_at_world_meta_start_place(self):
        content = load_content()
        engine = GameEngine(content=content)

        engine.start_new_game("Tester", "fighter")

        self.assertEqual(engine.player.current_place_id, content.start_place_id)

    def test_connections_reference_places_by_id(self):
        content = load_content()

        for place in content.places.values():
            for connection in place.connections:
                self.assertIn(connection.to, content.places)


if __name__ == "__main__":
    unittest.main()
