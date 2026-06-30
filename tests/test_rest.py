import unittest

from rpg_game.core.game import GameEngine


def _engine_at(place_id: str) -> GameEngine:
    engine = GameEngine()
    engine.start_new_game("Hero", "fighter")
    engine.player.current_place_id = place_id
    return engine


def _store_place_id(engine: GameEngine) -> str:
    return next(place.id for place in engine.content.places.values() if place.has_store)


def _safe_place_id(engine: GameEngine) -> str:
    return next(place.id for place in engine.content.places.values() if not place.has_store)


class RestTests(unittest.TestCase):
    def test_rest_in_town_restores_hp_and_mana(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        engine.player.current_place_id = _store_place_id(engine)
        engine.player.hp = 1
        engine.player.mana = 0

        result = engine.rest()

        self.assertEqual(result.outcome, "rested")
        self.assertEqual(engine.player.hp, engine.player.max_hp)
        self.assertEqual(engine.player.mana, engine.effective_stat('max_mana'))

    def test_rest_outside_town_is_rejected_and_does_not_mutate_state(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        engine.player.current_place_id = _safe_place_id(engine)
        engine.player.hp = 1
        engine.player.mana = 0

        result = engine.rest()

        self.assertEqual(result.outcome, "not_allowed")
        self.assertEqual(engine.player.hp, 1)
        self.assertEqual(engine.player.mana, 0)


if __name__ == "__main__":
    unittest.main()
