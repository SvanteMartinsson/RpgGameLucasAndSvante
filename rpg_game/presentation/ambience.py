"""B73 S1: zone ambience — a thin screen-space particle layer.

Particles live in SCREEN space (cheap: no world transform, no culling math) and
draw on top of the map, before the HUD. S1 ships one preset: mork_skog
fireflies — a few dozen slow drifters with a sine bob and a pulsing glow.
Pure presentation; nothing here touches game rules or the engine RNG.
"""

from __future__ import annotations

import math
import random

import pygame

FIREFLY_COUNT = 28
FIREFLY_COLOR = (215, 235, 120)


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


class ParticleLayer:
    """A fixed pool of fireflies wrapped to the surface size."""

    def __init__(self, size: tuple[int, int], seed: int = 73):
        self.width, self.height = size
        self._rng = random.Random(seed)   # own stream: never the engine's
        self._tick = 0
        self._sprite_cache: dict = {}
        self.particles = [Firefly(self._rng, self.width, self.height)
                          for _ in range(FIREFLY_COUNT)]

    def resize(self, size: tuple[int, int]) -> None:
        if size != (self.width, self.height):
            self.__init__(size, seed=self._rng.randrange(1 << 16))

    def update(self) -> None:
        self._tick += 1
        for p in self.particles:
            p.x = (p.x + p.vx) % self.width
            p.phase += p.blink

    _GLOW_STEPS = 8   # quantized pulse brightnesses -> pre-rendered sprites

    def _glow_sprite(self, radius: int, step: int) -> pygame.Surface:
        key = (radius, step)
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

    def draw(self, surface: pygame.Surface) -> None:
        tick = self._tick
        for p in self.particles:
            glow = 0.5 + 0.5 * math.sin(p.phase)
            if glow < 0.15:
                continue                     # dark part of the pulse: invisible
            y = p.y + math.sin((tick * 0.02) + p.phase) * p.bob
            radius = p.size + (1 if glow > 0.8 else 0)
            step = min(self._GLOW_STEPS - 1, int(glow * self._GLOW_STEPS))
            sprite = self._glow_sprite(radius, step)
            surface.blit(sprite, (p.x - radius * 2, y - radius * 2))
