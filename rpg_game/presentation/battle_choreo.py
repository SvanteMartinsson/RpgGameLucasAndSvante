"""B107 S1: player attack choreography — parameters straight from the approved
Battle Screen Mock. Pure presentation: nothing here touches game rules or the
engine RNG (the whole timeline is frame-count driven).

Weight classes (mock values, ms converted to 60 fps frames):
- quick  {windup 0,            dash 90 px/110 ms,  fx 320 ms, return 160 ms, number 28 px beige}
- normal {windup 0,            dash 120 px/190 ms, fx 400 ms, return 220 ms, number 32 px white}
- power  {windup −28 px/260 ms, dash 150 px/140 ms, fx 520 ms, return 300 ms, number 40 px gold}

Action -> weight mapping (S1, documented in the night report):
- non-damage resolutions (heal/buff/identify): NO choreography
- the base attack maps via its ROLLED style: quick->quick, power->power,
  otherwise (plain roll) -> normal
- skills: any effect with hits>1 (multi-hit) or a primary damage multiplier
  < 1.0 -> quick; primary multiplier >= 1.5 -> power; else -> normal
B107 S2: enemy damage actions reuse the SAME mapping (they never roll a style,
so action_weight takes the effect branch) and the SAME timeline, mirrored by the
presentation — the enemy dashes left and the fx/number land on the hero.
"""

from __future__ import annotations

MS_PER_FRAME = 1000.0 / 60.0


def frames(ms: float) -> int:
    return max(1, round(ms / MS_PER_FRAME))


GOLD = (0xF4, 0xD0, 0x6F)
BEIGE = (222, 206, 168)
WHITE = (245, 245, 245)

WEIGHTS = {
    "quick": {"windup_px": 0, "windup": 0, "dash_px": 90, "dash": frames(110),
              "fx": frames(320), "ret": frames(160),
              "num_size": 28, "num_color": BEIGE},
    "normal": {"windup_px": 0, "windup": 0, "dash_px": 120, "dash": frames(190),
               "fx": frames(400), "ret": frames(220),
               "num_size": 32, "num_color": WHITE},
    "power": {"windup_px": -28, "windup": frames(260), "dash_px": 150, "dash": frames(140),
              "fx": frames(520), "ret": frames(300),
              "num_size": 40, "num_color": GOLD},
}

FX_FRAMES = 4            # the fx sheets are 4 native 32 px frames, steps(4) forwards
FX_SCALE = 8
SHAKE = frames(350)      # enemy shake with brightness flash 2.2 -> 1.6 -> normal
NUMBER_RISE_PX = 60      # the damage number rises 60 px ...
NUMBER_FADE = frames(800)   # ... and fades out over 800 ms
DEATH_FADE = frames(600)    # grayscale + opacity fade on kill
DEATH_ALPHA = 0.25


def action_weight(resolution, action) -> str | None:
    """The mock's weight class for a damage action, or None for no choreography
    (non-damage). Serves both the player (S1; a rolled base-attack style wins)
    and the enemy (S2; enemies never roll a style, so the effect branch runs)."""
    if not getattr(resolution, "damage_components", None):
        return None
    style = getattr(resolution, "rolled_style_id", "")
    if style:                       # the base attack: rolled family wins
        if "quick" in style:
            return "quick"
        if "power" in style:
            return "power"
        return "normal"
    if action is None:
        return "normal"
    multipliers = [effect.multiplier or 1.0 for effect in action.effects
                   if effect.type in ("instant_damage", "drain")]
    if not multipliers:
        return "normal"             # damage arrived some other way: default
    if any(getattr(effect, "hits", 1) > 1 for effect in action.effects):
        return "quick"              # multi-hit: quick fx per sub-hit
    primary = max(multipliers)
    if primary >= 1.5:
        return "power"
    if primary < 1.0:
        return "quick"
    return "normal"


class Choreography:
    """Frame-stepped timeline for one player attack: windup -> dash -> impact
    (fx + shake + number spawn + optional death fade) -> return. The caller
    draws the hero at `hero_offset()` and the fx frame from `fx_frame()`;
    `impact_now` is True exactly on the impact frame so pending numbers spawn
    at the hit, not at cast."""

    def __init__(self, weight: str):
        self.weight = weight
        spec = WEIGHTS[weight]
        self.spec = spec
        self._tick = 0
        self._impact = spec["windup"] + spec["dash"]
        self.total = self._impact + max(spec["fx"], spec["ret"])
        self.impact_now = False
        self.impact_done = False

    def update(self) -> None:
        self._tick += 1
        self.impact_now = (not self.impact_done) and self._tick >= self._impact
        if self.impact_now:
            self.impact_done = True

    @property
    def done(self) -> bool:
        return self._tick >= self.total

    def finish(self) -> None:
        """Skip-click: jump to the end state (impact counts as delivered)."""
        self._tick = self.total
        self.impact_now = not self.impact_done
        self.impact_done = True

    def hero_offset(self) -> int:
        """Horizontal px offset for the hero sprite this frame (+ = toward the
        enemy on the right)."""
        spec, t = self.spec, self._tick
        if t < spec["windup"]:
            return round(spec["windup_px"] * (t / max(1, spec["windup"])))
        if t < self._impact:
            f = (t - spec["windup"]) / max(1, spec["dash"])
            return round(spec["windup_px"] + (spec["dash_px"] - spec["windup_px"]) * f)
        ret_f = min(1.0, (t - self._impact) / max(1, spec["ret"]))
        return round(spec["dash_px"] * (1.0 - ret_f))

    def fx_frame(self) -> int | None:
        """Sheet frame index (0..3, steps(4) forwards) while the fx plays,
        else None."""
        if not self.impact_done or self._tick >= self._impact + self.spec["fx"]:
            return None
        f = (self._tick - self._impact) / self.spec["fx"]
        return min(FX_FRAMES - 1, int(f * FX_FRAMES))

    def shake_offset(self) -> tuple[int, int]:
        """Enemy sprite shake during SHAKE frames after impact."""
        if not self.impact_done:
            return (0, 0)
        t = self._tick - self._impact
        if t >= SHAKE:
            return (0, 0)
        return ((-3, 3)[t % 2], (1, -1)[(t // 2) % 2])

    def flash_brightness(self) -> float:
        """Enemy brightness multiplier: 2.2 at impact -> 1.6 -> 1.0."""
        if not self.impact_done:
            return 1.0
        t = self._tick - self._impact
        if t >= SHAKE:
            return 1.0
        f = t / SHAKE
        if f < 0.4:
            return 2.2 - (2.2 - 1.6) * (f / 0.4)
        return 1.6 - (1.6 - 1.0) * ((f - 0.4) / 0.6)
