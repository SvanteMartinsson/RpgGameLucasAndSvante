"""B135a: the quest engine — data model, per-quest state, progress hooks and
reward payout. Mirrors B67's travel-event model (events.py), which is proven:
frozen dataclasses for authored content, a parse function that VALIDATES at load,
and outcomes applied through EXISTING primitives.

Design decisions (Lucas, locked):
- Quests are SIDE content plus a few zone-intro "spine" quests. Nothing here gates
  zone progression: an unaccepted or unfinished quest never blocks travel.
- Rewards are mixed per quest and reuse existing primitives wherever possible
  (gold/xp/item/status/unlock_tome). Only `shop_discount` and `flag` needed new
  persistent player state — see the module note in game.py.

Objective kinds (v1 — deliberately small):
    kill_enemy    target = enemy id      count = how many
    kill_in_zone  target = zone/theme id count = how many
    deliver_item  target = item id       count = how many (consumed at turn-in)
    visit_place   target = place id      count = 1
    open_chests   target = ""            count = how many

Counter objectives (kill_*/open_chests/visit_place) are PUSHED by the engine's
hooks. `deliver_item` is PULLED from the inventory instead, so an item the player
already owns counts and nothing double-counts. `refresh` is the single place that
flips an active quest to `completed`, so "is it done" has ONE implementation.

Core purity: no print/input, no pygame, no unseeded rng. Every function is a pure
rule over the player's state; the presentation renders the returned strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rpg_game.core import combat, inventory, progression, tomes
from rpg_game.core.entities import ActiveStatus, GameContent, Player

# --- statuses ----------------------------------------------------------------

AVAILABLE = "available"
ACTIVE = "active"
COMPLETED = "completed"      # objective met, not handed in yet
TURNED_IN = "turned_in"      # handed in, rewards paid

# The push-counter kinds vs the pulled one.
COUNTER_KINDS = frozenset({"kill_enemy", "kill_in_zone", "visit_place", "open_chests"})
OBJECTIVE_KINDS = COUNTER_KINDS | {"deliver_item"}
REWARD_KINDS = frozenset({"gold", "xp", "item", "status", "unlock_tome",
                          "shop_discount", "flag"})

# Objective kinds whose `target` names a thing that must exist in content.
_TARGET_LOOKUP = {
    "kill_enemy": "enemies",
    "deliver_item": "items",
    "visit_place": "places",
}


# --- authored content --------------------------------------------------------

@dataclass(frozen=True)
class QuestObjective:
    kind: str
    target: str = ""
    count: int = 1


@dataclass(frozen=True)
class Quest:
    id: str
    title: str
    text: str
    giver_kind: str                       # "board" (notice board) | "bounty"
    objective: QuestObjective
    rewards: tuple[dict, ...] = ()
    zone: str = ""                        # hint shown in the log; "" = anywhere
    prereq_quest_ids: tuple[str, ...] = ()
    repeatable: bool = False


@dataclass
class QuestTurnInResult:
    ok: bool
    text: str = ""
    events: list[str] = field(default_factory=list)
    gold_gained: int = 0
    xp_gained: int = 0
    levels_gained: int = 0
    items_granted: tuple[str, ...] = ()


def parse_quests(data: dict) -> tuple[Quest, ...]:
    """quests.json -> Quest tuple. Shape errors raise here, at load."""
    quests = []
    for row in data.get("quests", ()):
        raw = row.get("objective") or {}
        objective = QuestObjective(
            kind=str(raw.get("kind", "")),
            target=str(raw.get("target", "")),
            count=int(raw.get("count", 1)),
        )
        if objective.count < 1:
            raise ValueError(f"quest {row.get('id')}: objective count must be >= 1")
        quests.append(Quest(
            id=row["id"],
            title=row["title"],
            text=row["text"],
            giver_kind=str(row.get("giver_kind", "board")),
            objective=objective,
            rewards=tuple(row.get("rewards", ())),
            zone=str(row.get("zone", "")),
            prereq_quest_ids=tuple(row.get("prereq_quest_ids", ())),
            repeatable=bool(row.get("repeatable", False)),
        ))
    return tuple(quests)


def validate_quests(quests: tuple[Quest, ...], content: GameContent) -> None:
    """Load-time validation (the B-pattern): an unknown objective kind, an unknown
    target/reward id or a broken prereq chain is a clear error, never a silent miss.
    Called from data_loader after the rest of the content exists."""
    by_id = {quest.id: quest for quest in quests}
    if len(by_id) != len(quests):
        raise ValueError("duplicate quest id in quests.json")
    zones = _known_zones(content)
    for quest in quests:
        objective = quest.objective
        if objective.kind not in OBJECTIVE_KINDS:
            raise ValueError(f"quest {quest.id} uses unknown objective kind "
                             f"{objective.kind!r}")
        lookup = _TARGET_LOOKUP.get(objective.kind)
        if lookup is not None:
            known = getattr(content, lookup, {})
            if objective.target not in known:
                raise ValueError(f"quest {quest.id} targets unknown "
                                 f"{objective.kind} {objective.target!r}")
        if objective.kind == "kill_in_zone" and zones and objective.target not in zones:
            raise ValueError(f"quest {quest.id} targets unknown zone "
                             f"{objective.target!r}")
        if quest.zone and zones and quest.zone not in zones:
            raise ValueError(f"quest {quest.id} has unknown zone hint {quest.zone!r}")
        for reward in quest.rewards:
            _validate_reward(quest, reward, content)
        for required in quest.prereq_quest_ids:
            if required not in by_id:
                raise ValueError(f"quest {quest.id} requires unknown quest {required!r}")
            if required == quest.id:
                raise ValueError(f"quest {quest.id} requires itself")
    _reject_prereq_cycles(by_id)


def _validate_reward(quest: Quest, reward: dict, content: GameContent) -> None:
    kind = str(reward.get("kind", ""))
    if kind not in REWARD_KINDS:
        raise ValueError(f"quest {quest.id} has unknown reward kind {kind!r}")
    if kind in ("gold", "xp") and int(reward.get("amount", 0)) <= 0:
        raise ValueError(f"quest {quest.id} {kind} reward must be positive")
    if kind == "item":
        item_id = str(reward.get("item_id", ""))
        if not _known_item(content, item_id):
            raise ValueError(f"quest {quest.id} rewards unknown item {item_id!r}")
    if kind == "unlock_tome":
        item_id = str(reward.get("item_id", ""))
        tome = content.items.get(item_id)
        if tome is None or not tomes.is_tome(tome):
            raise ValueError(f"quest {quest.id} unlock_tome references "
                             f"non-tome {item_id!r}")
    if kind == "shop_discount":
        percent = int(reward.get("percent", 0))
        if not 1 <= percent <= 50:
            raise ValueError(f"quest {quest.id} shop_discount must be 1-50%, "
                             f"got {percent}")
    if kind == "status" and not str(reward.get("stat", "")):
        raise ValueError(f"quest {quest.id} status reward needs a stat")
    if kind == "flag" and not str(reward.get("flag", "")):
        raise ValueError(f"quest {quest.id} flag reward needs a flag name")


def _known_item(content: GameContent, item_id: str) -> bool:
    return (item_id in content.items or item_id in content.weapons
            or item_id in getattr(content, "gear_items", {}))


def _known_zones(content: GameContent) -> set[str]:
    """The canonical zone names — core_zone's GROUND THEMES (cainos, mork_skog,
    cursed_mire, grave_heath), which are exactly the strings the shell's
    theme_for_tile returns and tags onto a spawn. Empty set = no map loaded (the
    terminal/sim content path), and then zone checks are skipped.

    NOTE: spawn-AREA ids are sub-areas ("skog_beast_1", "heath_ghoul_2") and are
    deliberately NOT the zone vocabulary — validating against them would accept a
    target the kill hook could never match."""
    return {str(zone) for zone in getattr(content, "zone_names", ()) if zone}


def _reject_prereq_cycles(by_id: dict[str, Quest]) -> None:
    """A prereq cycle would make both quests permanently unreachable."""
    state: dict[str, int] = {}

    def walk(quest_id: str, trail: tuple[str, ...]) -> None:
        mark = state.get(quest_id, 0)
        if mark == 1:
            raise ValueError("quest prereq cycle: " + " -> ".join((*trail, quest_id)))
        if mark == 2:
            return
        state[quest_id] = 1
        for required in by_id[quest_id].prereq_quest_ids:
            walk(required, (*trail, quest_id))
        state[quest_id] = 2

    for quest_id in by_id:
        walk(quest_id, ())


# --- per-quest state ---------------------------------------------------------

def state_of(player: Player, quest_id: str) -> dict:
    """The stored {status, progress} for a quest. A quest the save has never heard
    of reads as available with no progress — that is what makes an old save (no
    quest data at all) load as "everything available"."""
    stored = player.quest_states.get(quest_id) or {}
    return {"status": str(stored.get("status", AVAILABLE)),
            "progress": int(stored.get("progress", 0))}


def status_of(player: Player, quest_id: str) -> str:
    return state_of(player, quest_id)["status"]


def _store(player: Player, quest_id: str, status: str, progress: int) -> None:
    player.quest_states[quest_id] = {"status": status, "progress": max(0, progress)}


def prereqs_met(player: Player, quest: Quest) -> bool:
    return all(status_of(player, required) == TURNED_IN
               for required in quest.prereq_quest_ids)


def is_offerable(player: Player, quest: Quest) -> bool:
    """Shown on a board: never accepted (or repeatable and handed in) + prereqs."""
    status = status_of(player, quest.id)
    if not prereqs_met(player, quest):
        return False
    if status == AVAILABLE:
        return True
    return quest.repeatable and status == TURNED_IN


def offerable_quests(player: Player, quests, giver_kind: str = "") -> list[Quest]:
    return [quest for quest in quests
            if (not giver_kind or quest.giver_kind == giver_kind)
            and is_offerable(player, quest)]


def tracked_quests(player: Player, quests) -> list[Quest]:
    """Active + completed-but-not-handed-in, i.e. what the quest log lists."""
    return [quest for quest in quests
            if status_of(player, quest.id) in (ACTIVE, COMPLETED)]


def accept(player: Player, quest: Quest) -> bool:
    """Take the quest. Repeating a turned-in quest resets its progress."""
    if not is_offerable(player, quest):
        return False
    _store(player, quest.id, ACTIVE, 0)
    return True


def abandon(player: Player, quest: Quest) -> bool:
    """Drop an active quest back to available (progress is lost)."""
    if status_of(player, quest.id) not in (ACTIVE, COMPLETED):
        return False
    _store(player, quest.id, AVAILABLE, 0)
    return True


# --- progress ----------------------------------------------------------------

def objective_progress(player: Player, content: GameContent, quest: Quest) -> int:
    """How far along the objective is. Counters read the stored number; the
    delivery objective is counted from the inventory so pre-owned items count."""
    if quest.objective.kind == "deliver_item":
        return player.inventory.count(quest.objective.target)
    return state_of(player, quest.id)["progress"]


def is_objective_met(player: Player, content: GameContent, quest: Quest) -> bool:
    return objective_progress(player, content, quest) >= quest.objective.count


def refresh(player: Player, content: GameContent, quests) -> list[str]:
    """The ONE place an active quest becomes `completed`. Returns Quest-tab lines.
    Safe to call after any hook (and after picking an item up)."""
    lines = []
    for quest in quests:
        if status_of(player, quest.id) != ACTIVE:
            continue
        if is_objective_met(player, content, quest):
            _store(player, quest.id, COMPLETED,
                   state_of(player, quest.id)["progress"])
            lines.append(f"Quest ready to hand in: {quest.title}.")
    return lines


def _advance(player: Player, content: GameContent, quest: Quest, amount: int) -> list[str]:
    """Add to a counter objective, capped at its target.

    Logs a MILESTONE, not every tick: one line when the halfway mark is crossed,
    and nothing else (completion is refresh()'s "ready to hand in" line). Logging
    every increment turned an 8-kill quest into eight log lines; live progress
    belongs on the board and the quest log, which show it continuously."""
    count = quest.objective.count
    state = state_of(player, quest.id)
    before = state["progress"]
    after = min(count, before + amount)
    if after == before:
        return []
    _store(player, quest.id, ACTIVE, after)
    halfway = (count + 1) // 2
    if count >= 2 and before < halfway <= after < count:
        return [f"{quest.title}: {after}/{count}."]
    return []


def _push(player: Player, content: GameContent, quests, kind: str,
          target: str = "", amount: int = 1) -> list[str]:
    """Feed one world event to every active quest that is listening for it."""
    lines = []
    for quest in quests:
        objective = quest.objective
        if objective.kind != kind or status_of(player, quest.id) != ACTIVE:
            continue
        if objective.kind != "open_chests" and objective.target != target:
            continue
        lines.extend(_advance(player, content, quest, amount))
    lines.extend(refresh(player, content, quests))
    return lines


def note_kill(player: Player, content: GameContent, quests, enemy_id: str,
              zone: str = "") -> list[str]:
    """Hook: an enemy died. `zone` is supplied by the shell (which owns tiles) via
    the spawn tag on the enemy — core never resolves tiles itself."""
    lines = _push(player, content, quests, "kill_enemy", enemy_id)
    if zone:
        lines.extend(_push(player, content, quests, "kill_in_zone", zone))
    return lines


def note_chest_opened(player: Player, content: GameContent, quests) -> list[str]:
    return _push(player, content, quests, "open_chests")


def note_place_visited(player: Player, content: GameContent, quests,
                       place_id: str) -> list[str]:
    return _push(player, content, quests, "visit_place", place_id)


def note_item_acquired(player: Player, content: GameContent, quests) -> list[str]:
    """Hook: the player gained an item. Delivery objectives are inventory-pulled,
    so this only needs to re-check completion."""
    return refresh(player, content, quests)


# --- turn-in + rewards -------------------------------------------------------

def turn_in(player: Player, content: GameContent, quest: Quest) -> QuestTurnInResult:
    """Hand in a finished quest and pay its rewards ONCE. A quest that is not
    finished (or already handed in) is refused without side effects."""
    status = status_of(player, quest.id)
    if status == TURNED_IN and not quest.repeatable:
        return QuestTurnInResult(False, "You have already handed that in.")
    if status not in (ACTIVE, COMPLETED):
        return QuestTurnInResult(False, "You are not on that quest.")
    if not is_objective_met(player, content, quest):
        return QuestTurnInResult(False, "That is not finished yet.")

    # The delivery objective consumes what it asked for.
    if quest.objective.kind == "deliver_item":
        player.inventory.remove_consumable(quest.objective.target,
                                           quest.objective.count)

    result = QuestTurnInResult(True, f"Quest complete: {quest.title}.")
    for reward in quest.rewards:
        _grant_reward(player, content, reward, result)
    _store(player, quest.id, TURNED_IN, quest.objective.count)
    return result


def _grant_reward(player: Player, content: GameContent, reward: dict,
                  result: QuestTurnInResult) -> None:
    """Apply ONE reward through an existing primitive."""
    kind = str(reward.get("kind", ""))
    if kind == "gold":
        amount = int(reward["amount"])
        player.gold += amount
        result.gold_gained += amount
        result.events.append(f"Reward: {amount} gold.")
    elif kind == "xp":
        amount = int(reward["amount"])
        result.xp_gained += amount
        result.levels_gained += progression.award_xp(player, amount)
        result.events.append(f"Reward: {amount} XP.")
    elif kind == "item":
        item_id = str(reward["item_id"])
        count = int(reward.get("count", 1))
        for _ in range(count):
            inventory.grant_item(player, content, item_id)
        result.items_granted = (*result.items_granted, item_id)
        result.events.append(f"Reward: {_item_name(content, item_id)}.")
    elif kind == "unlock_tome":
        item_id = str(reward["item_id"])
        tome = content.items[item_id]
        if tomes.learn_blocker(player, content, tome) is None:
            tomes.learn(player, content, tome)     # B120 primitive, no purchase
            result.events.append(f"Reward: learned {tome.name}.")
        else:
            # Can't learn it yet (wrong class/level) — hand over the tome itself
            # so the reward is never silently lost.
            inventory.grant_item(player, content, item_id)
            result.items_granted = (*result.items_granted, item_id)
            result.events.append(f"Reward: {tome.name} (learn it when eligible).")
    elif kind == "status":
        stat = str(reward["stat"])
        magnitude = int(reward.get("magnitude", 0))
        duration = int(reward.get("duration", 3))
        combat.set_stat(player, stat, combat.get_stat(player, stat) + magnitude)
        player.active_statuses.append(ActiveStatus(
            type="buff", stat=stat, magnitude=magnitude, duration=duration,
            tick_timing="round_end", applied_delta=magnitude,
            base_duration=duration,
        ))
        result.events.append(f"Reward: {stat} {magnitude:+} for {duration} rounds.")
    elif kind == "shop_discount":
        percent = int(reward["percent"])
        # Persistent and additive-capped: several discounts never exceed 50%.
        player.shop_discount_pct = min(50, player.shop_discount_pct + percent)
        result.events.append(f"Reward: {percent}% off in shops "
                             f"(now {player.shop_discount_pct}%).")
    elif kind == "flag":
        player.quest_flags.add(str(reward["flag"]))


def _item_name(content: GameContent, item_id: str) -> str:
    for table in (content.items, content.weapons, getattr(content, "gear_items", {})):
        entry = table.get(item_id)
        if entry is not None:
            return entry.name
    return item_id


# --- display helpers (pure, so both shells share them) -----------------------

def objective_text(content: GameContent, quest: Quest) -> str:
    """One human line describing the goal, e.g. 'Defeat 5 Giant Rat'."""
    objective = quest.objective
    count = objective.count
    if objective.kind == "kill_enemy":
        enemy = content.enemies.get(objective.target)
        return f"Defeat {count} {enemy.name if enemy else objective.target}"
    if objective.kind == "kill_in_zone":
        return f"Defeat {count} foes in {zone_label(objective.target)}"
    if objective.kind == "deliver_item":
        return f"Deliver {count} {_item_name(content, objective.target)}"
    if objective.kind == "visit_place":
        place = content.places.get(objective.target)
        return f"Travel to {place.name if place else objective.target}"
    if objective.kind == "open_chests":
        return f"Open {count} chests"
    return objective.kind


def zone_label(zone: str) -> str:
    return zone.replace("_", " ").title() if zone else ""


def reward_text(content: GameContent, quest: Quest) -> str:
    """Short reward summary for a board row / log row."""
    parts = []
    for reward in quest.rewards:
        kind = str(reward.get("kind", ""))
        if kind == "gold":
            parts.append(f"{int(reward['amount'])} gold")
        elif kind == "xp":
            parts.append(f"{int(reward['amount'])} XP")
        elif kind == "item":
            parts.append(_item_name(content, str(reward["item_id"])))
        elif kind == "unlock_tome":
            parts.append(f"{_item_name(content, str(reward['item_id']))} (learned)")
        elif kind == "shop_discount":
            parts.append(f"{int(reward['percent'])}% shop discount")
        elif kind == "status":
            parts.append(f"{reward.get('stat', '')} boost")
    return ", ".join(parts)


def progress_text(player: Player, content: GameContent, quest: Quest) -> str:
    """'3/5' for counters, '' for a single-step objective that isn't done."""
    if quest.objective.count <= 1:
        return ""
    return f"{objective_progress(player, content, quest)}/{quest.objective.count}"
