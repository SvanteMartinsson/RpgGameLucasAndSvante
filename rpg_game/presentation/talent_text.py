"""Presentation helpers for talent descriptions.

Terminal and Pygame both use these functions so talent effect text stays
consistent across UI layers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from rpg_game.core import combat, talents
from rpg_game.core.game import GameEngine
from rpg_game.core.progression import round_half_up


@dataclass(frozen=True)
class TalentDetail:
    name: str
    status: str
    effect: str
    cost: str
    prerequisite: str
    rank: int = 0
    max_rank: int = 1
    rank_lines: tuple = ()


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
    # B103: immunity tags — the guard test found "immunity to flee_force".
    "debuff": "debuffs", "flee_force": "forced flee",
}
# B103: adjective forms for "vs <state> targets" condition phrases.
CONDITION_STATUS_LABELS = {
    "fire": "burning", "burn": "burning", "poison": "poisoned",
    "toxin": "poisoned", "freeze": "frozen", "chill": "chilled",
    "snare": "snared", "skip_turn": "stunned",
}

# B103: every effect type that appears in the data MUST be listed here AND have
# a branch in describe_effect. The guard test walks actions.json/talents.json
# and fails when future content introduces a type without a renderer — a raw
# identifier must never reach a menu again.
RENDERED_EFFECT_TYPES = {
    "damage", "instant_damage", "heal", "instant_heal", "drain",
    "apply_status", "stat_bonus", "conditional_damage_mod",
    "applied_status_mod", "elemental_attack_mod", "immunity",
}


def _describe_conditional(conditional: dict) -> str:
    """B103: computed, human text for a conditional damage modifier, built from
    the data's own fields — 'Fire damage +20% vs burning targets'."""
    multiplier = float(conditional.get("multiplier", 1.0))
    pct = round((multiplier - 1.0) * 100)
    damage_type = str(conditional.get("damage_type", ""))
    scope = f"{damage_type.capitalize()} damage" if damage_type else "Damage"
    predicate = conditional.get("predicate")
    subject = str(conditional.get("subject", "target"))
    if predicate == "has_status":
        raw = conditional.get("status_types", conditional.get("status_type"))
        names = [raw] if isinstance(raw, str) else list(raw or [])
        adjectives = " or ".join(CONDITION_STATUS_LABELS.get(n, n) for n in names)
        condition = f"vs {adjectives} targets"
    elif predicate in {"hp_pct_lte", "hp_pct_gte"}:
        side = "below" if predicate == "hp_pct_lte" else "above"
        threshold = round_half_up(float(conditional.get("threshold", 0)))
        if subject == "self":
            condition = f"when you are {side} {threshold}% HP"
        else:
            condition = f"vs targets {side} {threshold}% HP"
    elif predicate == "damage_type_is_weakness":
        condition = "when hitting a weakness"
    elif predicate == "has_tag":
        condition = f"vs {conditional.get('tag', '')} targets"
    else:
        condition = "under a condition"   # unreachable for known data (guard test)
    sign = "+" if pct >= 0 else ""
    return f"{scope} {sign}{pct}% {condition}"


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
            text = f"{stat_label(effect.stat, effect.magnitude)} {rounds} ({where})"
            # B103: on-event buffs say their trigger and stacking instead of
            # reading like an always-on buff (Fighter Rage).
            if effect.on_event == "on_damaged":
                text = f"when hit: {text}"
            elif effect.on_event:
                text = f"on {effect.on_event.replace('_', ' ').removeprefix('on ')}: {text}"
            if effect.max_stacks > 1:
                text += f", stacks up to {effect.max_stacks}"
            return text
        if status == "reflect":
            amount = f"{effect.multiplier}x Power" if effect.scale == "power" else str(effect.magnitude)
            # B123: an on_evade reflect (Riposte) reads as "when you evade" so it
            # never looks like an always-on thorns buff.
            trigger = " when you evade" if getattr(effect, "trigger", "") == "on_evade" else ""
            return f"reflect {amount} {effect.damage_type} damage{trigger} {rounds} ({where})"
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
        return _describe_conditional(effect.conditional)
    if kind == "applied_status_mod":
        # B103: computed from the data's fields — "your poison effects tick
        # +2 damage and last +1 round", not "grow stronger".
        name = STATUS_LABELS.get(effect.modifies_status_type, effect.modifies_status_type)
        parts = []
        if effect.mod_magnitude:
            parts.append(f"tick +{effect.mod_magnitude} damage")
        if effect.mod_duration:
            parts.append(f"last +{effect.mod_duration} round{'s' if effect.mod_duration != 1 else ''}")
        return f"your {name} effects " + " and ".join(parts or ["are unchanged"])
    if kind == "elemental_attack_mod":
        # B103: Flametongue/Rimeblade — "+4 fire damage on attacks".
        return f"+{effect.magnitude} {effect.damage_type} damage on attacks"
    if kind == "immunity":
        return f"immunity to {STATUS_LABELS.get(effect.tag, effect.tag)}"
    return kind.replace("_", " ")   # backstop only — the guard test keeps every
                                    # data-present type out of this branch


