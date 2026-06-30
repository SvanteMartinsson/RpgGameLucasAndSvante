"""Load authored JSON content into typed dataclasses.

This module is the boundary between data files and the runtime game state.
Keep defaults here when adding optional JSON fields so older data remains
loadable during development.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rpg_game.core.entities import (
    Connection,
    ConsumableItem,
    CombatAction,
    EnemyTemplate,
    EquipmentSlot,
    EffectSpec,
    GameContent,
    GearItem,
    Place,
    Position,
    PlayerClass,
    TalentNode,
    Tournament,
    TournamentReward,
    Weapon,
)
from rpg_game.core.equipment import ALLOWED_GEAR_STATS
from rpg_game.core import combat, traits


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
            wisdom=row["wisdom"],
            speed=row["speed"],
            crit_chance=row.get("crit_chance", 0),
            starting_weapon_id=row["starting_weapon_id"],
            starting_skill_ids=tuple(row.get("starting_skill_ids", ())),
        )
        for row in _read_json("classes.json")
    }
    for player_class in classes.values():
        if len(player_class.starting_skill_ids) > 4:
            raise ValueError(f"{player_class.id} has more than 4 equipped skills")

    weapons = {
        row["id"]: Weapon(
            id=row["id"],
            name=row["name"],
            damage_bonus=row["damage_bonus"],
            price=row["price"],
            damage_type=row.get("damage_type", "physical"),
            # Tier is derived from damage (single source of truth); any `tier` in
            # JSON is ignored.
            tier=combat.weapon_tier_from_damage(row["damage_bonus"]),
            category=row.get("category", "melee"),
        )
        for row in _read_json("weapons.json")
    }

    equipment_slots = {
        row["id"]: EquipmentSlot(
            id=row["id"],
            name=row["name"],
            slot_type=row["slot_type"],
            accepts=row.get("accepts", row["slot_type"]),
            order=row.get("order", 0),
        )
        for row in _read_json("equipment_slots.json")
    }

    gear_items = {
        row["id"]: GearItem(
            id=row["id"],
            name=row["name"],
            slot_type=row["slot_type"],
            tier=row["tier"],
            rarity=row["rarity"],
            level_req=row.get("level_req", max(1, row["tier"] - 2)),
            stat_modifiers={key: int(value) for key, value in row.get("stat_modifiers", {}).items()},
        )
        for row in _read_json("gear.json")
    }

    actions = {
        row["id"]: CombatAction(
            id=row["id"],
            name=row["name"],
            kind=row["kind"],
            hit_chance=row.get("hit_chance", 1.0),
            mana_cost=row.get("mana_cost", 0),
            cooldown_rounds=row.get("cooldown_rounds", 0),
            telegraph=row.get("telegraph", False),
            requires_weapon_category=row.get("requires_weapon_category", ""),
            effects=tuple(
                _effect_from_json(effect)
                for effect in row.get("effects", ())
            ),
        )
        for row in _read_json("actions.json")
    }

    talents = {
        row["id"]: TalentNode(
            id=row["id"],
            class_id=row["class_id"],
            branch=row["branch"],
            order=row["order"],
            name=row["name"],
            node_type=row["node_type"],
            max_rank=row.get("max_rank", 1),
            action_id=row.get("action_id", ""),
            requires=row.get("requires", ""),
            effects=tuple(
                _effect_from_json(effect)
                for effect in row.get("effects", ())
            ),
        )
        for row in _read_json("talents.json")
    }

    tournaments = {
        row["id"]: Tournament(
            id=row["id"],
            name=row["name"],
            place_id=row["place_id"],
            rank=row["rank"],
            description=row["description"],
            opponent_ids=tuple(row["opponent_ids"]),
            reward=TournamentReward(
                gold=row.get("reward", {}).get("gold", 0),
                item_ids=tuple(row.get("reward", {}).get("item_ids", ())),
            ),
            entry_fee=row.get("entry_fee", 0),
            repeatable=row.get("repeatable", False),
        )
        for row in _read_json("tournaments.json")
    }

    items = {
        row["id"]: ConsumableItem(
            id=row["id"],
            name=row["name"],
            kind=row["kind"],
            heal_amount=row.get("heal_amount", 0),
            price=row["price"],
            tier=row.get("tier", 1),
            mana_amount=row.get("mana_amount", 0),
            cures=tuple(row.get("cures", ())),
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
            speed=row["speed"],
            traits=tuple(row.get("traits", ())),
            # Resistances are derived from traits (single source of truth); any
            # `resistances` left in JSON is ignored.
            resistances=traits.resistances_from_traits(row.get("traits", ())),
            action_ids=tuple(row.get("action_ids", ("power", "normal", "quick"))),
            xp_reward=row["xp_reward"],
            gold_min=row["gold_min"],
            gold_max=row["gold_max"],
            tags=tuple(row.get("tags", ())),
            mana=row.get("mana", 0),
            ai=tuple(row.get("ai", ())),
            loot_table=tuple(row.get("loot_table", ())),
            unique_table=tuple(row.get("unique_table", ())),
            drop_chance=row.get("drop_chance", 0.0),
            rare_table_access=row.get("rare_table_access", False),
            level_min=row.get("level_min", row["level"]),
            level_max=row.get("level_max", row["level"]),
        )
        for row in _read_json("enemies.json")
    }

    rare_loot_table = tuple(_read_json("loot.json").get("rare_table", ()))

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
            level_min=row.get("level_min", 0),
            level_max=row.get("level_max", 0),
            rare_encounter=row.get("rare_encounter", ""),
            rare_chance=row.get("rare_chance", 0.0),
        )

    _validate_gear(equipment_slots, gear_items)
    _validate_tournaments(tournaments, enemies, places, weapons, items)

    return GameContent(
        start_place_id=world["meta"]["start_place_id"],
        classes=classes,
        weapons=weapons,
        equipment_slots=equipment_slots,
        gear_items=gear_items,
        items=items,
        actions=actions,
        talents=talents,
        tournaments=tournaments,
        enemies=enemies,
        places=places,
        rare_loot_table=rare_loot_table,
    )


def _validate_gear(equipment_slots, gear_items) -> None:
    accepted_types = {slot.accepts for slot in equipment_slots.values() if slot.slot_type != "weapon"}
    for gear in gear_items.values():
        if gear.slot_type not in accepted_types:
            raise ValueError(f"{gear.id} uses unknown slot_type {gear.slot_type}")
        invalid_stats = set(gear.stat_modifiers) - ALLOWED_GEAR_STATS
        if invalid_stats:
            raise ValueError(f"{gear.id} has unsupported stats: {', '.join(sorted(invalid_stats))}")


def _validate_tournaments(tournaments, enemies, places, weapons, items) -> None:
    for tournament in tournaments.values():
        if tournament.place_id not in places:
            raise ValueError(f"{tournament.id} references unknown place {tournament.place_id}")
        for enemy_id in tournament.opponent_ids:
            if enemy_id not in enemies:
                raise ValueError(f"{tournament.id} references unknown opponent {enemy_id}")
        for item_id in tournament.reward.item_ids:
            if item_id not in weapons and item_id not in items:
                raise ValueError(f"{tournament.id} references unknown reward {item_id}")


def _effect_from_json(effect: dict[str, Any]) -> EffectSpec:
    return EffectSpec(
        type=effect["type"],
        magnitude=effect.get("magnitude", 0),
        duration=effect.get("duration", 0),
        tick_timing=effect.get("tick_timing", "instant"),
        multiplier=effect.get("multiplier", 1.0),
        multiplier_min=effect.get("multiplier_min", 0.0),
        multiplier_max=effect.get("multiplier_max", 0.0),
        scale=effect.get("scale", "flat"),
        damage_type=effect.get("damage_type", "physical"),
        status_type=effect.get("status_type", ""),
        target=effect.get("target", "enemy"),
        stat=effect.get("stat", ""),
        ratio=effect.get("ratio", 0.0),
        modifies_status_type=effect.get("modifies_status_type", ""),
        mod_magnitude=effect.get("mod_magnitude", 0),
        mod_duration=effect.get("mod_duration", 0),
        tag=effect.get("tag", ""),
        crit_bonus=effect.get("crit_bonus", 0),
        conditional=effect.get("conditional", {}),
        trigger=effect.get("trigger", "on_hit"),
        armor_pen=effect.get("armor_pen", 0),
        hits=effect.get("hits", 1),
        max_stacks=effect.get("max_stacks", 1),
        on_event=effect.get("on_event", ""),
    )
