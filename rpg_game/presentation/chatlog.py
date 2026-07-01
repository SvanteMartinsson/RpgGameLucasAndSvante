"""The single chatbox shared by the overworld and battle screens.

ONE log store (a deque of (text, color) entries) rendered by ONE component, so
the combat log and the overworld log are the same surface. Also the single
semantic colour palette for log lines. Pure rendering helpers (pygame only); no
game rules here.
"""

from __future__ import annotations

import pygame

# Scrollback + sizing (shared by both screens).
LOG_HISTORY_MAX = 200
LOG_VISIBLE_DEFAULT = 10
LOG_VISIBLE_MIN = 5
LOG_VISIBLE_MAX = 18
LOG_SCROLL_STEP = 2

# --- Semantic palette ------------------------------------------------------
# One table drives every log-line colour. Rarity is shown by the item name's
# COLOUR (no "[rare]" text in chat). "mega rare" maps to the epic swatch.
LOG_COLORS = {
    "common": (170, 170, 170),
    "uncommon": (120, 200, 120),
    "rare": (90, 160, 235),
    "epic": (185, 120, 235),
    "mega rare": (185, 120, 235),
    "legendary": (235, 150, 60),
    "gold": (220, 180, 90),
    "xp": (170, 140, 225),
    "levelup": (200, 150, 240),
    "heal": (120, 205, 140),
    "damage": (220, 110, 100),
    "system": (140, 140, 150),
    "text": (222, 226, 235),
}
GOLD = LOG_COLORS["gold"]
XP = LOG_COLORS["xp"]
LEVELUP = LOG_COLORS["levelup"]
HEAL = LOG_COLORS["heal"]
DAMAGE = LOG_COLORS["damage"]
SYSTEM = LOG_COLORS["system"]
TEXT = LOG_COLORS["text"]


def rarity_color(rarity: str) -> tuple[int, int, int]:
    return LOG_COLORS.get(rarity, LOG_COLORS["common"])


def push(event_log, message: str, color=TEXT) -> bool:
    """Append (message, color) unless it exactly repeats the last line (dedupe).
    Returns True if it was appended."""
    if event_log and event_log[-1][0] == message:
        return False
    event_log.append((message, color))
    return True


def wrap_lines(text: str, max_width: int, font: "pygame.font.Font") -> list[str]:
    """Word-wrap text to max_width px, breaking over-long words by character."""
    if max_width <= 0 or not text:
        return [text or ""]
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = word if not current else f"{current} {word}"
        if font.size(candidate)[0] <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        if font.size(word)[0] <= max_width:
            current = word
        else:                                   # break a word too long for the box
            chunk = ""
            for char in word:
                if font.size(f"{chunk}{char}")[0] <= max_width:
                    chunk += char
                else:
                    lines.append(chunk)
                    chunk = char
            current = chunk
    if current:
        lines.append(current)
    return lines or [""]


def visual_lines(event_log, width: int, font: "pygame.font.Font") -> list[tuple[str, tuple, bool]]:
    """The log flattened to word-wrapped (text, color, newest) visual lines; the
    newest entry's lines stay bright."""
    entries = list(event_log)
    out: list[tuple[str, tuple, bool]] = []
    for idx, (text, color) in enumerate(entries):
        newest = idx == len(entries) - 1
        for piece in wrap_lines(text, width, font):
            out.append((piece, color, newest))
    return out


def draw(screen, rect: "pygame.Rect", event_log, font, *, visible: int, scroll: int,
         interactive: bool, edge, accent) -> int:
    """Render the chatbox panel (bottom-left style): a semi-transparent box with
    `visible` word-wrapped lines ending at `scroll`, and a "v N more v" hint when
    scrolled up. Every line keeps its full semantic colour (history is NOT muted),
    so rarity/gold/xp/heal colours read the same old or new. Returns clamped scroll."""
    line_h = font.get_height() + 3
    pad = 8
    overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
    overlay.fill((10, 12, 18, 180 if interactive else 220))
    screen.blit(overlay, rect.topleft)
    pygame.draw.rect(screen, edge, rect, width=1, border_radius=4)
    lines = visual_lines(event_log, rect.width - pad * 2, font)
    n = len(lines)
    if not lines:
        return 0
    scroll = min(scroll, max(0, n - visible))
    end = n - scroll
    start = max(0, end - visible)
    for i, (text, color, _newest) in enumerate(lines[start:end]):
        screen.blit(font.render(text, True, color), (rect.x + pad, rect.y + pad + i * line_h))
    if scroll:
        hint = font.render(f"v {scroll} more v", True, accent)
        screen.blit(hint, hint.get_rect(bottomright=(rect.right - pad, rect.bottom - 2)))
    return scroll