def skill_cost_text(action) -> str:
    bits = []
    if action.mana_cost:
        bits.append(f"{action.mana_cost} mana")
    if action.cooldown_rounds:
        bits.append(f"cooldown {action.cooldown_rounds}")
    return ", ".join(bits) if bits else "free"


def skill_effect_lines(action) -> list:
    """B89: what a skill DOES, as tooltip lines — effects, cost, weapon gate.
    Shared by the tome shop, the inventory tome tooltip and the skill rows so
    the wording never diverges."""
    # B123: Evasion (the buff) and Riposte (a pure on_evade reflect) are now
    # separate skills, so each effect describes itself via describe_effect — no
    # special combined line. describe_effect renders the reflect's "when you
    # evade" trigger and the evasion buff's "+30% evasion for 6 rounds".
    lines = [describe_effect(effect) for effect in action.effects]
    lines.append(skill_cost_text(action))
    if action.requires_weapon_category:
        lines.append(f"Requires a {action.requires_weapon_category} weapon")
    return lines


# --- B40 S5: character-creation helpers (no player exists yet) --------------

def starter_choices(content, class_id: str) -> list:
    """The two tier-1 ACTIVE talents a new character picks between (the
    passive tier-1 weapon talents are not starter material). Deterministic
    order (by id) so 'choice 1/2' is stable."""
    nodes = [n for n in content.talents.values()
             if n.class_id == class_id and n.order == 1 and n.node_type == "active"]
    return sorted(nodes, key=lambda n: n.id)[:2]


def node_preview_lines(content, node) -> list:
    """Read-only tooltip lines for a talent-tree preview node, built from
    content alone (character creation has no player state)."""
    lines = []
    if node.node_type == "active" and node.action_id in content.actions:
        action = content.actions[node.action_id]
        lines.append(f"Unlocks skill: {action.name}")
        lines.append(skill_cost_text(action))
        lines.extend(describe_effect(effect) for effect in action.effects)
    else:
        lines.append("Passive")
        lines.extend(describe_effect(effect) for effect in node.effects)
    if node.max_rank > 1:
        lines.append(f"Up to rank {node.max_rank}")
    if node.requires and node.requires in content.talents:
        lines.append(f"Requires: {content.talents[node.requires].name}")
    return lines


def branch_label(branch: str) -> str:
    return branch.replace("_", " ").title()


def cross_passive_parent_branch(content, node) -> str:
    """B105: a single-node branch whose prerequisite lives in ANOTHER branch of
    the same class (the flametongue/rimeblade pattern) is a cross-passive; it
    displays under its required branch's section, never as its own column.
    Returns that parent branch, or '' for ordinary nodes."""
    if not node.requires:
        return ""
    siblings = [n for n in content.talents.values()
                if n.class_id == node.class_id and n.branch == node.branch]
    if len(siblings) != 1:
        return ""
    required = content.talents.get(node.requires)
    if required is None or required.branch == node.branch:
        return ""
    return required.branch


