"""Serialize and restore the mutable game state to/from plain dicts.

Only the runtime `Player` state is persisted; static `GameContent` is reloaded
from the data files on load. Deserialization defaults every field so save files
from an older structure (missing fields) load without crashing.
"""

from __future__ import annotations

from dataclasses import dataclass

from rpg_game.core import entities
from rpg_game.core.entities import ActiveStatus, GameState, Inventory, Player


SAVE_VERSION = 1


@dataclass(frozen=True)
class SaveResult:
    success: bool
    message: str


@dataclass(frozen=True)
class LoadResult:
    success: bool
    message: str


def serialize_status(status: ActiveStatus) -> dict:
    return {
        "type": status.type,
        "magnitude": status.magnitude,
        "duration": status.duration,
        "tick_timing": status.tick_timing,
        "stat": status.stat,
        "applied_delta": status.applied_delta,
        "scale": status.scale,
        "multiplier": status.multiplier,
        "damage_type": status.damage_type,
        "tag": status.tag,
        "trigger": status.trigger,
        "max_stacks": status.max_stacks,
        "stacks": status.stacks,
        "on_event": status.on_event,
        "base_duration": status.base_duration,
        "weapon_bonus": status.weapon_bonus,
    }


def deserialize_status(data: dict) -> ActiveStatus:
    return ActiveStatus(
        type=data.get("type", ""),
        magnitude=data.get("magnitude", 0),
        duration=data.get("duration", 0),
        tick_timing=data.get("tick_timing", "instant"),
        stat=data.get("stat", ""),
        applied_delta=data.get("applied_delta", 0),
        scale=data.get("scale", "flat"),
        multiplier=data.get("multiplier", 1.0),
        damage_type=data.get("damage_type", "physical"),
        tag=data.get("tag", ""),
        trigger=data.get("trigger", "on_hit"),
        max_stacks=data.get("max_stacks", 1),
        stacks=data.get("stacks", 1),
        on_event=data.get("on_event", ""),
        base_duration=data.get("base_duration", 0),
        weapon_bonus=data.get("weapon_bonus", 0),
    )


def serialize_player(player: Player) -> dict:
    return {
        "name": player.name,
        "player_class": player.player_class,
        "level": player.level,
        "xp": player.xp,
        "xp_required": player.xp_required,
        "hp": player.hp,
        "max_hp": player.max_hp,
        "base_damage": player.base_damage,
        "armor": player.armor,
        "gold": player.gold,
        "equipped_weapon_id": player.equipped_weapon_id,
        "current_place_id": player.current_place_id,
        "respawn_place_id": player.respawn_place_id,
        "owned_weapon_ids": list(player.owned_weapon_ids),
        "owned_gear_ids": list(player.owned_gear_ids),
        "equipped_gear": dict(player.equipped_gear),
        "mana": player.mana,
        "wisdom": player.wisdom,
        "speed": player.speed,
        "crit_chance": player.crit_chance,
        "crit_mult": player.crit_mult,
        "evasion_chance": player.evasion_chance,
        "damage_dealt_mod": player.damage_dealt_mod,
        "damage_taken_mod": player.damage_taken_mod,
        "equipped_skill_ids": list(player.equipped_skill_ids),
        "talent_points": player.talent_points,
        "learned_talent_ids": sorted(player.learned_talent_ids),
        "resistances": dict(player.resistances),
        "active_statuses": [serialize_status(status) for status in player.active_statuses],
        "stat_bonuses": dict(player.stat_bonuses),
        "applied_status_mods": {key: dict(value) for key, value in player.applied_status_mods.items()},
        "cooldowns": dict(player.cooldowns),
        "accuracy_mod": player.accuracy_mod,
        "immunity_tags": sorted(player.immunity_tags),
        "tags": sorted(player.tags),
        "conditional_damage_mods": [dict(mod) for mod in player.conditional_damage_mods],
        "elemental_attack_mods": [dict(mod) for mod in player.elemental_attack_mods],
        "pending_stat_choices": player.pending_stat_choices,
        "completed_tournament_ids": sorted(player.completed_tournament_ids),
        "inventory": {"consumables": dict(player.inventory.consumables)},
    }


