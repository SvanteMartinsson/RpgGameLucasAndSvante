"""Rolling JSONL playtest logger for presentation layers.

The logger records only structured data already returned to presentation code:
snapshots, enemies and combat turn results. It does not affect game state.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from rpg_game.core import combat
from rpg_game.core.progression import round_half_up


DEFAULT_LOG_DIR = Path("playtest_logs")
KEEP_SESSIONS = 5

# Status ticks are emitted by core as plain event strings (no structured field on
# the result), so the logger parses the two known shapes from result.events:
#   "<actor> took <n> <type> damage from <status>."   (DoT: burn/poison/bleed…)
#   "<actor> regenerated <n> HP."                      (regen)
_DOT_DAMAGE_RE = re.compile(r"^(?P<target>.+) took (?P<amount>\d+) (?P<dtype>\w+) damage from (?P<status>\w+)\.$")
_REGEN_RE = re.compile(r"^(?P<target>.+) regenerated (?P<amount>\d+) HP\.$")


class PlaytestLogger:
    def __init__(self, log_dir: Path | str = DEFAULT_LOG_DIR, now=None) -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = uuid.uuid4().hex
        timestamp = _timestamp(now)
        safe_timestamp = timestamp.replace(":", "").replace("-", "").replace(".", "")
        self.path = self.log_dir / f"playtest_log_{safe_timestamp}_{self.session_id[:8]}.jsonl"
        self.path.touch()
        self._rotate()

    def session_start(self, snapshot) -> None:
        self.write(
            "session_start",
            player_name=snapshot.player.name,
            player_class=snapshot.player.class_id,
            player_level=snapshot.player.level,
        )

    def encounter_start(self, enemy, snapshot, location: str) -> None:
        self.write(
            "encounter_start",
            enemy_id=enemy.id,
            enemy_level=enemy.level,
            player_level=snapshot.player.level,
            location=location,
            loadout=_loadout(snapshot),
        )

    def equip(self, slot: str, item_id: str, damage_type: str = "", stats=None) -> None:
        self._equipment_event("equip", slot, item_id, damage_type, stats)

    def unequip(self, slot: str, item_id: str, damage_type: str = "", stats=None) -> None:
        self._equipment_event("unequip", slot, item_id, damage_type, stats)

    def _equipment_event(self, event: str, slot: str, item_id: str, damage_type: str, stats) -> None:
        fields = {"slot": slot, "item_id": item_id}
        if damage_type:
            fields["damage_type"] = damage_type
        if stats:
            fields["stats"] = dict(stats)
        self.write(event, **fields)

    def combat_result(self, result: combat.CombatTurnResult, enemy, snapshot, location: str) -> None:
        if result.flee_chance is not None:
            self.flee(result.flee_chance, result.outcome == "fled", enemy)
        for resolution in result.action_resolutions:
            self.attack(resolution, snapshot)
        for event in result.events:
            self._maybe_log_tick(event)
        if result.loot_drop is not None:
            self.drop(result.loot_drop, enemy)
        if result.xp_gained or result.gold_gained:
            self.reward(result, enemy)
        if result.levels_gained:
            for level in range(snapshot.player.level - result.levels_gained + 1, snapshot.player.level + 1):
                self.level_up(level)
        if result.respawn is not None:
            self.death(result.respawn, location)

    def flee(self, chance: float, success: bool, enemy) -> None:
        self.write(
            "flee",
            success=success,
            chance_pct=round_half_up(chance * 100),
            enemy_id=enemy.id,
            enemy_level=enemy.level,
        )

    def _maybe_log_tick(self, event: str) -> None:
        """Surface a status tick (DoT damage / regen heal) already present as a
        combat event string as its own structured row."""
        match = _DOT_DAMAGE_RE.match(event)
        if match:
            self.dot_tick(match["target"], match["status"], "damage",
                          int(match["amount"]), damage_type=match["dtype"])
            return
        match = _REGEN_RE.match(event)
        if match:
            self.dot_tick(match["target"], "regen", "heal", int(match["amount"]))

    def dot_tick(self, target: str, status: str, kind: str, amount: int, damage_type: str = "") -> None:
        fields = {"target": target, "status": status, "kind": kind, "amount": amount}
        if damage_type:
            fields["damage_type"] = damage_type
        self.write("dot_tick", **fields)

    def attack(self, resolution: combat.ActionResolution, snapshot) -> None:
        source = "player" if resolution.actor_name == snapshot.player.name else "enemy"
        fields = dict(
            source=source,
            action_id=resolution.action_id,
            rolled_style=resolution.rolled_style_id or _style_from_action_id(resolution.action_id),
            hit=bool(resolution.hit and not resolution.blocked and not resolution.evaded),
            crit=resolution.critical_hits > 0,
            damage=resolution.total_damage,
            damage_components=[
                {"type": component.damage_type, "amount": component.amount}
                for component in resolution.damage_components
            ],
        )
        if source == "player":
            # Attribute the player's attack to the weapon behind it, so a holy
            # hit is traceable to the holy weapon without guessing.
            fields["weapon"] = _equipped_weapon(snapshot)
        self.write("attack", **fields)

    def drop(self, drop, enemy) -> None:
        self.write(
            "drop",
            item_id=drop.item_id,
            rarity=drop.rarity,
            tier=drop.tier,
            enemy_id=enemy.id,
        )

    def reward(self, result: combat.CombatTurnResult, enemy) -> None:
        self.write("reward", xp=result.xp_gained, gold=result.gold_gained, enemy_id=enemy.id)

    def level_up(self, new_level: int) -> None:
        self.write("level_up", new_level=new_level)

    def death(self, respawn, location: str) -> None:
        self.write(
            "death",
            location=location,
            lost_xp=respawn.xp_lost,
            lost_gold=respawn.gold_lost,
            hp_after=respawn.hp,
            mana_after=respawn.mana,
        )

    def write(self, event: str, **fields) -> None:
        row = {
            "timestamp": _timestamp(),
            "session_id": self.session_id,
            "event": event,
            **fields,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    def _rotate(self) -> None:
        files = sorted(self.log_dir.glob("playtest_log_*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)
        for old in files[KEEP_SESSIONS:]:
            old.unlink(missing_ok=True)


def _timestamp(now=None) -> str:
    current = now() if callable(now) else now
    if current is None:
        current = datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.isoformat()


def _style_from_action_id(action_id: str) -> str:
    return action_id if action_id in combat.PLAYER_ATTACK_STYLE_IDS else ""


def _equipped_weapon(snapshot) -> dict:
    """Equipped weapon {id, damage_type} from the snapshot's weapon list."""
    weapon_id = snapshot.player.equipped_weapon_id
    for weapon in snapshot.weapons:
        if weapon.id == weapon_id:
            return {"id": weapon.id, "damage_type": weapon.damage_type}
    return {"id": weapon_id, "damage_type": ""}


def _loadout(snapshot) -> dict:
    """Compact current loadout: equipped weapon + filled (non-weapon) slots."""
    gear = {
        slot.id: slot.equipped_item_id
        for slot in snapshot.equipment_slots
        if slot.slot_type != "weapon" and slot.equipped_item_id
    }
    return {"weapon": _equipped_weapon(snapshot), "gear": gear}
