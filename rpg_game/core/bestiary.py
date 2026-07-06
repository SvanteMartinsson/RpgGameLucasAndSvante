"""B66: the bestiary — a knowledge codex over enemies.

Meeting an enemy registers it (name + silhouette in the codex); its DETAILS
(traits, resistances, skills, level band) unlock through knowledge: use
Identify on it once, or defeat enough of them. The state lives on the player
(persisted); entries are assembled fresh from content, so the codex always
reflects current enemy data. Arena duelists (tournament humans) are not wild
fauna and stay out of the codex.
"""

from __future__ import annotations

from dataclasses import dataclass

from rpg_game.core.entities import GameContent, Player

# Kills of one enemy type that unlock its details without an Identify.
KILL_UNLOCK = 5


def codex_enemy_ids(content: GameContent) -> list[str]:
    """The enemies the codex tracks: every non-arena template, by name."""
    wild = [enemy for enemy_id, enemy in content.enemies.items()
            if not enemy_id.startswith("arena_")]
    return [enemy.id for enemy in sorted(wild, key=lambda e: (e.level, e.name))]


def mark_seen(player: Player, enemy_id: str) -> None:
    if not enemy_id.startswith("arena_"):
        player.bestiary_seen.add(enemy_id)


def mark_identified(player: Player, enemy_id: str) -> None:
    if not enemy_id.startswith("arena_"):
        player.bestiary_seen.add(enemy_id)
        player.bestiary_identified.add(enemy_id)


def record_kill(player: Player, enemy_id: str) -> None:
    if not enemy_id.startswith("arena_"):
        player.bestiary_seen.add(enemy_id)
        player.bestiary_kills[enemy_id] = player.bestiary_kills.get(enemy_id, 0) + 1


def is_unlocked(player: Player, enemy_id: str) -> bool:
    """Details unlock via Identify OR KILL_UNLOCK defeats."""
    return (enemy_id in player.bestiary_identified
            or player.bestiary_kills.get(enemy_id, 0) >= KILL_UNLOCK)


@dataclass(frozen=True)
class BestiaryEntry:
    id: str
    name: str
    seen: bool
    unlocked: bool
    kills: int
    level_min: int
    level_max: int
    traits: tuple[str, ...]
    resistances: dict[str, float]
    skills: tuple[str, ...]


def entries(content: GameContent, player: Player) -> list[BestiaryEntry]:
    """Every codex row in display order (level, then name)."""
    rows = []
    for enemy_id in codex_enemy_ids(content):
        template = content.enemies[enemy_id]
        rows.append(BestiaryEntry(
            id=enemy_id,
            name=template.name,
            seen=enemy_id in player.bestiary_seen,
            unlocked=is_unlocked(player, enemy_id),
            kills=player.bestiary_kills.get(enemy_id, 0),
            level_min=template.level_min or template.level,
            level_max=template.level_max or template.level,
            traits=tuple(template.traits),
            resistances=dict(template.resistances),
            skills=tuple(content.actions[aid].name for aid in template.action_ids
                         if aid in content.actions),
        ))
    return rows


def progress(content: GameContent, player: Player) -> tuple[int, int, int]:
    """(seen, unlocked, total) over the codex roster."""
    ids = codex_enemy_ids(content)
    seen = sum(1 for enemy_id in ids if enemy_id in player.bestiary_seen)
    unlocked = sum(1 for enemy_id in ids if is_unlocked(player, enemy_id))
    return seen, unlocked, len(ids)
