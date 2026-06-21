"""Presentation helpers for talent descriptions.

Terminal and Pygame both use these functions so talent effect text stays
consistent across UI layers.
"""

from __future__ import annotations

from dataclasses import dataclass

from rpg_game.core.game import GameEngine


@dataclass(frozen=True)
class TalentDetail:
    name: str
    status: str
    effect: str
    cost: str
    prerequisite: str


def describe_effect(effect) -> str:
    kind = effect.type
    if kind in {"damage", "instant_damage"}:
        base = {"power": "Power", "basic_attack": "weapon", "flat": "flat"}.get(effect.scale, effect.scale)
        hits = f" x{effect.hits} hits" if effect.hits > 1 else ""
        return f"deal {effect.multiplier}x {base} {effect.damage_type} damage{hits}"
    if kind in {"instant_heal", "heal"}:
        return f"heal {effect.magnitude} HP"
    if kind == "drain":
        return f"drain {effect.multiplier}x Power {effect.damage_type}, heal {int(effect.ratio * 100)}% of it"
    if kind == "apply_status":
        status = effect.status_type or effect.damage_type
        where = "self" if effect.target == "self" else "enemy"
        if status in {"buff", "debuff"}:
            sign = "+" if effect.magnitude >= 0 else ""
            return f"{status} {sign}{effect.magnitude} {effect.stat} for {effect.duration} rounds ({where})"
        if status == "reflect":
            amount = f"{effect.multiplier}x Power" if effect.scale == "power" else str(effect.magnitude)
            return f"reflect {amount} {effect.damage_type} for {effect.duration} rounds ({where})"
        return f"apply {status} {effect.magnitude} for {effect.duration} rounds ({where})"
    if kind == "stat_bonus":
        return f"+{effect.magnitude} {effect.stat}"
    if kind == "conditional_damage_mod":
        return "conditional damage bonus"
    if kind == "applied_status_mod":
        return f"improve {effect.modifies_status_type} effects"
    if kind == "immunity":
        return f"immunity to {effect.tag}"
    return kind


def skill_cost_text(action) -> str:
    bits = []
    if action.mana_cost:
        bits.append(f"{action.mana_cost} mana")
    if action.cooldown_rounds:
        bits.append(f"cooldown {action.cooldown_rounds}")
    return ", ".join(bits) if bits else "free"


def describe_talent(engine: GameEngine, node) -> str:
    if node.node_type == "active" and node.action_id in engine.content.actions:
        action = engine.content.actions[node.action_id]
        effects = "; ".join(describe_effect(effect) for effect in action.effects) or "active skill"
        return f"Active: {effects} ({skill_cost_text(action)})"
    if node.effects:
        return "Passive: " + "; ".join(describe_effect(effect) for effect in node.effects)
    return node.node_type


def talent_prereq_name(engine: GameEngine, node) -> str:
    if node.order <= 1:
        return "none"
    for candidate in engine.content.talents.values():
        if (
            candidate.class_id == node.class_id
            and candidate.branch == node.branch
            and candidate.order == node.order - 1
        ):
            return candidate.name
    return "unknown"


def talent_prereq_text(engine: GameEngine, node) -> str:
    prerequisite = talent_prereq_name(engine, node)
    return " | no prerequisite" if prerequisite == "none" else f" | requires {prerequisite}"


def talent_status(engine: GameEngine, node) -> str:
    player = engine.player
    if node.id in player.learned_talent_ids:
        return "[LEARNED]"
    if node.id in {available.id for available in engine.available_talents()}:
        return "[CAN LEARN]"
    return "[LOCKED]"


def talent_detail(engine: GameEngine, node) -> TalentDetail:
    action = engine.content.actions.get(node.action_id) if node.action_id else None
    return TalentDetail(
        name=node.name,
        status=talent_status(engine, node),
        effect=describe_talent(engine, node),
        cost=skill_cost_text(action) if action is not None else "passive",
        prerequisite=talent_prereq_name(engine, node),
    )
