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
    "ambience": True,      # B73 S2 zone particle layer
    "sound_master": 1.0,   # B69 master volume 0.0..1.0 (SFX play at master × sfx)
    "sound_sfx": 1.0,      # B69 SFX bus volume 0.0..1.0
    "sound_music": 1.0,    # B69 music bus volume 0.0..1.0 (loop at master × music)
    "last_class": "",      # B119 class the load-lock is anchored to ("" = none yet)
}


# B92: THE options list both settings surfaces (start menu + in-game overlay)
# render, so they can never diverge again. kind: "toggle" flips on/off,
# "steps" cycles through the tuple, "slider" is a 0.0-1.0 volume (the in-game
# overlay drags it, the start menu cycles it in 10% steps). "hotkey" is a
# display hint for the in-game overlay.
OPTIONS = (
    {"key": "fullscreen", "label": "Fullscreen", "kind": "toggle", "hotkey": "F11"},
    {"key": "log_visible", "label": "Log rows", "kind": "steps", "steps": (5, 8, 10, 12, 14, 18)},
    {"key": "minimap", "label": "Minimap", "kind": "toggle", "hotkey": "N"},
    {"key": "combat_fx", "label": "Combat animations", "kind": "toggle"},
    {"key": "combat_skip", "label": "Combat skip-click", "kind": "toggle"},
    {"key": "ambience", "label": "Ambience", "kind": "toggle"},
    {"key": "sound_music", "label": "Music volume", "kind": "slider"},
)


def option_label(option: dict, value) -> str:
    if option["kind"] == "toggle":
        return f"{option['label']}: {'On' if value else 'Off'}"
    if option["kind"] == "slider":
        try:
            percent = int(round(max(0.0, min(1.0, float(value))) * 100))
        except (TypeError, ValueError):
            percent = 100
        return f"{option['label']}: {percent}"
    return f"{option['label']}: {value}"


def cycle_value(option: dict, value):
    """The next value a click-to-cycle surface (start menu) moves to."""
    if option["kind"] == "toggle":
        return not value
    if option["kind"] == "steps":
        bigger = [step for step in option["steps"] if step > value]
        return bigger[0] if bigger else option["steps"][0]
    try:
        percent = int(round(max(0.0, min(1.0, float(value))) * 100))
    except (TypeError, ValueError):
        percent = 100
    return 0.0 if percent >= 100 else min(100, percent + 10) / 100


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


# --- B119: class-locked save loading ---------------------------------------
def profile_class(path: str | None = None) -> str:
    """The class the player is currently locked to for loading ("" until the
    first game starts). Resolves the path at CALL time so tests can patch
    SETTINGS_PATH, like load()."""
    return str(load(path).get("last_class", "") or "")


def set_profile_class(class_id: str, path: str | None = None) -> None:
    """Anchor the load-lock to class_id when a game is started or loaded. Keeps
    every other pref intact (load-merge, then persist)."""
    values = load(path)
    values["last_class"] = class_id
    save(values, path)
