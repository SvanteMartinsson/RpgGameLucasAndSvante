"""Render the B111 hero-scale before/after comparison."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from rpg_game.core.game import GameEngine  # noqa: E402
from rpg_game.presentation import pygame_battle as battle_ui  # noqa: E402


def render_scale(scale: int, path: Path) -> None:
    battle_ui.HERO_SCALE = scale
    battle_ui._hero_frames = "unloaded"
    engine = GameEngine()
    engine.start_new_game("Hero", "fighter")
    enemy = engine.content.enemies["cave_bear"].create_enemy()
    battle = battle_ui.BattleApp(engine=engine, enemy=enemy, standalone=False)
    battle.draw()
    pygame.image.save(battle.screen, path)


def render(out_dir: Path) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    out_dir.mkdir(parents=True, exist_ok=True)
    render_scale(7, out_dir / "b111_hero_scale_before.png")
    render_scale(3, out_dir / "b111_hero_scale_after.png")
    battle_ui.HERO_SCALE = 3
    battle_ui._hero_frames = "unloaded"
    pygame.quit()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    render(root / "docs" / "nightly")
    print("wrote B111 before/after renders")
