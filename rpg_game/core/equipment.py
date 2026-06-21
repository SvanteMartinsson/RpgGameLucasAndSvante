from __future__ import annotations

from dataclasses import dataclass

from rpg_game.core.entities import GameContent, GearItem, Player


ALLOWED_GEAR_STATS = {"max_hp", "max_mana", "armor", "speed", "crit_chance", "damage"}


@dataclass(frozen=True)
class EquipmentResult:
    success: bool
    message: str
    gear_id: str = ""
    slot_id: str = ""


def recompute_gear_modifiers(player: Player, content: GameContent) -> None:
    totals = {stat: 0 for stat in ALLOWED_GEAR_STATS}
    for gear_id in player.equipped_gear.values():
        gear = content.gear_items.get(gear_id)
        if gear is None:
            continue
        for stat, value in gear.stat_modifiers.items():
            totals[stat] = totals.get(stat, 0) + value
    player.gear_stat_modifiers = {stat: value for stat, value in totals.items() if value}
    clamp_resource_caps(player)


def effective_stat(player: Player, stat: str) -> int:
    return player.effective_stat(stat)


def gear_modifier_total(player: Player, stat: str) -> int:
    return player.gear_stat_modifiers.get(stat, 0)


def clamp_resource_caps(player: Player) -> None:
    player.hp = min(player.hp, effective_stat(player, "max_hp"))
    player.mana = min(player.mana, effective_stat(player, "max_mana"))


def equip_gear(player: Player, content: GameContent, gear_id: str, slot_id: str = "") -> EquipmentResult:
    gear = content.gear_items.get(gear_id)
    if gear is None:
        return EquipmentResult(False, f"Unknown gear: {gear_id}.")
    if gear.id not in player.owned_gear_ids:
        return EquipmentResult(False, f"{gear.name} is not owned.")
    if player.level < gear.level_req:
        return EquipmentResult(False, f"{gear.name} requires level {gear.level_req}.", gear.id, slot_id)

    selected_slot = _resolve_slot(player, content, gear, slot_id)
    if selected_slot == "":
        return EquipmentResult(False, f"No open {gear.slot_type} slot. Unequip one first.", gear.id, "")
    if selected_slot not in content.equipment_slots:
        return EquipmentResult(False, f"Unknown slot: {slot_id}.", gear.id, slot_id)
    slot = content.equipment_slots[selected_slot]
    if slot.accepts != gear.slot_type:
        return EquipmentResult(False, f"{gear.name} cannot be equipped in {slot.name}.", gear.id, selected_slot)

    player.equipped_gear[selected_slot] = gear.id
    recompute_gear_modifiers(player, content)
    return EquipmentResult(True, f"Equipped {gear.name} in {slot.name}.", gear.id, selected_slot)


def unequip_gear(player: Player, content: GameContent, slot_id: str) -> EquipmentResult:
    if slot_id not in content.equipment_slots:
        return EquipmentResult(False, f"Unknown slot: {slot_id}.", "", slot_id)
    gear_id = player.equipped_gear.get(slot_id, "")
    if not gear_id:
        return EquipmentResult(False, f"{content.equipment_slots[slot_id].name} is already empty.", "", slot_id)
    del player.equipped_gear[slot_id]
    recompute_gear_modifiers(player, content)
    gear = content.gear_items.get(gear_id)
    name = gear.name if gear else gear_id
    return EquipmentResult(True, f"Unequipped {name}.", gear_id, slot_id)


def _resolve_slot(player: Player, content: GameContent, gear: GearItem, slot_id: str) -> str:
    if slot_id:
        return slot_id
    candidates = [
        slot
        for slot in sorted(content.equipment_slots.values(), key=lambda item: item.order)
        if slot.accepts == gear.slot_type and slot.slot_type != "weapon"
    ]
    for slot in candidates:
        if slot.id not in player.equipped_gear:
            return slot.id
    return ""
