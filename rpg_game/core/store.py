from __future__ import annotations

from dataclasses import dataclass

from rpg_game.core import combat
from rpg_game.core.entities import GameContent, Player
from rpg_game.core.progression import round_half_up


SELL_FRACTION = 0.5
# A town's single store_inventory is split across its trade buildings by category
# (B-doors): the blacksmith trades weapons, the barracks armour (gear), the general
# shop consumables. Each maps to the StoreEntry kinds it buys and the sellable kinds
# it takes. category=None keeps the old unsplit behaviour (whole inventory).
STORE_CATEGORIES = {
    # B91: every store buys miscellaneous (junk/materials) so a full bag can be
    # emptied at whichever counter is closest; buy assortments are unchanged.
    "weapons": {"buy": {"weapon"}, "sell": {"weapon", "miscellaneous"}},
    "armor":   {"buy": {"gear"}, "sell": {"gear", "miscellaneous"}},
    "general": {"buy": {"consumable"}, "sell": {"miscellaneous"}},
}
GEAR_RARITY_VALUE = {
    "common": 10,
    "uncommon": 18,
    "rare": 32,
    "mega rare": 55,
    "legendary": 90,
}
# B8 2b: gear value scales with TIER like weapons do (a t5 chest can't cost one
# fight). Tuned against the B62 economy sim (net gold/fight 11->56->59->108 per
# zone): a piece costs roughly 30-50% of the same-tier weapon, ~2-5 fights of
# its home zone. The old flat rarity-only value underpriced t3+ by ~5x.
GEAR_TIER_VALUE = {1: 20, 2: 55, 3: 140, 4: 280, 5: 480}


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
    description: str = ""


@dataclass(frozen=True)
class SellResult:
    success: bool
    message: str


def sell_value(price: int) -> int:
    return round_half_up(price * SELL_FRACTION)


def buy_price(player, price: int) -> int:
    """B135a: the ONE place a buy price is adjusted for the player. A quest
    `shop_discount` reward sets a persistent percentage off; without one this
    returns the price unchanged. Both the displayed price (get_store_entries) and
    the charged price (buy_item) go through here so they can never disagree.
    Never drops below 1 gold."""
    percent = min(50, max(0, getattr(player, "shop_discount_pct", 0)))
    if not percent:
        return price
    return max(1, price - round_half_up(price * percent / 100))


def gear_value(gear) -> int:
    """Full shop value of a gear piece (gear has no authored price): derived from
    its tier + rarity. Buy at full value, sell at SELL_FRACTION of it."""
    tier_value = GEAR_TIER_VALUE.get(gear.tier, GEAR_TIER_VALUE[5])
    return tier_value + GEAR_RARITY_VALUE.get(gear.rarity, 10)


def gear_sell_value(gear) -> int:
    return round_half_up(gear_value(gear) * SELL_FRACTION)


