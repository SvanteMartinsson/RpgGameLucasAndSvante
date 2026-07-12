"""B73/B110: zone ambience — a thin world-space particle layer.

Particles live in WORLD space, draw through the map camera transform and are
culled before blitting. A particle therefore stays put while the camera passes
it instead of following the player. S1 shipped the mork_skog fireflies;
S2 turns the layer preset-driven: PRESETS maps zone theme -> particle preset,
and the engine supports the draft kinds (drift/mist/fall) so proposals render.
ONLY presets listed in PRESETS are live in the game — proposal presets live in
ambience_drafts.py until Lucas approves them.

Pure presentation; nothing here touches game rules or the engine RNG.
"""

from __future__ import annotations

import math
import random

import pygame

FIREFLY_COUNT = 28
FIREFLY_COLOR = (215, 235, 120)

# Zone theme -> preset. All four zones wired (Lucas GO 2026-07-12): mork_skog
# fireflies since S1; cainos/cursed_mire/grave_heath moved here from the drafts
# (ambience_drafts) behaviour-preserving vs their approved GIF renders.
PRESETS: dict[str, dict] = {
    "mork_skog": {"kind": "firefly", "count": FIREFLY_COUNT, "color": FIREFLY_COLOR},
    # Warm pollen/seeds drifting in a slight crosswind — bright, friendly zone.
    "cainos": {
        "kind": "drift", "count": 22,
        "colors": ((235, 225, 170), (210, 220, 150)),
        "size": (1, 2), "vx": (0.08, 0.3), "vy": (0.02, 0.12),
        "sway": (4, 10), "alpha": 80,
    },
    # Low drifting haze — large soft blobs creeping horizontally.
    "cursed_mire": {
        "kind": "mist", "count": 10,
        "colors": ((150, 170, 150), (130, 150, 140)),
        "size": (28, 48), "vx": (0.04, 0.14), "vy": (-0.01, 0.01),
        "sway": (2, 6), "alpha": 26,
    },
    # Ash/dust motes falling slowly with sway; the odd ember.
    "grave_heath": {
        "kind": "fall", "count": 26,
        "colors": ((150, 145, 140), (120, 115, 110), (200, 120, 60)),
        "size": (1, 2), "vx": (-0.06, 0.06), "vy": (0.15, 0.4),
        "sway": (2, 7), "alpha": 100,
    },
}


class Firefly:
    __slots__ = ("x", "y", "vx", "phase", "bob", "size", "blink")

    def __init__(self, rng: random.Random, bounds: tuple[float, float, float, float]):
        left, top, right, bottom = bounds
        self.x = rng.uniform(left, right)
        self.y = rng.uniform(top, top + (bottom - top) * 0.9)
        self.vx = rng.uniform(-0.25, 0.25) or 0.1
        self.phase = rng.uniform(0, math.tau)
        self.bob = rng.uniform(6, 16)
        self.size = rng.choice((2, 2, 3))
        self.blink = rng.uniform(0.02, 0.05)


class Drifter:
    """Generic non-pulsing particle for the drift/mist/fall kinds: constant
    velocity + a sine sway, drawn as a soft circle at fixed alpha."""

    __slots__ = ("x", "y", "vx", "vy", "phase", "sway", "size", "color")

    def __init__(self, rng: random.Random, bounds: tuple[float, float, float, float], preset: dict):
        left, top, right, bottom = bounds
        self.x = rng.uniform(left, right)
        self.y = rng.uniform(top, bottom)
        self.vx = rng.uniform(*preset.get("vx", (-0.1, 0.1)))
        self.vy = rng.uniform(*preset.get("vy", (0.0, 0.0)))
        self.phase = rng.uniform(0, math.tau)
        self.sway = rng.uniform(*preset.get("sway", (0.0, 0.0)))
        lo, hi = preset.get("size", (2, 3))
        self.size = rng.randint(lo, hi)
        colors = preset.get("colors", (FIREFLY_COLOR,))
        self.color = colors[rng.randrange(len(colors))]


