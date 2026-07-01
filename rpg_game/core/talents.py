from __future__ import annotations

from rpg_game.core import combat
from rpg_game.core.entities import ActiveStatus, CombatAction, GameContent, Player, TalentNode
from rpg_game.core.progression import round_half_up


MAX_EQUIPPED_SKILLS = 4

# B36: placeholder rank multipliers (sim-tuned later). Rank 1 is the authored
# magnitude; higher ranks scale linearly. Active skills also gain +1 round on
# their DoT/buff/debuff durations at rank 3 (see combat.talent_rank_scaling).
RANK_MULT = combat.TALENT_RANK_MULT


def rank_mult(rank: int) -> float:
    return RANK_MULT.get(rank, 1.0)


def talent_max_rank(node: TalentNode) -> int:
    return max(1, node.max_rank)


def unlocked_skill_ids(player: Player, content: GameContent) -> list[str]:
    """All active skills the player may equip: class starters + learned talent
    actives + skills learned from tomes (B38)."""
    ids: list[str] = []
    for skill_id in content.classes[player.player_class].starting_skill_ids:
        if skill_id not in ids:
            ids.append(skill_id)
    for talent_id in sorted(player.learned_talent_ids):
        talent = content.talents.get(talent_id)
        if (
            talent is not None
            and talent.node_type == "active"
            and talent.action_id
            and talent.action_id not in ids
        ):
            ids.append(talent.action_id)
    for skill_id in player.learned_skill_ids:      # B38: tome-taught skills
        if skill_id not in ids and skill_id in content.actions:
            ids.append(skill_id)
    return ids


def equippable_skills(player: Player, content: GameContent) -> list[CombatAction]:
    return [content.actions[skill_id] for skill_id in unlocked_skill_ids(player, content) if skill_id in content.actions]


def equip_skill(player: Player, content: GameContent, action_id: str) -> str:
    if action_id not in unlocked_skill_ids(player, content):
        raise ValueError("skill is not unlocked")
    name = content.actions[action_id].name if action_id in content.actions else action_id
    if action_id in player.equipped_skill_ids:
        return f"{name} is already equipped."
    if len(player.equipped_skill_ids) >= MAX_EQUIPPED_SKILLS:
        raise ValueError("cannot equip more than 4 skills")
    player.equipped_skill_ids = (*player.equipped_skill_ids, action_id)
    return f"Equipped {name}."


def unequip_skill(player: Player, content: GameContent, action_id: str) -> str:
    if action_id not in player.equipped_skill_ids:
        raise ValueError("skill is not equipped")
    player.equipped_skill_ids = tuple(skill_id for skill_id in player.equipped_skill_ids if skill_id != action_id)
    name = content.actions[action_id].name if action_id in content.actions else action_id
    return f"Unequipped {name}."


def available_talents(player: Player, content: GameContent) -> list[TalentNode]:
    return [
        talent
        for talent in sorted(content.talents.values(), key=lambda node: (node.branch, node.order))
        if talent.class_id == player.player_class
        and talent.id not in player.learned_talent_ids
        and _prerequisite_met(player, content, talent)
    ]


def talent_rank(player: Player, node_id: str) -> int:
    return player.talent_ranks.get(node_id, 0)


def upgradable_talents(player: Player, content: GameContent) -> list[TalentNode]:
    """Owned nodes that still have a rank to gain (rank >= 1 and < max_rank)."""
    return [
        talent
        for talent in sorted(content.talents.values(), key=lambda node: (node.branch, node.order))
        if talent.class_id == player.player_class
        and 1 <= talent_rank(player, talent.id) < talent_max_rank(talent)
    ]


def allocate_talent(player: Player, content: GameContent, node_id: str) -> str:
    """Learn a new node (rank 0 -> 1) or upgrade an owned one (+1, up to its
    max_rank). One talent point per step either way."""
    if player.talent_points <= 0:
        raise ValueError("player has no talent points")

    if node_id not in content.talents:
        raise ValueError(f"unknown talent: {node_id}")

    talent = content.talents[node_id]
    if talent.class_id != player.player_class:
        raise ValueError("talent belongs to another class")

    current = talent_rank(player, node_id)
    max_rank = talent_max_rank(talent)
    if current >= max_rank:
        raise ValueError("talent is already at max rank")

    if current == 0:
        # Learning rank 1: prerequisites and the 4-skill equip cap are gated here
        # only (an upgrade never re-checks them).
        if not _prerequisite_met(player, content, talent):
            raise ValueError("talent prerequisite is not met")
        if (
            talent.node_type == "active"
            and talent.action_id
            and talent.action_id not in player.equipped_skill_ids
            and len(player.equipped_skill_ids) >= MAX_EQUIPPED_SKILLS
        ):
            raise ValueError("cannot equip more than 4 skills")
        player.talent_ranks[node_id] = 1
        player.learned_talent_ids.add(node_id)
        player.talent_points -= 1
        if talent.node_type == "active" and talent.action_id:
            _equip_skill(player, talent.action_id)
        sync_runtime(player, content)
        return f"Learned {talent.name}."

    player.talent_ranks[node_id] = current + 1
    player.talent_points -= 1
    sync_runtime(player, content)
    return f"Upgraded {talent.name} to rank {current + 1}/{max_rank}."


def sync_runtime(player: Player, content: GameContent) -> None:
    """Rebuild every rank-derived runtime structure from talent_ranks: the
    action_id -> rank lookup combat uses, and all passive contributions. Called
    after allocation and after a load so the two stay consistent."""
    _rebuild_skill_ranks(player, content)
    _recompute_passives(player, content)


