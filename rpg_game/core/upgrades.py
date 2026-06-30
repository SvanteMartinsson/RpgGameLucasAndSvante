"""B37 Slice 2: permanent, one-time item upgrades (blacksmith=weapons, mage
tower=armour).

An upgradable item (rarity >= rare, not excluded) carries an authored recipe of
two variants; each variant applies its stat deltas and costs distinct materials +
gold. Tier and required-level are NEVER touched — they stay derived from the
weapon's BASE damage_bonus. Deltas live on the player (upgrade_stat_bonuses for
flats, weapon_upgrade_components for the elemental damage component), separate
from damage_bonus.
"""

from __future__ import annotations

from dataclasses import dataclass

from rpg_game.core.entities import GameContent, Player, UpgradeRecipe, UpgradeVariant


@dataclass(frozen=True)
class UpgradeResult:
    success: bool
    message: str


# Data-driven removal: items that meet the rarity bar but must NOT be upgradable.
# Never hardcode "all rare" — list specific ids here to retract upgradability
# without changing their rarity. (worldsplitter is the ultimate weapon — it cannot
# be reforged.)
UPGRADE_EXCLUSIONS: set[str] = {"worldsplitter"}

RARITY_RANK = {"common": 0, "uncommon": 1, "rare": 2, "mega rare": 3, "legendary": 4}
MIN_UPGRADE_RARITY = "rare"

# Upgrade stations: the blacksmith reforges weapons, the mage tower enchants
# armour (the barracks hosts armour upgrades until a dedicated mage-tower building
# ships — same mechanic, different door). Each station has a `tier` it can handle,
# wired for future town-size gating but pinned to MAX now (upgrades everything).
STATION_CATEGORY = {"blacksmith": "weapon", "mage_tower": "armour", "barracks": "armour"}
STATION_MAX_TIER = 99


def station_category(building_id: str) -> str | None:
    return STATION_CATEGORY.get(building_id)


def station_tier(building_id: str) -> int:
    # No-op gating hook: every station is MAX tier in v1. A future town-size pass
    # can lower this per building without touching the rest of the system.
    return STATION_MAX_TIER

# Flat stats an upgrade variant may add to the effective stat. Element mods are
# handled separately (a damage component on hit), weapons only.
UPGRADE_FLAT_STATS = {"damage", "crit_chance", "wisdom", "armor", "max_hp", "speed", "max_mana"}


def rarity_rank(rarity: str) -> int:
    return RARITY_RANK.get(rarity, 0)


def item_rarity(content: GameContent, item_id: str) -> str:
    if item_id in content.weapons:
        return content.weapons[item_id].rarity
    if item_id in content.gear_items:
        return content.gear_items[item_id].rarity
    return "common"


def item_category(content: GameContent, item_id: str) -> str | None:
    if item_id in content.weapons:
        return "weapon"
    if item_id in content.gear_items:
        return "armour"
    return None


def item_tier(content: GameContent, item_id: str) -> int:
    if item_id in content.weapons:
        return content.weapons[item_id].tier
    if item_id in content.gear_items:
        return content.gear_items[item_id].tier
    return 0


def station_can_upgrade(building_id: str, content: GameContent, item_id: str) -> bool:
    """A station handles an item if the categories match and the item's tier is
    within the station's tier (no-op now: STATION_MAX_TIER covers everything)."""
    category = station_category(building_id)
    if category is None or item_category(content, item_id) != category:
        return False
    return item_tier(content, item_id) <= station_tier(building_id)


def owned_upgradable(player: Player, content: GameContent, category: str) -> list[str]:
    """Owned items of `category` that are upgradable AND have an authored recipe
    (so a station has something concrete to offer). Includes already-upgraded
    items so the UI can show their locked state."""
    owned = (player.owned_weapon_ids if category == "weapon" else player.owned_gear_ids)
    return [
        item_id for item_id in owned
        if is_upgradable(content, item_id) and recipe_for(content, item_id) is not None
    ]


