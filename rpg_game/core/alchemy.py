"""B68: alchemy — brew potions from miscellaneous materials + gold.

Recipes are data (brews.json), shaped like the upgrade recipes: consume
materials + gold, produce a consumable. This gives the material drop pile a
RECURRING sink (upgrades are one-time) and makes the consumable economy
player-driven. Brewing is deliberately cheaper than the shop price — the
materials are farmed — without being free.
"""

from __future__ import annotations

from dataclasses import dataclass

from rpg_game.core.entities import GameContent, Player


@dataclass(frozen=True)
class BrewRecipe:
    id: str
    output: str
    gold: int
    materials: tuple[tuple[str, int], ...]   # (material_item_id, count)


@dataclass(frozen=True)
class BrewResult:
    success: bool
    message: str
    output_id: str = ""


def brew_blocker(player: Player, recipe: BrewRecipe) -> str | None:
    """None if the player can brew this now, else a human-readable reason."""
    if player.gold < recipe.gold:
        return "Not enough gold."
    for material_id, count in recipe.materials:
        if player.inventory.count(material_id) < count:
            return f"Missing materials."
    return None


def brew(player: Player, content: GameContent, recipe: BrewRecipe) -> BrewResult:
    """Consume the recipe's materials + gold and add the output potion."""
    blocker = brew_blocker(player, recipe)
    if blocker:
        return BrewResult(False, blocker)
    player.gold -= recipe.gold
    for material_id, count in recipe.materials:
        for _ in range(count):
            player.inventory.remove_consumable(material_id)
    player.inventory.add_consumable(recipe.output)
    output_name = content.items[recipe.output].name
    return BrewResult(True, f"Brewed {output_name}.", output_id=recipe.output)
