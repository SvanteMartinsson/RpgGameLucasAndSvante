from __future__ import annotations

from rpg_game.core import combat
from rpg_game.core.entities import GameContent, Player, TalentNode


MAX_EQUIPPED_SKILLS = 4


def available_talents(player: Player, content: GameContent) -> list[TalentNode]:
    return [
        talent
        for talent in sorted(content.talents.values(), key=lambda node: (node.branch, node.order))
        if talent.class_id == player.player_class
        and talent.id not in player.learned_talent_ids
        and _prerequisite_met(player, content, talent)
    ]


def allocate_talent(player: Player, content: GameContent, node_id: str) -> str:
    if player.talent_points <= 0:
        raise ValueError("player has no talent points")

    if node_id not in content.talents:
        raise ValueError(f"unknown talent: {node_id}")

    talent = content.talents[node_id]
    if talent.class_id != player.player_class:
        raise ValueError("talent belongs to another class")
    if talent.id in player.learned_talent_ids:
        raise ValueError("talent is already learned")
    if not _prerequisite_met(player, content, talent):
        raise ValueError("talent prerequisite is not met")
    if (
        talent.node_type == "active"
        and talent.action_id
        and talent.action_id not in player.equipped_skill_ids
        and len(player.equipped_skill_ids) >= MAX_EQUIPPED_SKILLS
    ):
        raise ValueError("cannot equip more than 4 skills")

    player.learned_talent_ids.add(talent.id)
    player.talent_points -= 1

    if talent.node_type == "active" and talent.action_id:
        _equip_skill(player, talent.action_id)
    elif talent.node_type == "passive":
        _apply_passive(player, talent)

    return f"Learned {talent.name}."


def _prerequisite_met(player: Player, content: GameContent, talent: TalentNode) -> bool:
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


def _apply_passive(player: Player, talent: TalentNode) -> None:
    result = combat.ActionResolution(
        action_id=talent.id,
        action_name=talent.name,
        actor_name=player.name,
        target_name=player.name,
    )
    for effect in talent.effects:
        combat.apply_effect(player, player, effect, result, weapon=None)
