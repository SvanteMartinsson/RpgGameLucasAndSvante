"""Render B134's battle skill cells (wide rectangles filling the ACTIONS band).

Pass 'before' or 'after' as the suffix; run the 'before' against the pre-B134
checkout to capture B130's squares for comparison.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from rpg_game.core.game import GameEngine  # noqa: E402
from rpg_game.presentation import chatlog  # noqa: E402
from rpg_game.presentation.pygame_battle import BattleApp  # noqa: E402

# A few log lines so the whole HUD (log + vitals + actions) reads in the shot.
LOG_LINES = [
    "A Giant Rat appears!",
    "Hero uses Deadly Precision for 21 physical damage!",
    "Giant Rat hits Hero for 6 physical damage.",
]


def render(path: Path) -> None:
    engine = GameEngine()
    engine.start_new_game("Hero", "rogue")
    # A full 4-skill loadout, incl. the longest rogue name, so the 2x2 grid and
    # the name-in-cell result are both visible.
    engine.player.learned_skill_ids = ("evasion", "riposte")
    engine.player.equipped_skill_ids = ("rupture", "deadly_precision", "evasion", "riposte")
    enemy = engine.content.enemies["giant_rat"].create_enemy()
    battle = BattleApp(engine=engine, enemy=enemy, standalone=False)
    for line in LOG_LINES:
        battle.push_log(line, chatlog.COMBAT if hasattr(chatlog, "COMBAT") else (210, 214, 224))
    battle.open_submenu("skill")
    battle.draw()
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(battle.screen, path)


def main(suffix: str) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    root = Path(__file__).resolve().parents[2] / "docs" / "nightly"
    out = root / f"b134_skill_cells_{suffix}.png"
    render(out)
    pygame.quit()
    print(f"wrote {out.name}")


if __name__ == "__main__":
    import sys

    main(sys.argv[1] if len(sys.argv) > 1 else "after")
