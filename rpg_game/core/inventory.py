from __future__ import annotations

from dataclasses import dataclass

from rpg_game.core import equipment
from rpg_game.core.entities import GameContent, Player


@dataclass(frozen=True)
class UseItemResult:
    success: bool
    message: str


def use_consumable(player: Player, content: GameContent, item_id: str) -> UseItemResult:
    normalized = item_id.strip().lower()
    if normalized not in content.items:
        return UseItemResult(False, "Unknown item.")

    if player.inventory.count(normalized) <= 0:
        return UseItemResult(False, "You do not have that item.")

    item = content.items[normalized]
    if item.kind != "consumable":
        return UseItemResult(False, "That item cannot be consumed.")

    effects: list[str] = []

    if item.heal_amount:
        before = player.hp
        player.hp = min(equipment.effective_stat(player, "max_hp"), player.hp + item.heal_amount)
        effects.append(f"healed {player.hp - before} HP")

    if item.mana_amount:
        before_mana = player.mana
        player.mana = min(equipment.effective_stat(player, "max_mana"), player.mana + item.mana_amount)
        effects.append(f"restored {player.mana - before_mana} mana")

    for tag in item.cures:
        if any(status.type == tag or status.tag == tag for status in player.active_statuses):
            player.active_statuses = [
                status
                for status in player.active_statuses
                if status.type != tag and status.tag != tag
            ]
            effects.append(f"cured {tag}")

    player.inventory.remove_consumable(normalized)
    summary = ", ".join(effects) if effects else "no effect"
    return UseItemResult(True, f"Used {item.name} and {summary}.")
