"""B136b: render all four day/night phases and MEASURE night readability.

Writes docs/nightly/b136_phase_<phase>.png for review, then prints the rails the
tint's alpha cap is justified by.

A tint can only ever SCALE the contrast already in the frame, never add any:
blending an alpha-a overlay multiplies every luminance DIFFERENCE by (1 - a/255).
So the primary rail is RELATIVE — how much of daylight's separation survives —
and it is analytic, not a taste call: daylight.contrast_retained(NIGHT_ALPHA).
The measurements below exist to confirm that model holds on a real frame and to
put absolute numbers next to it:

  * global contrast   — luminance std-dev over the frame, as a % of the day
    frame's. Must clear daylight.MIN_CONTRAST_RETAINED. This is the rail.
  * hero legibility   — |mean luminance of the hero sprite - mean luminance of the
    ring of background around it|. The one genuinely ABSOLUTE floor here: below
    ~8 levels out of 255 the hero starts melting into the ground, and the day
    frame's ~39 leaves real room to spend.
  * tile separation   — per-TILE mean luminance reduced to p5/p50/p95, and the
    smallest gap between those three (within-tile texture averaged out, which is
    how a player reads terrain). Reported as a ratio vs day rather than against
    a fixed floor: the absolute value is dominated by how homogeneous the chosen
    frame is (mostly grass here -> only ~11 levels even at noon), so a fixed
    floor would measure the screenshot, not the tint.

Enemy sprites are deliberately absent: fights run in the BATTLE shell, which
draws no tint at all, so a night encounter is lit exactly like a day one.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
from PIL import Image  # noqa: E402

from rpg_game.core import daynight  # noqa: E402
from rpg_game.presentation import daylight  # noqa: E402
from rpg_game.presentation.pygame_overworld import OverworldApp  # noqa: E402

VIEW = (640, 400)

# The one absolute floor, in luminance levels out of 255: below ~8 levels of
# separation the hero starts melting into the ground it stands on.
MIN_SPRITE_DELTA = 8.0


def _luminance(image: Image.Image):
    return image.convert("L")


def _stdev(gray: Image.Image) -> float:
    pixels = list(gray.getdata())
    mean = sum(pixels) / len(pixels)
    return (sum((p - mean) ** 2 for p in pixels) / len(pixels)) ** 0.5


def _tile_bands(gray: Image.Image, cell: int):
    """(p5, p50, p95) of the per-TILE mean luminance — the dark, mid and bright
    terrain bands as a player reads them (texture inside a tile averaged out)."""
    means = []
    for y in range(0, gray.height - cell + 1, cell):
        for x in range(0, gray.width - cell + 1, cell):
            means.append(_mean(gray, (x, y, x + cell, y + cell)))
    means.sort()
    pick = lambda q: means[min(len(means) - 1, int(len(means) * q))]   # noqa: E731
    return pick(0.05), pick(0.50), pick(0.95)


def _mean(gray: Image.Image, box) -> float:
    crop = list(gray.crop(box).getdata())
    return sum(crop) / len(crop) if crop else 0.0


def _ring_mean(gray: Image.Image, box, pad: int) -> float:
    """Mean luminance of the frame AROUND `box` (the background the sprite sits
    against): the padded box minus the box itself."""
    x0, y0, x1, y1 = box
    outer = (max(0, x0 - pad), max(0, y0 - pad),
             min(gray.width, x1 + pad), min(gray.height, y1 + pad))
    total, count = 0.0, 0
    for y in range(outer[1], outer[3]):
        for x in range(outer[0], outer[2]):
            if x0 <= x < x1 and y0 <= y < y1:
                continue
            total += gray.getpixel((x, y))
            count += 1
    return total / count if count else 0.0


def _frame(app: OverworldApp, phase: str, progress: float) -> Image.Image:
    app.engine.set_world_phase(phase)
    app.engine.player.world_time_seconds += daynight.PHASE_SECONDS[phase] * progress
    app.screen.fill((0, 0, 0))
    app._draw_map()
    app._draw_daylight_tint()
    app._draw_ambience()
    app._draw_hud()
    raw = pygame.image.tostring(app.screen, "RGB")
    return Image.frombytes("RGB", app.screen.get_size(), raw)


def render(out_dir: Path) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    app = OverworldApp()
    app.screen = pygame.Surface(VIEW)

    # Stand just outside the starting town so the frame carries open terrain,
    # cobble, a building and the hero — everything the rails measure against.
    town_tile = next(iter(app.zone.towns))
    app.world.set_tile(town_tile[0] + 3, town_tile[1] + 2)
    app.sync_location()

    zoom = app._zoom_factor()
    ox, oy = app.world.camera_offset(max(1, VIEW[0] // zoom), max(1, VIEW[1] // zoom))
    hero = app.world.player.move(-ox, -oy)
    hero_box = (hero.x * zoom, hero.y * zoom,
                (hero.x + hero.width) * zoom, (hero.y + hero.height) * zoom)

    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    day_stdev = None
    for phase in daynight.PHASE_ORDER:
        # Mid-phase for the transitions (that's where the interpolation lives).
        progress = 0.5 if phase in ("dawn", "dusk") else 0.25
        image = _frame(app, phase, progress)
        image.save(out_dir / f"b136_phase_{phase}.png")
        gray = _luminance(image)
        stdev = _stdev(gray)
        if phase == "day":
            day_stdev = stdev
        hero_delta = abs(_mean(gray, hero_box) - _ring_mean(gray, hero_box, 6 * zoom))
        low, mid, high = _tile_bands(gray, app.world.tw * zoom)
        band_gap = min(mid - low, high - mid)
        _r, _g, _b, a = daylight.tint_for(phase, progress)
        rows.append((phase, a, stdev, hero_delta, band_gap))

    day_gap = next(gap for phase, _a, _s, _h, gap in rows if phase == "day")
    print(f"RAIL: alpha cap {daylight.NIGHT_ALPHA} -> analytic "
          f"{daylight.contrast_retained(daylight.NIGHT_ALPHA):.1%} of contrast retained "
          f"(floor {daylight.MIN_CONTRAST_RETAINED:.0%})")
    print(f"{'phase':6} {'alpha':>5} {'contrast':>9} {'vs day':>7} "
          f"{'hero Δ':>7} {'tile band Δ':>12} {'vs day':>7}")
    for phase, alpha, stdev, hero_delta, band_gap in rows:
        ratio = stdev / day_stdev if day_stdev else 0.0
        gap_ratio = f"{band_gap / day_gap:.0%}" if day_gap else "-"
        ok = hero_delta >= MIN_SPRITE_DELTA and ratio >= daylight.MIN_CONTRAST_RETAINED
        print(f"{phase:6} {alpha:5d} {stdev:9.2f} {ratio:>6.1%} "
              f"{hero_delta:7.2f} {band_gap:12.1f} {gap_ratio:>7}"
              f"{'' if ok else '  <-- TOO DARK'}")
    print(f"floors: contrast vs day >= {daylight.MIN_CONTRAST_RETAINED:.0%} (the rail) · "
          f"hero Δ >= {MIN_SPRITE_DELTA} levels out of 255 (absolute)")
    print("tile band Δ is reported, not gated — see the module docstring.")
    pygame.quit()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    render(root / "docs" / "nightly")
