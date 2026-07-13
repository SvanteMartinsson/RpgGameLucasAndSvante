"""Render B132's two surfaces: the battle skill submenu (a clipped skill name
with its focus tooltip) and the character screen (equip slots showing their
type glyph even when filled). Pass 'before' or 'after' as the suffix."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from rpg_game.core.game import GameEngine  # noqa: E402
from rpg_game.presentation.pygame_battle import BattleApp  # noqa: E402
from rpg_game.presentation.pygame_overworld import OverworldApp  # noqa: E402


def render_skill(path: Path) -> None:
    engine = GameEngine()
    engine.start_new_game("Hero", "rogue")
    engine.player.learned_skill_ids = ("evasion", "riposte")
    # deadly_precision first so it is the focused (top-left) clipped cell.
    engine.player.equipped_skill_ids = ("deadly_precision", "rupture", "evasion", "riposte")
    enemy = engine.content.enemies["giant_rat"].create_enemy()
    battle = BattleApp(engine=engine, enemy=enemy, standalone=False)
    battle.open_submenu("skill")
    battle.draw()
    pygame.image.save(battle.screen, path)


def render_character(path: Path) -> None:
    engine = GameEngine()
    engine.start_new_game("Hero", "fighter")
    app = OverworldApp(engine=engine)
    app.display = pygame.Surface((980, 660))
    app.screen = pygame.Surface((980, 660))
    # Fill several slots so the type-glyph-when-filled treatment is visible.
    for gear_id, slot in (("padded_vest", "chest"), ("worn_boots", "feet"),
                          ("threadbare_gloves", "hands"), ("tin_amulet", "amulet")):
        if gear_id in engine.content.gear_items:
            engine.player.owned_gear_ids = (*engine.player.owned_gear_ids, gear_id)
            try:
                engine.equip_gear(gear_id, slot)
            except Exception:
                pass
    app.overlay = "character"
    app.draw()
    pygame.image.save(app.screen, path)


def main(suffix: str) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    root = Path(__file__).resolve().parents[2] / "docs" / "nightly"
    root.mkdir(parents=True, exist_ok=True)
    render_skill(root / f"b132_skill_cell_{suffix}.png")
    render_character(root / f"b132_character_slots_{suffix}.png")
    pygame.quit()
    print(f"wrote b132_skill_cell_{suffix}.png + b132_character_slots_{suffix}.png")


if __name__ == "__main__":
    import sys

    main(sys.argv[1] if len(sys.argv) > 1 else "after")
