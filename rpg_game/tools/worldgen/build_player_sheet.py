"""B83: slice Lucas's walk_sheet_review.png into clean runtime sheets.

The review sheet is 9 labelled rows (r0-r8) x 4 frames on a flat grey
background with a label column at the left. This tool colour-keys the grey,
finds each row's frame clusters, normalizes every frame into a uniform cell
(bottom-centred) and writes:

    player_walk.png   8 rows (N NE E SE S SW W NW) x 4 frames
    player_idle.png   1 row (front/blink)          x 4 frames

Regenerate after art updates:

    .venv/bin/python -m rpg_game.tools.worldgen.build_player_sheet
"""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

SPRITES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "assets", "sprites", "generated")
REVIEW_SHEET = os.path.join(SPRITES_DIR, "walk_sheet_review.png")
LABEL_MARGIN = 44          # the r0-r8 label column at the left
BG_TOLERANCE = 14
FRAMES_PER_ROW = 4
ROW_ORDER = ("N", "NE", "E", "SE", "S", "SW", "W", "NW", "IDLE")   # r0..r8 (Lucas)


def _is_bg(pixel, bg) -> bool:
    return (abs(pixel[0] - bg[0]) <= BG_TOLERANCE
            and abs(pixel[1] - bg[1]) <= BG_TOLERANCE
            and abs(pixel[2] - bg[2]) <= BG_TOLERANCE)


def _bands(flags: list[bool]) -> list[tuple[int, int]]:
    """Contiguous True-runs as (start, end_exclusive)."""
    bands, start = [], None
    for i, flag in enumerate(flags):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            bands.append((start, i))
            start = None
    if start is not None:
        bands.append((start, len(flags)))
    return bands


def build(review_path: str = REVIEW_SHEET) -> tuple[str, str]:
    pygame.init()
    pygame.display.set_mode((1, 1))
    sheet = pygame.image.load(review_path).convert_alpha()
    width, height = sheet.get_size()
    bg = sheet.get_at((width - 2, 2))[:3]

    opaque = [[not _is_bg(sheet.get_at((x, y)), bg)
               for x in range(LABEL_MARGIN, width)]
              for y in range(height)]
    row_bands = _bands([any(row) for row in opaque])
    assert len(row_bands) == len(ROW_ORDER), f"expected 9 rows, found {len(row_bands)}"

    frames: list[list[pygame.Rect]] = []
    for y0, y1 in row_bands:
        col_flags = [any(opaque[y][x] for y in range(y0, y1))
                     for x in range(len(opaque[0]))]
        col_bands = _bands(col_flags)
        assert len(col_bands) == FRAMES_PER_ROW, \
            f"row {len(frames)}: expected 4 frames, found {len(col_bands)}"
        frames.append([pygame.Rect(LABEL_MARGIN + x0, y0, x1 - x0, y1 - y0)
                       for x0, x1 in col_bands])

    cell_w = max(r.width for row in frames for r in row) + 2
    cell_h = max(r.height for row in frames for r in row) + 2

    def compose(rows: list[list[pygame.Rect]]) -> pygame.Surface:
        out = pygame.Surface((cell_w * FRAMES_PER_ROW, cell_h * len(rows)), pygame.SRCALPHA)
        for ri, row in enumerate(rows):
            for ci, rect in enumerate(row):
                frame = pygame.Surface(rect.size, pygame.SRCALPHA)
                frame.blit(sheet, (0, 0), rect)
                # colour-key the grey INSIDE the crop too
                for yy in range(rect.height):
                    for xx in range(rect.width):
                        if _is_bg(frame.get_at((xx, yy)), bg):
                            frame.set_at((xx, yy), (0, 0, 0, 0))
                # bottom-centred in the uniform cell (shared ground line)
                dx = ci * cell_w + (cell_w - rect.width) // 2
                dy = ri * cell_h + (cell_h - rect.height)
                out.blit(frame, (dx, dy))
        return out

    walk_path = os.path.join(SPRITES_DIR, "player_walk.png")
    idle_path = os.path.join(SPRITES_DIR, "player_idle.png")
    pygame.image.save(compose(frames[:8]), walk_path)
    pygame.image.save(compose(frames[8:9]), idle_path)
    return walk_path, idle_path


if __name__ == "__main__":
    walk, idle = build()
    print(f"wrote {walk}\nwrote {idle}")
