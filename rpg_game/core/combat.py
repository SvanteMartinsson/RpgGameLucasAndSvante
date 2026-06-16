from __future__ import annotations

import random
from dataclasses import dataclass, field

from rpg_game.core.entities import Enemy, Player, Weapon
from rpg_game.core.progression import round_half_up


@dataclass(frozen=True)
class Attack:
    id: str
    name: str
    hit_chance: float
    multiplier: float


ATTACKS: dict[str, Attack] = {
    "power": Attack("power", "Power attack", 0.30, 2.0),
    "normal": Attack("normal", "Normal attack", 0.55, 1.5),
    "quick": Attack("quick", "Quick attack", 0.75, 1.0),
}


@dataclass
class AttackResult:
    attacker_name: str
    target_name: str
    attack_name: str
    hit: bool
    damage: int = 0

    def message(self) -> str:
        if not self.hit:
            return f"{self.attacker_name}'s {self.attack_name} missed."
        return (
            f"{self.attacker_name}'s {self.attack_name} hit "
            f"{self.target_name} for {self.damage} damage."
        )


@dataclass
class CombatTurnResult:
    outcome: str
    events: list[str] = field(default_factory=list)
    player_hp: int = 0
    enemy_hp: int = 0
    xp_gained: int = 0
    gold_gained: int = 0
    levels_gained: int = 0
    pending_stat_choices: int = 0


def get_attack(attack_id: str) -> Attack:
    normalized = attack_id.strip().lower()
    if normalized not in ATTACKS:
        raise ValueError(f"unknown attack: {attack_id}")
    return ATTACKS[normalized]


def attack_hits(attack: Attack, rng: random.Random) -> bool:
    return rng.random() < attack.hit_chance


def apply_armor(raw_damage: int, armor: int) -> int:
    return max(1, raw_damage - armor)


def calculate_player_damage(player: Player, weapon: Weapon, attack: Attack, target_armor: int) -> int:
    raw_damage = round_half_up((player.base_damage + weapon.damage_bonus) * attack.multiplier)
    return apply_armor(raw_damage, target_armor)


def calculate_enemy_damage(enemy: Enemy, attack: Attack, target_armor: int) -> int:
    raw_damage = round_half_up(enemy.damage * attack.multiplier)
    return apply_armor(raw_damage, target_armor)


def resolve_player_attack(
    player: Player,
    enemy: Enemy,
    weapon: Weapon,
    attack: Attack,
    rng: random.Random,
) -> AttackResult:
    if not attack_hits(attack, rng):
        return AttackResult(player.name, enemy.name, attack.name, hit=False)

    damage = calculate_player_damage(player, weapon, attack, enemy.armor)
    enemy.hp = max(0, enemy.hp - damage)
    return AttackResult(player.name, enemy.name, attack.name, hit=True, damage=damage)


def resolve_enemy_attack(
    enemy: Enemy,
    player: Player,
    attack: Attack,
    rng: random.Random,
) -> AttackResult:
    if not attack_hits(attack, rng):
        return AttackResult(enemy.name, player.name, attack.name, hit=False)

    damage = calculate_enemy_damage(enemy, attack, player.armor)
    player.hp = max(0, player.hp - damage)
    return AttackResult(enemy.name, player.name, attack.name, hit=True, damage=damage)
