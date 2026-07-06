"""B65: zone bosses — the game's spine and ending.

Five authored lairs (bosses.json) hold one named boss each. A boss is a strong,
readable enemy built on existing primitives (telegraphs, hp-phase AI, traits);
nothing here touches combat resolution. This module owns the META rules:
who may be challenged, what a first defeat grants, and when the final
confrontation (and the ending) unlocks. Defeated bosses persist on the player
(`defeated_boss_ids`) and stay down — a lair is a one-time wall, not a farm.
"""

from __future__ import annotations

from dataclasses import dataclass

from rpg_game.core.entities import GameContent, Player


@dataclass(frozen=True)
class BossRewardResult:
    boss_id: str
    gold: int
    item_names: tuple[str, ...]
    events: tuple[str, ...]
    final: bool = False


def challenge_blocker(player: Player, content: GameContent, boss_id: str) -> str:
    """Why this boss can NOT be challenged right now ('' = go ahead)."""
    boss = content.bosses.get(boss_id)
    if boss is None:
        return "There is no such lair."
    if boss.id in player.defeated_boss_ids:
        return "The lair lies silent."
    missing = [required for required in boss.requires_defeated
               if required not in player.defeated_boss_ids]
    if missing:
        names = ", ".join(content.enemies[content.bosses[required].enemy_id].name
                          for required in missing)
        return f"The gate holds fast. Undefeated: {names}."
    return ""


def undefeated_prerequisites(player: Player, content: GameContent, boss_id: str) -> tuple[str, ...]:
    boss = content.bosses.get(boss_id)
    if boss is None:
        return ()
    return tuple(required for required in boss.requires_defeated
                 if required not in player.defeated_boss_ids)


def on_first_defeat(player: Player, content: GameContent, boss_id: str) -> BossRewardResult:
    """Mark the boss defeated and grant its one-time reward. The caller (engine
    victory path) guarantees this runs at most once per boss per player."""
    boss = content.bosses[boss_id]
    player.defeated_boss_ids.add(boss.id)
    player.gold += boss.reward_gold

    item_names: list[str] = []
    for item_id in boss.reward_item_ids:
        if item_id in content.weapons:
            if item_id not in player.owned_weapon_ids:
                player.owned_weapon_ids = (*player.owned_weapon_ids, item_id)
            item_names.append(content.weapons[item_id].name)
        elif item_id in content.gear_items:
            if item_id not in player.owned_gear_ids:
                player.owned_gear_ids = (*player.owned_gear_ids, item_id)
            item_names.append(content.gear_items[item_id].name)
        else:
            player.inventory.add_consumable(item_id)
            item_names.append(content.items[item_id].name)

    enemy_name = content.enemies[boss.enemy_id].name
    events = [f"{enemy_name} is felled. The lair falls silent."]
    reward_bits = [f"{boss.reward_gold} gold"] if boss.reward_gold else []
    reward_bits.extend(item_names)
    if reward_bits:
        events.append(f"Boss reward: {', '.join(reward_bits)}.")
    remaining = [other for other in content.bosses.values()
                 if not other.final and other.id not in player.defeated_boss_ids]
    if boss.final:
        events.append("The curse over the land is broken. THE PALE SOVEREIGN HAS FALLEN.")
    elif remaining:
        events.append(f"Zone bosses remaining: {len(remaining)}.")
    else:
        events.append("All four zone bosses are down. The Pale Gate will open now.")
    return BossRewardResult(
        boss_id=boss.id,
        gold=boss.reward_gold,
        item_names=tuple(item_names),
        events=tuple(events),
        final=boss.final,
    )


def zone_bosses_defeated(player: Player, content: GameContent) -> bool:
    """True when every non-final boss is down (the final gate condition)."""
    return all(boss.id in player.defeated_boss_ids
               for boss in content.bosses.values() if not boss.final)


def main_goal_complete(player: Player, content: GameContent) -> bool:
    """True when the final boss is defeated — the game has been finished."""
    return any(boss.final and boss.id in player.defeated_boss_ids
               for boss in content.bosses.values())
