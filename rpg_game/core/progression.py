import math
from dataclasses import dataclass

from rpg_game.core import equipment
from rpg_game.core.entities import Player

# Gold lost on death scales with level: level * GOLD_LOSS_PER_LEVEL.
GOLD_LOSS_PER_LEVEL = 25

# Cost to move your respawn point to a rest town, scaled by the town's zone:
# zone 1 is free; zone 2 costs RESPAWN_RELOCATION_BASE; each zone above adds
# RESPAWN_RELOCATION_STEP (zone N>=2: BASE + (N-2)*STEP -> 700 / 1000 / 1300 ...).
RESPAWN_RELOCATION_BASE = 700
RESPAWN_RELOCATION_STEP = 300


def respawn_relocation_cost(zone: int) -> int:
    if zone <= 1:
        return 0
    return RESPAWN_RELOCATION_BASE + (zone - 2) * RESPAWN_RELOCATION_STEP


# Cost to rest at a town inn (heal to full). The first rest is free via the Rest
# Voucher granted at new game; after that it costs gold, scaled by the town's zone.
REST_COST_ZONE1 = 50
REST_COST_LATER = 100


def rest_cost(zone: int) -> int:
    return REST_COST_ZONE1 if zone <= 1 else REST_COST_LATER

# Global, tunable scalar on every enemy's max HP at creation (wild and arena),
# so fights last longer without touching the per-enemy numbers or their ratios.
# 1.0 reproduces the pre-multiplier values exactly.
ENEMY_HP_MULTIPLIER = 2.0

# Flee chance scales with difficulty via level delta (enemy_level - player_level):
# trivial enemies are easy to leave, dangerous ones a real gamble. Tunable.
FLEE_BASE_CHANCE = 0.60          # even level
FLEE_CHANCE_PER_LEVEL = 0.05     # lost per level the enemy is above you
FLEE_CHANCE_FLOOR = 0.35         # vs a much stronger enemy
FLEE_CHANCE_CAP = 0.85           # vs a much weaker enemy
EARLY_XP_REQUIREMENTS = {
    1: 10,
    2: 30,
}


def round_half_up(value: float) -> int:
    return math.floor(value + 0.5)


@dataclass(frozen=True)
class RespawnResult:
    """What the on-death penalty cost the player (for presentation)."""

    hp: int
    mana: int
    xp_lost: int
    gold_lost: int


def apply_death_penalty(player: Player) -> RespawnResult:
    """Apply the on-death penalty in place and report what was lost.

    - HP and mana are restored to FULL (you respawn ready to act again — no
      soft-lock where you wake at half HP with no gold to heal).
    - Within-level XP progress resets to the level floor; the level is never
      reduced.
    - Gold drops by level * GOLD_LOSS_PER_LEVEL, clamped to [0, current gold].
    """
    new_hp = equipment.effective_stat(player, "max_hp")
    new_mana = equipment.effective_stat(player, "max_mana")
    xp_lost = player.xp
    gold_lost = min(player.gold, player.level * GOLD_LOSS_PER_LEVEL)
    player.hp = new_hp
    player.mana = new_mana
    player.xp = 0
    player.gold -= gold_lost
    return RespawnResult(hp=new_hp, mana=new_mana, xp_lost=xp_lost, gold_lost=gold_lost)


def xp_required_for_level(level: int) -> int:
    if level < 1:
        raise ValueError("level must be at least 1")
    if level in EARLY_XP_REQUIREMENTS:
        return EARLY_XP_REQUIREMENTS[level]
    return round_half_up(100 * (1.5 ** (level - 1)))


def level_scaled_xp(base_xp: int, player_level: int, enemy_level: int) -> int:
    if base_xp < 0:
        raise ValueError("base_xp must not be negative")
    diff = enemy_level - player_level
    multiplier = max(0.25, min(2.0, 1 + (0.25 * diff)))
    return max(1, round_half_up(base_xp * multiplier))


def award_xp(player: Player, amount: int) -> int:
    if amount < 0:
        raise ValueError("amount must not be negative")

    levels_gained = 0
    player.xp += amount

    while player.xp >= player.xp_required:
        player.xp -= player.xp_required
        player.level += 1
        player.xp_required = xp_required_for_level(player.level)
        player.pending_stat_choices += 1
        player.talent_points += 1
        levels_gained += 1

    return levels_gained


def apply_stat_choice(player: Player, stat: str) -> str:
    if player.pending_stat_choices <= 0:
        raise ValueError("player has no pending stat choices")

    normalized = stat.strip().lower()
    if normalized in {"damage", "dmg"}:
        player.base_damage += 5
        message = f"Damage increased to {player.base_damage}."
    elif normalized in {"hp", "health"}:
        player.max_hp += 10
        player.hp = min(equipment.effective_stat(player, "max_hp"), player.hp + 10)
        message = f"Max HP increased to {player.max_hp}."
    else:
        raise ValueError("stat must be 'damage' or 'hp'")

    player.pending_stat_choices -= 1
    return message
