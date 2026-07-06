"""B71: named save slots + the autosave.

Three manual slots + one autosave live under saves/ at the project root. This
module owns the paths, the cheap metadata peek the pickers show (name, class,
level, place, playtime — read straight from the JSON without a full
deserialize), and the one-time migration of the legacy root savegame.json into
slot 1. Writing/reading full saves stays on GameEngine.save/load.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SAVES_DIR = os.path.join(_PROJECT_ROOT, "saves")
SLOT_PATHS = tuple(os.path.join(SAVES_DIR, f"slot{i}.json") for i in (1, 2, 3))
AUTOSAVE_PATH = os.path.join(SAVES_DIR, "autosave.json")


@dataclass(frozen=True)
class SlotSummary:
    path: str
    name: str
    player_class: str
    level: int
    place_id: str
    playtime_seconds: int

    def playtime_label(self) -> str:
        hours, rest = divmod(self.playtime_seconds, 3600)
        minutes = rest // 60
        return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def ensure_saves_dir() -> None:
    os.makedirs(SAVES_DIR, exist_ok=True)


def migrate_legacy(legacy_path: str) -> bool:
    """Move a legacy root savegame.json into slot 1 (once): only when slot 1 is
    still empty. Returns True when a migration happened."""
    if not os.path.exists(legacy_path) or os.path.exists(SLOT_PATHS[0]):
        return False
    ensure_saves_dir()
    os.replace(legacy_path, SLOT_PATHS[0])
    return True


def slot_summary(path: str) -> SlotSummary | None:
    """The picker metadata for a save file, or None when absent/unreadable."""
    try:
        with open(path, encoding="utf-8") as save_file:
            data = json.load(save_file)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    player = data.get("player", data)
    if not isinstance(player, dict):
        return None
    return SlotSummary(
        path=path,
        name=str(player.get("name", "Hero")),
        player_class=str(player.get("player_class", "?")),
        level=int(player.get("level", 1)),
        place_id=str(player.get("current_place_id", "")),
        playtime_seconds=int(player.get("playtime_seconds", 0)),
    )


def all_summaries() -> list[SlotSummary | None]:
    """Summaries for the three manual slots (index = slot number - 1)."""
    return [slot_summary(path) for path in SLOT_PATHS]
