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
            # Starting vitals for both sides, so a fight's opening state is visible.
            player_hp=snapshot.player.hp,
            player_max_hp=snapshot.player.max_hp,
            player_mana=snapshot.player.mana,
            player_max_mana=snapshot.player.max_mana,
            enemy_hp=enemy.hp,
            enemy_max_hp=getattr(enemy, "max_hp", enemy.hp),
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
        player_name = snapshot.player.name
        enemy_max_hp = getattr(enemy, "max_hp", enemy.hp)
        for resolution in result.action_resolutions:
            # End-of-turn HP of whichever side this resolution targeted. Each
            # combatant takes at most one hit per turn, so the turn-final HP is
            # this event's post-state. Pure observation off the returned result.
            healer_is_player = resolution.actor_name == player_name
            if resolution.target_name == player_name:
                hp_after, max_hp = result.player_hp, snapshot.player.max_hp
            else:
                hp_after, max_hp = result.enemy_hp, enemy_max_hp
            # A pure heal (no damage) is not an attack — logging it as one showed the
            # WRONG side's HP as "target" (B16.1). Log it as its own heal row instead;
            # a drain (damage + heal) still logs the attack AND a heal row.
            if not (resolution.total_damage == 0 and resolution.total_healing > 0):
                self.attack(resolution, snapshot, target_hp_after=hp_after, target_max_hp=max_hp)
            if resolution.total_healing > 0:
                healer_hp = result.player_hp if healer_is_player else result.enemy_hp
                healer_max = snapshot.player.max_hp if healer_is_player else enemy_max_hp
                self.heal(resolution, healer_is_player, healer_hp, healer_max)
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
            # snapshot is built post-respawn, so its place is the respawn place.
            self.death(result.respawn, location, snapshot.place.id)

    def display(self, trigger: str, surface, window, transform=None,
                mode: str = "", desktops=None) -> None:
        """Record a display-geometry event tagged with the action that triggered
        it, so a playtest log shows which actions cause window/anchoring changes
        (the recurring fullscreen bug). Takes plain size tuples — no pygame here.

        `fills` is the key signal: a correctly-filled frame has surface == window;
        when they diverge the logical surface sits in a corner of a larger window.
        """
        surface = tuple(surface)
        window = tuple(window) if window else surface
        fields = {
            "trigger": trigger,
            "surface": list(surface),
            "window": list(window),
            "fills": surface == window,
        }
        if mode:
            fields["mode"] = mode
        if transform is not None:
            fields["transform"] = list(transform)
        if desktops is not None:
            fields["desktops"] = [list(d) for d in desktops]
        self.write("display", **fields)

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

    def attack(self, resolution: combat.ActionResolution, snapshot,
               target_hp_after: int | None = None, target_max_hp: int | None = None) -> None:
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
        if target_hp_after is not None:
            # The defender's HP after this event, so the HP trajectory through the
            # fight is reconstructable turn by turn.
            fields["target_hp_after"] = target_hp_after
            fields["target_max_hp"] = target_max_hp
        self.write("attack", **fields)

    def heal(self, resolution, healer_is_player: bool, healer_hp_after: int,
             healer_max_hp: int) -> None:
        """A heal reads as: who healed themselves and by how much (the healer is the
        actor; the amount is the actual HP restored). Fixes the old confusing row
        that logged a self-heal as an 'attack' on the other side."""
        self.write(
            "heal",
            source="player" if healer_is_player else "enemy",
            action_id=resolution.action_id,
            healer_name=resolution.actor_name,
            amount=resolution.total_healing,
            healer_hp_after=healer_hp_after,
            healer_max_hp=healer_max_hp,
        )

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

    def death(self, respawn, location: str, respawn_place_id: str = "") -> None:
        # `hp_after`/`mana_after` are the post-respawn vitals (half of max after
        # the death penalty), NOT the HP at the moment of death (always 0). The
        # explicit respawn_* fields disambiguate that and say where you reappear.
        self.write(
            "death",
            location=location,
            lost_xp=respawn.xp_lost,
            lost_gold=respawn.gold_lost,
            hp_after=respawn.hp,
            mana_after=respawn.mana,
            respawn_hp=respawn.hp,
            respawn_place_id=respawn_place_id,
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