def grouped_class_talents(content, class_id: str) -> list:
    """B105: the class tree as (branch, nodes) sections — main branches in
    stable id order with nodes in order-sequence, cross-passives appended under
    their required branch. Presentation only; the tree data is untouched.
    A node with node.branch != the section branch is a cross-passive row."""
    main: dict = {}
    cross: list = []
    nodes = sorted((n for n in content.talents.values() if n.class_id == class_id),
                   key=lambda n: (n.order, n.id))
    for node in nodes:
        parent = cross_passive_parent_branch(content, node)
        if parent:
            cross.append((parent, node))
        else:
            main.setdefault(node.branch, []).append(node)
    for parent, node in cross:
        main.setdefault(parent, []).append(node)
    return sorted(main.items())


def class_tree_columns(content, class_id: str) -> list:
    """The class's full tree as (branch, nodes-in-order) columns for the
    read-only creation preview. B105: cross-passives sit inside their parent
    branch's column instead of getting a column of their own."""
    return grouped_class_talents(content, class_id)


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


def _scaled_effect(effect, mult: float, duration_bonus: int):
    """A copy of `effect` with the B36 rank scaling baked into its numbers,
    mirroring the engine rules (combat._effect_* and talents._recompute_passives)
    so the description IS the computed value, never a 'x1.25 magnitude' step."""
    changes = {}
    if effect.type in {"damage", "instant_damage", "drain"}:
        changes["multiplier"] = round(effect.multiplier * mult, 2)
    elif effect.type == "apply_status":
        if effect.scale == "power":   # power reflects read the multiplier (B86)
            changes["multiplier"] = round(effect.multiplier * mult, 2)
        if effect.magnitude:
            changes["magnitude"] = round_half_up(effect.magnitude * mult)
        if effect.duration and duration_bonus:
            changes["duration"] = effect.duration + duration_bonus
    elif effect.magnitude and effect.type in {"instant_heal", "heal", "stat_bonus", "elemental_attack_mod"}:
        changes["magnitude"] = round_half_up(effect.magnitude * mult)
    elif effect.type == "conditional_damage_mod" and "multiplier" in effect.conditional:
        # Mirror talents._recompute_passives: the delta above 1.0 scales.
        base = float(effect.conditional["multiplier"])
        changes["conditional"] = {**effect.conditional,
                                  "multiplier": 1.0 + (base - 1.0) * mult}
    elif effect.type == "applied_status_mod" and effect.mod_magnitude:
        changes["mod_magnitude"] = round_half_up(effect.mod_magnitude * mult)
    return replace(effect, **changes) if changes else effect


def talent_rank_lines(content, node, current_rank: int = 0) -> list:
    """B90: one line per rank with the COMPUTED values at that rank, the
    current rank marked. Works for active skills and passive nodes."""
    if node.node_type == "active" and node.action_id in content.actions:
        effects = content.actions[node.action_id].effects
        duration_scales = True   # actives gain +1 round at rank 3
    else:
        effects = node.effects
        duration_scales = False
    lines = []
    for rank in range(1, talents.talent_max_rank(node) + 1):
        mult, duration_bonus = combat.talent_rank_scaling(rank)
        if not duration_scales:
            duration_bonus = 0
        text = "; ".join(describe_effect(_scaled_effect(e, mult, duration_bonus)) for e in effects)
        marker = "  <- current" if rank == current_rank else ""
        lines.append(f"Rank {rank}: {text or 'no effect data'}{marker}")
    return lines


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
        rank_lines=tuple(talent_rank_lines(engine.content, node, talent_rank(engine, node))),
    )