def deserialize_player(data: dict, default_place_id: str = "") -> Player:
    inventory_data = data.get("inventory", {})
    inventory = Inventory(
        consumables={key: int(value) for key, value in inventory_data.get("consumables", {}).items()}
    )
    return Player(
        name=data.get("name", "Hero"),
        player_class=data.get("player_class", "fighter"),
        level=data.get("level", 1),
        xp=data.get("xp", 0),
        xp_required=data.get("xp_required", 100),
        hp=data.get("hp", 1),
        max_hp=data.get("max_hp", 1),
        base_damage=data.get("base_damage", 0),
        armor=data.get("armor", 0),
        gold=data.get("gold", 0),
        equipped_weapon_id=data.get("equipped_weapon_id", ""),
        inventory=inventory,
        current_place_id=data.get("current_place_id") or default_place_id,
        # Migration: legacy saves stored the purchased respawn in last_rest_place_id
        # while respawn_place_id was auto-set by movement (unreliable). If the
        # legacy key is present, trust the purchased value (or default Hordanita);
        # otherwise the new respawn_place_id is the single source of truth.
        respawn_place_id=(
            (data.get("last_rest_place_id") or default_place_id)
            if "last_rest_place_id" in data
            else (data.get("respawn_place_id") or default_place_id)
        ),
        owned_weapon_ids=tuple(data.get("owned_weapon_ids", ())),
        owned_gear_ids=tuple(data.get("owned_gear_ids", ())),
        equipped_gear={key: str(value) for key, value in data.get("equipped_gear", {}).items()},
        mana=data.get("mana", 0),
        # max_mana is derived from wisdom; old saves only stored max_mana, so fall
        # back to max_mana // MANA_PER_WISDOM when wisdom is absent.
        wisdom=data.get("wisdom", data.get("max_mana", 0) // entities.MANA_PER_WISDOM),
        speed=data.get("speed", 0),
        crit_chance=data.get("crit_chance", 0),
        crit_mult=data.get("crit_mult", 2.0),
        evasion_chance=data.get("evasion_chance", 0),
        damage_dealt_mod=data.get("damage_dealt_mod", 0),
        damage_taken_mod=data.get("damage_taken_mod", 0),
        equipped_skill_ids=tuple(data.get("equipped_skill_ids", ())),
        talent_points=data.get("talent_points", 0),
        learned_talent_ids=set(data.get("learned_talent_ids", ())),
        resistances={key: float(value) for key, value in data.get("resistances", {}).items()},
        active_statuses=[deserialize_status(status) for status in data.get("active_statuses", ())],
        stat_bonuses={key: int(value) for key, value in data.get("stat_bonuses", {}).items()},
        applied_status_mods={
            key: {inner_key: int(inner_value) for inner_key, inner_value in value.items()}
            for key, value in data.get("applied_status_mods", {}).items()
        },
        cooldowns={key: int(value) for key, value in data.get("cooldowns", {}).items()},
        accuracy_mod=data.get("accuracy_mod", 0),
        immunity_tags=set(data.get("immunity_tags", ())),
        tags=set(data.get("tags", ())),
        conditional_damage_mods=[dict(mod) for mod in data.get("conditional_damage_mods", ())],
        elemental_attack_mods=[dict(mod) for mod in data.get("elemental_attack_mods", ())],
        pending_stat_choices=data.get("pending_stat_choices", 0),
        completed_tournament_ids=set(data.get("completed_tournament_ids", ())),
    )


def serialize_state(state: GameState) -> dict:
    return {"version": SAVE_VERSION, "player": serialize_player(state.player)}
