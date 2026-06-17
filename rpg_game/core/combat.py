"""Combat rules and the shared action/effect resolver.

Every combat action should flow through `resolve_action`: base attacks, skills,
items, weapon swaps and enemy actions. Presentation code should consume the
structured result objects instead of duplicating combat rules.
"""

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
    LootDrop,
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
        hit_chance=0.50,
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


@dataclass(frozen=True)
class EnemyReveal:
    name: str
    level: int
    power: int
    armor: int
    speed: int
    resistances: dict[str, float]
    tags: tuple[str, ...]
    skill_ids: tuple[str, ...]
    skills: tuple[str, ...]


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
    loot_drop: LootDrop | None = None
    enemy_reveal: EnemyReveal | None = None


@dataclass
class DamageComponent:
    amount: int
    damage_type: str
    effectiveness: str = ""


Actor = Player | Enemy


def get_attack(attack_id: str) -> CombatAction:
    normalized = attack_id.strip().lower()
    if normalized not in ATTACKS:
        raise ValueError(f"unknown attack: {attack_id}")
    return ATTACKS[normalized]


def identify_enemy(enemy: Enemy, actions: dict[str, CombatAction]) -> EnemyReveal:
    enemy.identified = True
    return EnemyReveal(
        name=enemy.name,
        level=enemy.level,
        power=enemy.damage,
        armor=enemy.armor,
        speed=enemy.speed,
        resistances=dict(enemy.resistances),
        tags=tuple(sorted(enemy.tags)),
        skill_ids=tuple(enemy.action_ids),
        skills=tuple(actions[action_id].name for action_id in enemy.action_ids if action_id in actions),
    )


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


def effectiveness_label(resist: float) -> str:
    if resist > 1.0:
        return "super effective"
    if resist < 1.0:
        return "resisted"
    return ""


def _effect_source_value(actor: Actor, weapon: Weapon | None, effect: EffectSpec, weapon_scaled: bool) -> int:
    if effect.scale == "basic_attack":
        return _basic_attack_base(actor, weapon)
    if effect.scale == "power":
        base = get_stat(actor, "power")
        if weapon_scaled and weapon is not None:
            base += weapon.damage_bonus
        return base
    if effect.scale == "flat":
        return effect.magnitude
    raise ValueError(f"unknown damage scale: {effect.scale}")


def compute_damage_components(
    actor: Actor,
    target: Actor,
    weapon: Weapon | None,
    effect: EffectSpec,
    *,
    rng: random.Random | None = None,
    result: ActionResolution | None = None,
    weapon_scaled: bool = False,
) -> tuple[list[DamageComponent], int, bool]:
    """Resolve one damage instance into per-type components plus a floored total.

    Each component is mitigated against its own resistance (armor reduces only
    physical); the same rolled+crit multiplier scales every component. Flat
    mitigation applies once to the summed components.
    """
    multiplier = effect.multiplier
    crit = rolls_crit(actor, effect, rng)
    if crit:
        multiplier *= actor.crit_mult
        if result is not None:
            result.critical_hits += 1

    raw_components = _raw_damage_components(actor, target, weapon, effect, multiplier, weapon_scaled)

    components: list[DamageComponent] = []
    for amount, damage_type in raw_components:
        resist = get_resistance(target, damage_type)
        resolved = round_half_up(amount * resist)
        if damage_type == "physical":
            resolved -= max(0, target.armor - effect.armor_pen)
        components.append(DamageComponent(max(0, resolved), damage_type, effectiveness_label(resist)))

    total = _total_after_mitigation(target, components)
    return components, total, crit


def _raw_damage_components(
    actor: Actor,
    target: Actor,
    weapon: Weapon | None,
    effect: EffectSpec,
    multiplier: float,
    weapon_scaled: bool,
) -> list[tuple[int, str]]:
    source = _effect_source_value(actor, weapon, effect, weapon_scaled)
    primary = round_half_up(source * multiplier)
    primary = apply_conditional(primary, actor, target, effect)
    primary = apply_damage_dealt_mod(primary, actor)
    components = [(primary, _effect_damage_type(actor, weapon, effect))]
    components.extend(_elemental_attack_components(actor, effect, multiplier))
    return components


def _elemental_attack_components(actor: Actor, effect: EffectSpec, multiplier: float) -> list[tuple[int, str]]:
    if effect.scale != "basic_attack" or not isinstance(actor, Player):
        return []
    return [
        (round_half_up(multiplier * int(mod["mod_value"])), str(mod["damage_type"]))
        for mod in actor.elemental_attack_mods
    ]


def _total_after_mitigation(target: Actor, components: list[DamageComponent]) -> int:
    subtotal = sum(component.amount for component in components) - active_mitigation(target)
    total = max(1, subtotal)
    return max(1, round_half_up(total * (1 + target.damage_taken_mod / 100)))


def calculate_effect_damage(
    actor: Actor,
    target: Actor,
    weapon: Weapon | None,
    effect: EffectSpec,
    rng: random.Random | None = None,
    result: ActionResolution | None = None,
    weapon_scaled: bool = False,
) -> int:
    _, total, _ = compute_damage_components(
        actor, target, weapon, effect, rng=rng, result=result, weapon_scaled=weapon_scaled
    )
    return total


