from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Literal

from rpg_game.core.entities import (
    ActiveStatus,
    CombatAction,
    ConsumableItem,
    EffectSpec,
    Enemy,
    Inventory,
    Player,
    Weapon,
)
from rpg_game.core.progression import round_half_up


DAMAGE_TYPES = {"physical", "fire", "frost", "holy", "poison"}


ATTACKS: dict[str, CombatAction] = {
    "power": CombatAction(
        id="power",
        name="Power attack",
        kind="base_attack",
        hit_chance=0.30,
        effects=(
            EffectSpec(
                type="damage",
                scale="basic_attack",
                multiplier=2.0,
                damage_type="weapon",
            ),
        ),
    ),
    "normal": CombatAction(
        id="normal",
        name="Normal attack",
        kind="base_attack",
        hit_chance=0.55,
        effects=(
            EffectSpec(
                type="damage",
                scale="basic_attack",
                multiplier=1.5,
                damage_type="weapon",
            ),
        ),
    ),
    "quick": CombatAction(
        id="quick",
        name="Quick attack",
        kind="base_attack",
        hit_chance=0.75,
        effects=(
            EffectSpec(
                type="damage",
                scale="basic_attack",
                multiplier=1.0,
                damage_type="weapon",
            ),
        ),
    ),
}


@dataclass
class ActionResolution:
    action_id: str
    action_name: str
    actor_name: str
    target_name: str
    blocked: bool = False
    hit: bool = True
    events: list[str] = field(default_factory=list)
    total_damage: int = 0
    mana_spent: int = 0


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


Actor = Player | Enemy


def get_attack(attack_id: str) -> CombatAction:
    normalized = attack_id.strip().lower()
    if normalized not in ATTACKS:
        raise ValueError(f"unknown attack: {attack_id}")
    return ATTACKS[normalized]


def actor_name(actor: Actor) -> str:
    return actor.name


def actor_speed(actor: Actor) -> int:
    return actor.speed


def actor_is_alive(actor: Actor) -> bool:
    return actor.hp > 0


def ordered_by_speed(player: Player, enemy: Enemy) -> list[Actor]:
    if player.speed >= enemy.speed:
        return [player, enemy]
    return [enemy, player]


def get_resistance(actor: Actor, damage_type: str) -> float:
    return actor.resistances.get(damage_type, 1.0)


def attack_hits(action: CombatAction, rng: random.Random) -> bool:
    return rng.random() < action.hit_chance


def apply_damage_mitigation(raw_damage: int, target: Actor, damage_type: str) -> int:
    mitigated = raw_damage
    if damage_type == "physical":
        mitigated = max(1, raw_damage - target.armor)
    return round_half_up(mitigated * get_resistance(target, damage_type))


def apply_armor(raw_damage: int, armor: int) -> int:
    return max(1, raw_damage - armor)


def _basic_attack_base(actor: Actor, weapon: Weapon | None) -> int:
    if isinstance(actor, Player):
        if weapon is None:
            raise ValueError("player basic attacks require a weapon")
        return actor.base_damage + weapon.damage_bonus
    return actor.damage


def _effect_damage_type(actor: Actor, weapon: Weapon | None, effect: EffectSpec) -> str:
    if effect.damage_type == "weapon":
        return weapon.damage_type if isinstance(actor, Player) and weapon else "physical"
    return effect.damage_type


def calculate_effect_damage(
    actor: Actor,
    target: Actor,
    weapon: Weapon | None,
    effect: EffectSpec,
) -> int:
    if effect.scale == "basic_attack":
        raw_damage = round_half_up(_basic_attack_base(actor, weapon) * effect.multiplier)
    elif effect.scale == "flat":
        raw_damage = round_half_up(effect.magnitude * effect.multiplier)
    else:
        raise ValueError(f"unknown damage scale: {effect.scale}")

    damage_type = _effect_damage_type(actor, weapon, effect)
    return apply_damage_mitigation(raw_damage, target, damage_type)


def calculate_player_damage(player: Player, weapon: Weapon, attack: CombatAction, target_armor: int) -> int:
    target = Enemy(
        id="dummy",
        name="Dummy",
        level=1,
        max_hp=1,
        hp=1,
        damage=0,
        armor=target_armor,
        speed=0,
        resistances={},
        action_ids=(),
        xp_reward=0,
        gold_min=0,
        gold_max=0,
    )
    damage_effect = next(effect for effect in attack.effects if effect.type == "damage")
    return calculate_effect_damage(player, target, weapon, damage_effect)


