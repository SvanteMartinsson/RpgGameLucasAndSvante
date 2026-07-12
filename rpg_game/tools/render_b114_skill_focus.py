"""Render B114's default-focused battle skill menu."""

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
    engine.start_new_game("Hero", "fighter")
    engine.player.learned_skill_ids = ("power",)
    engine.player.equipped_skill_ids = ("frenzy", "power")
    enemy = engine.content.enemies["cave_bear"].create_enemy()
    battle = BattleApp(engine=engine, enemy=enemy, standalone=False)
    battle.open_submenu("skill")
    battle.draw()
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(battle.screen, path)
    pygame.quit()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    render(root / "docs" / "nightly" / "b114_keyboard_skill_focus.png")
    print("wrote B114 skill-focus render")
