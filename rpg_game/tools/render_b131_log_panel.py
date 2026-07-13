"""Render B131's battle screen (narrower log panel, wider vitals/actions) with
the log populated by typical combat lines so wrapping is visible."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from rpg_game.core.game import GameEngine  # noqa: E402
from rpg_game.presentation import chatlog  # noqa: E402
from rpg_game.presentation.pygame_battle import BattleApp  # noqa: E402

TYPICAL_LINES = [
    "A Razortusk Boar appears!",
    "Hero uses Deadly Precision for 42 physical damage!",
    "Razortusk Boar hits Hero for 31 physical damage.",
    "Critical! Hero uses Power Slash for 88 physical damage!",
    "Hero is afflicted with Vulnerability (physical +25% for 3 rounds).",
    "You found a Legendary Amulet of the Pale Sovereign!",
    "Hero gains 128 XP from the Razortusk Boar.",
]


def render(path: Path) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    engine = GameEngine()
    engine.start_new_game("Hero", "fighter")
    enemy = engine.content.enemies["razortusk_boar"].create_enemy()
    battle = BattleApp(engine=engine, enemy=enemy, standalone=False)
    for line in TYPICAL_LINES:
        battle.push_log(line, chatlog.COMBAT if hasattr(chatlog, "COMBAT") else (210, 214, 224))
    battle.draw()   # combat mode: both the log and the vitals/actions columns show
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(battle.screen, path)
    pygame.quit()


if __name__ == "__main__":
    import sys

    root = Path(__file__).resolve().parents[2]
    name = sys.argv[1] if len(sys.argv) > 1 else "b131_log_panel_after"
    render(root / "docs" / "nightly" / f"{name}.png")
    print(f"wrote {name}.png")