class ParticleLayer:
    """A fixed, culled pool recycled around the player in world coordinates."""

    def __init__(
        self,
        size: tuple[int, int],
        seed: int = 73,
        preset: dict | None = None,
        world_center: tuple[float, float] = (0, 0),
    ):
        self.width, self.height = size
        self.world_center = world_center
        self.preset = preset or PRESETS["mork_skog"]
        self._rng = random.Random(seed)   # own stream: never the engine's
        self._tick = 0
        self._sprite_cache: dict = {}
        bounds = self._spawn_bounds(world_center)
        if self.preset.get("kind", "firefly") == "firefly":
            self.particles = [Firefly(self._rng, bounds)
                              for _ in range(self.preset.get("count", FIREFLY_COUNT))]
        else:
            self.particles = [Drifter(self._rng, bounds, self.preset)
                              for _ in range(self.preset.get("count", 30))]

    def _spawn_bounds(self, center: tuple[float, float]) -> tuple[float, float, float, float]:
        cx, cy = center
        return (cx - self.width / 2, cy - self.height / 2,
                cx + self.width / 2, cy + self.height / 2)

    def resize(self, size: tuple[int, int], world_center: tuple[float, float] | None = None) -> None:
        if size != (self.width, self.height):
            self.__init__(size, seed=self._rng.randrange(1 << 16), preset=self.preset,
                          world_center=world_center or self.world_center)

    def update(self, world_center: tuple[float, float] | None = None) -> None:
        """Advance drift, recycling only particles well outside the live view.

        Recycling keeps the fixed pool cheap on an arbitrarily large map. The
        generous margin is important: ordinary camera movement never moves an
        on-screen particle, so the player can visibly walk past it.
        """
        if world_center is not None:
            self.world_center = world_center
        self._tick += 1
        if self.preset.get("kind", "firefly") == "firefly":
            for p in self.particles:
                p.x += p.vx
                p.phase += p.blink
        else:
            for p in self.particles:
                p.x += p.vx
                p.y += p.vy
                p.phase += 0.02
        self._recycle_outliers()

    def _recycle_outliers(self) -> None:
        cx, cy = self.world_center
        span_x = self.width * 1.5
        span_y = self.height * 1.5
        left, right = cx - span_x / 2, cx + span_x / 2
        top, bottom = cy - span_y / 2, cy + span_y / 2
        for p in self.particles:
            while p.x < left:
                p.x += span_x
            while p.x > right:
                p.x -= span_x
            while p.y < top:
                p.y += span_y
            while p.y > bottom:
                p.y -= span_y

    _GLOW_STEPS = 8   # quantized pulse brightnesses -> pre-rendered sprites

    def _glow_sprite(self, radius: int, step: int) -> pygame.Surface:
        key = ("glow", radius, step)
        sprite = self._sprite_cache.get(key)
        if sprite is None:
            alpha = int(40 + (step / (self._GLOW_STEPS - 1)) * 160)
            sprite = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
            pygame.draw.circle(sprite, (*FIREFLY_COLOR, alpha // 3),
                               (radius * 2, radius * 2), radius * 2)
            pygame.draw.circle(sprite, (*FIREFLY_COLOR, alpha),
                               (radius * 2, radius * 2), radius)
            self._sprite_cache[key] = sprite
        return sprite

    def _soft_sprite(self, radius: int, color: tuple, alpha: int) -> pygame.Surface:
        key = ("soft", radius, color, alpha)
        sprite = self._sprite_cache.get(key)
        if sprite is None:
            sprite = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
            pygame.draw.circle(sprite, (*color, alpha // 3),
                               (radius * 2, radius * 2), radius * 2)
            pygame.draw.circle(sprite, (*color, alpha),
                               (radius * 2, radius * 2), radius)
            self._sprite_cache[key] = sprite
        return sprite

    @staticmethod
    def _visible(x: float, y: float, radius: int, view_size: tuple[int, int]) -> bool:
        width, height = view_size
        margin = radius * 2
        return -margin <= x <= width + margin and -margin <= y <= height + margin

    def _blit_world_sprite(
        self,
        surface: pygame.Surface,
        sprite: pygame.Surface,
        world_pos: tuple[float, float],
        camera_offset: tuple[int, int],
        zoom: int,
        radius: int,
    ) -> None:
        sx = world_pos[0] - camera_offset[0]
        sy = world_pos[1] - camera_offset[1]
        view_size = (surface.get_width() // zoom, surface.get_height() // zoom)
        if not self._visible(sx, sy, radius, view_size):
            return
        if zoom != 1:
            sprite = pygame.transform.scale(sprite, (sprite.get_width() * zoom,
                                                       sprite.get_height() * zoom))
        surface.blit(sprite, ((sx - radius * 2) * zoom, (sy - radius * 2) * zoom))

    def draw(
        self,
        surface: pygame.Surface,
        camera_offset: tuple[int, int] = (0, 0),
        zoom: int = 1,
    ) -> None:
        tick = self._tick
        if self.preset.get("kind", "firefly") == "firefly":
            for p in self.particles:
                glow = 0.5 + 0.5 * math.sin(p.phase)
                if glow < 0.15:
                    continue                     # dark part of the pulse: invisible
                y = p.y + math.sin((tick * 0.02) + p.phase) * p.bob
                radius = p.size + (1 if glow > 0.8 else 0)
                step = min(self._GLOW_STEPS - 1, int(glow * self._GLOW_STEPS))
                sprite = self._glow_sprite(radius, step)
                self._blit_world_sprite(surface, sprite, (p.x, y), camera_offset, zoom, radius)
            return
        alpha = self.preset.get("alpha", 90)
        for p in self.particles:
            x = p.x + math.sin(tick * 0.02 + p.phase) * p.sway
            sprite = self._soft_sprite(p.size, p.color, alpha)
            self._blit_world_sprite(surface, sprite, (x, p.y), camera_offset, zoom, p.size)
