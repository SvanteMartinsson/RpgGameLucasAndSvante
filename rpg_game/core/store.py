from __future__ import annotations

from dataclasses import dataclass

from rpg_game.core import combat
from rpg_game.core.entities import GameContent, Player
from rpg_game.core.progression import round_half_up


SELL_FRACTION = 0.5


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


@dataclass(frozen=True)
class SellEntry:
    id: str
    name: str
    kind: str
    value: int
    count: int


@dataclass(frozen=True)
class SellResult:
    success: bool
    message: str


def sell_value(price: int) -> int:
    return round_half_up(price * SELL_FRACTION)


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
                    description=(
                        f"+{weapon.damage_bonus} damage, tier {weapon.tier}, "
                        f"requires level {combat.weapon_required_level(weapon)}"
                    ),
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
        if weapon.id not in player.owned_weapon_ids:
            player.owned_weapon_ids = (*player.owned_weapon_ids, weapon.id)
        required_level = combat.weapon_required_level(weapon)
        if player.level < required_level:
            return PurchaseResult(
                True,
                f"Bought {weapon.name}. Requires level {required_level} to equip.",
            )
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


def get_sellables(player: Player, content: GameContent) -> list[SellEntry]:
    entries: list[SellEntry] = []
    for item_id, count in sorted(player.inventory.consumables.items()):
        item = content.items.get(item_id)
        if item is not None and item.kind == "junk":
            entries.append(SellEntry(item_id, item.name, "junk", sell_value(item.price), count))
    for weapon_id in player.owned_weapon_ids:
        if weapon_id == player.equipped_weapon_id:
            continue
        weapon = content.weapons[weapon_id]
        entries.append(SellEntry(weapon_id, weapon.name, "weapon", sell_value(weapon.price), 1))
    return entries


def sell_item(player: Player, content: GameContent, item_id: str) -> SellResult:
    normalized = item_id.strip().lower()
    place = content.places[player.current_place_id]
    if not place.has_store:
        return SellResult(False, "There is no store here.")

    if normalized in content.weapons and normalized in player.owned_weapon_ids:
        if normalized == player.equipped_weapon_id:
            return SellResult(False, "You cannot sell the equipped weapon. Swap to another first.")
        weapon = content.weapons[normalized]
        value = sell_value(weapon.price)
        player.owned_weapon_ids = tuple(
            owned_id for owned_id in player.owned_weapon_ids if owned_id != normalized
        )
        player.gold += value
        return SellResult(True, f"Sold {weapon.name} for {value} gold.")

    if player.inventory.count(normalized) > 0:
        item = content.items[normalized]
        if item.kind != "junk":
            return SellResult(False, "You can only sell junk and unequipped weapons.")
        value = sell_value(item.price)
        player.inventory.remove_consumable(normalized)
        player.gold += value
        return SellResult(True, f"Sold {item.name} for {value} gold.")

    return SellResult(False, "You do not have that to sell.")
