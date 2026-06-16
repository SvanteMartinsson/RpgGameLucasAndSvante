from __future__ import annotations

import random

from rpg_game.core.entities import Connection, Enemy, GameContent, Place, Player


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


def create_encounter(player: Player, content: GameContent, rng: random.Random) -> Enemy | None:
    place = get_current_place(player, content)
    if not place.encounters:
        return None
    enemy_id = rng.choice(place.encounters)
    return content.enemies[enemy_id].create_enemy()
