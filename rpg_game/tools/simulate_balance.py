from __future__ import annotations

import argparse

from rpg_game.core.data_loader import load_content
from rpg_game.core.simulation import simulate_matrix


def main() -> None:
    parser = argparse.ArgumentParser(description="Run attack-only balance simulations.")
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-turns", type=int, default=50)
    parser.add_argument("--classes", nargs="*", default=None)
    parser.add_argument("--enemies", nargs="*", default=None)
    args = parser.parse_args()

    content = load_content()
    class_ids = args.classes or sorted(content.classes)
    enemy_ids = args.enemies or sorted(content.enemies)
    results = simulate_matrix(
        class_ids,
        enemy_ids,
        trials=args.trials,
        seed=args.seed,
        max_turns=args.max_turns,
    )

    print("class,enemy,trials,win_rate,avg_turns,avg_victory_hp,avg_enemy_hp_on_loss,timeouts")
    for result in results:
        print(
            f"{result.class_id},{result.enemy_id},{result.trials},"
            f"{result.win_rate:.2f},{result.average_turns:.2f},"
            f"{result.average_victory_hp:.2f},{result.average_enemy_hp_on_loss:.2f},"
            f"{result.timeouts}"
        )


if __name__ == "__main__":
    main()
