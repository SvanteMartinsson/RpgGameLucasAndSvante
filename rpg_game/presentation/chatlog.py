"""The single chatbox shared by the overworld and battle screens.

ONE log store (a deque of (payload, color) entries) rendered by ONE component,
so the combat log and the overworld log are the same surface. Also the single
semantic colour palette for log lines. Pure rendering helpers (pygame only); no
game rules here.

B44/B16.1 (v4): a payload is normally a plain str (whole line one colour), but
can be `Segments` — ((text, colour), ...) — for lines that mix colours (item
name in rarity colour + amber gold on the SAME row). Payloads also carry a
`channel` ("world" | "combat") so the overworld log can filter on tabs; plain
strs default to "world" and `ChannelText` tags without breaking str-consumers.
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


# --- Channels + payload types (B44/B16.1) ------------------------------------

CHANNEL_WORLD = "world"
CHANNEL_COMBAT = "combat"


class ChannelText(str):
    """A plain log line tagged with its channel. IS a str, so every existing
    consumer (equality, .lower(), rendering) keeps working untouched."""
    channel = CHANNEL_WORLD

    def __new__(cls, text: str, channel: str = CHANNEL_WORLD):
        obj = super().__new__(cls, text)
        obj.channel = channel
        return obj


class Segments(tuple):
    """A rich log line: ((text, colour), ...) — colours change WITHIN the row
    (rarity-coloured item name, amber gold). Tagged with a channel like
    ChannelText. `text` gives the plain-string view for dedupe/tests."""
    channel = CHANNEL_WORLD

    def __new__(cls, parts, channel: str = CHANNEL_WORLD):
        obj = super().__new__(cls, tuple(tuple(part) for part in parts))
        obj.channel = channel
        return obj

    @property
    def text(self) -> str:
        return "".join(part for part, _color in self)


def channel_of(payload) -> str:
    return getattr(payload, "channel", CHANNEL_WORLD)


def plain(payload) -> str:
    """The plain-text view of any payload (str passes through, Segments joins)."""
    if isinstance(payload, Segments):
        return payload.text
    return str(payload)


def push(event_log, message, color=TEXT, channel: str = CHANNEL_WORLD) -> bool:
    """Append (message, color) unless it exactly repeats the last line (dedupe).
    Returns True if it was appended."""
    if channel != CHANNEL_WORLD and isinstance(message, str) and not isinstance(message, ChannelText):
        message = ChannelText(message, channel)
    if event_log and event_log[-1][0] == message:
        return False
    event_log.append((message, color))
    return True


def push_rich(event_log, parts, color=TEXT, channel: str = CHANNEL_WORLD) -> bool:
    """Append a Segments line (per-segment colours). Deduped like push()."""
    payload = Segments(parts, channel)
    if event_log and event_log[-1][0] == payload:
        return False
    event_log.append((payload, color))
    return True


def wrap_lines(text: str, max_width: int, font: "pygame.font.Font") -> list[str]:
    """Word-wrap text to max_width px. B57: delegates to THE shared wrap in ui
    (kept as a thin adapter for this module's argument order)."""
    from rpg_game.presentation import ui
    return ui.wrap(text, font, max_width)


def wrap_segments(parts, max_width: int, font: "pygame.font.Font") -> list[tuple]:
    """Word-wrap a Segments payload to max_width px, preserving each word's
    segment colour. Returns visual lines as tuples of (text, colour) chunks
    (adjacent same-colour words merged)."""
    words: list[tuple[str, tuple]] = []
    for text, color in parts:
        words.extend((word, color) for word in str(text).split())
    lines: list[list[tuple[str, tuple]]] = []
    current: list[tuple[str, tuple]] = []

    def line_text(chunks) -> str:
        return " ".join(word for word, _c in chunks)

    for word, color in words:
        if current and font.size(line_text(current + [(word, color)]))[0] > max_width:
            lines.append(current)
            current = []
        current.append((word, color))
    if current:
        lines.append(current)

    merged_lines: list[tuple] = []
    for chunks in lines:
        merged: list[tuple[str, tuple]] = []
        for word, color in chunks:
            if merged and merged[-1][1] == color:
                merged[-1] = (merged[-1][0] + " " + word, color)
            else:
                if merged:
                    merged[-1] = (merged[-1][0] + " ", merged[-1][1])
                merged.append((word, color))
        merged_lines.append(tuple(merged))
    return merged_lines


def visual_lines(event_log, width: int, font: "pygame.font.Font",
                 channel: str | None = None) -> list[tuple]:
    """The log flattened to word-wrapped (payload, color, newest) visual lines;
    the newest entry's lines stay bright. Plain entries keep a str payload;
    Segments entries yield a tuple of (text, colour) chunks. `channel` filters
    entries to that channel (None = all — the ALL tab)."""
    entries = [entry for entry in event_log
               if channel is None or channel_of(entry[0]) == channel]
    out: list[tuple] = []
    for idx, (payload, color) in enumerate(entries):
        newest = idx == len(entries) - 1
        if isinstance(payload, Segments):
            for chunks in wrap_segments(payload, width, font):
                out.append((chunks, color, newest))
        else:
            for piece in wrap_lines(payload, width, font):
                out.append((piece, color, newest))
    return out


def draw(screen, rect: "pygame.Rect", event_log, font, *, visible: int, scroll: int,
         interactive: bool, edge, accent, channel: str | None = None) -> int:
    """Render the chatbox panel (bottom-left style): a semi-transparent box with
    `visible` word-wrapped lines ending at `scroll`, and a "v N more v" hint when
    scrolled up. Every line keeps its full semantic colour (history is NOT muted),
    so rarity/gold/xp/heal colours read the same old or new. Segments lines render
    chunk by chunk (colours change within the row). `channel` filters to a tab's
    channel (B16.1). Returns clamped scroll."""
    line_h = font.get_height() + 3
    pad = 8
    overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
    overlay.fill((10, 12, 18, 180 if interactive else 220))
    screen.blit(overlay, rect.topleft)
    pygame.draw.rect(screen, edge, rect, width=1, border_radius=4)
    lines = visual_lines(event_log, rect.width - pad * 2, font, channel=channel)
    n = len(lines)
    if not lines:
        return 0
    scroll = min(scroll, max(0, n - visible))
    end = n - scroll
    start = max(0, end - visible)
    for i, (payload, color, _newest) in enumerate(lines[start:end]):
        y = rect.y + pad + i * line_h
        if isinstance(payload, str):
            screen.blit(font.render(payload, True, color), (rect.x + pad, y))
        else:   # Segments visual line: (text, colour) chunks left-to-right
            x = rect.x + pad
            for text, chunk_color in payload:
                img = font.render(text, True, chunk_color)
                screen.blit(img, (x, y))
                x += img.get_width()
    if scroll:
        hint = font.render(f"v {scroll} more v", True, accent)
        screen.blit(hint, hint.get_rect(bottomright=(rect.right - pad, rect.bottom - 2)))
    return scroll
