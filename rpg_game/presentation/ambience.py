"""B73: zone ambience — a thin screen-space particle layer.

Particles live in SCREEN space (cheap: no world transform, no culling math) and
draw on top of the map, before the HUD. S1 shipped the mork_skog fireflies;
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

# Zone theme -> preset. S2 wires ONLY mork_skog (behaviour-preserving move of
# the S1 fireflies into the table). Other zones stay empty until Lucas picks
# from the drafts (ambience_drafts.DRAFT_PRESETS).
PRESETS: dict[str, dict] = {
    "mork_skog": {"kind": "firefly", "count": FIREFLY_COUNT, "color": FIREFLY_COLOR},
}


class Firefly:
    __slots__ = ("x", "y", "vx", "phase", "bob", "size", "blink")

    def __init__(self, rng: random.Random, width: int, height: int):
        self.x = rng.uniform(0, width)
        self.y = rng.uniform(0, height * 0.9)
        self.vx = rng.uniform(-0.25, 0.25) or 0.1
        self.phase = rng.uniform(0, math.tau)
        self.bob = rng.uniform(6, 16)
        self.size = rng.choice((2, 2, 3))
        self.blink = rng.uniform(0.02, 0.05)


class Drifter:
    """Generic non-pulsing particle for the drift/mist/fall kinds: constant
    velocity + a sine sway, drawn as a soft circle at fixed alpha."""

    __slots__ = ("x", "y", "vx", "vy", "phase", "sway", "size", "color")

    def __init__(self, rng: random.Random, width: int, height: int, preset: dict):
        self.x = rng.uniform(0, width)
        self.y = rng.uniform(0, height)
        self.vx = rng.uniform(*preset.get("vx", (-0.1, 0.1)))
        self.vy = rng.uniform(*preset.get("vy", (0.0, 0.0)))
        self.phase = rng.uniform(0, math.tau)
        self.sway = rng.uniform(*preset.get("sway", (0.0, 0.0)))
        lo, hi = preset.get("size", (2, 3))
        self.size = rng.randint(lo, hi)
        colors = preset.get("colors", (FIREFLY_COLOR,))
        self.color = colors[rng.randrange(len(colors))]


class ParticleLayer:
    """A fixed pool of particles wrapped to the surface size. Default preset =
    the S1 mork_skog fireflies (byte-identical behaviour)."""

    def __init__(self, size: tuple[int, int], seed: int = 73, preset: dict | None = None):
        self.width, self.height = size
        self.preset = preset or PRESETS["mork_skog"]
        self._rng = random.Random(seed)   # own stream: never the engine's
        self._tick = 0
        self._sprite_cache: dict = {}
        if self.preset.get("kind", "firefly") == "firefly":
            self.particles = [Firefly(self._rng, self.width, self.height)
                              for _ in range(self.preset.get("count", FIREFLY_COUNT))]
        else:
            self.particles = [Drifter(self._rng, self.width, self.height, self.preset)
                              for _ in range(self.preset.get("count", 30))]

    def resize(self, size: tuple[int, int]) -> None:
        if size != (self.width, self.height):
            self.__init__(size, seed=self._rng.randrange(1 << 16), preset=self.preset)

    def update(self) -> None:
        self._tick += 1
        if self.preset.get("kind", "firefly") == "firefly":
            for p in self.particles:
                p.x = (p.x + p.vx) % self.width
                p.phase += p.blink
        else:
            for p in self.particles:
                p.x = (p.x + p.vx) % self.width
                p.y = (p.y + p.vy) % self.height
                p.phase += 0.02

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

    def draw(self, surface: pygame.Surface) -> None:
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
                surface.blit(sprite, (p.x - radius * 2, y - radius * 2))
            return
        alpha = self.preset.get("alpha", 90)
        for p in self.particles:
            x = p.x + math.sin(tick * 0.02 + p.phase) * p.sway
            sprite = self._soft_sprite(p.size, p.color, alpha)
            surface.blit(sprite, (x - p.size * 2, p.y - p.size * 2))
