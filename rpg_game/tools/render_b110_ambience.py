"""Render B110's moving-camera proof GIF into docs/nightly.

The camera follows the hero east through Mork Skog. World-space fireflies keep
their world coordinates, so they slide west on screen as the camera passes.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
from PIL import Image  # noqa: E402

from rpg_game.presentation.pygame_overworld import OverworldApp  # noqa: E402


def render(path: Path, frames: int = 32) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    app = OverworldApp()
    app.screen = pygame.Surface((640, 400))

    # A clear stretch inside Mork Skog, away from camera/map edges.
    tile = next(
        (x, 40)
        for x in range(90, 145)
        if app.zone.theme_for_tile((x, 40)) == "mork_skog"
    )
    app.world.set_tile(*tile)
    app._ambience = None
    app._ambience_theme = ""

    images: list[Image.Image] = []
    for _ in range(frames):
        app.screen.fill((0, 0, 0))
        app._draw_map()
        app._draw_ambience()
        raw = pygame.image.tostring(app.screen, "RGB")
        images.append(Image.frombytes("RGB", app.screen.get_size(), raw))
        # Move far enough per frame for the camera motion to be unambiguous.
        app.world.player.x += 8

    path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(path, save_all=True, append_images=images[1:], duration=85, loop=0,
                   optimize=False)
    pygame.quit()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    output = root / "docs" / "nightly" / "b110_world_space_ambience.gif"
    render(output)
    print(f"wrote {output}")
