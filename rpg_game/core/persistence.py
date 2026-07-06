"""Serialize and restore the mutable game state to/from plain dicts.

Only the runtime `Player` state is persisted; static `GameContent` is reloaded
from the data files on load.

B59 hardening — three guarantees:
  * ONE field table (`PLAYER_FIELDS`) drives both directions, so a new Player
    field cannot be serialized-but-not-restored (or vice versa). Fields that are
    DERIVED at runtime are declared in `DERIVED_FIELDS`; a field in neither set
    fails the round-trip coverage test.
  * Saves carry a schema version. Old saves are lifted step-by-step through the
    `MIGRATIONS` table (version -> migration) before deserialization — ad-hoc
    key-juggling lives in exactly one place per version bump.
  * `verify_invariants` checks cross-field invariants (talent_ranks is the
    source of truth for learned_talent_ids) at load with a named error.

Derived fields are REBUILT after load by the engine (equipment.recompute_gear_
modifiers -> upgrades.recompute_upgrade_modifiers, talents.sync_runtime); they
are never read from a save.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, fields as dataclass_fields

from rpg_game.core import entities
from rpg_game.core.entities import ActiveStatus, GameState, Inventory, Player

# Bump on EVERY schema change and add a MIGRATIONS entry lifting the previous
# version one step. Version 1 = everything up to the pre-B59 schema (including
# older key layouts that were patched ad hoc — now materialized in 1 -> 2).
SAVE_VERSION = 2


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


# --- the field table ---------------------------------------------------------
# name -> (to_json, from_json). from_json receives the raw JSON value or None
# (key absent) and must return the field value, applying the default itself.

def _int(default: int = 0):
    return (lambda v: v, lambda raw: int(raw) if raw is not None else default)


def _float(default: float):
    return (lambda v: v, lambda raw: float(raw) if raw is not None else default)


def _str(default: str = ""):
    return (lambda v: v, lambda raw: str(raw) if raw is not None else default)


def _str_tuple():
    return (lambda v: list(v), lambda raw: tuple(raw) if raw else ())


def _str_set():
    return (lambda v: sorted(v), lambda raw: set(raw) if raw else set())


def _dict_of(cast):
    return (lambda v: dict(v),
            lambda raw: {key: cast(value) for key, value in raw.items()} if raw else {})


def _list_of_dicts():
    return (lambda v: [dict(item) for item in v],
            lambda raw: [dict(item) for item in raw] if raw else [])


PLAYER_FIELDS: dict[str, tuple] = {
    "name": _str("Hero"),
    "player_class": _str("fighter"),
    "level": _int(1),
    "xp": _int(0),
    "xp_required": _int(100),
    "hp": _int(1),
    "max_hp": _int(1),
    "base_damage": _int(0),
    "armor": _int(0),
    "gold": _int(0),
    "equipped_weapon_id": _str(""),
    "inventory": (
        lambda inv: {"consumables": dict(inv.consumables)},
        lambda raw: Inventory(consumables={k: int(v) for k, v in (raw or {}).get("consumables", {}).items()}),
    ),
    "current_place_id": _str(""),      # "" is post-filled with default_place_id
    "respawn_place_id": _str(""),      # "" is post-filled with default_place_id
    "owned_weapon_ids": _str_tuple(),
    "owned_gear_ids": _str_tuple(),
    "equipped_gear": _dict_of(str),
    "mana": _int(0),
    "wisdom": _int(0),
    "speed": _int(0),
    "crit_chance": _int(0),
    "crit_mult": _float(2.0),
    "evasion_chance": _int(0),
    "damage_dealt_mod": _int(0),
    "damage_taken_mod": _int(0),
    "equipped_skill_ids": _str_tuple(),
    "talent_points": _int(0),
    "learned_skill_ids": _str_tuple(),
    "opened_chest_ids": _str_tuple(),   # B63 world chests
    "playtime_seconds": _int(0),        # B71 play time
    "bestiary_seen": _str_set(),        # B66 bestiary
    "bestiary_identified": _str_set(),
    "bestiary_kills": _dict_of(int),
    "learned_talent_ids": _str_set(),
    "talent_ranks": _dict_of(int),
    "resistances": _dict_of(float),
    "active_statuses": (
        lambda statuses: [serialize_status(status) for status in statuses],
        lambda raw: [deserialize_status(status) for status in raw] if raw else [],
    ),
    "stat_bonuses": _dict_of(int),
    "applied_status_mods": (
        lambda v: {key: dict(value) for key, value in v.items()},
        lambda raw: {key: {ik: int(iv) for ik, iv in value.items()} for key, value in raw.items()} if raw else {},
    ),
    "cooldowns": _dict_of(int),
    "accuracy_mod": _int(0),
    "immunity_tags": _str_set(),
    "tags": _str_set(),
    "conditional_damage_mods": _list_of_dicts(),
    "elemental_attack_mods": _list_of_dicts(),
    "pending_stat_choices": _int(0),
    "completed_tournament_ids": _str_set(),
    "item_upgrades": _dict_of(str),
    # B11 fog-of-war: base64 of the reveal bitset ("" when nothing revealed).
    "revealed_tiles": (
        lambda bits: base64.b64encode(bytes(bits)).decode("ascii"),
        lambda raw: bytearray(base64.b64decode(raw or "")),
    ),
}

# Runtime-derived Player fields — never persisted, always rebuilt after load
# (equipment.recompute_gear_modifiers / talents.sync_runtime, called by the
# engine). The coverage test enforces PLAYER_FIELDS ∪ DERIVED_FIELDS == Player.
DERIVED_FIELDS = {
    "max_mana",                    # derived from wisdom (+ gear/upgrade bonuses)
    "gear_stat_modifiers",         # recomputed from equipped_gear
    "talent_skill_ranks",          # rebuilt from talent_ranks
    "upgrade_stat_bonuses",        # rebuilt from item_upgrades
    "weapon_upgrade_components",   # rebuilt from item_upgrades
}


def serialize_player(player: Player) -> dict:
    return {name: to_json(getattr(player, name)) for name, (to_json, _) in PLAYER_FIELDS.items()}


def deserialize_player(data: dict, default_place_id: str = "") -> Player:
    kwargs = {name: from_json(data.get(name)) for name, (_, from_json) in PLAYER_FIELDS.items()}
    kwargs["current_place_id"] = kwargs["current_place_id"] or default_place_id
    kwargs["respawn_place_id"] = kwargs["respawn_place_id"] or default_place_id
    return Player(**kwargs)


# --- migrations ---------------------------------------------------------------

def _migrate_v1_to_v2(data: dict) -> dict:
    """Materialize the pre-B59 ad-hoc rules as an explicit migration:
    * legacy purchased respawn lived in last_rest_place_id — trust it over the
      movement-polluted respawn_place_id;
    * wisdom is derived from a stored max_mana when absent (pre-wisdom saves);
    * talent_ranks synthesized from learned_talent_ids (pre-B36 saves), and
      learned_talent_ids re-derived from ranks (the invariant's source of truth).
    """
    data = dict(data)
    if "last_rest_place_id" in data:
        data["respawn_place_id"] = data.pop("last_rest_place_id") or ""
    if "wisdom" not in data:
        data["wisdom"] = data.get("max_mana", 0) // entities.MANA_PER_WISDOM
    ranks = data.get("talent_ranks") or {tid: 1 for tid in data.get("learned_talent_ids", ())}
    data["talent_ranks"] = {key: int(value) for key, value in ranks.items() if int(value) >= 1}
    data["learned_talent_ids"] = sorted(data["talent_ranks"])
    return data


MIGRATIONS = {
    1: _migrate_v1_to_v2,
}


def migrate_player_data(data: dict, version: int) -> dict:
    """Lift a player dict from `version` to SAVE_VERSION one step at a time."""
    while version < SAVE_VERSION:
        step = MIGRATIONS.get(version)
        if step is None:
            raise ValueError(f"no migration from save version {version}")
        data = step(data)
        version += 1
    return data


def verify_invariants(player: Player) -> None:
    """Cross-field invariants a loaded player must satisfy (named error, not a
    silent drift): talent_ranks is the source of truth for learned_talent_ids."""
    ranked = {talent_id for talent_id, rank in player.talent_ranks.items() if rank >= 1}
    if player.learned_talent_ids != ranked:
        raise ValueError(
            "save invariant broken: learned_talent_ids "
            f"{sorted(player.learned_talent_ids)} != rank>=1 nodes {sorted(ranked)}")
    negative = [talent_id for talent_id, rank in player.talent_ranks.items() if rank < 1]
    if negative:
        raise ValueError(f"save invariant broken: non-positive talent ranks for {sorted(negative)}")


def persisted_field_names() -> set[str]:
    """All Player dataclass fields that must be covered by PLAYER_FIELDS."""
    return {f.name for f in dataclass_fields(Player)} - DERIVED_FIELDS


def serialize_state(state: GameState) -> dict:
    return {"version": SAVE_VERSION, "player": serialize_player(state.player)}
