"""B136d: prove the per-phase ambience — a GIF per zone, plus an fps cost check.

Writes docs/nightly/b136_ambience_<zone>_<phase>.gif (day + night for every
zone) so the firefly move is reviewable side by side, then measures the frame
cost the layer adds IN EACH PHASE.

The B73 budget is <5% of FRAME TIME, so the denominator is the 60 fps frame
budget (16.67 ms) — not the map draw, which under the dummy video driver on a
small surface takes well under a millisecond and would make any absolute cost
look enormous as a ratio. Both numbers are printed; only the frame-budget one
is gated.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
from PIL import Image  # noqa: E402

from rpg_game.presentation.pygame_overworld import OverworldApp  # noqa: E402

VIEW = (640, 400)
ZONES = ("cainos", "mork_skog", "cursed_mire", "grave_heath")
PHASES = ("day", "night")
BUDGET = 0.05          # B73: the layer may cost at most 5% of frame time
FRAME_BUDGET = 1.0 / 60.0   # the denominator that actually means "fps cost"
WARMUP = 20
SAMPLES = 120


def _tile_for(app: OverworldApp, theme: str):
    """A walkable-ish tile inside `theme`. grave_heath is a southern y-band
    (min_tile_y 100), so the scan has to sweep the full map, not a few rows."""
    for y in range(10, app.world.tmx.height - 10, 5):
        for x in range(10, app.world.tmx.width - 10, 5):
            if app.zone.theme_for_tile((x, y)) == theme:
                return (x, y)
    return None


def _measure(app: OverworldApp) -> tuple[float, float]:
    """(map-only seconds/frame, map+ambience seconds/frame), best-of timing."""
    for _ in range(WARMUP):
        app.screen.fill((0, 0, 0))
        app._draw_map()
        app._draw_daylight_tint()
        app._draw_ambience()

    start = time.perf_counter()
    for _ in range(SAMPLES):
        app.screen.fill((0, 0, 0))
        app._draw_map()
        app._draw_daylight_tint()
    bare = (time.perf_counter() - start) / SAMPLES

    start = time.perf_counter()
    for _ in range(SAMPLES):
        app.screen.fill((0, 0, 0))
        app._draw_map()
        app._draw_daylight_tint()
        app._draw_ambience()
    full = (time.perf_counter() - start) / SAMPLES
    return bare, full


def render(out_dir: Path) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    app = OverworldApp()
    app.screen = pygame.Surface(VIEW)
    app._settings["ambience"] = True
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for theme in ZONES:
        tile = _tile_for(app, theme)
        if tile is None:
            print(f"{theme}: no tile found, skipped")
            continue
        for phase in PHASES:
            app.world.set_tile(*tile)
            app.sync_location()
            app.engine.set_world_phase(phase)
            app._ambience = None

            frames = []
            for _ in range(30):
                app.screen.fill((0, 0, 0))
                app._draw_map()
                app._draw_daylight_tint()
                app._draw_ambience()
                raw = pygame.image.tostring(app.screen, "RGB")
                frames.append(Image.frombytes("RGB", app.screen.get_size(), raw))
            path = out_dir / f"b136_ambience_{theme}_{phase}.gif"
            frames[0].save(path, save_all=True, append_images=frames[1:],
                           duration=85, loop=0, optimize=False)

            bare, full = _measure(app)
            overhead = (full - bare) / bare if bare else 0.0
            kind = app._ambience.preset.get("kind", "firefly")
            count = len(app._ambience.particles)
            rows.append((theme, phase, kind, count, bare, full, overhead))

    print(f"{'zone':13} {'phase':6} {'kind':8} {'n':>4} "
          f"{'map ms':>8} {'+amb ms':>8} {'amb ms':>7} {'of frame':>9} {'of map':>8}")
    worst = 0.0
    for theme, phase, kind, count, bare, full, overhead in rows:
        cost = full - bare
        share = cost / FRAME_BUDGET
        worst = max(worst, share)
        flag = "" if share <= BUDGET else "  <-- OVER BUDGET"
        print(f"{theme:13} {phase:6} {kind:8} {count:4d} "
              f"{bare * 1000:8.2f} {full * 1000:8.2f} {cost * 1000:7.2f} "
              f"{share:8.1%} {overhead:7.0%}{flag}")
    print(f"budget {BUDGET:.0%} of the {FRAME_BUDGET * 1000:.2f} ms 60fps frame "
          f"· worst measured {worst:.1%}")
    pygame.quit()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    render(root / "docs" / "nightly")
