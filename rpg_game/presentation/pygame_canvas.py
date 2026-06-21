"""Helpers for presenting fixed-layout screens at any window size.

The battle shell, character creation and the start menu are authored against a
fixed design size. Rather than reflow them, they draw onto a fixed-size canvas
that is blitted *centered* onto the actual display surface (which may be a
window or a borderless-fullscreen surface of any size), with the background
filling the rest. This preserves their aspect/layout and keeps them centered and
on-screen in both display modes — no hardcoded assumptions about the real
window size leak into the drawing code.

Mouse input is in display coordinates, so callers translate it back into canvas
coordinates with ``to_canvas`` using the offset ``present`` returns.
"""

from __future__ import annotations

import pygame


def acquire_display(default_size: tuple[int, int]) -> pygame.Surface:
    """Return the current display surface, creating a window if none exists.

    Reusing the existing surface lets a screen inherit the caller's display mode
    (e.g. a battle entered from a fullscreen overworld stays fullscreen).
    """
    surface = pygame.display.get_surface()
    if surface is None or surface.get_size() == (0, 0):
        surface = pygame.display.set_mode(default_size)
    return surface


def present(display: pygame.Surface, canvas: pygame.Surface, bg) -> tuple[int, int]:
    """Fill the display, blit the canvas centered, flip; return the offset.

    The offset is clamped to be non-negative so the canvas's top-left stays on
    screen even if the display is smaller than the canvas.
    """
    display.fill(bg)
    offset = (
        max(0, (display.get_width() - canvas.get_width()) // 2),
        max(0, (display.get_height() - canvas.get_height()) // 2),
    )
    display.blit(canvas, offset)
    pygame.display.flip()
    return offset


def to_canvas(pos: tuple[int, int], offset: tuple[int, int]) -> tuple[int, int]:
    """Translate a display-space mouse position into canvas space."""
    return (pos[0] - offset[0], pos[1] - offset[1])
