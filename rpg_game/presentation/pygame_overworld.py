"""Pygame overworld movement shell (presentation layer 2a).

Minsta möjliga bevis för Tiled-tekniken: ladda en handgjord .tmx-karta via
pytmx, rendera den, och flytta en spelar-sprite med piltangenter/WASD med
tile-kollision mot blockerade tiles.

Detta lager är HELT skilt från striden och rör INTE spelkärnan
(`rpg_game/core`). Ingen koppling till world-grafen och inga encounters ännu —
det är nästa slice. Rörelse och kollision hör hemma här i presentationen, inte
i core.

Kör:

    python3 -m rpg_game.presentation.pygame_overworld
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import pygame
from pytmx.util_pygame import load_pygame

DEFAULT_MAP = os.path.join(os.path.dirname(__file__), "..", "data", "maps", "testmap.tmx")

FPS = 60
PLAYER_SIZE = 22
PLAYER_SPEED = 3  # pixels per frame
BG = (18, 20, 28)
PLAYER_COLOR = (235, 200, 90)
PLAYER_EDGE = (40, 36, 16)
COLLISION_LAYER = "walls"


@dataclass
class Overworld:
    """Map + player state with pure, headless-testable movement logic."""

    map_path: str = DEFAULT_MAP
    tmx: object = field(init=False)
    tw: int = field(init=False)
    th: int = field(init=False)
    map_px_w: int = field(init=False)
    map_px_h: int = field(init=False)
    blocked: set = field(init=False)
    player: pygame.Rect = field(init=False)

    def __post_init__(self) -> None:
        self.tmx = load_pygame(self.map_path)
        self.tw, self.th = self.tmx.tilewidth, self.tmx.tileheight
        self.map_px_w = self.tmx.width * self.tw
        self.map_px_h = self.tmx.height * self.th
        self.blocked = self._load_blocked()
        self.player = pygame.Rect(0, 0, PLAYER_SIZE, PLAYER_SIZE)
        self._place_player_at_first_free_tile()

    def _load_blocked(self) -> set:
        """Blocked tiles = every tile present in the collision layer."""
        try:
            layer = self.tmx.get_layer_by_name(COLLISION_LAYER)
        except (ValueError, KeyError):
            return set()
        return {(x, y) for x, y, _img in layer.tiles()}

    def _place_player_at_first_free_tile(self) -> None:
        for ty in range(self.tmx.height):
            for tx in range(self.tmx.width):
                if (tx, ty) not in self.blocked:
                    self.player.center = (tx * self.tw + self.tw // 2, ty * self.th + self.th // 2)
                    return

    # -- movement / collision (pure, no display required) -------------------

    def is_blocked(self, rect: pygame.Rect) -> bool:
        """True if rect leaves the map or overlaps any blocked tile."""
        if rect.left < 0 or rect.top < 0 or rect.right > self.map_px_w or rect.bottom > self.map_px_h:
            return True
        left, right = rect.left // self.tw, (rect.right - 1) // self.tw
        top, bottom = rect.top // self.th, (rect.bottom - 1) // self.th
        for ty in range(top, bottom + 1):
            for tx in range(left, right + 1):
                if (tx, ty) in self.blocked:
                    return True
        return False

    def try_move(self, dx: int, dy: int) -> None:
        """Move the player by (dx, dy), resolving each axis independently so a
        wall on one axis does not cancel motion on the other."""
        if dx:
            moved = self.player.move(dx, 0)
            if not self.is_blocked(moved):
                self.player = moved
        if dy:
            moved = self.player.move(0, dy)
            if not self.is_blocked(moved):
                self.player = moved

    # -- camera -------------------------------------------------------------

    def camera_offset(self, view_w: int, view_h: int) -> tuple[int, int]:
        """Center on the player, clamped to the map; center map if it fits."""
        if self.map_px_w <= view_w:
            ox = (self.map_px_w - view_w) // 2
        else:
            ox = max(0, min(self.player.centerx - view_w // 2, self.map_px_w - view_w))
        if self.map_px_h <= view_h:
            oy = (self.map_px_h - view_h) // 2
        else:
            oy = max(0, min(self.player.centery - view_h // 2, self.map_px_h - view_h))
        return ox, oy


class OverworldApp:
    def __init__(self, map_path: str = DEFAULT_MAP) -> None:
        pygame.init()
        pygame.display.set_caption("Svantrenish RPG — Overworld")
        self.world = Overworld(map_path)
        view_w = min(self.world.map_px_w, 960)
        view_h = min(self.world.map_px_h, 640)
        self.screen = pygame.display.set_mode((view_w, view_h))
        self.clock = pygame.time.Clock()
        self.running = True

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False

    def update(self) -> None:
        keys = pygame.key.get_pressed()
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        self.world.try_move(dx * PLAYER_SPEED, dy * PLAYER_SPEED)

    def draw(self) -> None:
        view_w, view_h = self.screen.get_size()
        ox, oy = self.world.camera_offset(view_w, view_h)
        self.screen.fill(BG)
        tmx = self.world.tmx
        for layer in tmx.visible_layers:
            if not hasattr(layer, "tiles"):
                continue
            for x, y, image in layer.tiles():
                self.screen.blit(image, (x * self.world.tw - ox, y * self.world.th - oy))
        player = self.world.player.move(-ox, -oy)
        pygame.draw.rect(self.screen, PLAYER_COLOR, player, border_radius=4)
        pygame.draw.rect(self.screen, PLAYER_EDGE, player, width=2, border_radius=4)
        pygame.display.flip()

    def run(self) -> None:
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()


def main(argv: list[str] | None = None) -> None:
    import sys

    argv = argv if argv is not None else sys.argv[1:]
    map_path = argv[0] if argv else DEFAULT_MAP
    OverworldApp(map_path).run()


if __name__ == "__main__":
    main()
