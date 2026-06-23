#!/usr/bin/env python3
"""recolor_themes.py — tonal harmonisation of the dark overworld zones.

Lifts EVERY themed sheet for mork_skog and cursed_mire into the same
light/saturation family as cainos, so the hard seam between zones softens and
props/trees stop drowning in dark ground. The transform is per-pixel in HSV:
multiply Value and Saturation by per-theme factors, PRESERVE hue (zone identity),
and skip fully transparent pixels (alpha == 0). Sheets are overwritten in place
at identical dimensions.

Scope: art/asset only. cainos sheets are NEVER touched (they live outside
assets/.../generated). Other generated themes (ash_waste, frostfell, …) are not
touched either — only the two themes the overworld actually uses for its dark
regions.

Run ONCE against the committed (pristine) sheets. It lifts from whatever is on
disk, so re-running double-applies the lift — restore via `git checkout` first.

Factors were tuned (see the repo discussion) so the base-grass tile-0 luma lands
in the target window while staying below cainos (~106) so zones read distinct:
  mork_skog   V*1.70 S*1.70 : luma 51 -> ~81   (target 78-88)
  cursed_mire V*1.40 S*1.50 : luma 64 -> ~87   (target 80-90)
"""
from __future__ import annotations

import colorsys
import glob
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

# (value_multiplier, saturation_multiplier)
THEME_FACTORS = {
    "mork_skog": (1.70, 1.70),
    "cursed_mire": (1.40, 1.50),
}
SHEET_DIRS = (
    "rpg_game/assets/tiles/generated",
    "rpg_game/assets/props/generated",
)


def theme_sheets(theme: str) -> list[str]:
    """All generated sheets for a theme (grass/stone/wall + plant/props/struct/shadow)."""
    sheets: list[str] = []
    for directory in SHEET_DIRS:
        sheets += sorted(glob.glob(os.path.join(directory, f"*__{theme}.png")))
    return sheets


def _lift_rgb(r: int, g: int, b: int, fv: float, fs: float) -> tuple[int, int, int]:
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    s = min(1.0, s * fs)
    v = min(1.0, v * fv)
    nr, ng, nb = colorsys.hsv_to_rgb(h, s, v)
    return (round(nr * 255), round(ng * 255), round(nb * 255))


def recolor_surface(surface: "pygame.Surface", fv: float, fs: float) -> "pygame.Surface":
    """Apply the HSV lift to a per-pixel-alpha surface, caching by colour so a
    palette of a few hundred RGB values isn't reconverted millions of times."""
    surface = surface.convert_alpha()
    width, height = surface.get_size()
    cache: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    surface.lock()
    for y in range(height):
        for x in range(width):
            r, g, b, a = surface.get_at((x, y))
            if a == 0:  # preserve transparency exactly
                continue
            key = (r, g, b)
            new = cache.get(key)
            if new is None:
                new = cache[key] = _lift_rgb(r, g, b, fv, fs)
            surface.set_at((x, y), (new[0], new[1], new[2], a))
    surface.unlock()
    return surface


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))  # needed for convert_alpha()
    for theme, (fv, fs) in THEME_FACTORS.items():
        for path in theme_sheets(theme):
            surface = pygame.image.load(path)
            lifted = recolor_surface(surface, fv, fs)
            pygame.image.save(lifted, path)
            print(f"lifted {os.path.basename(path)}  (V*{fv} S*{fs})")
    pygame.quit()


if __name__ == "__main__":
    main()
