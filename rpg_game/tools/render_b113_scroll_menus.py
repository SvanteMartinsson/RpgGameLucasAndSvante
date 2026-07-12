"""Render B113's settings and tome panels at their scrolled positions."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from rpg_game.presentation.pygame_overworld import OverworldApp  # noqa: E402


def render(out_dir: Path) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    out_dir.mkdir(parents=True, exist_ok=True)

    app = OverworldApp()
    app.display = pygame.Surface((720, 480))
    app.screen = pygame.Surface((720, 480))
    app.overlay = "settings"
    app.draw()
    app._menu_scrolls["settings"].offset = app._menu_scrolls["settings"].maximum
    app.draw()
    pygame.image.save(app.screen, out_dir / "b113_settings_scrolled.png")

    app.overlay = ""
    app._open_tome_shop("tower")
    app.draw()
    app._menu_scrolls["tomes"].offset = app._menu_scrolls["tomes"].maximum
    app.draw()
    pygame.image.save(app.screen, out_dir / "b113_tomes_scrolled.png")
    pygame.quit()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    render(root / "docs" / "nightly")
    print("wrote B113 scrolled menu renders")
