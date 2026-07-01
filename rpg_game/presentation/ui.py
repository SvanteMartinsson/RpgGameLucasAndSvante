"""Shared menu-UI primitives for the pygame screens (overworld + battle).

SLICE 1 of the menu program: the foundation the 7-point menu spec builds on. It
supplies ONE Button (a superset of the old per-screen dataclasses), a hover
timer + tooltip renderer, and a reusable menu-row renderer. Pure pygame
rendering + geometry — NO game rules here. Screens keep owning their own event
loops and button lists; this module only provides the widgets they share.

This slice introduces the primitives WITHOUT changing menu content — the
inventory/shop/character/creation apply-slices adopt them later.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame


# --- unified Button --------------------------------------------------------
@dataclass
class Button:
    """The single button both screens use — the superset of the two old ones:

    - ``restricted``: overworld's "clickable but sperred-looking" state (a
      level-locked row still fires so the player gets a "needs level N" reason).
    - ``hotkey`` / ``sublabel``: battle's keyboard trigger + optional secondary
      label.

    ``on_click`` is usually a zero-arg callable, but the start menu stores a
    plain string result there, so it is typed permissively (``object``).
    """

    rect: "pygame.Rect"
    label: str
    on_click: object
    enabled: bool = True
    restricted: bool = False
    hotkey: str = ""
    sublabel: str = ""


# --- hover / tooltip -------------------------------------------------------
HOVER_DELAY_MS = 1000     # dwell time before a tooltip appears (~1 s)

# Tooltip palette (self-contained so both screens get one consistent look).
TOOLTIP_BG = (18, 20, 28)
TOOLTIP_EDGE = (92, 98, 122)
TOOLTIP_TITLE = (224, 228, 236)
TOOLTIP_VALUE = (196, 202, 216)
TOOLTIP_BODY = (150, 156, 172)
TOOLTIP_ALPHA = 240


@dataclass
class Tooltip:
    """What a hover popup shows: a title, zero or more stat/value rows, and a
    short free-text description. Any part may be empty."""

    title: str
    lines: list = field(default_factory=list)   # e.g. ["Damage: 12", "Tier 3"]
    body: str = ""                               # short description paragraph


@dataclass
class HoverTracker:
    """Per-frame hover state shared by both screens.

    Each frame the screen calls ``begin()``, registers the hoverable rects with
    ``add(rect, payload)``, then ``update(mouse_pos, now_ms)``. When the mouse
    dwells on ONE rect for longer than ``delay_ms`` the payload becomes
    ``active`` (what the tooltip renders). Moving onto a different rect restarts
    the timer; leaving every rect clears ``active``.

    No zones registered -> ``active`` stays None -> nothing draws, so wiring this
    into a loop is a no-op until a menu opts in with ``add()``.
    """

    delay_ms: int = HOVER_DELAY_MS
    _zones: list = field(default_factory=list)   # (rect, payload)
    _key: object = None                          # geometry of the dwelt-on rect
    _since_ms: int = 0                           # when the current dwell began
    active: object = None                        # payload past the delay

    def begin(self) -> None:
        self._zones = []

    def add(self, rect, payload) -> None:
        """Register a hoverable rect + its tooltip payload. Ignored if payload
        is None (a row with nothing to explain simply isn't hoverable)."""
        if payload is not None:
            self._zones.append((pygame.Rect(rect), payload))

    def update(self, mouse_pos, now_ms) -> None:
        hit = next(((r, p) for r, p in self._zones if r.collidepoint(mouse_pos)), None)
        if hit is None:
            self._key = None
            self.active = None
            return
        rect, payload = hit
        key = tuple(rect)
        if key != self._key:                    # moved onto a new zone -> restart
            self._key = key
            self._since_ms = now_ms
            self.active = None
        elif self.active is None and now_ms - self._since_ms >= self.delay_ms:
            self.active = payload                # dwell satisfied -> show it


def _wrap(text: str, font: "pygame.font.Font", max_width: int) -> list:
    """Greedy word-wrap to max_width px (character-breaks an over-long word)."""
    if max_width <= 0 or not text:
        return [text or ""]
    lines: list = []
    current = ""
    for word in text.split():
        candidate = word if not current else f"{current} {word}"
        if font.size(candidate)[0] <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        if font.size(word)[0] <= max_width:
            current = word
        else:
            chunk = ""
            for ch in word:
                if font.size(f"{chunk}{ch}")[0] <= max_width:
                    chunk += ch
                else:
                    lines.append(chunk)
                    chunk = ch
            current = chunk
    if current:
        lines.append(current)
    return lines or [""]


def draw_tooltip(screen, tooltip: "Tooltip", anchor, title_font, body_font,
                 *, max_width: int = 280) -> "pygame.Rect":
    """Render a tooltip panel near ``anchor`` (usually the mouse), clamped inside
    the screen. ``title_font`` draws the title; ``body_font`` draws the stat rows
    and the wrapped description. Returns the drawn rect."""
    pad = 10
    gap = 3
    inner_w = max(1, max_width - 2 * pad)
    rows: list = [title_font.render(tooltip.title, True, TOOLTIP_TITLE)]
    for line in tooltip.lines:
        rows.append(body_font.render(str(line), True, TOOLTIP_VALUE))
    if tooltip.body:
        for line in _wrap(tooltip.body, body_font, inner_w):
            rows.append(body_font.render(line, True, TOOLTIP_BODY))
    width = min(max_width, max(s.get_width() for s in rows) + 2 * pad)
    height = sum(s.get_height() for s in rows) + gap * (len(rows) - 1) + 2 * pad

    ax, ay = anchor
    rect = pygame.Rect(ax + 16, ay + 16, width, height)
    sw, sh = screen.get_size()
    if rect.right > sw:
        rect.right = min(sw - 4, ax - 4)          # flip to the mouse's left
    if rect.left < 0:
        rect.left = 4
    if rect.bottom > sh:
        rect.bottom = min(sh - 4, ay - 4)         # flip above the mouse
    if rect.top < 0:
        rect.top = 4

    panel = pygame.Surface(rect.size, pygame.SRCALPHA)
    panel.fill((*TOOLTIP_BG, TOOLTIP_ALPHA))
    screen.blit(panel, rect.topleft)
    pygame.draw.rect(screen, TOOLTIP_EDGE, rect, width=1, border_radius=5)
    y = rect.y + pad
    for surf in rows:
        screen.blit(surf, (rect.x + pad, y))
        y += surf.get_height() + gap
    return rect