def get_store_entries(content: GameContent, place_id: str, category: str | None = None,
                      *, player: Player | None = None) -> list[StoreEntry]:
    """Store stock for a place. B135a: pass `player` to price the rows with that
    player's quest shop discount applied — the same buy_price() the charge uses,
    so the shown price is always the paid price."""
    place = content.places[place_id]
    if not place.has_store:
        return []

    def shown(price: int) -> int:
        return buy_price(player, price) if player is not None else price

    entries: list[StoreEntry] = []
    for item_id in place.store_inventory:
        if item_id in content.weapons:
            weapon = content.weapons[item_id]
            entries.append(
                StoreEntry(
                    id=weapon.id,
                    name=weapon.name,
                    kind="weapon",
                    price=shown(weapon.price),
                    description=(
                        f"+{weapon.damage_bonus} damage, tier {weapon.tier}, "
                        f"requires level {combat.weapon_required_level(weapon)}"
                    ),
                )
            )
        elif item_id in content.gear_items:
            gear = content.gear_items[item_id]
            mods = ", ".join(f"{stat} {value:+}" for stat, value in gear.stat_modifiers.items())
            entries.append(
                StoreEntry(
                    id=gear.id,
                    name=gear.name,
                    kind="gear",
                    price=shown(gear_value(gear)),
                    description=f"[{gear.rarity}] {mods}, requires level {gear.level_req}",
                )
            )
        elif item_id in content.items:
            item = content.items[item_id]
            entries.append(
                StoreEntry(
                    id=item.id,
                    name=item.name,
                    kind="consumable",
                    price=shown(item.price),
                    description=f"Heals {item.heal_amount} HP",
                )
            )
        else:
            raise ValueError(f"unknown store item: {item_id}")
    if category is not None:
        kinds = STORE_CATEGORIES[category]["buy"]
        entries = [entry for entry in entries if entry.kind in kinds]
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
        price = buy_price(player, weapon.price)     # B135a: quest shop discount
        if player.gold < price:
            return PurchaseResult(False, f"Not enough gold. {weapon.name} costs {price}.")
        player.gold -= price
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

    if normalized in content.gear_items:
        gear = content.gear_items[normalized]
        price = buy_price(player, gear_value(gear))  # B135a: quest shop discount
        if player.gold < price:
            return PurchaseResult(False, f"Not enough gold. {gear.name} costs {price}.")
        player.gold -= price
        if gear.id not in player.owned_gear_ids:
            player.owned_gear_ids = (*player.owned_gear_ids, gear.id)
        return PurchaseResult(True, f"Bought {gear.name}. Equip it in Character.")

    if normalized in content.items:
        item = content.items[normalized]
        price = buy_price(player, item.price)        # B135a: quest shop discount
        if player.gold < price:
            return PurchaseResult(False, f"Not enough gold. {item.name} costs {price}.")
        player.gold -= price
        player.inventory.add_consumable(item.id)
        return PurchaseResult(True, f"Bought {item.name}.")

    raise ValueError(f"unknown item: {item_id}")


def get_sellables(player: Player, content: GameContent, category: str | None = None) -> list[SellEntry]:
    entries: list[SellEntry] = []
    for item_id, count in sorted(player.inventory.consumables.items()):
        item = content.items.get(item_id)
        if item is not None and item.kind == "miscellaneous":
            entries.append(SellEntry(item_id, item.name, "miscellaneous", sell_value(item.price), count,
                                     description="Miscellaneous"))
    for weapon_id in player.owned_weapon_ids:
        if weapon_id == player.equipped_weapon_id:
            continue
        weapon = content.weapons[weapon_id]
        entries.append(SellEntry(weapon_id, weapon.name, "weapon", sell_value(weapon.price), 1,
                                 description=f"+{weapon.damage_bonus} damage, tier {weapon.tier}"))
    equipped_gear_ids = set(player.equipped_gear.values())
    for gear_id in player.owned_gear_ids:
        if gear_id in equipped_gear_ids:
            continue
        gear = content.gear_items[gear_id]
        mods = ", ".join(f"{stat} {value:+}" for stat, value in gear.stat_modifiers.items())
        entries.append(SellEntry(gear_id, gear.name, "gear", gear_sell_value(gear), 1,
                                 description=f"[{gear.rarity}] {mods}"))
    if category is not None:
        kinds = STORE_CATEGORIES[category]["sell"]
        entries = [entry for entry in entries if entry.kind in kinds]
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

    if normalized in content.gear_items and normalized in player.owned_gear_ids:
        if normalized in set(player.equipped_gear.values()):
            return SellResult(False, "You cannot sell equipped gear. Unequip it first.")
        gear = content.gear_items[normalized]
        value = gear_sell_value(gear)
        player.owned_gear_ids = tuple(owned_id for owned_id in player.owned_gear_ids if owned_id != normalized)
        player.gold += value
        return SellResult(True, f"Sold {gear.name} for {value} gold.")

    if player.inventory.count(normalized) > 0:
        item = content.items[normalized]
        if item.kind != "miscellaneous":
            return SellResult(False, "You can only sell miscellaneous items and unequipped weapons.")
        value = sell_value(item.price)
        player.inventory.remove_consumable(normalized)
        player.gold += value
        return SellResult(True, f"Sold {item.name} for {value} gold.")

    return SellResult(False, "You do not have that to sell.")
