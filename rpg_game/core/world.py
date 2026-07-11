from __future__ import annotations

import random

from rpg_game.core.entities import Connection, Enemy, EnemyTemplate, GameContent, Place, Player
from rpg_game.core.progression import round_half_up

# Per-level stat growth for wild spawns, applied relative to the template's base
# level. Tunable. A level-5 giant rat (base 1) becomes a real threat, not just
# more XP. Progression pass 2026-07-12: damage growth 0.12 -> 0.08 — the delta
# curve gets its threat from raised BASE kits (flatter level scaling), so an
# on-level fight bites without a +4-level one exploding.
HP_GROWTH_PER_LEVEL = 0.20
DAMAGE_GROWTH_PER_LEVEL = 0.08


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
    # NOTE: travel/enter set location only. The respawn point is a persistent
    # player field changed ONLY by a purchased relocation (relocate_respawn) —
    # never auto-moved by location/zone/death, so you never respawn somewhere
    # you didn't choose.
    return f"Travelled to {new_place.name}."


def enter_place(player: Player, content: GameContent, place_id: str) -> str:
    """Set the player's location directly, without the adjacency gate.

    Free-walk presentation reaches a place by walking onto it, so there is no
    "from" place to validate against. Sets location only — the respawn point is
    NOT touched here (it moves solely via a purchased relocation). Locked places
    are still refused, same as travel.
    """
    normalized = place_id.strip().lower()
    if normalized not in content.places:
        raise ValueError(f"unknown place: {place_id}")
    new_place = content.places[normalized]
    if new_place.locked:
        raise ValueError(f"{new_place.name} is locked.")
    player.current_place_id = normalized
    return f"Entered {new_place.name}."


def roll_enemy_level(template: EnemyTemplate, rng: random.Random, region: "Place | None" = None,
                     band: tuple[int, int] | None = None) -> int:
    """Roll a wild spawn level uniformly within a range.

    Precedence: an explicit `band` (a spawn AREA's level_min/level_max, see
    spawns.band_at) outranks the region's band (set on the place), which
    outranks the enemy type's band. Falls back to the fixed base level (so
    arena templates never vary). Always exactly one rng draw.
    """
    if band is not None:
        low, high = band
    elif region is not None and (region.level_min or region.level_max):
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


def create_encounter(player: Player, content: GameContent, rng: random.Random,
                     pool=None, band: tuple[int, int] | None = None) -> Enemy | None:
    """Generate a wild encounter: roll a level in the enemy's range and scale
    its stats to it. Tournament opponents do NOT use this path (see
    GameEngine.create_tournament_opponent), so their fixed levels never roll.

    B48: with `pool` (a weighted (enemy_id, weight) sequence from
    spawns.pool_at) the enemy comes from the tile's drawn areas; the region's
    level band still applies unless `band` (the tile's spawn-AREA band from
    spawns.band_at) overrides it. Tile-less callers (terminal, sims) omit both
    and keep the classic place-pool + rare-slot path unchanged."""
    place = get_current_place(player, content)
    if pool:
        from rpg_game.core import spawns
        enemy_id = spawns.weighted_pick(tuple(pool), rng)
    else:
        if not place.encounters:
            return None
        if place.rare_encounter and rng.random() < place.rare_chance:
            enemy_id = place.rare_encounter
        else:
            enemy_id = rng.choice(place.encounters)
    template = content.enemies[enemy_id]
    enemy = template.create_enemy()
    scale_enemy_to_level(enemy, template.level, roll_enemy_level(template, rng, region=place, band=band))
    return enemy
