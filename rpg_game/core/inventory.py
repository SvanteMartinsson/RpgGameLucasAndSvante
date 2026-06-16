from __future__ import annotations

from dataclasses import dataclass

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

    before = player.hp
    player.hp = min(player.max_hp, player.hp + item.heal_amount)
    player.inventory.remove_consumable(normalized)
    healed = player.hp - before
    return UseItemResult(True, f"Used {item.name} and healed {healed} HP.")
