"""B136b: the darkness tint — how a phase looks, as a pure colour rule.

The world's art NEVER changes with the hour. Night is one translucent rectangle
blitted over the finished map, and this module answers the only question that
needs answering: given (phase, progress-inside-phase), what RGBA is it?

Keyframes per phase, linearly interpolated over the phase's progress, so the sky
slides instead of snapping at a boundary:

    dawn   night blue  -> a rosy glow -> clear      (the light comes back)
    day    clear
    dusk   clear -> a warm amber damp -> night blue (the warning)
    night  night blue

THE READABILITY RAIL. Blitting an alpha-`a` overlay scales every luminance
DIFFERENCE in the frame by (1 - a/255) — tiles, the player sprite and the enemy
sprites all lose contrast by exactly that factor, and a tint can never ADD
separation back. `NIGHT_ALPHA` is therefore capped so at least
`MIN_CONTRAST_RETAINED` of daylight's contrast survives. That is an analytic
rail, not a taste call, and tools/render_b136_phases.py confirms it on a real
frame: at alpha 125 the night keeps 51% of the day frame's contrast and the hero
still stands 19 luminance levels clear of the ground it walks on (the floor is
8). Going darker than the cap makes the game unplayable, not atmospheric.

Pure presentation: no game rules, no engine rng, no pygame types in the API.
"""

from __future__ import annotations

# A tint is (r, g, b, a); a == 0 means "draw nothing at all".
CLEAR = (0, 0, 0, 0)

# The readability rail (see the module docstring). Keep at least half of
# daylight's contrast; 125/255 sits just inside that at 51.0%. Lucas's night pass
# on the rendered alpha ladder (100 / 130 / 160) put the "reads as night, still
# reads as a map" point right here — 100 was overcast rather than dark.
MIN_CONTRAST_RETAINED = 0.50
NIGHT_ALPHA = 125

NIGHT_TINT = (14, 20, 52, NIGHT_ALPHA)      # deep, cold blue
DUSK_GLOW = (92, 48, 26, 55)                # warm amber damp, half-way through dusk
DAWN_GLOW = (96, 60, 70, 45)                # rosy, half-way through dawn

# phase -> ((progress, rgba), ...) ascending by progress. First/last entries pin
# the phase's ends, so consecutive phases agree at their shared boundary.
KEYFRAMES: dict[str, tuple[tuple[float, tuple[int, int, int, int]], ...]] = {
    "dawn": ((0.0, NIGHT_TINT), (0.5, DAWN_GLOW), (1.0, CLEAR)),
    "day": ((0.0, CLEAR), (1.0, CLEAR)),
    "dusk": ((0.0, CLEAR), (0.6, DUSK_GLOW), (1.0, NIGHT_TINT)),
    "night": ((0.0, NIGHT_TINT), (1.0, NIGHT_TINT)),
}

# HUD indicator dot colour per phase (the label text comes from core.daynight).
PHASE_COLORS: dict[str, tuple[int, int, int]] = {
    "dawn": (232, 168, 150),
    "day": (240, 214, 130),
    "dusk": (206, 132, 74),
    "night": (128, 150, 214),
}


def contrast_retained(alpha: int) -> float:
    """The fraction of the frame's luminance contrast an alpha-`alpha` overlay
    leaves behind. Blending is c' = c*(1-a/255) + tint*(a/255), so a DIFFERENCE
    between two pixels is scaled by exactly (1 - a/255)."""
    return 1.0 - max(0, min(255, int(alpha))) / 255.0


def tint_for(phase: str, progress: float = 0.0) -> tuple[int, int, int, int]:
    """The overlay RGBA for a phase at `progress` (0..1) through it.

    An unknown phase reads as full daylight — a broken phase string must never
    black the screen out.
    """
    frames = KEYFRAMES.get(phase)
    if frames is None:
        return CLEAR
    position = max(0.0, min(1.0, float(progress)))
    previous_at, previous = frames[0]
    for at, rgba in frames[1:]:
        if position <= at:
            span = at - previous_at
            ratio = 0.0 if span <= 0.0 else (position - previous_at) / span
            return _lerp(previous, rgba, ratio)
        previous_at, previous = at, rgba
    return previous


def _lerp(a: tuple[int, int, int, int], b: tuple[int, int, int, int],
          ratio: float) -> tuple[int, int, int, int]:
    return tuple(int(round(start + (end - start) * ratio)) for start, end in zip(a, b))
