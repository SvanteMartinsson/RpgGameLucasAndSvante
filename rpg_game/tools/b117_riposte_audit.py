"""Seeded B117 Riposte-build gate.

Baseline on commit eed4795 with the same N/seed was 54.5% wins, 5.375 turns
against the on-level Cave Bear. The rebuilt skill must enter, not overshoot,
the rogue's 70–90% neutral win corridor while keeping TTK in 4–6.
"""

from rpg_game.core.simulation import simulate_matchup


if __name__ == "__main__":
    plan = ("rogue_duelist_d1_evasion", "rogue_duelist_d2_riposte")
    result = simulate_matchup(
        "rogue", "cave_bear", trials=200, seed=11700,
        use_skills=True, level=3, talent_plan=plan,
    )
    print(
        f"after: wins={result.win_rate * 100:.1f}%, "
        f"turns={result.average_turns:.3f}, "
        f"victory_hp={result.average_victory_hp:.2f}, timeouts={result.timeouts}"
    )
    if not (0.70 <= result.win_rate <= 0.90 and 4 <= result.average_turns <= 6):
        raise SystemExit("HALT: Riposte build left the rogue corridor")
