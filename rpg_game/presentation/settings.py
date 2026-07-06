"""B70: user settings — a tiny settings.json beside the saves (never in a save).

Presentation-level preferences only (display + HUD); game rules never read
this. Missing file or keys fall back to the defaults, unknown keys are kept
(forward-compatible), and writes are atomic enough for a prefs file.
"""

from __future__ import annotations

import json
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SETTINGS_PATH = os.path.join(_PROJECT_ROOT, "settings.json")

DEFAULTS = {
    "fullscreen": False,
    "log_visible": 10,     # chatbox rows (LOG_VISIBLE_MIN..MAX)
    "minimap": True,       # B11 minimap on by default
    "combat_fx": True,     # B72 floaters/blink/shake
    "combat_skip": False,  # B75 skip-click through round playback (Lucas: default off)
}


def load(path: str | None = None) -> dict:
    """The saved settings merged over the defaults (defaults on any error).
    The path resolves at CALL time so tests can patch SETTINGS_PATH."""
    path = path or SETTINGS_PATH
    merged = dict(DEFAULTS)
    try:
        with open(path, encoding="utf-8") as settings_file:
            data = json.load(settings_file)
        if isinstance(data, dict):
            merged.update(data)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return merged


def save(values: dict, path: str | None = None) -> None:
    path = path or SETTINGS_PATH
    try:
        with open(path, "w", encoding="utf-8") as settings_file:
            json.dump(values, settings_file, indent=2)
    except OSError:
        pass   # a prefs write must never crash the game
