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
    reflected_damage: int = 0
    critical_hits: int = 0
    evaded: bool = False
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


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def attack_hits(action: CombatAction, rng: random.Random) -> bool:
    return rng.random() < effective_hit_chance(action, accuracy_mod=0)


def effective_hit_chance(action: CombatAction, accuracy_mod: int = 0) -> float:
    return round(clamp((action.hit_chance * 100) + accuracy_mod, 0, 100) / 100, 10)


def apply_damage_mitigation(raw_damage: int, target: Actor, damage_type: str) -> int:
    return apply_damage_mitigation_with_armor_pen(raw_damage, target, damage_type, armor_pen=0)


def apply_damage_mitigation_with_armor_pen(
    raw_damage: int,
    target: Actor,
    damage_type: str,
    armor_pen: int = 0,
) -> int:
    mitigated = round_half_up(raw_damage * get_resistance(target, damage_type))
    if damage_type == "physical":
        mitigated -= max(0, target.armor - armor_pen)
    mitigated -= active_mitigation(target)
    return max(1, mitigated)


def active_mitigation(actor: Actor) -> int:
    return sum(status.magnitude for status in actor.active_statuses if status.type == "mitigation")


def apply_armor(raw_damage: int, armor: int) -> int:
    return max(1, raw_damage - armor)


def _basic_attack_base(actor: Actor, weapon: Weapon | None) -> int:
    if isinstance(actor, Player):
        if weapon is None:
            raise ValueError("player basic attacks require a weapon")
        return actor.base_damage + weapon.damage_bonus
    return actor.damage


def get_stat(actor: Actor, stat: str) -> int:
    if stat == "power":
        return actor.base_damage if isinstance(actor, Player) else actor.damage
    return getattr(actor, stat)


def set_stat(actor: Actor, stat: str, value: int) -> None:
    if stat == "power":
        if isinstance(actor, Player):
            actor.base_damage = value
        else:
            actor.damage = value
        return
    setattr(actor, stat, value)


def _effect_damage_type(actor: Actor, weapon: Weapon | None, effect: EffectSpec) -> str:
    if effect.damage_type == "weapon":
        return weapon.damage_type if isinstance(actor, Player) and weapon else "physical"
    return effect.damage_type


def calculate_effect_damage(
    actor: Actor,
    target: Actor,
    weapon: Weapon | None,
    effect: EffectSpec,
    rng: random.Random | None = None,
    result: ActionResolution | None = None,
) -> int:
    if effect.scale == "basic_attack":
        raw_damage = round_half_up(_basic_attack_base(actor, weapon) * effect.multiplier)
    elif effect.scale == "power":
        raw_damage = round_half_up(get_stat(actor, "power") * effect.multiplier)
    elif effect.scale == "flat":
        raw_damage = round_half_up(effect.magnitude * effect.multiplier)
    else:
        raise ValueError(f"unknown damage scale: {effect.scale}")

    raw_damage = apply_conditional(raw_damage, actor, target, effect)
    raw_damage = apply_damage_dealt_mod(raw_damage, actor)
    if rolls_crit(actor, effect, rng):
        raw_damage = round_half_up(raw_damage * actor.crit_mult)
        if result is not None:
            result.critical_hits += 1

    damage_type = _effect_damage_type(actor, weapon, effect)
    damage = apply_damage_mitigation_with_armor_pen(raw_damage, target, damage_type, effect.armor_pen)
    return apply_damage_taken_mod(damage, target)


def apply_damage_dealt_mod(raw_damage: int, actor: Actor) -> int:
    return round_half_up(raw_damage * (1 + actor.damage_dealt_mod / 100))


def apply_damage_taken_mod(damage: int, target: Actor) -> int:
    return max(1, round_half_up(damage * (1 + target.damage_taken_mod / 100)))


def effective_crit_chance(actor: Actor, effect: EffectSpec) -> int:
    return max(0, actor.crit_chance + effect.crit_bonus)


def rolls_crit(actor: Actor, effect: EffectSpec, rng: random.Random | None) -> bool:
    chance = effective_crit_chance(actor, effect)
    if chance <= 0:
        return False
    if rng is None:
        return False
    return rng.random() < (chance / 100)


def apply_conditional(raw_damage: int, actor: Actor, target: Actor, effect: EffectSpec) -> int:
    conditional = effect.conditional
    modified = raw_damage
    if conditional and condition_matches(actor, target, conditional, _effect_damage_type(actor, None, effect)):
        modified = round_half_up(modified * float(conditional.get("multiplier", 1.0)))
    for passive in actor.conditional_damage_mods:
        if condition_matches(actor, target, passive, _effect_damage_type(actor, None, effect)):
            modified = round_half_up(modified * float(passive.get("multiplier", 1.0)))
    return modified


