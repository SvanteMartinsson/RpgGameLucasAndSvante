"""Render B130's battle skill menu (2x2 square block + Esc cell beside it)."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from rpg_game.core.game import GameEngine  # noqa: E402
from rpg_game.presentation.pygame_battle import BattleApp  # noqa: E402


def render(path: Path) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    engine = GameEngine()
    engine.start_new_game("Hero", "rogue")
    # A full 4-skill loadout so the grid shows the 2x2 block + the Esc cell.
    engine.player.learned_skill_ids = ("evasion", "riposte")
    engine.player.equipped_skill_ids = ("rupture", "deadly_precision", "evasion", "riposte")
    enemy = engine.content.enemies["giant_rat"].create_enemy()
    battle = BattleApp(engine=engine, enemy=enemy, standalone=False)
    battle.open_submenu("skill")
    battle.draw()
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(battle.screen, path)
    pygame.quit()


if __name__ == "__main__":
    import sys

    root = Path(__file__).resolve().parents[2]
    name = sys.argv[1] if len(sys.argv) > 1 else "b130_skill_grid_after"
    render(root / "docs" / "nightly" / f"{name}.png")
    print(f"wrote {name}.png")
