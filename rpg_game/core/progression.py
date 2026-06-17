import math

from rpg_game.core.entities import Player


def round_half_up(value: float) -> int:
    return math.floor(value + 0.5)


def xp_required_for_level(level: int) -> int:
    if level < 1:
        raise ValueError("level must be at least 1")
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
        player.hp = min(player.max_hp, player.hp + 10)
        message = f"Max HP increased to {player.max_hp}."
    else:
        raise ValueError("stat must be 'damage' or 'hp'")

    player.pending_stat_choices -= 1
    return message
