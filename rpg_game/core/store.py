from __future__ import annotations

from dataclasses import dataclass

from rpg_game.core.entities import GameContent, Player


@dataclass(frozen=True)
class StoreEntry:
    id: str
    name: str
    kind: str
    price: int
    description: str


@dataclass(frozen=True)
class PurchaseResult:
    success: bool
    message: str


def get_store_entries(content: GameContent, place_id: str) -> list[StoreEntry]:
    place = content.places[place_id]
    if not place.has_store:
        return []

    entries: list[StoreEntry] = []
    for item_id in place.store_inventory:
        if item_id in content.weapons:
            weapon = content.weapons[item_id]
            entries.append(
                StoreEntry(
                    id=weapon.id,
                    name=weapon.name,
                    kind="weapon",
                    price=weapon.price,
                    description=f"+{weapon.damage_bonus} damage",
                )
            )
        elif item_id in content.items:
            item = content.items[item_id]
            entries.append(
                StoreEntry(
                    id=item.id,
                    name=item.name,
                    kind="consumable",
                    price=item.price,
                    description=f"Heals {item.heal_amount} HP",
                )
            )
        else:
            raise ValueError(f"unknown store item: {item_id}")
    return entries


def buy_item(player: Player, content: GameContent, item_id: str) -> PurchaseResult:
    normalized = item_id.strip().lower()
    place = content.places[player.current_place_id]
    if not place.has_store:
        return PurchaseResult(False, "There is no store here.")
    if normalized not in place.store_inventory:
        return PurchaseResult(False, "That item is not sold here.")

    if normalized in content.weapons:
        weapon = content.weapons[normalized]
        if player.gold < weapon.price:
            return PurchaseResult(False, f"Not enough gold. {weapon.name} costs {weapon.price}.")
        player.gold -= weapon.price
        player.equipped_weapon_id = weapon.id
        return PurchaseResult(True, f"Bought and equipped {weapon.name}.")

    if normalized in content.items:
        item = content.items[normalized]
        if player.gold < item.price:
            return PurchaseResult(False, f"Not enough gold. {item.name} costs {item.price}.")
        player.gold -= item.price
        player.inventory.add_consumable(item.id)
        return PurchaseResult(True, f"Bought {item.name}.")

    raise ValueError(f"unknown item: {item_id}")