def format_damage_event(actor: Actor, action_name: str, target: Actor, components: list[DamageComponent], crit: bool) -> str:
    parts = " + ".join(f"{component.amount} {component.damage_type}" for component in components)
    flags = [f"{component.damage_type} {component.effectiveness}" for component in components if component.effectiveness]
    flag_text = f" ({', '.join(flags)})" if flags else ""
    crit_text = " critical hit!" if crit else ""
    return f"{actor_name(actor)}'s {action_name} dealt {parts}{flag_text}{crit_text} to {actor_name(target)}."


def action_uses_weapon_scaling(action: CombatAction) -> bool:
    return bool(action.requires_weapon_category)


def weapon_required_level(weapon: Weapon) -> int:
    return max(1, weapon.tier - 2)


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
    required_damage_type = conditional.get("damage_type")
    if required_damage_type and damage_type != required_damage_type:
        return False

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
        status_types = conditional.get("status_types", conditional.get("status_type"))
        if isinstance(status_types, list):
            names = {str(status_type) for status_type in status_types}
        else:
            names = {str(status_types)}
        return any(status.type in names or status.tag in names for status in subject.active_statuses)
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

    blocked_reason = blocked_action_reason(actor, action, weapon=weapon)
    if blocked_reason:
        result.blocked = True
        result.events.append(blocked_reason)
        return result

    if action.mana_cost:
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
        apply_effect(
            actor,
            target,
            effect,
            result,
            weapon=weapon,
            rng=rng,
            weapon_scaled=action_uses_weapon_scaling(action),
        )

    if action.cooldown_rounds:
        actor.cooldowns[action.id] = action.cooldown_rounds

    return result


def action_can_be_evaded(action: CombatAction) -> bool:
    return any(effect.type in {"damage", "instant_damage", "drain"} for effect in action.effects)


def rolls_evasion(target: Actor, rng: random.Random) -> bool:
    if target.evasion_chance <= 0:
        return False
    return rng.random() < (target.evasion_chance / 100)


def blocked_action_reason(
    actor: Actor,
    action: CombatAction,
    *,
    weapon: Weapon | None = None,
) -> str:
    if actor.mana < action.mana_cost:
        return f"{actor_name(actor)} does not have enough mana for {action.name}."
    if actor.cooldowns.get(action.id, 0) > 0:
        return f"{actor_name(actor)} cannot use {action.name} for {actor.cooldowns[action.id]} more round(s)."
    if isinstance(actor, Player) and action.requires_weapon_category:
        if weapon is None or weapon.category != action.requires_weapon_category:
            return f"{actor_name(actor)} needs a {action.requires_weapon_category} weapon for {action.name}."
    required_level = action_required_player_level(action)
    if isinstance(actor, Player) and required_level and actor.level < required_level:
        return f"{actor_name(actor)} needs level {required_level} for {action.name}."
    return ""


def action_required_player_level(action: CombatAction) -> int:
    for effect in action.effects:
        if effect.type == "swap_weapon":
            return effect.magnitude
    return 0


def available_actions(
    actor: Actor,
    actions: dict[str, CombatAction],
    *,
    weapon: Weapon | None = None,
) -> list[CombatAction]:
    action_ids = actor.equipped_skill_ids if isinstance(actor, Player) else actor.action_ids
    base_ids = ("power", "normal", "quick") if isinstance(actor, Player) else ()
    return [
        actions[action_id]
        for action_id in (*base_ids, *action_ids)
        if action_id in actions and not blocked_action_reason(actor, actions[action_id], weapon=weapon)
    ]


def action_is_ready(actor: Actor, action: CombatAction | None) -> bool:
    return action is not None and not blocked_action_reason(actor, action)


def actor_has_status(actor: Actor, tag: str) -> bool:
    return any(status.type == tag or status.tag == tag for status in actor.active_statuses)


def hp_percent(actor: Actor) -> float:
    if actor.max_hp <= 0:
        return 0.0
    return actor.hp / actor.max_hp * 100


def ai_condition_met(
    actor: Enemy,
    target: Actor,
    condition: dict[str, object],
    actions: dict[str, CombatAction],
) -> bool:
    """Evaluate a rule condition. Multiple predicates are ANDed together."""
    for key, value in condition.items():
        if key == "always":
            continue
        if key == "self_hp_below":
            if not hp_percent(actor) < float(value):
                return False
        elif key == "target_hp_below":
            if not hp_percent(target) < float(value):
                return False
        elif key == "skill_ready":
            if not action_is_ready(actor, actions.get(str(value))):
                return False
        elif key == "self_has_status":
            if not actor_has_status(actor, str(value)):
                return False
        elif key == "target_has_status":
            if not actor_has_status(target, str(value)):
                return False
        else:
            raise ValueError(f"unknown ai condition: {key}")
    return True