def calculate_enemy_damage(enemy: Enemy, attack: CombatAction, target_armor: int) -> int:
    target = Player(
        name="Dummy",
        player_class="fighter",
        level=1,
        xp=0,
        xp_required=100,
        hp=1,
        max_hp=1,
        base_damage=0,
        armor=target_armor,
        gold=0,
        equipped_weapon_id="knife",
        inventory=Inventory(),
        current_place_id="",
        respawn_place_id="",
    )
    damage_effect = next(effect for effect in attack.effects if effect.type == "damage")
    return calculate_effect_damage(enemy, target, None, damage_effect)


def resolve_action(
    actor: Actor,
    target: Actor,
    action: CombatAction,
    rng: random.Random,
    *,
    weapon: Weapon | None = None,
) -> ActionResolution:
    result = ActionResolution(
        action_id=action.id,
        action_name=action.name,
        actor_name=actor_name(actor),
        target_name=actor_name(target),
    )

    if isinstance(actor, Player) and actor.mana < action.mana_cost:
        result.blocked = True
        result.events.append(f"{actor.name} does not have enough mana for {action.name}.")
        return result

    if isinstance(actor, Player) and action.mana_cost:
        actor.mana -= action.mana_cost
        result.mana_spent = action.mana_cost

    if not attack_hits(action, rng):
        result.hit = False
        result.events.append(f"{actor_name(actor)}'s {action.name} missed.")
        return result

    for effect in action.effects:
        apply_effect(actor, target, effect, result, weapon=weapon)

    return result


def apply_effect(
    actor: Actor,
    target: Actor,
    effect: EffectSpec,
    result: ActionResolution,
    *,
    weapon: Weapon | None,
) -> None:
    if effect.type == "damage":
        damage_type = _effect_damage_type(actor, weapon, effect)
        damage = calculate_effect_damage(actor, target, weapon, effect)
        target.hp = max(0, target.hp - damage)
        result.total_damage += damage
        result.events.append(
            f"{actor_name(actor)}'s {result.action_name} dealt {damage} {damage_type} damage to {actor_name(target)}."
        )
        return

    if effect.type == "apply_status":
        status_type = effect.status_type or effect.damage_type
        target.active_statuses.append(
            ActiveStatus(
                type=status_type,
                magnitude=effect.magnitude,
                duration=effect.duration,
                tick_timing=effect.tick_timing,
            )
        )
        result.events.append(f"{actor_name(target)} is affected by {status_type}.")
        return

    if effect.type == "heal":
        before = actor.hp
        actor.hp = min(actor.max_hp, actor.hp + effect.magnitude)
        result.events.append(f"{actor_name(actor)} healed {actor.hp - before} HP.")
        return

    if effect.type == "swap_weapon":
        if not isinstance(actor, Player):
            raise ValueError("only players can swap weapons")
        actor.equipped_weapon_id = effect.status_type
        result.events.append(f"{actor.name} swapped weapon.")
        return

    raise ValueError(f"unknown effect type: {effect.type}")


def tick_statuses(actor: Actor, timing: Literal["round_start", "round_end"]) -> list[str]:
    events: list[str] = []
    remaining: list[ActiveStatus] = []
    for status in actor.active_statuses:
        if status.tick_timing == timing:
            events.extend(apply_status_tick(actor, status))
            status.duration -= 1
        if status.duration > 0:
            remaining.append(status)
    actor.active_statuses = remaining
    return events


def apply_status_tick(actor: Actor, status: ActiveStatus) -> list[str]:
    if status.type in DAMAGE_TYPES:
        damage = apply_damage_mitigation(status.magnitude, actor, status.type)
        actor.hp = max(0, actor.hp - damage)
        return [f"{actor_name(actor)} took {damage} {status.type} damage from {status.type}."]
    return []


def create_item_action(item: ConsumableItem) -> CombatAction:
    return CombatAction(
        id=f"use_{item.id}",
        name=f"Use {item.name}",
        kind="item",
        effects=(EffectSpec(type="heal", magnitude=item.heal_amount),),
    )


def create_weapon_swap_action(weapon_id: str) -> CombatAction:
    return CombatAction(
        id=f"swap_{weapon_id}",
        name="Swap weapon",
        kind="weapon_swap",
        effects=(EffectSpec(type="swap_weapon", status_type=weapon_id),),
    )