def _rebuild_skill_ranks(player: Player, content: GameContent) -> None:
    skill_ranks: dict[str, int] = {}
    for node_id, rank in player.talent_ranks.items():
        node = content.talents.get(node_id)
        if node is not None and node.node_type == "active" and node.action_id and rank >= 1:
            skill_ranks[node.action_id] = rank
    player.talent_skill_ranks = skill_ranks


def _recompute_passives(player: Player, content: GameContent) -> None:
    """Re-derive all passive contributions from learned passives at their current
    ranks. The standalone collections are rebuilt from scratch (nothing else
    writes them); stat_bonus is reconciled against the live attribute via a delta
    so level-up gains are preserved."""
    player.applied_status_mods = {}
    player.conditional_damage_mods = []
    player.elemental_attack_mods = []
    player.immunity_tags = set()

    desired_stats: dict[str, int] = {}
    on_event_buffs: dict[tuple, tuple] = {}
    for node_id, rank in player.talent_ranks.items():
        node = content.talents.get(node_id)
        if node is None or node.node_type != "passive" or rank < 1:
            continue
        mult = rank_mult(rank)
        for effect in node.effects:
            if effect.type == "stat_bonus":
                desired_stats[effect.stat] = desired_stats.get(effect.stat, 0) + round_half_up(effect.magnitude * mult)
            elif effect.type == "elemental_attack_mod":
                player.elemental_attack_mods.append(
                    {"damage_type": effect.damage_type, "mod_value": round_half_up(effect.magnitude * mult)}
                )
            elif effect.type == "conditional_damage_mod":
                conditional = dict(effect.conditional)
                if "multiplier" in conditional:
                    base = float(conditional["multiplier"])
                    conditional["multiplier"] = 1.0 + (base - 1.0) * mult  # scale the delta above 1.0
                player.conditional_damage_mods.append(conditional)
            elif effect.type == "applied_status_mod":
                current = player.applied_status_mods.setdefault(effect.modifies_status_type, {})
                current["magnitude"] = current.get("magnitude", 0) + round_half_up(effect.mod_magnitude * mult)
                current["duration"] = current.get("duration", 0) + effect.mod_duration
            elif effect.type == "immunity":
                player.immunity_tags.add(effect.tag)
            elif effect.type == "apply_status" and effect.on_event:
                key = (effect.stat, effect.status_type, effect.on_event)
                on_event_buffs[key] = (effect, round_half_up(effect.magnitude * mult))

    _reconcile_stat_bonuses(player, desired_stats)
    _sync_on_event_buffs(player, on_event_buffs)


def _reconcile_stat_bonuses(player: Player, desired: dict[str, int]) -> None:
    for stat in set(player.stat_bonuses) | set(desired):
        delta = desired.get(stat, 0) - player.stat_bonuses.get(stat, 0)
        if not delta:
            continue
        combat.set_stat(player, stat, combat.get_stat(player, stat) + delta)
        if stat == "max_hp" and delta > 0:
            player.hp = min(combat.effective_max_hp(player), player.hp + delta)
        if stat == "max_mana" and delta > 0:
            player.mana = min(combat.effective_max_mana(player), player.mana + delta)
    player.stat_bonuses = dict(desired)


def _sync_on_event_buffs(player: Player, targets: dict[tuple, tuple]) -> None:
    """Keep on-event passive buffs (e.g. Fighter Rage) at their ranked magnitude
    without duplicating the latent status."""
    matched: set[tuple] = set()
    for status in player.active_statuses:
        if not status.on_event or status.type != "buff":
            continue
        key = (status.stat, status.type, status.on_event)
        if key in targets:
            _, magnitude = targets[key]
            status.magnitude = magnitude
            if status.stacks:  # mid-combat: refresh the applied stat contribution
                previous = status.applied_delta
                status.applied_delta = status.stacks * magnitude
                combat.set_stat(player, status.stat,
                                combat.get_stat(player, status.stat) - previous + status.applied_delta)
            matched.add(key)
    for key, (effect, magnitude) in targets.items():
        if key in matched:
            continue
        player.active_statuses.append(
            ActiveStatus(
                type=effect.status_type,
                magnitude=magnitude,
                duration=effect.duration,
                tick_timing=effect.tick_timing,
                stat=effect.stat,
                applied_delta=0,
                scale=effect.scale,
                multiplier=effect.multiplier,
                damage_type=effect.damage_type,
                tag=effect.tag or effect.status_type,
                trigger=effect.trigger,
                max_stacks=effect.max_stacks,
                stacks=0,
                on_event=effect.on_event,
                base_duration=effect.duration,
            )
        )


def _prerequisite_met(player: Player, content: GameContent, talent: TalentNode) -> bool:
    if talent.requires:
        return talent.requires in player.learned_talent_ids
    if talent.order <= 1:
        return True
    previous = _previous_talent(content, talent)
    return previous is not None and previous.id in player.learned_talent_ids


def _previous_talent(content: GameContent, talent: TalentNode) -> TalentNode | None:
    for candidate in content.talents.values():
        if (
            candidate.class_id == talent.class_id
            and candidate.branch == talent.branch
            and candidate.order == talent.order - 1
        ):
            return candidate
    return None


def _equip_skill(player: Player, action_id: str) -> None:
    if action_id in player.equipped_skill_ids:
        return
    if len(player.equipped_skill_ids) >= MAX_EQUIPPED_SKILLS:
        raise ValueError("cannot equip more than 4 skills")
    player.equipped_skill_ids = (*player.equipped_skill_ids, action_id)
