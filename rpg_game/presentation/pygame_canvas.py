"""Helpers for windowing and presenting fixed-layout screens at any size.

The battle shell, character creation and the start menu are authored against a
fixed design size. Rather than reflow them, they draw onto a fixed-size canvas
that ``present`` blits onto the real display surface: centered at native size
when the display is at least as large, and **scaled down to fit** (preserving
aspect) when it is smaller — so no content is ever clipped off-screen. The
background fills the rest.

Windowed mode is a normal resizable OS window (``pygame.RESIZABLE``), and the
initial size is clamped to the desktop work area so it can never open larger
than the screen. ``present`` returns a transform ``(offset_x, offset_y, scale)``
and ``to_canvas`` maps display-space mouse positions back into canvas space.
"""

from __future__ import annotations

import pygame

WINDOW_FLAGS = pygame.RESIZABLE
# Leave headroom for the OS menu bar / dock / title bar so the window fits.
_DESKTOP_MARGIN = 0.92

Transform = tuple[int, int, float]


def desktop_size() -> tuple[int, int]:
    try:
        sizes = pygame.display.get_desktop_sizes()
        if sizes and sizes[0][0] > 0 and sizes[0][1] > 0:
            return sizes[0]
    except Exception:  # pragma: no cover - driver without desktop info
        pass
    info = pygame.display.Info()
    return (info.current_w, info.current_h)


def fit_size(preferred: tuple[int, int]) -> tuple[int, int]:
    """Clamp a preferred window size to the available desktop work area."""
    dw, dh = desktop_size()
    if dw <= 0 or dh <= 0:
        return preferred
    return (min(preferred[0], int(dw * _DESKTOP_MARGIN)),
            min(preferred[1], int(dh * _DESKTOP_MARGIN)))


def open_window(preferred: tuple[int, int]) -> pygame.Surface:
    """Open a normal resizable window, clamped so it fits the desktop."""
    return pygame.display.set_mode(fit_size(preferred), WINDOW_FLAGS)


def acquire_display(default_size: tuple[int, int]) -> pygame.Surface:
    """Return the current display surface, creating a resizable window if none
    exists. Reusing the existing surface lets a screen inherit the caller's
    display mode (e.g. a battle entered from a fullscreen overworld)."""
    surface = pygame.display.get_surface()
    if surface is None or surface.get_size() == (0, 0):
        surface = open_window(default_size)
    return surface


def present(display: pygame.Surface, canvas: pygame.Surface, bg) -> Transform:
    """Fill the display, blit the canvas (scaled to fit, centered), flip."""
    display.fill(bg)
    dw, dh = display.get_size()
    cw, ch = canvas.get_size()
    scale = min(1.0, dw / cw, dh / ch) if cw and ch else 1.0
    if scale < 1.0:
        frame = pygame.transform.scale(canvas, (max(1, int(cw * scale)), max(1, int(ch * scale))))
    else:
        frame = canvas
    fw, fh = frame.get_size()
    ox, oy = max(0, (dw - fw) // 2), max(0, (dh - fh) // 2)
    display.blit(frame, (ox, oy))
    pygame.display.flip()
    return (ox, oy, scale)


def to_canvas(pos: tuple[int, int], transform: Transform) -> tuple[int, int]:
    """Translate a display-space position into canvas space."""
    ox, oy, scale = transform
    scale = scale or 1.0
    return (int((pos[0] - ox) / scale), int((pos[1] - oy) / scale))
