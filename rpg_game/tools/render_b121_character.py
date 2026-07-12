"""Render B121's character screen — a fully-equipped and an empty state.

The centre figure is the Lucas-locked placeholder (dark hood-open cloak, cyan
eyes); the real illustration drops in later. Left = stats total (+from_gear),
right = the full scrollable inventory (rarity-coloured).
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from rpg_game.core.game import GameEngine  # noqa: E402
from rpg_game.presentation.pygame_overworld import OverworldApp  # noqa: E402


def _app(engine: GameEngine) -> OverworldApp:
    app = OverworldApp(engine=engine)
    app.display = pygame.Surface((980, 660))
    app.screen = pygame.Surface((980, 660))
    app.overlay = "character"
    return app


def render(out_dir: Path) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    out_dir.mkdir(parents=True, exist_ok=True)

    # Fully equipped: gear in several slots + a spread of owned items to scroll.
    full = GameEngine()
    full.start_new_game("Verra", "fighter")
    full.player.owned_weapon_ids = tuple(dict.fromkeys(
        (*full.player.owned_weapon_ids, "sword", "rimebrand")))
    full.player.owned_gear_ids = (
        "training_cap", "padded_vest", "threadbare_gloves", "patched_trousers",
        "worn_boots", "tin_amulet", "novice_ring", "swift_ring", "guard_cap")
    for gear_id, slot in (("padded_vest", "chest"), ("training_cap", "head"),
                          ("threadbare_gloves", "hands"), ("patched_trousers", "legs"),
                          ("worn_boots", "feet"), ("tin_amulet", "amulet")):
        full.equip_gear(gear_id, slot)
    full.equip_gear("novice_ring")
    full.equip_gear("swift_ring")
    full.player.inventory.add_consumable("hp_potion")
    full.player.inventory.add_consumable("hp_potion")
    app = _app(full)
    app.draw()
    pygame.image.save(app.screen, out_dir / "b121_character_full.png")

    # Empty: a fresh character with nothing equipped beyond the starter weapon.
    bare = GameEngine()
    bare.start_new_game("Verra", "fighter")
    app = _app(bare)
    app.draw()
    pygame.image.save(app.screen, out_dir / "b121_character_empty.png")

    pygame.quit()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    render(root / "docs" / "nightly")
    print("wrote B121 character-screen renders (full + empty)")