def condition_matches(actor: Actor, target: Actor, conditional: dict[str, object], damage_type: str = "") -> bool:
    subject_name = str(conditional.get("subject", "target"))
    subject = actor if subject_name == "self" else target
    predicate = conditional.get("predicate")
    if predicate == "hp_pct_lte":
        threshold = float(conditional["threshold"])
        return (subject.hp / subject.max_hp) * 100 <= threshold
    if predicate == "hp_pct_gte":
        threshold = float(conditional["threshold"])
        return (subject.hp / subject.max_hp) * 100 >= threshold
    if predicate == "has_status":
        status_type = str(conditional["status_type"])
        return any(status.type == status_type or status.tag == status_type for status in subject.active_statuses)
    if predicate == "damage_type_is_weakness":
        return get_resistance(subject, damage_type) > 1.0
    if predicate == "has_tag":
        return str(conditional["tag"]) in subject.tags
    return False


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
    damage_effect = next(effect for effect in attack.effects if effect.type in {"damage", "instant_damage"})
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
    damage_effect = next(effect for effect in attack.effects if effect.type in {"damage", "instant_damage"})
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

    blocked_reason = blocked_action_reason(actor, action)
    if blocked_reason:
        result.blocked = True
        result.events.append(blocked_reason)
        return result

    if isinstance(actor, Player) and action.mana_cost:
        actor.mana -= action.mana_cost
        result.mana_spent = action.mana_cost

    if not (rng.random() < effective_hit_chance(action, actor.accuracy_mod)):
        result.hit = False
        result.events.append(f"{actor_name(actor)}'s {action.name} missed.")
        return result

    if action_can_be_evaded(action) and rolls_evasion(target, rng):
        result.hit = False
        result.evaded = True
        result.events.append(f"{actor_name(target)} evaded {actor_name(actor)}'s {action.name}.")
        apply_reflects(target, actor, result, trigger="on_evade")
        if action.cooldown_rounds:
            actor.cooldowns[action.id] = action.cooldown_rounds
        return result

    for effect in action.effects:
        apply_effect(actor, target, effect, result, weapon=weapon, rng=rng)

    if action.cooldown_rounds:
        actor.cooldowns[action.id] = action.cooldown_rounds

    return result


def action_can_be_evaded(action: CombatAction) -> bool:
    return any(effect.type in {"damage", "instant_damage", "drain"} for effect in action.effects)


def rolls_evasion(target: Actor, rng: random.Random) -> bool:
    if target.evasion_chance <= 0:
        return False
    return rng.random() < (target.evasion_chance / 100)


def blocked_action_reason(actor: Actor, action: CombatAction) -> str:
    if isinstance(actor, Player) and actor.mana < action.mana_cost:
        return f"{actor.name} does not have enough mana for {action.name}."
    if actor.cooldowns.get(action.id, 0) > 0:
        return f"{actor_name(actor)} cannot use {action.name} for {actor.cooldowns[action.id]} more round(s)."
    return ""


def available_actions(actor: Actor, actions: dict[str, CombatAction]) -> list[CombatAction]:
    action_ids = actor.equipped_skill_ids if isinstance(actor, Player) else actor.action_ids
    base_ids = ("power", "normal", "quick") if isinstance(actor, Player) else ()
    return [
        actions[action_id]
        for action_id in (*base_ids, *action_ids)
        if action_id in actions and not blocked_action_reason(actor, actions[action_id])
    ]


def tick_cooldowns(actor: Actor, skip: set[str] | None = None) -> None:
    skip = skip or set()
    actor.cooldowns = {
        action_id: remaining if action_id in skip else remaining - 1
        for action_id, remaining in actor.cooldowns.items()
        if (remaining if action_id in skip else remaining - 1) > 0
    }


