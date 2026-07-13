"""B107 S2 acceptance: headless GIFs of the enemy attack choreography (mirror of
S1) for each weight class -> docs/nightly/b107s2_{quick,normal,power}.gif.

The enemy dashes LEFT toward the hero, the fx sheet + weighted damage number land
on the HERO, the hero flashes/shakes on impact, and the enemy idle holds still
during the swing. Pure presentation — no engine RNG is touched.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
from PIL import Image  # noqa: E402

from rpg_game.core import combat  # noqa: E402
from rpg_game.core.game import GameEngine  # noqa: E402
from rpg_game.presentation import pygame_battle as pb  # noqa: E402

WEIGHT_AMOUNT = {"quick": 6, "normal": 14, "power": 27}


def _pick_animated_enemy(engine) -> str:
    """An enemy with both an idle sheet (so the freeze reads) and a still."""
    for enemy_id in engine.content.enemies:
        if pb.enemy_idle_frames(enemy_id) and pb.enemy_sprite(enemy_id) is not None:
            return enemy_id
    # fall back to any enemy with a sprite
    for enemy_id in engine.content.enemies:
        if pb.enemy_sprite(enemy_id) is not None:
            return enemy_id
    return "cave_bear"


def _enemy_res(amount: int) -> "combat.ActionResolution":
    res = combat.ActionResolution(action_id="", action_name="Claw",
                                  actor_name="Foe", target_name="Hero")
    res.damage_components = [combat.DamageComponent(amount, "physical")]
    return res


def render_weight(weight: str, enemy_id: str, out: Path, scale: float = 0.5) -> None:
    engine = GameEngine()
    engine.start_new_game("Hero", "fighter")
    enemy = engine.content.enemies[enemy_id].create_enemy()
    battle = pb.BattleApp(engine=engine, enemy=enemy, standalone=False)
    battle._combat_fx = True
    # a few idle frames of lead-in so the still-vs-swing contrast is visible
    for _ in range(6):
        battle.draw()
    battle._start_choreography(weight, _enemy_res(WEIGHT_AMOUNT[weight]), attacker="enemy")

    frames: list[Image.Image] = []
    guard = 0
    trailing = 0
    while guard < 200:
        battle.draw()
        surf = battle.screen
        if scale != 1.0:
            size = (int(surf.get_width() * scale), int(surf.get_height() * scale))
            surf = pygame.transform.smoothscale(surf, size)
        raw = pygame.image.tostring(surf, "RGB")
        frames.append(Image.frombytes("RGB", surf.get_size(), raw))
        guard += 1
        if battle._choreo is None:
            trailing += 1
            if trailing >= 8:      # hold the settled frame briefly
                break

    out.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(out, save_all=True, append_images=frames[1:],
                   duration=33, loop=0, optimize=False)


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    root = Path(__file__).resolve().parents[2] / "docs" / "nightly"
    engine = GameEngine()
    engine.start_new_game("Hero", "fighter")
    enemy_id = _pick_animated_enemy(engine)
    for weight in ("quick", "normal", "power"):
        out = root / f"b107s2_{weight}.gif"
        render_weight(weight, enemy_id, out)
        print(f"wrote {out.name} (enemy={enemy_id})")
    pygame.quit()


if __name__ == "__main__":
    main()