def choose_enemy_action(
    enemy: Enemy,
    target: Actor,
    actions: dict[str, CombatAction],
    rng: random.Random,
) -> CombatAction | None:
    """Pick an enemy action via its ordered ai rules.

    Returns the first rule whose condition is true and whose action is ready
    (off cooldown + enough mana). If no rule matches, uniformly picks a ready
    non-telegraph action. Never returns an action that is not ready.
    """
    ready = available_actions(enemy, actions)
    ready_by_id = {action.id: action for action in ready}
    for rule in enemy.ai:
        action_id = str(rule.get("action", ""))
        action = ready_by_id.get(action_id)
        if action is None:
            continue
        if ai_condition_met(enemy, target, dict(rule.get("condition", {})), actions):
            return action
    fallback = [action for action in ready if not action.telegraph]
    if not fallback:
        return None
    return rng.choice(fallback)


def enemy_take_turn(
    enemy: Enemy,
    target: Actor,
    actions: dict[str, CombatAction],
    rng: random.Random,
) -> ActionResolution:
    """Resolve a full enemy turn: release a charged telegraph, or pick + act."""
    if enemy.charging_action_id:
        action = actions[enemy.charging_action_id]
        enemy.charging_action_id = ""
        return resolve_action(enemy, target, action, rng)

    action = choose_enemy_action(enemy, target, actions, rng)
    if action is None:
        result = ActionResolution(
            action_id="",
            action_name="",
            actor_name=actor_name(enemy),
            target_name=actor_name(target),
        )
        result.events.append(f"{actor_name(enemy)} hesitates.")
        return result

    if action.telegraph:
        enemy.charging_action_id = action.id
        result = ActionResolution(
            action_id=action.id,
            action_name=action.name,
            actor_name=actor_name(enemy),
            target_name=actor_name(target),
        )
        result.events.append(f"{actor_name(enemy)} charges {action.name}.")
        return result

    return resolve_action(enemy, target, action, rng)


def tick_cooldowns(actor: Actor, skip: set[str] | None = None) -> None:
    skip = skip or set()
    actor.cooldowns = {
        action_id: remaining if action_id in skip else remaining - 1
        for action_id, remaining in actor.cooldowns.items()
        if (remaining if action_id in skip else remaining - 1) > 0
    }


def consume_skip_turn(actor: Actor) -> list[str]:
    for index, status in enumerate(actor.active_statuses):
        if status.type != "skip_turn":
            continue
        del actor.active_statuses[index]
        return [f"{actor_name(actor)} is frozen and loses the turn."]
    return []


def apply_effect(
    actor: Actor,
    target: Actor,
    effect: EffectSpec,
    result: ActionResolution,
    *,
    weapon: Weapon | None,
    rng: random.Random | None = None,
    weapon_scaled: bool = False,
) -> None:
    effect_target = actor if effect.target == "self" else target

    if effect.type in {"damage", "instant_damage"}:
        for _ in range(effect.hits):
            components, total, crit = compute_damage_components(
                actor,
                effect_target,
                weapon,
                effect,
                rng=rng,
                result=result,
                weapon_scaled=weapon_scaled,
            )
            primary_type = components[0].damage_type
            deal_damage(actor, effect_target, total, primary_type, result)
            result.events.append(
                format_damage_event(actor, result.action_name, effect_target, components, crit)
            )
        return

    if effect.type == "instant_heal":
        before = effect_target.hp
        effect_target.hp = min(effect_target.max_hp, effect_target.hp + effect.magnitude)
        result.events.append(f"{actor_name(effect_target)} healed {effect_target.hp - before} HP.")
        return

    if effect.type == "drain":
        components, total, crit = compute_damage_components(
            actor,
            effect_target,
            weapon,
            effect,
            rng=rng,
            result=result,
            weapon_scaled=weapon_scaled,
        )
        primary_type = components[0].damage_type
        deal_damage(actor, effect_target, total, primary_type, result)
        heal = round_half_up(total * effect.ratio)
        before = actor.hp
        actor.hp = min(actor.max_hp, actor.hp + heal)
        parts = " + ".join(f"{component.amount} {component.damage_type}" for component in components)
        flags = [f"{component.damage_type} {component.effectiveness}" for component in components if component.effectiveness]
        flag_text = f" ({', '.join(flags)})" if flags else ""
        crit_text = " critical hit!" if crit else ""
        result.events.append(
            f"{actor_name(actor)}'s {result.action_name} drained {parts}{flag_text}{crit_text} from {actor_name(effect_target)}."
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
                        weapon_bonus=weapon.damage_bonus if weapon_scaled and weapon is not None else 0,
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
                weapon_bonus=weapon.damage_bonus if weapon_scaled and weapon is not None else 0,
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
            raw_damage = round_half_up((get_stat(bearer, "power") + status.weapon_bonus) * status.multiplier)
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


def create_weapon_swap_action(weapon: Weapon) -> CombatAction:
    return CombatAction(
        id=f"swap_{weapon.id}",
        name="Swap weapon",
        kind="weapon_swap",
        effects=(
            EffectSpec(
                type="swap_weapon",
                status_type=weapon.id,
                magnitude=weapon_required_level(weapon),
            ),
        ),
    )