def apply_effect(
    actor: Actor,
    target: Actor,
    effect: EffectSpec,
    result: ActionResolution,
    *,
    weapon: Weapon | None,
    rng: random.Random | None = None,
) -> None:
    effect_target = actor if effect.target == "self" else target

    if effect.type in {"damage", "instant_damage"}:
        damage_type = _effect_damage_type(actor, weapon, effect)
        for _ in range(effect.hits):
            damage = calculate_effect_damage(actor, effect_target, weapon, effect, rng=rng, result=result)
            deal_damage(actor, effect_target, damage, damage_type, result)
            result.events.append(
                f"{actor_name(actor)}'s {result.action_name} dealt {damage} {damage_type} damage to {actor_name(effect_target)}."
            )
        return

    if effect.type == "instant_heal":
        before = effect_target.hp
        effect_target.hp = min(effect_target.max_hp, effect_target.hp + effect.magnitude)
        result.events.append(f"{actor_name(effect_target)} healed {effect_target.hp - before} HP.")
        return

    if effect.type == "drain":
        damage_type = _effect_damage_type(actor, weapon, effect)
        damage = calculate_effect_damage(actor, effect_target, weapon, effect, rng=rng, result=result)
        deal_damage(actor, effect_target, damage, damage_type, result)
        heal = round_half_up(damage * effect.ratio)
        before = actor.hp
        actor.hp = min(actor.max_hp, actor.hp + heal)
        result.events.append(
            f"{actor_name(actor)}'s {result.action_name} drained {damage} {damage_type} damage from {actor_name(effect_target)}."
        )
        result.events.append(f"{actor_name(actor)} healed {actor.hp - before} HP.")
        return

    if effect.type == "apply_status":
        status_type = effect.status_type or effect.damage_type
        tag = effect.tag or status_type
        if is_immune(effect_target, tag):
            result.events.append(f"{actor_name(effect_target)} is immune to {tag}.")
            return
        magnitude = effect.magnitude
        duration = effect.duration
        if isinstance(actor, Player):
            status_mod = actor.applied_status_mods.get(status_type, {})
            magnitude += status_mod.get("magnitude", 0)
            duration += status_mod.get("duration", 0)

        applied_delta = 0
        if status_type in {"buff", "debuff"}:
            if effect.on_event:
                effect_target.active_statuses.append(
                    ActiveStatus(
                        type=status_type,
                        magnitude=magnitude,
                        duration=duration,
                        tick_timing=effect.tick_timing,
                        stat=effect.stat,
                        applied_delta=0,
                        scale=effect.scale,
                        multiplier=effect.multiplier,
                        damage_type=effect.damage_type,
                        tag=tag,
                        trigger=effect.trigger,
                        max_stacks=effect.max_stacks,
                        stacks=0,
                        on_event=effect.on_event,
                        base_duration=duration,
                    )
                )
                result.events.append(f"{actor_name(effect_target)} is affected by {status_type}.")
                return
            existing = find_stackable_status(effect_target, status_type, effect.stat)
            if existing and effect.max_stacks > 1:
                existing.stacks = min(effect.max_stacks, existing.stacks + 1)
                previous_delta = existing.applied_delta
                existing.applied_delta = existing.stacks * magnitude
                set_stat(effect_target, effect.stat, get_stat(effect_target, effect.stat) - previous_delta + existing.applied_delta)
                existing.duration = duration
                existing.max_stacks = effect.max_stacks
                result.events.append(f"{actor_name(effect_target)}'s {status_type} refreshed.")
                return
            applied_delta = magnitude
            set_stat(effect_target, effect.stat, get_stat(effect_target, effect.stat) + applied_delta)

        effect_target.active_statuses.append(
            ActiveStatus(
                type=status_type,
                magnitude=magnitude,
                duration=duration,
                tick_timing=effect.tick_timing,
                stat=effect.stat,
                applied_delta=applied_delta,
                scale=effect.scale,
                multiplier=effect.multiplier,
                damage_type=effect.damage_type,
                tag=tag,
                trigger=effect.trigger,
                max_stacks=effect.max_stacks,
                stacks=1,
                on_event=effect.on_event,
                base_duration=duration,
            )
        )
        result.events.append(f"{actor_name(effect_target)} is affected by {status_type}.")
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

    if effect.type == "stat_bonus":
        if not isinstance(actor, Player):
            raise ValueError("stat bonuses are only supported for players")
        actor.stat_bonuses[effect.stat] = actor.stat_bonuses.get(effect.stat, 0) + effect.magnitude
        set_stat(actor, effect.stat, get_stat(actor, effect.stat) + effect.magnitude)
        if effect.stat == "max_mana":
            actor.mana = min(actor.max_mana, actor.mana + effect.magnitude)
        if effect.stat == "max_hp":
            actor.hp = min(actor.max_hp, actor.hp + effect.magnitude)
        result.events.append(f"{actor.name} gained {effect.magnitude} {effect.stat}.")
        return

    if effect.type == "applied_status_mod":
        if not isinstance(actor, Player):
            raise ValueError("status modifiers are only supported for players")
        current = actor.applied_status_mods.setdefault(effect.modifies_status_type, {})
        current["magnitude"] = current.get("magnitude", 0) + effect.mod_magnitude
        current["duration"] = current.get("duration", 0) + effect.mod_duration
        result.events.append(f"{actor.name}'s {effect.modifies_status_type} effects improved.")
        return

    if effect.type == "immunity":
        if not isinstance(actor, Player):
            raise ValueError("immunity passives are only supported for players")
        actor.immunity_tags.add(effect.tag)
        result.events.append(f"{actor.name} gained immunity to {effect.tag}.")
        return

    if effect.type == "conditional_damage_mod":
        if not isinstance(actor, Player):
            raise ValueError("conditional damage modifiers are only supported for players")
        actor.conditional_damage_mods.append(effect.conditional)
        result.events.append(f"{actor.name} gained a conditional damage modifier.")
        return

    raise ValueError(f"unknown effect type: {effect.type}")


