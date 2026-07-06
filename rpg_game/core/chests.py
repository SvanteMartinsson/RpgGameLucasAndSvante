"""B63: world loot chests.

A chest is authored data (chests.json): a tile, a themed sprite, a gold range
and a weighted loot table gated by a tier cap (low zones cannot chest-drop
top-tier items — same spirit as the enemy rare-table caps). Opening is a
one-time event per player: the id is recorded in player.opened_chest_ids
(persisted), the roll uses the engine's seeded rng, and the item lands through
the same LootDrop/collect path enemy drops use — no parallel loot logic.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from rpg_game.core.entities import ChestDef, GameContent, LootDrop, Player


@dataclass(frozen=True)
class ChestResult:
    success: bool
    message: str
    gold: int = 0
    drop: LootDrop | None = None


def eligible_loot(chest: ChestDef) -> list[dict[str, object]]:
    """The chest's loot pool after its tier cap (mirrors enemy loot gating)."""
    return [entry for entry in chest.loot_table
            if int(entry.get("rarity_tier", 1)) <= chest.tier_cap]


def is_opened(player: Player, chest_id: str) -> bool:
    return chest_id in player.opened_chest_ids


def roll_chest(chest: ChestDef, content: GameContent, rng: random.Random) -> tuple[int, dict | None]:
    """Roll a chest's payout: gold in [gold_min, gold_max] + one weighted entry
    from the tier-capped pool (None with an empty pool)."""
    gold = rng.randint(chest.gold_min, chest.gold_max)
    pool = eligible_loot(chest)
    if not pool:
        return gold, None
    total = sum(float(entry["weight"]) for entry in pool)
    roll = rng.random() * total
    upto = 0.0
    for entry in pool:
        upto += float(entry["weight"])
        if roll < upto:
            return gold, entry
    return gold, pool[-1]


def make_drop(entry: dict, content: GameContent) -> LootDrop:
    """Classify a chest loot entry exactly like enemy drops (authored rarity)."""
    item_id = str(entry["item_id"])
    tier = int(entry.get("rarity_tier", 1))
    if item_id in content.weapons:
        weapon = content.weapons[item_id]
        return LootDrop(item_id, weapon.name, "weapon", tier, weapon.rarity, 0)
    if item_id in content.gear_items:
        gear = content.gear_items[item_id]
        return LootDrop(item_id, gear.name, "gear", gear.tier, gear.rarity, 0)
    item = content.items[item_id]
    return LootDrop(item_id, item.name, item.kind, tier, "common", 0)
