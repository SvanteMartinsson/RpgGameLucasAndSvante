"""Presentation helpers for talent descriptions.

Terminal and Pygame both use these functions so talent effect text stays
consistent across UI layers.
"""

from __future__ import annotations

from dataclasses import dataclass

from rpg_game.core import combat, talents
from rpg_game.core.game import GameEngine


@dataclass(frozen=True)
class TalentDetail:
    name: str
    status: str
    effect: str
    cost: str
    prerequisite: str
    rank: int = 0
    max_rank: int = 1
    next_rank: str = ""


# B78: player-facing words for internal stat names — raw identifiers like
# "damage_dealt_mod" must never reach a menu. Percent-stats phrase as "+N% ...".
STAT_LABELS = {
    "power": "damage",
    "damage": "damage",
    "hp": "HP",
    "max_hp": "max HP",
    "max_mana": "max mana",
    "mana": "mana",
    "wisdom": "Wisdom",
    "speed": "Speed",
    "armor": "Armor",
    "crit_chance": "crit chance",
    "evasion_chance": "evasion",
    "accuracy_mod": "accuracy",
    "damage_dealt_mod": "damage dealt",
    "damage_taken_mod": "damage taken",
}
PERCENT_STATS = {"crit_chance", "evasion_chance", "accuracy_mod",
                 "damage_dealt_mod", "damage_taken_mod"}
# Friendly names for applied statuses (tag beats status_type when set).
STATUS_LABELS = {
    "fire": "burning", "poison": "poison", "skip_turn": "stun",
    "mitigation": "damage block", "burn": "burning", "toxin": "poison",
    "freeze": "freeze (skip a turn)", "chill": "chill", "snare": "snare",
}


def stat_label(stat: str, magnitude: int) -> str:
    label = STAT_LABELS.get(stat, stat.replace("_", " "))
    sign = "+" if magnitude >= 0 else ""
    unit = "%" if stat in PERCENT_STATS else ""
    return f"{sign}{magnitude}{unit} {label}"


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
        rounds = f"for {effect.duration} rounds" if effect.duration != 1 else "for 1 round"
        if status in {"buff", "debuff"}:
            return f"{stat_label(effect.stat, effect.magnitude)} {rounds} ({where})"
        if status == "reflect":
            amount = f"{effect.multiplier}x Power" if effect.scale == "power" else str(effect.magnitude)
            return f"reflect {amount} {effect.damage_type} damage {rounds} ({where})"
        name = STATUS_LABELS.get(getattr(effect, "tag", "") or status, status)
        if status == "mitigation":
            return f"block {effect.magnitude} damage per hit {rounds} ({where})"
        if status == "skip_turn" or getattr(effect, "tag", "") == "freeze":
            return f"{name} — the target loses its turn ({where})"
        if effect.magnitude and effect.damage_type:
            return f"{name}: {effect.magnitude} {effect.damage_type}/round {rounds} ({where})"
        if getattr(effect, "stat", ""):
            return f"{name}: {stat_label(effect.stat, effect.magnitude)} {rounds} ({where})"
        return f"{name} {rounds} ({where})"
    if kind == "stat_bonus":
        return stat_label(effect.stat, effect.magnitude)
    if kind == "conditional_damage_mod":
        return "bonus damage under a condition"
    if kind == "applied_status_mod":
        return f"your {STATUS_LABELS.get(effect.modifies_status_type, effect.modifies_status_type)} effects grow stronger"
    if kind == "immunity":
        return f"immunity to {STATUS_LABELS.get(effect.tag, effect.tag)}"
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


def talent_rank(engine: GameEngine, node) -> int:
    return engine.player.talent_ranks.get(node.id, 0)


def talent_rank_label(engine: GameEngine, node) -> str:
    """A short rank tag for an owned node, e.g. 'rank 2/3'; '' if not owned."""
    rank = talent_rank(engine, node)
    return f"rank {rank}/{talents.talent_max_rank(node)}" if rank >= 1 else ""


def talent_action_label(engine: GameEngine, node) -> str:
    """The button verb for this node: Learn (rank 0), Upgrade (1..max-1), Max."""
    rank = talent_rank(engine, node)
    if rank == 0:
        return "Learn"
    return "Upgrade" if rank < talents.talent_max_rank(node) else "Max"


def talent_can_allocate(engine: GameEngine, node) -> bool:
    rank = talent_rank(engine, node)
    if engine.player.talent_points <= 0:
        return False
    if rank == 0:
        return node.id in {available.id for available in engine.available_talents()}
    return rank < talents.talent_max_rank(node)


def talent_next_rank_text(engine: GameEngine, node) -> str:
    """Describe what the next point buys: the magnitude step (and the +1 round of
    duration an active skill gains at rank 3)."""
    rank = talent_rank(engine, node)
    max_rank = talents.talent_max_rank(node)
    if rank == 0:
        return "learn at rank 1"
    if rank >= max_rank:
        return "at max rank"
    nxt = rank + 1
    parts = [f"x{combat.TALENT_RANK_MULT.get(nxt, 1.0):g} magnitude"]
    if node.node_type == "active" and nxt >= combat.TALENT_RANK_DURATION_BONUS_AT:
        parts.append("+1 round duration")
    return f"rank {nxt}: " + ", ".join(parts)


def talent_detail(engine: GameEngine, node) -> TalentDetail:
    action = engine.content.actions.get(node.action_id) if node.action_id else None
    return TalentDetail(
        name=node.name,
        status=talent_status(engine, node),
        effect=describe_talent(engine, node),
        cost=skill_cost_text(action) if action is not None else "passive",
        prerequisite=talent_prereq_name(engine, node),
        rank=talent_rank(engine, node),
        max_rank=talents.talent_max_rank(node),
        next_rank=talent_next_rank_text(engine, node),
    )
