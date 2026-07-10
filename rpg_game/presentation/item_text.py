"""B40 S2: item tooltip builders — what the hover layer says about an item.

Pure functions from core objects to ui.Tooltip payloads, shared by the
inventory/shop/character screens so every menu explains an item the same way
(menu-spec point 2). They read core data (weapons/gear/consumables) and call
core rules (sell value, equip level) — they duplicate none of them.
"""

from __future__ import annotations

from rpg_game.core import combat, store
from rpg_game.presentation import ui
from rpg_game.presentation import ui_text as T
from rpg_game.presentation.talent_text import STATUS_LABELS, skill_effect_lines, stat_label


def on_hit_lines(weapon) -> list:
    """B41 procs, one line each: 'On hit: 30% chance of burning (6 fire/round)'."""
    lines = []
    for proc in weapon.on_hit:
        pct = int(round(proc.get("chance", 0) * 100))
        if "heal_self" in proc:
            lines.append(f"On hit: {pct}% chance to heal {proc['heal_self']} HP")
            continue
        key = proc.get("tag") or proc.get("status_type", "")
        name = STATUS_LABELS.get(key, key)
        if proc.get("magnitude") and proc.get("stat"):
            detail = f" ({stat_label(proc['stat'], proc['magnitude'])})"
        elif proc.get("magnitude") and proc.get("damage_type"):
            detail = f" ({proc['magnitude']} {proc['damage_type']}/round)"
        else:
            detail = ""
        lines.append(f"On hit: {pct}% chance of {name}{detail}")
    return lines


def sell_line(price: int) -> str:
    return f"Sells for {store.sell_value(price)} gold"


def weapon_tooltip(weapon, *, price_line: str = "") -> ui.Tooltip:
    """Tooltip for a content Weapon: type/damage on top, gating below, procs
    spelled out. ``price_line`` is context-dependent (sell in inventory, cost
    in a shop), so the caller supplies it."""
    lines = [
        f"{T.weapon_type(weapon.category)} weapon — {weapon.damage_type} damage",
        f"Damage bonus: +{weapon.damage_bonus}",
        f"Tier {weapon.tier} · needs Lv {combat.weapon_required_level(weapon)}",
        *on_hit_lines(weapon),
    ]
    if price_line:
        lines.append(price_line)
    return ui.Tooltip(title=weapon.name, lines=lines)


def gear_tooltip(gear, *, price_line: str = "") -> ui.Tooltip:
    """Tooltip for gear — works for both the content GearItem (dict mods) and
    the GearSnapshot (tuple mods)."""
    mods = gear.stat_modifiers
    pairs = mods.items() if isinstance(mods, dict) else mods
    lines = [stat_label(stat, value) for stat, value in pairs]
    req = getattr(gear, "level_req", 0) or getattr(gear, "required_level", 1)
    lines.append(f"{gear.rarity.title()} · tier {gear.tier} · needs Lv {req}")
    if price_line:
        lines.append(price_line)
    return ui.Tooltip(title=gear.name, lines=lines)


def consumable_tooltip(item, content, *, price_line: str = "") -> ui.Tooltip:
    """Tooltip for a bag item (consumable/tome/miscellaneous). ``content``
    resolves a tome's taught action to its display name."""
    lines = []
    if item.kind == "tome":
        action = content.actions.get(item.teaches)
        lines.append(f"Teaches: {action.name if action is not None else item.teaches}")
        if action is not None:
            # B89: say what the taught skill DOES, with the shared skill wording.
            lines.extend(skill_effect_lines(action))
        if item.level_req > 1:
            lines.append(f"Needs Lv {item.level_req}")
    if item.heal_amount:
        lines.append(f"Restores {item.heal_amount} HP")
    if item.mana_amount:
        lines.append(f"Restores {item.mana_amount} mana")
    if item.cures:
        lines.append("Cures: " + ", ".join(STATUS_LABELS.get(c, c) for c in item.cures))
    if item.kind == "miscellaneous":
        lines.append("Junk or material — sell it, or brew with it at an apothecary.")
    if price_line:
        lines.append(price_line)
    return ui.Tooltip(title=item.name, lines=lines)
