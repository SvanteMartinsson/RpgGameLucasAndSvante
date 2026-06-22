from __future__ import annotations

import random

from rpg_game.core.entities import Connection, Enemy, EnemyTemplate, GameContent, Place, Player
from rpg_game.core.progression import round_half_up

# Per-level stat growth for wild spawns, applied relative to the template's base
# level. Tunable. A level-5 giant rat (base 1) becomes a real threat, not just
# more XP.
HP_GROWTH_PER_LEVEL = 0.20
DAMAGE_GROWTH_PER_LEVEL = 0.12


def get_current_place(player: Player, content: GameContent) -> Place:
    return content.places[player.current_place_id]


def available_destinations(player: Player, content: GameContent) -> list[Place]:
    place = get_current_place(player, content)
    destinations = [content.places[connection.to] for connection in place.connections]
    return [destination for destination in destinations if not destination.locked]


def available_connections(player: Player, content: GameContent) -> list[Connection]:
    place = get_current_place(player, content)
    return [
        connection
        for connection in place.connections
        if not content.places[connection.to].locked
    ]


def travel(player: Player, content: GameContent, destination_id: str) -> str:
    normalized = destination_id.strip().lower()
    current = get_current_place(player, content)
    connected_place_ids = {connection.to for connection in current.connections}
    if normalized not in connected_place_ids:
        raise ValueError(f"cannot travel to {destination_id} from {current.name}")
    if content.places[normalized].locked:
        # TODO: Add unlock state and progression rules when locked areas become playable.
        raise ValueError(f"{content.places[normalized].name} is locked.")
    player.current_place_id = normalized
    new_place = content.places[normalized]
    player.respawn_place_id = new_place.respawn_place_id
    return f"Travelled to {new_place.name}."


def enter_place(player: Player, content: GameContent, place_id: str) -> str:
    """Set the player's location directly, without the adjacency gate.

    Free-walk presentation reaches a place by walking onto it, so there is no
    "from" place to validate against. This mirrors :func:`travel`'s state update
    (location + respawn point) but skips the connection check. Locked places are
    still refused, same as travel.
    """
    normalized = place_id.strip().lower()
    if normalized not in content.places:
        raise ValueError(f"unknown place: {place_id}")
    new_place = content.places[normalized]
    if new_place.locked:
        raise ValueError(f"{new_place.name} is locked.")
    player.current_place_id = normalized
    player.respawn_place_id = new_place.respawn_place_id
    return f"Entered {new_place.name}."


def roll_enemy_level(template: EnemyTemplate, rng: random.Random, region: "Place | None" = None) -> int:
    """Roll a wild spawn level uniformly within a range.

    A region's level band (set on the place) overrides the enemy type's band, so
    a shared enemy rolls higher in the west without changing the core. Falls back
    to the type band, then the fixed base level (so arena templates never vary).
    """
    if region is not None and (region.level_min or region.level_max):
        low = region.level_min or region.level_max
        high = region.level_max or region.level_min
    else:
        low = template.level_min or template.level
        high = template.level_max or template.level
    if high < low:
        low, high = high, low
    return rng.randint(low, high)


def scale_enemy_to_level(enemy: Enemy, base_level: int, target_level: int) -> None:
    """Scale a spawned enemy's combat stats from its base level to the rolled
    level in place. HP and power grow; level is updated so Identify and the XP
    multiplier see the rolled level."""
    enemy.level = target_level
    delta = target_level - base_level
    if delta == 0:
        return
    enemy.max_hp = max(1, round_half_up(enemy.max_hp * (1 + HP_GROWTH_PER_LEVEL * delta)))
    enemy.hp = enemy.max_hp
    enemy.damage = max(1, round_half_up(enemy.damage * (1 + DAMAGE_GROWTH_PER_LEVEL * delta)))


def create_encounter(player: Player, content: GameContent, rng: random.Random) -> Enemy | None:
    """Generate a wild encounter: roll a level in the enemy's range and scale
    its stats to it. Tournament opponents do NOT use this path (see
    GameEngine.create_tournament_opponent), so their fixed levels never roll."""
    place = get_current_place(player, content)
    if not place.encounters:
        return None
    if place.rare_encounter and rng.random() < place.rare_chance:
        enemy_id = place.rare_encounter
    else:
        enemy_id = rng.choice(place.encounters)
    template = content.enemies[enemy_id]
    enemy = template.create_enemy()
    scale_enemy_to_level(enemy, template.level, roll_enemy_level(template, rng, region=place))
    return enemy