def is_upgradable(content: GameContent, item_id: str) -> bool:
    """Rarity >= rare AND not excluded. Independent of whether a recipe exists yet
    (so the 'Upgradable' tag can lead authored content)."""
    if item_id in UPGRADE_EXCLUSIONS:
        return False
    return rarity_rank(item_rarity(content, item_id)) >= rarity_rank(MIN_UPGRADE_RARITY)


def recipe_for(content: GameContent, item_id: str) -> UpgradeRecipe | None:
    return content.upgrade_recipes.get(item_id)


def variant_for(content: GameContent, item_id: str, variant_id: str) -> UpgradeVariant | None:
    recipe = recipe_for(content, item_id)
    if recipe is None:
        return None
    return next((v for v in recipe.variants if v.id == variant_id), None)


def is_upgraded(player: Player, item_id: str) -> bool:
    return item_id in player.item_upgrades


def applied_variant(content: GameContent, player: Player, item_id: str) -> UpgradeVariant | None:
    variant_id = player.item_upgrades.get(item_id)
    return variant_for(content, item_id, variant_id) if variant_id else None


def owns_item(player: Player, content: GameContent, item_id: str) -> bool:
    if item_id in content.weapons:
        return item_id in player.owned_weapon_ids
    if item_id in content.gear_items:
        return item_id in player.owned_gear_ids
    return False


def missing_materials(player: Player, variant: UpgradeVariant) -> list[tuple[str, int, int]]:
    """(material_id, have, need) for every material the player is short on."""
    short = []
    for material_id, need in variant.materials:
        have = player.inventory.count(material_id)
        if have < need:
            short.append((material_id, have, need))
    return short


def can_afford(player: Player, variant: UpgradeVariant) -> bool:
    return player.gold >= variant.gold and not missing_materials(player, variant)


def apply_upgrade(player: Player, content: GameContent, item_id: str, variant_id: str) -> UpgradeResult:
    """Validate, consume gold + materials, record the chosen variant. One-time and
    permanent. Never touches tier/required-level/damage_bonus."""
    if not is_upgradable(content, item_id):
        return UpgradeResult(False, "This item cannot be upgraded.")
    if not owns_item(player, content, item_id):
        return UpgradeResult(False, "You do not own that item.")
    if is_upgraded(player, item_id):
        return UpgradeResult(False, "That item has already been upgraded.")
    variant = variant_for(content, item_id, variant_id)
    if variant is None:
        return UpgradeResult(False, "Unknown upgrade variant.")
    if player.gold < variant.gold:
        return UpgradeResult(False, f"Not enough gold — needs {variant.gold}.")
    if missing_materials(player, variant):
        return UpgradeResult(False, "You lack the required materials.")

    player.gold -= variant.gold
    for material_id, need in variant.materials:
        player.inventory.remove_consumable(material_id, need)
    player.item_upgrades[item_id] = variant_id
    return UpgradeResult(True, f"Upgraded to {variant.name}.")


def recompute_upgrade_modifiers(player: Player, content: GameContent) -> None:
    """Rebuild the derived upgrade contributions from the EQUIPPED items' recorded
    variants: flat stat deltas (weapon + gear) into upgrade_stat_bonuses, and the
    equipped weapon's elemental component into weapon_upgrade_components."""
    flats: dict[str, int] = {}
    components: list[dict[str, object]] = []

    def fold(item_id: str, allow_element: bool) -> None:
        variant = applied_variant(content, player, item_id)
        if variant is None:
            return
        for mod in variant.mods:
            if mod.type == "flat" and mod.stat in UPGRADE_FLAT_STATS:
                flats[mod.stat] = flats.get(mod.stat, 0) + mod.value
            elif mod.type == "element" and allow_element:
                components.append({"damage_type": mod.damage_type, "mod_value": mod.value})

    fold(player.equipped_weapon_id, allow_element=True)
    for gear_id in player.equipped_gear.values():
        fold(gear_id, allow_element=False)   # armour v1: flats only, no element

    player.upgrade_stat_bonuses = {stat: value for stat, value in flats.items() if value}
    player.weapon_upgrade_components = components
