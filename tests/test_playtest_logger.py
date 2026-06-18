import json
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta

from rpg_game.core.game import GameEngine
from rpg_game.core.progression import RespawnResult
from rpg_game.core.view import build_snapshot
from rpg_game.presentation.playtest_logger import PlaytestLogger


class SequenceRng:
    def __init__(self, values):
        self.values = list(values)

    def random(self):
        return self.values.pop(0) if self.values else 0.99

    def randint(self, minimum, _maximum):
        return minimum

    def choice(self, values):
        return values[0]


class PlaytestLoggerTests(unittest.TestCase):
    def test_session_writes_parseable_jsonl_for_headless_fight(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = GameEngine(rng=SequenceRng([0.0, 0.0, 0.0, 0.99, 0.0, 0.0]))
            engine.start_new_game("Logger", "fighter")
            enemy = engine.content.enemies["giant_rat"].create_enemy()
            enemy.hp = 1
            enemy.drop_chance = 1.0
            enemy.loot_table = ({"item_id": "rat_pelt", "weight": 1, "rarity_tier": 1},)
            logger = PlaytestLogger(folder)
            snapshot = build_snapshot(engine)

            logger.session_start(snapshot)
            logger.encounter_start(enemy, snapshot, engine.player.current_place_id)
            result = engine.run_combat_turn(enemy, "attack")
            logger.combat_result(result, enemy, build_snapshot(engine), engine.player.current_place_id)
            logger.death(RespawnResult(hp=50, mana=10, xp_lost=7, gold_lost=3), "burg_5")

            rows = _read_jsonl(logger.path)

        self.assertTrue(all("timestamp" in row and "session_id" in row for row in rows))
        self.assertEqual(rows[0]["event"], "session_start")
        self.assertEqual(rows[0]["player_name"], "Logger")
        self.assertEqual(rows[1]["event"], "encounter_start")
        self.assertEqual(rows[1]["enemy_id"], "giant_rat")

        attack = next(row for row in rows if row["event"] == "attack")
        self.assertEqual(attack["source"], "player")
        self.assertEqual(attack["rolled_style"], "quick")
        self.assertTrue(attack["hit"])
        self.assertFalse(attack["crit"])
        self.assertGreaterEqual(attack["damage"], 1)
        self.assertEqual(attack["damage_components"][0]["type"], "physical")

        drop = next(row for row in rows if row["event"] == "drop")
        self.assertEqual(drop["item_id"], "rat_pelt")
        self.assertEqual(drop["rarity"], "common")
        self.assertEqual(drop["tier"], 1)

        reward = next(row for row in rows if row["event"] == "reward")
        self.assertEqual(reward["xp"], result.xp_gained)
        self.assertEqual(reward["gold"], result.gold_gained)

        death = next(row for row in rows if row["event"] == "death")
        self.assertEqual(death["lost_xp"], 7)
        self.assertEqual(death["lost_gold"], 3)
        self.assertEqual(death["hp_after"], 50)
        self.assertEqual(death["mana_after"], 10)

    def test_rotation_keeps_latest_five_sessions(self):
        with tempfile.TemporaryDirectory() as folder:
            base = datetime(2026, 1, 1, tzinfo=UTC)
            old_paths = []
            for index in range(5):
                path = os.path.join(folder, f"playtest_log_old_{index}.jsonl")
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write("{}\n")
                stamp = (base + timedelta(seconds=index)).timestamp()
                os.utime(path, (stamp, stamp))
                old_paths.append(path)

            logger = PlaytestLogger(folder)

            remaining = sorted(os.path.basename(path) for path in os.listdir(folder))
            self.assertEqual(len(remaining), 5)
            self.assertNotIn(os.path.basename(old_paths[0]), remaining)
            self.assertIn(os.path.basename(logger.path), remaining)


def _read_jsonl(path):
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


if __name__ == "__main__":
    unittest.main()
