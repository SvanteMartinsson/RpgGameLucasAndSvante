"""B38: skill tomes — the acquisition path for the B27 elemental skill pool.

A tome is an item (kind == "tome") that teaches one action on use, gated by a
level requirement. Tomes are sold at MAGE TOWERS (the same building-id gating as
the B37 upgrade station), bought with gold into the inventory, then consumed to
learn the skill into the player's non-talent `learned_skill_ids` pool (which
`talents.unlocked_skill_ids` merges). Learning does NOT auto-equip — the player
still equips within the max-4 limit via the normal skill screen.
"""

from __future__ import annotations

from rpg_game.core import talents
from rpg_game.core.entities import ConsumableItem, GameContent, Player

# Mage-tower buildings sell tomes (mirrors upgrades.STATION_CATEGORY gating).
TOWER_BUILDING_IDS = {"tower", "mage_tower"}


def is_tome(item: ConsumableItem) -> bool:
    return item.kind == "tome"


def all_tomes(content: GameContent) -> list[ConsumableItem]:
    return [item for item in content.items.values() if is_tome(item)]


def tomes_for_sale(building_id: str, content: GameContent) -> list[ConsumableItem]:
    """Tomes offered by a mage-tower building (empty for any other building)."""
    if building_id not in TOWER_BUILDING_IDS:
        return []
    return sorted(all_tomes(content), key=lambda t: (t.level_req, t.name))


def learn_blocker(player: Player, content: GameContent, tome: ConsumableItem) -> str | None:
    """None if the tome can be learned now, else a human-readable reason."""
    if not is_tome(tome) or not tome.teaches:
        return "That is not a skill tome."
    if tome.teaches not in content.actions:
        return "This tome teaches nothing."
    if player.level < tome.level_req:
        return f"Requires level {tome.level_req}."
    if tome.teaches in talents.unlocked_skill_ids(player, content):
        return "You already know that skill."
    return None


def learn(player: Player, content: GameContent, tome: ConsumableItem) -> None:
    """Add the taught skill to the player's learned pool (idempotent)."""
    if tome.teaches and tome.teaches not in player.learned_skill_ids:
        player.learned_skill_ids = (*player.learned_skill_ids, tome.teaches)
