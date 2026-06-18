"""Deterministic combat simulations for tuning.

The simulator uses the public `GameEngine` combat API and seeded RNG. It is not
part of normal gameplay; it exists to turn balance questions into repeatable
numbers before manual playtesting.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from rpg_game.core.game import GameEngine


@dataclass(frozen=True)
class FightSimulation:
    class_id: str
    enemy_id: str
    seed: int
    outcome: str
    turns: int
    player_hp: int
    player_max_hp: int
    enemy_hp: int
    enemy_max_hp: int


@dataclass(frozen=True)
class MatchupSimulation:
    class_id: str
    enemy_id: str
    trials: int
    victories: int
    defeats: int
    timeouts: int
    average_turns: float
    average_victory_hp: float
    average_enemy_hp_on_loss: float

    @property
    def win_rate(self) -> float:
        return self.victories / self.trials if self.trials else 0.0


def simulate_fight(
    class_id: str,
    enemy_id: str,
    *,
    seed: int = 0,
    max_turns: int = 50,
) -> FightSimulation:
    """Run one attack-only fight and return a compact result."""
    engine = GameEngine(rng=random.Random(seed))
    engine.start_new_game(f"{class_id.title()} Sim", class_id)
    enemy = engine.content.enemies[enemy_id].create_enemy()

    outcome = "timeout"
    turns = 0
    while turns < max_turns and outcome == "timeout":
        turns += 1
        result = engine.run_combat_turn(enemy, "attack")
        if result.outcome in {"victory", "defeat"}:
            outcome = result.outcome
            break
        outcome = "timeout"

    return FightSimulation(
        class_id=class_id,
        enemy_id=enemy_id,
        seed=seed,
        outcome=outcome,
        turns=turns,
        player_hp=engine.player.hp,
        player_max_hp=engine.player.max_hp,
        enemy_hp=enemy.hp,
        enemy_max_hp=enemy.max_hp,
    )


def simulate_matchup(
    class_id: str,
    enemy_id: str,
    *,
    trials: int = 100,
    seed: int = 0,
    max_turns: int = 50,
) -> MatchupSimulation:
    """Run many seeded fights for one class/enemy matchup."""
    fights = [
        simulate_fight(class_id, enemy_id, seed=seed + index, max_turns=max_turns)
        for index in range(trials)
    ]
    victories = [fight for fight in fights if fight.outcome == "victory"]
    defeats = [fight for fight in fights if fight.outcome == "defeat"]
    timeouts = [fight for fight in fights if fight.outcome == "timeout"]
    return MatchupSimulation(
        class_id=class_id,
        enemy_id=enemy_id,
        trials=trials,
        victories=len(victories),
        defeats=len(defeats),
        timeouts=len(timeouts),
        average_turns=_average(fight.turns for fight in fights),
        average_victory_hp=_average(fight.player_hp for fight in victories),
        average_enemy_hp_on_loss=_average(fight.enemy_hp for fight in defeats),
    )


def simulate_matrix(
    class_ids: list[str],
    enemy_ids: list[str],
    *,
    trials: int = 100,
    seed: int = 0,
    max_turns: int = 50,
) -> list[MatchupSimulation]:
    """Run a class-by-enemy matrix with stable per-cell seeds."""
    results = []
    for class_index, class_id in enumerate(class_ids):
        for enemy_index, enemy_id in enumerate(enemy_ids):
            cell_seed = seed + class_index * 10_000 + enemy_index * 1_000
            results.append(
                simulate_matchup(
                    class_id,
                    enemy_id,
                    trials=trials,
                    seed=cell_seed,
                    max_turns=max_turns,
                )
            )
    return results


def _average(values) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0
