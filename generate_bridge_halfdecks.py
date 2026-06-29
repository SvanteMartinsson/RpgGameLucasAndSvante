#!/usr/bin/env python3
"""generate_bridge_halfdecks.py — build the four half-deck bridge tiles
deterministically by 9-slicing water_bridge tiles 13 (E-W) and 14 (N-S).

Why: a 2-wide bridge built from two RAW deck tiles (13/13 or 14/14) shows a
doubled rail down the MIDDLE ("two thin bridges"). The fix is half-deck tiles
that carry a rail on the OUTER edge only, so a pair reads as ONE wide bridge with
rails just on the outside and clean planking across the middle.

9-slice (matches the architect's reference sheet):
  E-W (tile 13) stretched to 64px TALL: top rail = src rows 0-4 (4px), plank-mid =
    src rows 4-23 (19px) stretched to 51px, bottom rail = src rows 23-32 (9px).
    64 = 4 + 51 + 9. Split: ew_north = top 32px, ew_south = bottom 32px.
  N-S (tile 14) stretched to 64px WIDE: left rail = src cols 0-8 (8px), plank-mid =
    src cols 8-26 (18px) stretched to 50px, right rail = src cols 26-32 (6px).
    64 = 8 + 50 + 6. Split: ns_west = left 32px, ns_east = right 32px.

Writes a separate 4x1 sheet; the crisp source sheet is untouched. Deterministic +
idempotent: same bytes (md5) every run. Order in the sheet (tile index):
  0 ew_north, 1 ew_south, 2 ns_west, 3 ns_east.
"""
from __future__ import annotations

import hashlib
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame  # noqa: E402

SRC = "rpg_game/assets/tiles/generated/water_bridge_32x32_crisp.png"
OUT = "rpg_game/assets/tiles/generated/bridge_halfdeck_32x32.png"

TS = 32
# water_bridge is an 8-col sheet; tile 13 = (col 5, row 1), tile 14 = (col 6, row 1).
EW_SRC = (13 % 8 * TS, 13 // 8 * TS)   # (160, 32)
NS_SRC = (14 % 8 * TS, 14 // 8 * TS)   # (192, 32)


def _ew_64(src: "pygame.Surface") -> "pygame.Surface":
    """Tile 13 (E-W deck) 9-sliced vertically to a 32x64 deck: 4px top rail, 51px
    stretched planks, 9px bottom rail."""
    tile = src.subsurface((*EW_SRC, TS, TS))
    out = pygame.Surface((TS, 64), pygame.SRCALPHA)
    out.fill((0, 0, 0, 0))
    out.blit(tile.subsurface((0, 0, TS, 4)), (0, 0))                                  # top rail
    out.blit(pygame.transform.scale(tile.subsurface((0, 4, TS, 19)), (TS, 51)), (0, 4))  # planks
    out.blit(tile.subsurface((0, 23, TS, 9)), (0, 55))                                # bottom rail
    return out


def _ns_64(src: "pygame.Surface") -> "pygame.Surface":
    """Tile 14 (N-S deck) 9-sliced horizontally to a 64x32 deck: 8px left rail, 50px
    stretched planks, 6px right rail."""
    tile = src.subsurface((*NS_SRC, TS, TS))
    out = pygame.Surface((64, TS), pygame.SRCALPHA)
    out.fill((0, 0, 0, 0))
    out.blit(tile.subsurface((0, 0, 8, TS)), (0, 0))                                   # left rail
    out.blit(pygame.transform.scale(tile.subsurface((8, 0, 18, TS)), (50, TS)), (8, 0))  # planks
    out.blit(tile.subsurface((26, 0, 6, TS)), (58, 0))                                 # right rail
    return out


def build(src_path: str = SRC) -> "pygame.Surface":
    src = pygame.image.load(src_path).convert_alpha()
    ew, ns = _ew_64(src), _ns_64(src)
    sheet = pygame.Surface((4 * TS, TS), pygame.SRCALPHA)
    sheet.fill((0, 0, 0, 0))
    sheet.blit(ew.subsurface((0, 0, TS, TS)), (0 * TS, 0))    # 0 ew_north (top half)
    sheet.blit(ew.subsurface((0, TS, TS, TS)), (1 * TS, 0))   # 1 ew_south (bottom half)
    sheet.blit(ns.subsurface((0, 0, TS, TS)), (2 * TS, 0))    # 2 ns_west (left half)
    sheet.blit(ns.subsurface((TS, 0, TS, TS)), (3 * TS, 0))   # 3 ns_east (right half)
    return sheet


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))  # for convert_alpha()
    sheet = build()
    pygame.image.save(sheet, OUT)
    with open(OUT, "rb") as f:
        md5 = hashlib.md5(f.read()).hexdigest()
    print(f"wrote {OUT}  (4x1 atlas: ew_north, ew_south, ns_west, ns_east)  md5 {md5}")
    pygame.quit()


if __name__ == "__main__":
    main()
