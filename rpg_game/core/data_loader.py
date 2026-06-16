from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rpg_game.core.entities import (
    Connection,
    ConsumableItem,
    EnemyTemplate,
    GameContent,
    Place,
    Position,
    PlayerClass,
    Weapon,
)


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_STORE_INVENTORY = ("hp_potion", "sword", "axe", "longsword")


def _read_json(filename: str) -> Any:
    with (DATA_DIR / filename).open(encoding="utf-8") as file:
        return json.load(file)


def load_content() -> GameContent:
    classes = {
        row["id"]: PlayerClass(
            id=row["id"],
            name=row["name"],
            max_hp=row["max_hp"],
            base_damage=row["base_damage"],
            armor=row["armor"],
            starting_weapon_id=row["starting_weapon_id"],
        )
        for row in _read_json("classes.json")
    }

    weapons = {
        row["id"]: Weapon(
            id=row["id"],
            name=row["name"],
            damage_bonus=row["damage_bonus"],
            price=row["price"],
        )
        for row in _read_json("weapons.json")
    }

    items = {
        row["id"]: ConsumableItem(
            id=row["id"],
            name=row["name"],
            kind=row["kind"],
            heal_amount=row["heal_amount"],
            price=row["price"],
        )
        for row in _read_json("items.json")
    }

    enemies = {
        row["id"]: EnemyTemplate(
            id=row["id"],
            name=row["name"],
            level=row["level"],
            max_hp=row["max_hp"],
            damage=row["damage"],
            armor=row["armor"],
            xp_reward=row["xp_reward"],
            gold_min=row["gold_min"],
            gold_max=row["gold_max"],
        )
        for row in _read_json("enemies.json")
    }

    world = _read_json("world.json")
    places = {}
    for row in world["places"]:
        position = row["position"]
        connections = tuple(
            Connection(
                to=connection["to"],
                travel=connection["travel"],
                distance_px=connection["distance_px"],
                distance_km_approx=connection["distance_km_approx"],
            )
            for connection in row["connections"]
        )
        places[row["id"]] = Place(
            id=row["id"],
            name=row["name"],
            type=row["type"],
            description=row["description"],
            has_store=row["has_store"],
            mana_site=row["mana_site"],
            port=row["port"],
            position=Position(x=position["x"], y=position["y"]),
            danger_tier=row["danger_tier"],
            encounters=tuple(row["encounters"]),
            respawn=row["respawn"],
            locked=row["locked"],
            connections=connections,
            store_inventory=tuple(row.get("store_inventory", DEFAULT_STORE_INVENTORY)),
            respawn_place_id=row["id"] if row["respawn"] else world["meta"]["start_place_id"],
        )

    return GameContent(
        start_place_id=world["meta"]["start_place_id"],
        classes=classes,
        weapons=weapons,
        items=items,
        enemies=enemies,
        places=places,
    )
