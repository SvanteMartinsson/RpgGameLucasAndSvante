import math
from dataclasses import dataclass

from rpg_game.core import equipment, entities
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


# B8 2b: stable fast travel. The price anchors to the DEPARTURE zone's economy
# (B62 N=300: net gold/fight per zone below) and grows with distance, so a
# typical neighbouring hop costs ~2 fights of local income and a cross-map ride
# from the heath ~3-4 — "dyrare söderut" by construction. Zone 4 = grave heath
# (the southern band); 1-3 are the west->east x-bands.
FAST_TRAVEL_ZONE_NET = {1: 11, 2: 56, 3: 59, 4: 108}
FAST_TRAVEL_DISTANCE_SCALE = 150  # tiles for +1x the zone base


def fast_travel_cost(distance_tiles: int, departure_zone: int) -> int:
    base = FAST_TRAVEL_ZONE_NET.get(departure_zone, FAST_TRAVEL_ZONE_NET[4])
    return round_half_up(base * (1.0 + distance_tiles / FAST_TRAVEL_DISTANCE_SCALE))


# Highest loot rarity tier an enemy of a given level may drop from the shared rare
# table. Keeps top-end weapons (tier 5 pyre_scepter/gravewarden_blade, tier 6
# worldsplitter) rare from LOW-tier wild enemies: a level-3 bear can't hand out a
# tier-5 staff. Tunable. (Only applies when the enemy has rare_table_access.)
def rare_tier_cap(level: int) -> int:
    if level >= 8:
        return 6
    if level >= 5:
        return 5
    return 4

# B24-flag: a stricter ceiling on the SHARED rare table for LOW-level wild enemies.
# rare_tier_cap (above) gates the whole pool incl. an enemy's own curated loot, where
# a level-4 enemy is meant to keep its hand-placed tier-4 items (e.g. plague_acolyte's
# haste_circuit). The shared rare table is different: it shouldn't hand out tier-4
# rare weapons (consecrated_maul, venomfang) to a level-3/4 wild kill. Below
# RARE_TABLE_LOW_LEVEL the shared table is capped at RARE_TABLE_LOW_LEVEL_TIER; at or
# above it the general rare_tier_cap applies. Both tunable.
RARE_TABLE_LOW_LEVEL = 5
RARE_TABLE_LOW_LEVEL_TIER = 3


def rare_table_tier_cap(level: int) -> int:
    """Tier ceiling for the SHARED rare table only (not an enemy's own loot)."""
    if level < RARE_TABLE_LOW_LEVEL:
        return RARE_TABLE_LOW_LEVEL_TIER
    return rare_tier_cap(level)

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


# Lever e (progression pass 2026-07-12): automatic per-level base-damage growth
# per class, applied on EVERY level gain regardless of the chosen main stat.
# Only the tank has one — its damage floor was falling 4-5x behind fighter/
# hunter by L12; the growth narrows that to <=2x while its identity (bulk, slow
# kills) stays with the HP main-stat choice. Tunable.
CLASS_DAMAGE_PER_LEVEL = {"tank": 6}   # L12 optimized-DPS gap vs fighter: 4.4x -> 1.8x


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
        player.base_damage += CLASS_DAMAGE_PER_LEVEL.get(player.player_class, 0)
        levels_gained += 1

    return levels_gained


# B35 + Wisdom slice: a level-up grants EVERY stat its baseline; the chosen MAIN
# stat takes the bigger main value instead. Universal + flat — no level scaling.
# Choices: hp / wisdom / damage / crit (no speed, no mana — mana is derived from
# wisdom). Wisdom has no baseline; its main value is +2 (Wisdom Slice B, sim-
# tuned): it both scales spell damage with level toward TTK parity and makes the
# wisdom level-up choice competitive with damage +4.
# Class-identity pass 2026-07-12 (lever a): per-level HP baseline is now
# archetype-differentiated. Glass cannons (fighter/hunter/rogue/mage) get +2 —
# they stay frail as they level, which is the whole point of the archetype. The
# tank keeps +2 (its bulk lives in maining HP). Only the cleric, whose defensive
# identity is sustained survival, keeps the night's +3.
LEVEL_STAT_BASELINE = {"hp": 2, "damage": 1, "crit": 1}
CLASS_HP_BASELINE = {"cleric": 3}
LEVEL_STAT_MAIN = {"hp": 8, "damage": 4, "crit": 4, "wisdom": 2}
_STAT_ALIASES = {"health": "hp", "dmg": "damage", "crit_chance": "crit", "wis": "wisdom"}


def level_up_gains(main_stat: str, class_id: str = "") -> dict[str, int]:
    """The per-stat increase for a level-up where `main_stat` was chosen: every
    stat gets its baseline (wisdom has none), the main stat gets the main value.
    `class_id` picks the per-class HP baseline (tank keeps +2)."""
    main = _STAT_ALIASES.get(main_stat.strip().lower(), main_stat.strip().lower())
    if main not in LEVEL_STAT_MAIN:
        raise ValueError("stat must be one of: hp, wisdom, damage, crit")
    baseline = dict(LEVEL_STAT_BASELINE)
    baseline["hp"] = CLASS_HP_BASELINE.get(class_id, baseline["hp"])
    return {stat: (LEVEL_STAT_MAIN[stat] if stat == main else baseline.get(stat, 0))
            for stat in LEVEL_STAT_MAIN}


def apply_stat_choice(player: Player, stat: str) -> str:
    if player.pending_stat_choices <= 0:
        raise ValueError("player has no pending stat choices")

    gains = level_up_gains(stat, class_id=player.player_class)
    main = _STAT_ALIASES.get(stat.strip().lower(), stat.strip().lower())
    player.max_hp += gains["hp"]
    player.base_damage += gains["damage"]
    player.crit_chance += gains["crit"]
    player.wisdom += gains["wisdom"]            # raises derived max_mana by wisdom*MANA_PER_WISDOM
    # Heal into the new headroom so the level feels rewarding.
    player.hp = min(equipment.effective_stat(player, "max_hp"), player.hp + gains["hp"])
    player.mana = min(equipment.effective_stat(player, "max_mana"),
                      player.mana + gains["wisdom"] * entities.MANA_PER_WISDOM)

    player.pending_stat_choices -= 1
    return (f"Level up ({main.upper()}): HP +{gains['hp']}, Wisdom +{gains['wisdom']}, "
            f"Damage +{gains['damage']}, Crit +{gains['crit']}.")
