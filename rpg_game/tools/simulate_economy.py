"""B62: economy/loot-flow report per zone band.

    python3 -m rpg_game.tools.simulate_economy --trials 300

Measures (never tunes): gold in per fight (kill + drop sell value), drop rates
per rarity, material inflow, and the rest-cost pressure per zone — the decision
basis for shop/enchant/rest pricing (B8 2b, B22).
"""

from __future__ import annotations

import argparse

from rpg_game.core.data_loader import load_content
from rpg_game.core.simulation import simulate_economy_band

# (zone label, pool place, on-level player level, rest zone index)
BANDS = (
    ("cainos", "burg_54", 3, 1),
    ("mork_skog", "burg_146", 6, 2),
    ("cursed_mire", "burg_320", 8, 3),
    ("grave_heath", "burg_121", 11, 4),
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the B62 economy/loot-flow report.")
    parser.add_argument("--trials", type=int, default=200)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--class-id", default="fighter")
    args = parser.parse_args()

    content = load_content()
    print(f"B62 economy report — {args.class_id}, N={args.trials}/band, seed={args.seed}")
    for zone, place_id, level, rest_zone in BANDS:
        report = simulate_economy_band(
            args.class_id, place_id, level=level, trials=args.trials,
            seed=args.seed, rest_zone=rest_zone, content=content)
        place = content.places[place_id]
        print(f"\n=== {zone} (pool {place_id} {place.name}) · player L{level} ===")
        print(f"  win {report.win_rate * 100:5.1f}%   avg turns {report.average_turns:4.1f}   "
              f"dmg taken/fight {report.average_damage_taken:5.1f} (max hp {report.player_max_hp})")
        print(f"  gold in/victory: kill {report.average_kill_gold:6.1f} + sell {report.average_sell_value:5.1f}")
        print(f"  drop rate {report.drop_rate * 100:5.1f}% of victories   rarities: "
              + (", ".join(f"{r} {n}" for r, n in report.rarity_counts) or "-"))
        materials = ", ".join(f"{item} x{n}" for item, n in report.material_counts) or "-"
        print(f"  materials: {materials}")
        print(f"  rest: cost {report.rest_cost}g · {report.fights_per_rest:4.1f} fights/rest "
              f"-> {report.rest_cost_per_fight:5.2f}g/fight   NET {report.net_gold_per_fight:+6.1f}g/fight")


if __name__ == "__main__":
    main()