def deal_damage(
    attacker: Actor,
    target: Actor,
    damage: int,
    damage_type: str,
    result: ActionResolution,
    *,
    allow_reflect: bool = True,
) -> None:
    target.hp = max(0, target.hp - damage)
    if allow_reflect:
        result.total_damage += damage
        apply_on_damaged_statuses(target)
    if allow_reflect:
        apply_reflects(target, attacker, result)


def find_stackable_status(actor: Actor, status_type: str, stat: str) -> ActiveStatus | None:
    for status in actor.active_statuses:
        if status.type == status_type and status.stat == stat and status.max_stacks > 1:
            return status
    return None


def apply_on_damaged_statuses(actor: Actor) -> None:
    for status in actor.active_statuses:
        if status.on_event != "on_damaged" or status.type != "buff":
            continue
        previous_delta = status.applied_delta
        status.stacks = min(status.max_stacks, status.stacks + 1)
        status.applied_delta = status.stacks * status.magnitude
        set_stat(actor, status.stat, get_stat(actor, status.stat) - previous_delta + status.applied_delta)
        status.duration = status.base_duration


def apply_reflects(bearer: Actor, attacker: Actor, result: ActionResolution, trigger: str = "on_hit") -> None:
    for status in bearer.active_statuses:
        if status.type != "reflect" or status.trigger != trigger:
            continue
        if status.scale == "power":
            raw_damage = round_half_up(get_stat(bearer, "power") * status.multiplier)
        else:
            raw_damage = status.magnitude
        reflected = apply_damage_mitigation(raw_damage, attacker, status.damage_type)
        attacker.hp = max(0, attacker.hp - reflected)
        result.reflected_damage += reflected
        result.events.append(f"{actor_name(bearer)} reflected {reflected} damage to {actor_name(attacker)}.")


def is_immune(actor: Actor, tag: str) -> bool:
    return tag in actor.immunity_tags


def tick_statuses(actor: Actor, timing: Literal["round_start", "round_end"]) -> list[str]:
    events: list[str] = []
    remaining: list[ActiveStatus] = []
    for status in actor.active_statuses:
        if status.on_event and status.stacks == 0:
            remaining.append(status)
            continue
        if status.tick_timing == timing:
            events.extend(apply_status_tick(actor, status))
            status.duration -= 1
        if status.duration > 0:
            remaining.append(status)
        elif status.applied_delta:
            set_stat(actor, status.stat, get_stat(actor, status.stat) - status.applied_delta)
            events.append(f"{actor_name(actor)}'s {status.type} expired.")
    actor.active_statuses = remaining
    return events


def apply_status_tick(actor: Actor, status: ActiveStatus) -> list[str]:
    if status.type in DAMAGE_TYPES or status.tag in DAMAGE_TYPES:
        damage_type = status.type if status.type in DAMAGE_TYPES else status.tag
        damage = apply_damage_mitigation(status.magnitude, actor, damage_type)
        actor.hp = max(0, actor.hp - damage)
        return [f"{actor_name(actor)} took {damage} {damage_type} damage from {status.type}."]
    if status.type == "regen":
        before = actor.hp
        actor.hp = min(actor.max_hp, actor.hp + status.magnitude)
        return [f"{actor_name(actor)} regenerated {actor.hp - before} HP."]
    return []


def create_item_action(item: ConsumableItem) -> CombatAction:
    return CombatAction(
        id=f"use_{item.id}",
        name=f"Use {item.name}",
        kind="item",
        effects=(EffectSpec(type="instant_heal", magnitude=item.heal_amount, target="self"),),
    )


def create_weapon_swap_action(weapon_id: str) -> CombatAction:
    return CombatAction(
        id=f"swap_{weapon_id}",
        name="Swap weapon",
        kind="weapon_swap",
        effects=(EffectSpec(type="swap_weapon", status_type=weapon_id),),
    )
