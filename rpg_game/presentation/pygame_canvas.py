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

import os

import pygame

# SCALED lets SDL scale the logical render surface up to the real (HiDPI/Retina)
# framebuffer with integer scaling — crisp pixel art, and content fills the screen
# instead of sitting 1:1 in the top-left of a 2x buffer. RESIZABLE (not exclusive
# FULLSCREEN) keeps the macOS window controls + app-switching; the OS green button
# still gives true native fullscreen.
WINDOW_FLAGS = pygame.RESIZABLE | pygame.SCALED
# Leave headroom for the OS menu bar / dock / title bar so the window fits.
_DESKTOP_MARGIN = 0.92


def set_display_mode(size: tuple[int, int], flags: int = WINDOW_FLAGS) -> pygame.Surface:
    """set_mode with two safeguards:

    1. Headless fallback: if no hardware renderer exists (dummy driver in tests),
       SCALED can't initialize, so retry without it.
    2. macOS-HiDPI anchoring fix (the recurring fullscreen bug): on some monitors
       SCALED yields a *logical* surface smaller than the *physical* window and
       fails to upscale it, so content sits 1:1 in the top-left of a 2x buffer.
       Every correctly-filled frame has surface size == window size, so if they
       diverge we recreate at the real window size without SCALED (we scale the
       canvas crisply in present()/draw() instead). One-time, at creation."""
    try:
        surface = pygame.display.set_mode(size, flags)
    except pygame.error:
        surface = pygame.display.set_mode(size, flags & ~pygame.SCALED)
    try:
        window = pygame.display.get_window_size()
    except Exception:  # pragma: no cover - driver without window info
        window = surface.get_size()
    if window[0] > 0 and window[1] > 0 and window != surface.get_size():
        surface = pygame.display.set_mode(window, flags & ~pygame.SCALED)
    return surface

Transform = tuple[int, int, float]

# Set RPG_DISPLAY_DEBUG=1 to log display geometry at every change. Kept in for
# diagnosing fullscreen anchoring regressions (the bug that recurs). It prints
# the LOGICAL surface present() centers against, the OS window size, the desktop
# sizes, the canvas, and the transform — a logical-vs-physical gap (e.g. Retina
# 2x) shows up as content that centers in the math yet sits top-left on screen.
_DISPLAY_DEBUG = bool(os.environ.get("RPG_DISPLAY_DEBUG"))
# Lines are also appended here so they survive the window closing. Override with
# RPG_DISPLAY_DEBUG_LOG. The file is truncated once per process at import.
_DEBUG_LOG_PATH = os.environ.get("RPG_DISPLAY_DEBUG_LOG", "/tmp/rpg_display_debug.log")
_last_debug_key = None

if _DISPLAY_DEBUG:
    try:
        with open(_DEBUG_LOG_PATH, "w", encoding="utf-8") as _fh:
            _fh.write("# rpg display debug — surface(get_size) is what present() centers against\n")
    except Exception:  # pragma: no cover - logging must never break the game
        pass


def _debug_display(tag: str, display: pygame.Surface, transform: Transform | None = None) -> None:
    if not _DISPLAY_DEBUG:
        return
    global _last_debug_key
    try:
        window = pygame.display.get_window_size()
    except Exception:
        window = None
    try:
        desktops = pygame.display.get_desktop_sizes()
    except Exception:
        desktops = None
    key = (tag, display.get_size(), window, transform)
    if key == _last_debug_key:
        return
    _last_debug_key = key
    line = (f"[display:{tag}] surface(get_size)={display.get_size()} window={window} "
            f"desktops={desktops} transform={transform}")
    print(line, flush=True)
    try:
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:  # pragma: no cover
        pass


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
    """Open a normal resizable (SCALED) window, clamped so it fits the desktop."""
    return set_display_mode(fit_size(preferred), WINDOW_FLAGS)


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
    transform = (ox, oy, scale)
    _debug_display(f"present canvas={cw}x{ch}", display, transform)
    return transform


def to_canvas(pos: tuple[int, int], transform: Transform) -> tuple[int, int]:
    """Translate a display-space position into canvas space."""
    ox, oy, scale = transform
    scale = scale or 1.0
    return (int((pos[0] - ox) / scale), int((pos[1] - oy) / scale))
