"""Render the zone reference map (docs/ZONE_MAP.png).

B48 authoring aid: the in-game M-map schematic, upscaled, with the wild-region
bands tinted and labelled, every town named, and the B65 boss lairs marked.
Regenerate after changing zones/lairs:

    .venv/bin/python -m rpg_game.tools.worldgen.render_zone_map

Render-only — touches no game data and no seeded streams.
"""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

SCALE = 5
# zone id -> (tint RGBA, label). Bands come from core_zone wild_regions (first
# match wins): heath y>=100, mire x>=159, skog x>=83, else cainos.
ZONES = {
    "cainos": ((235, 210, 90, 34), "CAINOS"),
    "mork_skog": ((40, 120, 50, 40), "MORK SKOG"),
    "cursed_mire": ((90, 60, 140, 44), "CURSED MIRE"),
    "grave_heath": ((110, 120, 140, 44), "GRAVE HEATH"),
}
ZONE_POOL_PLACE = {"cainos": "burg_54", "mork_skog": "burg_146",
                   "cursed_mire": "burg_320", "grave_heath": "burg_121"}
BOUNDARY = (255, 255, 255)
LAIR = (235, 80, 80)
TOWN = (250, 245, 230)
POOL_TOWN = (255, 210, 90)


def zone_at(x: int, y: int) -> str:
    if y >= 100:
        return "grave_heath"
    if x >= 159:
        return "cursed_mire"
    if x >= 83:
        return "mork_skog"
    return "cainos"


def render(out_path: str) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    from rpg_game.presentation.pygame_overworld import OverworldApp

    app = OverworldApp()
    terrain = app._build_map_terrain()
    w, h = terrain.get_size()
    surf = pygame.transform.scale(terrain, (w * SCALE, h * SCALE))

    # Zone tints + boundary lines
    tint = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    for zone, (color, _) in ZONES.items():
        for (x0, y0, x1, y1) in _zone_rects(zone, w, h):
            tint.fill(color, pygame.Rect(x0 * SCALE, y0 * SCALE,
                                         (x1 - x0) * SCALE, (y1 - y0) * SCALE))
    surf.blit(tint, (0, 0))
    pygame.draw.line(surf, BOUNDARY, (83 * SCALE, 0), (83 * SCALE, 100 * SCALE), 2)
    pygame.draw.line(surf, BOUNDARY, (159 * SCALE, 0), (159 * SCALE, 100 * SCALE), 2)
    pygame.draw.line(surf, BOUNDARY, (0, 100 * SCALE), (w * SCALE, 100 * SCALE), 2)

    font = pygame.font.SysFont("menlo,consolas,monospace", 13)
    font_big = pygame.font.SysFont("menlo,consolas,monospace", 26, bold=True)

    def label(text, pos, color, fnt=font):
        img = fnt.render(text, True, color)
        x = min(pos[0], surf.get_width() - img.get_width() - 4)   # keep on-canvas
        y = min(max(pos[1], 2), surf.get_height() - img.get_height() - 2)
        back = pygame.Surface((img.get_width() + 6, img.get_height() + 2), pygame.SRCALPHA)
        back.fill((10, 10, 14, 170))
        surf.blit(back, (x - 3, y - 1))
        surf.blit(img, (x, y))

    # Zone titles with pool + level band
    content = app.engine.content
    titles = {"cainos": (6, 4), "mork_skog": (86, 4), "cursed_mire": (162, 4),
              "grave_heath": (6, 104)}
    for zone, (tx, ty) in titles.items():
        place = content.places[ZONE_POOL_PLACE[zone]]
        band = (f"Lv {place.level_min}-{place.level_max}"
                if place.level_max else "Lv per enemy")
        label(ZONES[zone][1], (tx * SCALE, ty * SCALE), (255, 255, 255), font_big)
        label(f"pool: {place.id} ({place.name})  {band}",
              (tx * SCALE, ty * SCALE + 30), (235, 235, 235))

    # Towns: dot + name (pool towns highlighted)
    pool_ids = set(ZONE_POOL_PLACE.values())
    for place_id, tile in sorted(app.town_tile_by_place.items()):
        x, y = tile
        color = POOL_TOWN if place_id in pool_ids else TOWN
        pygame.draw.circle(surf, color, (x * SCALE, y * SCALE), 6)
        pygame.draw.circle(surf, (20, 20, 24), (x * SCALE, y * SCALE), 6, 2)
        name = content.places[place_id].name if place_id in content.places else place_id
        label(name, (x * SCALE + 9, y * SCALE - 8), color)

    # B65 boss lairs (labels below the marker so they never fight town names)
    for boss in content.bosses.values():
        x, y = boss.lair_tile
        rect = pygame.Rect(x * SCALE - 6, y * SCALE - 6, 12, 12)
        pygame.draw.rect(surf, LAIR, rect)
        pygame.draw.rect(surf, (20, 20, 24), rect, 2)
        label(f"BOSS {content.enemies[boss.enemy_id].name}",
              (x * SCALE - 20, y * SCALE + 10), LAIR)

    # Start tile (label below, clear of the town's own name)
    sx, sy = app.zone.start_tile
    pygame.draw.circle(surf, (140, 220, 255), (sx * SCALE, sy * SCALE), 5)
    label("START", (sx * SCALE - 18, sy * SCALE + 9), (140, 220, 255))

    pygame.image.save(surf, out_path)
    pygame.quit()


def _zone_rects(zone: str, w: int, h: int):
    if zone == "grave_heath":
        return [(0, 100, w, h)]
    if zone == "cursed_mire":
        return [(159, 0, w, 100)]
    if zone == "mork_skog":
        return [(83, 0, 159, 100)]
    return [(0, 0, 83, 100)]


if __name__ == "__main__":
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    out = os.path.join(root, "docs", "ZONE_MAP.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    render(out)
    print(f"wrote {out}")
