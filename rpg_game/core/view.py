"""Read-only state snapshots for presentation layers.

Terminal UI may still call `GameEngine` directly while it is simple, but Pygame
should prefer these immutable snapshots for rendering and use `GameEngine`
methods only for commands that mutate state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rpg_game.core import combat

if TYPE_CHECKING:
    from rpg_game.core.game import GameEngine


@dataclass(frozen=True)
class StatusSnapshot:
    name: str
    duration: int
    stacks: int


@dataclass(frozen=True)
class ConnectionSnapshot:
    place_id: str
    name: str
    travel: str
    distance_km_approx: float
    locked: bool


@dataclass(frozen=True)
class WeaponSnapshot:
    id: str
    name: str
    damage_bonus: int
    damage_type: str
    category: str
    tier: int
    required_level: int
    equipped: bool
    equippable: bool


@dataclass(frozen=True)
class EquipmentSlotSnapshot:
    id: str
    name: str
    slot_type: str
    equipped_item_id: str
    equipped_item_name: str


@dataclass(frozen=True)
class GearSnapshot:
    id: str
    name: str
    slot_type: str
    tier: int
    rarity: str
    required_level: int
    stat_modifiers: tuple[tuple[str, int], ...]
    equipped_slot_id: str
    equippable: bool


@dataclass(frozen=True)
class SkillSnapshot:
    id: str
    name: str
    equipped: bool
    mana_cost: int
    cooldown_rounds: int
    requires_weapon_category: str
    blocked_reason: str


@dataclass(frozen=True)
class TournamentSnapshot:
    id: str
    name: str
    rank: str
    description: str
    opponent_count: int
    reward_gold: int
    reward_item_names: tuple[str, ...]
    completed: bool


@dataclass(frozen=True)
class StatDeltaSnapshot:
    """B121a: a single character-screen stat row, split into what the player has
    now (`total` = `effective_stat`) and how much of that comes from equipped gear
    (`from_gear` = `gear_stat_modifiers[stat]`, plus the equipped weapon's
    `damage_bonus` for the "damage"/Power row). The implicit base is `total -
    from_gear`. Computed in the core; presentation only draws it."""
    stat: str
    label: str
    total: int
    from_gear: int


@dataclass(frozen=True)
class PlayerSnapshot:
    name: str
    class_id: str
    class_name: str
    level: int
    xp: int
    xp_required: int
    hp: int
    max_hp: int
    mana: int
    max_mana: int
    wisdom: int
    base_damage: int
    weapon_damage_bonus: int
    total_damage: int
    armor: int
    speed: int
    crit_chance: int
    gold: int
    talent_points: int
    equipped_weapon_id: str
    statuses: tuple[StatusSnapshot, ...]
    stats: tuple[StatDeltaSnapshot, ...]


@dataclass(frozen=True)
class PlaceSnapshot:
    id: str
    name: str
    type: str
    description: str
    has_store: bool
    danger_tier: int
    safe: bool


@dataclass(frozen=True)
class GameSnapshot:
    player: PlayerSnapshot
    place: PlaceSnapshot
    connections: tuple[ConnectionSnapshot, ...]
    weapons: tuple[WeaponSnapshot, ...]
    equipment_slots: tuple[EquipmentSlotSnapshot, ...]
    gear: tuple[GearSnapshot, ...]
    skills: tuple[SkillSnapshot, ...]
    tournaments: tuple[TournamentSnapshot, ...]


# B121a: ordered stat rows for the character screen's stats zone — the single
# source for stat labelling. "damage" is shown as "Power" per CHARACTER_SCREEN.md;
# max_mana/wisdom cover the caster stats. Only stats that gear can modify are
# meaningful here (see equipment.ALLOWED_GEAR_STATS).
_CHARACTER_STATS: tuple[tuple[str, str], ...] = (
    ("max_hp", "Max HP"),
    ("max_mana", "Max Mana"),
    ("damage", "Power"),
    ("armor", "Armor"),
    ("speed", "Speed"),
    ("crit_chance", "Crit %"),
    ("wisdom", "Wisdom"),
)


def build_snapshot(engine: "GameEngine") -> GameSnapshot:
    """Build an immutable rendering snapshot from public engine state."""
    player = engine.player
    player_class = engine.content.classes[player.player_class]
    weapon = engine.content.weapons[player.equipped_weapon_id]
    place = engine.current_place()
    return GameSnapshot(
        player=PlayerSnapshot(
            name=player.name,
            class_id=player.player_class,
            class_name=player_class.name,
            level=player.level,
            xp=player.xp,
            xp_required=player.xp_required,
            hp=player.hp,
            max_hp=engine.effective_stat("max_hp"),
            mana=player.mana,
            max_mana=engine.effective_stat("max_mana"),
            wisdom=engine.effective_stat("wisdom"),
            base_damage=player.base_damage,
            weapon_damage_bonus=weapon.damage_bonus,
            total_damage=engine.effective_stat("damage") + weapon.damage_bonus,
            armor=engine.effective_stat("armor"),
            speed=engine.effective_stat("speed"),
            crit_chance=engine.effective_stat("crit_chance"),
            gold=player.gold,
            talent_points=player.talent_points,
            equipped_weapon_id=player.equipped_weapon_id,
            statuses=_status_snapshots(player.active_statuses),
            stats=tuple(_stat_delta_snapshot(engine, weapon, stat, label) for stat, label in _CHARACTER_STATS),
        ),
        place=PlaceSnapshot(
            id=place.id,
            name=place.name,
            type=place.type,
            description=place.description,
            has_store=place.has_store,
            danger_tier=place.danger_tier,
            safe=not place.encounters,
        ),
        connections=tuple(
            ConnectionSnapshot(
                place_id=connection.to,
                name=engine.content.places[connection.to].name,
                travel=connection.travel,
                distance_km_approx=connection.distance_km_approx,
                locked=engine.content.places[connection.to].locked,
            )
            for connection in engine.available_connections()
        ),
        weapons=tuple(_weapon_snapshot(engine, weapon_id) for weapon_id in player.owned_weapon_ids),
        equipment_slots=tuple(_equipment_slot_snapshot(engine, slot_id) for slot_id in sorted(engine.content.equipment_slots, key=lambda item: engine.content.equipment_slots[item].order)),
        gear=tuple(_gear_snapshot(engine, gear_id) for gear_id in player.owned_gear_ids),
        skills=tuple(_skill_snapshot(engine, action_id) for action_id in engine.player.equipped_skill_ids),
        tournaments=tuple(_tournament_snapshot(engine, tournament) for tournament in engine.available_tournaments()),
    )


def _stat_delta_snapshot(engine: "GameEngine", weapon, stat: str, label: str) -> StatDeltaSnapshot:
    """B121a: split a stat into total (effective) and the part contributed by gear.
    The weapon's damage_bonus is folded into the Power row on both sides so the
    total matches PlayerSnapshot.total_damage and the delta reflects the weapon."""
    total = engine.effective_stat(stat)
    from_gear = engine.gear_modifier_total(stat)
    if stat == "damage":
        total += weapon.damage_bonus
        from_gear += weapon.damage_bonus
    return StatDeltaSnapshot(stat=stat, label=label, total=total, from_gear=from_gear)


def _status_snapshots(statuses) -> tuple[StatusSnapshot, ...]:
    return tuple(
        StatusSnapshot(
            name=status.tag or status.type,
            duration=status.duration,
            stacks=status.stacks,
        )
        for status in statuses
    )


def _weapon_snapshot(engine: "GameEngine", weapon_id: str) -> WeaponSnapshot:
    player = engine.player
    weapon = engine.content.weapons[weapon_id]
    required_level = combat.weapon_required_level(weapon)
    return WeaponSnapshot(
        id=weapon.id,
        name=weapon.name,
        damage_bonus=weapon.damage_bonus,
        damage_type=weapon.damage_type,
        category=weapon.category,
        tier=weapon.tier,
        required_level=required_level,
        equipped=weapon.id == player.equipped_weapon_id,
        equippable=player.level >= required_level,
    )


def _equipment_slot_snapshot(engine: "GameEngine", slot_id: str) -> EquipmentSlotSnapshot:
    slot = engine.content.equipment_slots[slot_id]
    if slot.id == "weapon":
        weapon = engine.content.weapons[engine.player.equipped_weapon_id]
        return EquipmentSlotSnapshot(slot.id, slot.name, slot.slot_type, weapon.id, weapon.name)
    gear_id = engine.player.equipped_gear.get(slot.id, "")
    gear = engine.content.gear_items.get(gear_id)
    return EquipmentSlotSnapshot(
        id=slot.id,
        name=slot.name,
        slot_type=slot.slot_type,
        equipped_item_id=gear.id if gear else "",
        equipped_item_name=gear.name if gear else "",
    )


def _gear_snapshot(engine: "GameEngine", gear_id: str) -> GearSnapshot:
    gear = engine.content.gear_items[gear_id]
    equipped_slot_id = next((slot_id for slot_id, equipped_id in engine.player.equipped_gear.items() if equipped_id == gear.id), "")
    return GearSnapshot(
        id=gear.id,
        name=gear.name,
        slot_type=gear.slot_type,
        tier=gear.tier,
        rarity=gear.rarity,
        required_level=gear.level_req,
        stat_modifiers=tuple(sorted(gear.stat_modifiers.items())),
        equipped_slot_id=equipped_slot_id,
        equippable=engine.player.level >= gear.level_req,
    )


def _skill_snapshot(engine: "GameEngine", action_id: str) -> SkillSnapshot:
    player = engine.player
    action = engine.content.actions[action_id]
    weapon = engine.content.weapons[player.equipped_weapon_id]
    return SkillSnapshot(
        id=action.id,
        name=action.name,
        equipped=action.id in player.equipped_skill_ids,
        mana_cost=action.mana_cost,
        cooldown_rounds=action.cooldown_rounds,
        requires_weapon_category=action.requires_weapon_category,
        blocked_reason=combat.blocked_action_reason(player, action, weapon=weapon),
    )


def _tournament_snapshot(engine: "GameEngine", tournament) -> TournamentSnapshot:
    reward_item_names = []
    for item_id in tournament.reward.item_ids:
        if item_id in engine.content.weapons:
            reward_item_names.append(engine.content.weapons[item_id].name)
        elif item_id in engine.content.items:
            reward_item_names.append(engine.content.items[item_id].name)
    return TournamentSnapshot(
        id=tournament.id,
        name=tournament.name,
        rank=tournament.rank,
        description=tournament.description,
        opponent_count=len(tournament.opponent_ids),
        reward_gold=tournament.reward.gold,
        reward_item_names=tuple(reward_item_names),
        completed=tournament.id in engine.player.completed_tournament_ids,
    )
