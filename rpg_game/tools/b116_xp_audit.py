"""B116 before/after encounter-equivalent audit for the weakest rogue path.

Uses the real enemy reward scaling and XP award path. Giant Rat is the weakest
ordinary encounter (5 base XP), so this is the conservative upper bound on
encounters needed; gear, talents and combat wins do not inflate the reward.
"""

from __future__ import annotations

from rpg_game.core import progression
from rpg_game.core.game import GameEngine


def encounters_to_level_four(level_three_requirement: int) -> tuple[int, dict[int, int]]:
    original = progression.EARLY_XP_REQUIREMENTS.get(3)
    progression.EARLY_XP_REQUIREMENTS[3] = level_three_requirement
    try:
        engine = GameEngine()
        engine.start_new_game("Weak Rogue", "rogue")
        total = 0
        by_level: dict[int, int] = {}
        while engine.player.level < 4:
            level = engine.player.level
            enemy = engine.content.enemies["giant_rat"].create_enemy()
            gained = progression.level_scaled_xp(
                enemy.xp_reward, engine.player.level, enemy.level)
            progression.award_xp(engine.player, gained)
            total += 1
            by_level[level] = by_level.get(level, 0) + 1
        return total, by_level
    finally:
        if original is None:
            progression.EARLY_XP_REQUIREMENTS.pop(3, None)
        else:
            progression.EARLY_XP_REQUIREMENTS[3] = original


if __name__ == "__main__":
    for label, requirement in (("before", 225), ("after", 70)):
        total, by_level = encounters_to_level_four(requirement)
        print(f"{label}: total={total}, L1={by_level[1]}, L2={by_level[2]}, L3={by_level[3]}")
