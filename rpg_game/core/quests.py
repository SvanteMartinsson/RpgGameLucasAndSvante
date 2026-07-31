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
    giver_kind: str                       # "board" | "bounty" | "character" (B139b)
    objective: QuestObjective
    rewards: tuple[dict, ...] = ()
    zone: str = ""                        # hint shown in the log; "" = anywhere
    prereq_quest_ids: tuple[str, ...] = ()
    repeatable: bool = False
    # B139a: chains. A STORY is a chain of separate quests, not stages inside one
    # quest — the player walks back to the giver between parts, and that walking
    # back IS the relationship. `chain_id` groups the parts, `chain_index` is the
    # 1-based position ("Part 2 of 4"), and `next_quest_id` names the part this one
    # unlocks. All optional: a standalone quest sets none of them.
    chain_id: str = ""
    chain_index: int = 0
    next_quest_id: str = ""
    # THE DIRECTOR'S FIELD. A suggestion shown to the player, deliberately NOT a
    # gate: a chain must never block a player from walking where they like, so
    # this only ever renders as a hint. 0 = no suggestion.
    recommended_level: int = 0
    # B139b: the PERSON who gives this quest. Set together with
    # giver_kind="character" (validate_characters enforces the pair). A character
    # quest is offered AT the character, never on the notice board — the board
    # keeps the impersonal work, because stories come from people.
    giver_character_id: str = ""


@dataclass
class QuestTurnInResult:
    ok: bool
    text: str = ""
    events: list[str] = field(default_factory=list)
    gold_gained: int = 0
    xp_gained: int = 0
    levels_gained: int = 0
    items_granted: tuple[str, ...] = ()
    # B139a: set when this turn-in unlocked the next part of a chain, so the shell
    # can jump the player straight to it instead of making them hunt the list.
    next_quest_id: str = ""


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
            # B139a: every chain field defaults to "unset", so a quests.json
            # written before chains existed parses to exactly what it parsed to
            # before — no migration, no version bump.
            chain_id=str(row.get("chain_id", "")),
            chain_index=int(row.get("chain_index", 0)),
            next_quest_id=str(row.get("next_quest_id", "")),
            recommended_level=int(row.get("recommended_level", 0)),
            giver_character_id=str(row.get("giver_character_id", "")),
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
    _validate_chains(by_id)


def _validate_chains(by_id: dict[str, Quest]) -> None:
    """B139a: a chain must be a well-formed line of parts, checked at load.

    A broken chain is worse than a broken single quest: it strands a story
    half-told, and the player has no way to tell that from "the author meant
    that". So every one of these is an error at startup, not a silent miss.
    """
    for quest in by_id.values():
        if quest.recommended_level and quest.recommended_level < 1:
            raise ValueError(f"quest {quest.id} recommended_level must be >= 1")
        if quest.chain_index and not quest.chain_id:
            raise ValueError(f"quest {quest.id} has a chain_index but no chain_id")
        if quest.chain_id and quest.chain_index < 1:
            raise ValueError(f"quest {quest.id} is in chain {quest.chain_id!r} "
                             f"but has no 1-based chain_index")
        if not quest.next_quest_id:
            continue
        if quest.next_quest_id == quest.id:
            raise ValueError(f"quest {quest.id} chains to itself")
        following = by_id.get(quest.next_quest_id)
        if following is None:
            raise ValueError(f"quest {quest.id} chains to unknown quest "
                             f"{quest.next_quest_id!r}")
        # The next part belongs to the SAME story, or "Part 2 of 4" is a lie.
        if quest.chain_id and following.chain_id != quest.chain_id:
            raise ValueError(f"quest {quest.id} (chain {quest.chain_id!r}) chains to "
                             f"{following.id} in chain {following.chain_id!r}")
        if quest.repeatable:
            raise ValueError(f"quest {quest.id} is repeatable AND chains to "
                             f"{following.id} — a story part cannot repeat")

    # One predecessor per part: two quests unlocking the same part would make
    # "which part comes next" ambiguous and the part offer fire twice.
    predecessors: dict[str, str] = {}
    for quest in by_id.values():
        if not quest.next_quest_id:
            continue
        earlier = predecessors.get(quest.next_quest_id)
        if earlier is not None:
            raise ValueError(f"quests {earlier} and {quest.id} both chain to "
                             f"{quest.next_quest_id}")
        predecessors[quest.next_quest_id] = quest.id

    # Unique positions inside a chain, so the part numbering is a real ordering.
    seen_positions: dict[str, dict[int, str]] = {}
    for quest in by_id.values():
        if not quest.chain_id:
            continue
        taken = seen_positions.setdefault(quest.chain_id, {})
        if quest.chain_index in taken:
            raise ValueError(f"chain {quest.chain_id!r} has two part "
                             f"{quest.chain_index}s: {taken[quest.chain_index]} "
                             f"and {quest.id}")
        taken[quest.chain_index] = quest.id

    _reject_chain_cycles(by_id)


def _reject_chain_cycles(by_id: dict[str, Quest]) -> None:
    """A next_quest_id loop would make a story that never ends."""
    state: dict[str, int] = {}

    def walk(quest_id: str, trail: tuple[str, ...]) -> None:
        mark = state.get(quest_id, 0)
        if mark == 1:
            raise ValueError("quest chain cycle: " + " -> ".join((*trail, quest_id)))
        if mark == 2:
            return
        state[quest_id] = 1
        following = by_id[quest_id].next_quest_id
        if following and following in by_id:
            walk(following, (*trail, quest_id))
        state[quest_id] = 2

    for quest_id in by_id:
        walk(quest_id, ())


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


def prereqs_met(player: Player, quest: Quest, all_quests=()) -> bool:
    """Whether this quest's prerequisites are satisfied.

    B139a: `next_quest_id` IS the chain's ordering — a part is not offered until
    the part that names it has been handed in. That makes one field the single
    source of truth: an author writes the chain forwards once, instead of also
    repeating it backwards in every part's prereq_quest_ids where the two could
    silently disagree. Pass `all_quests` so the predecessor can be found; without
    it only the explicit prereqs are checked.
    """
    if not all(status_of(player, required) == TURNED_IN
               for required in quest.prereq_quest_ids):
        return False
    earlier = chain_predecessor(all_quests, quest)
    return earlier is None or status_of(player, earlier.id) == TURNED_IN


def is_offerable(player: Player, quest: Quest, all_quests=()) -> bool:
    """Shown on a board: never accepted (or repeatable and handed in) + prereqs."""
    status = status_of(player, quest.id)
    if not prereqs_met(player, quest, all_quests):
        return False
    if status == AVAILABLE:
        return True
    return quest.repeatable and status == TURNED_IN


def offerable_quests(player: Player, quests, giver_kind: str = "") -> list[Quest]:
    return [quest for quest in quests
            if (not giver_kind or quest.giver_kind == giver_kind)
            and is_offerable(player, quest, quests)]


# --- B139a: chains ------------------------------------------------------------
# Every chain question below is DERIVED from the quest statuses that already
# persist. No new player field, no save migration: "part 3 is waiting for you" is
# just "part 2 is turned_in and part 3 is still available".

def chain_parts(quests, chain_id: str) -> list[Quest]:
    """Every part of a chain, in story order."""
    if not chain_id:
        return []
    return sorted((q for q in quests if q.chain_id == chain_id),
                  key=lambda q: q.chain_index)


def chain_part_text(quests, quest: Quest) -> str:
    """'Part 2 of 4' for a chained quest, '' for a standalone one."""
    if not quest.chain_id or not quest.chain_index:
        return ""
    total = len(chain_parts(quests, quest.chain_id))
    return f"Part {quest.chain_index} of {total}" if total else ""


def chain_predecessor(quests, quest: Quest) -> "Quest | None":
    """The part that unlocks this one (None for a first part / standalone)."""
    return next((q for q in quests if q.next_quest_id and q.next_quest_id == quest.id),
                None)


def chain_next(quests, quest: Quest) -> "Quest | None":
    """The part this one unlocks, if it names one and it exists."""
    if not quest.next_quest_id:
        return None
    return next((q for q in quests if q.id == quest.next_quest_id), None)


def is_new_chain_offer(player: Player, quests, quest: Quest) -> bool:
    """Whether this quest is a chain continuation WAITING to be picked up.

    True exactly while its predecessor is handed in and this part has not been
    accepted yet. That is what the UI marks: a continuation must be ANNOUNCED,
    never quietly appear among the ordinary notices — the whole point of chains is
    that the player comes back for the next part on purpose.
    """
    if not is_offerable(player, quest, quests):
        return False
    earlier = chain_predecessor(quests, quest)
    return earlier is not None and status_of(player, earlier.id) == TURNED_IN


def new_chain_offers(player: Player, quests, giver_kind: str = "") -> list[Quest]:
    """Every chain continuation currently waiting to be picked up."""
    return [quest for quest in quests
            if (not giver_kind or quest.giver_kind == giver_kind)
            and is_new_chain_offer(player, quests, quest)]


def recommended_level_text(quest: Quest) -> str:
    """The director's hint. Never a gate — see Quest.recommended_level."""
    return f"Recommended level {quest.recommended_level}" if quest.recommended_level else ""


def is_below_recommended_level(player: Player, quest: Quest) -> bool:
    """Whether to render the hint as a WARNING. Still never blocks anything."""
    return bool(quest.recommended_level) and player.level < quest.recommended_level


def tracked_quests(player: Player, quests) -> list[Quest]:
    """Active + completed-but-not-handed-in, i.e. what the quest log lists."""
    return [quest for quest in quests
            if status_of(player, quest.id) in (ACTIVE, COMPLETED)]


def accept(player: Player, quest: Quest, all_quests=()) -> bool:
    """Take the quest. Repeating a turned-in quest resets its progress.

    The chain order is enforced HERE too, not only in the board listing: a UI bug
    (or a hand-edited save) must not be able to start part 3 before part 2.
    """
    if not is_offerable(player, quest, all_quests):
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
    # B139a: a chain continuation is ANNOUNCED. Handing in part 2 must not leave
    # part 3 to be discovered by chance in a list — the offer is the reason to walk
    # back, so it gets its own line. Rewards are stored before this so the
    # announcement is the LAST thing the player reads.
    following = chain_next(content.quests, quest)
    if following is not None and status_of(player, following.id) == AVAILABLE:
        result.next_quest_id = following.id
        result.events.append(f"The story continues: {following.title}.")
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


# --- B135e: the repeatable bounty board --------------------------------------
# Bounties are GENERATED, not authored: each slot rolls a species out of the
# player's current zone and asks for N of them. They exist so grinding has a
# direction, NOT as an income source — see BOUNTY_BONUS_FRACTION.

MAX_BOUNTY_SLOTS = 3          # how many bounties hang on the board at once
BOUNTY_MIN_COUNT = 3
BOUNTY_MAX_COUNT = 6

# B62 ECONOMY RAIL. A bounty's gold is a FRACTION of what its own kills already
# pay: clearing N enemies earns N * avg_kill_gold anyway, and the bounty adds
# this much on top. Well under 1.0, so per-kill income while on a bounty can
# never beat free grinding by much — and because a bounty names ONE species, the
# player spends extra time finding it, which eats even this margin. The authored
# one-shot quests may pay richer precisely because they cannot be repeated.
BOUNTY_BONUS_FRACTION = 0.35
BOUNTY_XP_FRACTION = 0.35


def bounty_zone_for(player: Player, content: GameContent) -> str:
    """The zone a bounty should be rolled from: the one whose level band contains
    the player's level, else the closest band below (so a high-level player still
    gets the toughest zone rather than nothing)."""
    bands = getattr(content, "zone_bands", {}) or {}
    if not bands:
        return ""
    fitting = [zone for zone, (low, high) in bands.items()
               if low <= player.level <= high]
    if fitting:
        return sorted(fitting, key=lambda z: bands[z][0])[0]
    below = [zone for zone, (low, _high) in bands.items() if low <= player.level]
    if below:
        return sorted(below, key=lambda z: bands[z][0])[-1]
    return sorted(bands, key=lambda z: bands[z][0])[0]


def _bounty_rng(zone: str, slot: int, roll: int) -> "random.Random":
    """A dedicated deterministic stream per (zone, slot, roll).

    Deliberately NOT the engine rng: rolling a bounty must not consume draws from
    the stream that drives encounters/loot/the map (CLAUDE.md determinism rule).
    A string seed is stable across runs and platforms."""
    import random
    return random.Random(f"bounty|{zone}|{slot}|{roll}")


def bounty_roll_count(player: Player, slot: int) -> int:
    return int((player.bounty_rolls or {}).get(str(slot), 0))


def generate_bounty(player: Player, content: GameContent, slot: int,
                    taken: tuple[str, ...] = (), zone: str = "") -> Quest | None:
    """Roll slot `slot`'s current bounty. Deterministic: the same player state
    always yields the same bounty, and handing one in bumps only that slot's
    counter, which rerolls only that slot. `taken` lists species already posted in
    earlier slots — the draw walks on until it finds a distinct one, so the board
    never shows the same beast twice (still deterministic: it is the same stream).
    `zone` overrides the level-derived zone (used by the economy check tool)."""
    zone = zone or bounty_zone_for(player, content)
    roster = (getattr(content, "zone_enemies", {}) or {}).get(zone, ())
    if not roster:
        return None
    roll = bounty_roll_count(player, slot)
    rng = _bounty_rng(zone, slot, roll)
    # The SPECIES advances by rotation: a seeded starting offset per slot, then
    # +1 per hand-in. This makes "the slot never re-posts what it just paid out"
    # true BY CONSTRUCTION (no repeat while the roster has >1 entry) instead of
    # relying on a redraw loop, and the board eventually cycles the whole roster.
    # The count and therefore the reward still roll per hand-in.
    base = _bounty_rng(zone, slot, 0).randrange(len(roster))
    index = (base + roll) % len(roster)
    for _ in range(len(roster)):          # keep the slots on distinct species
        if roster[index] not in taken:
            break
        index = (index + 1) % len(roster)
    enemy_id = roster[index]
    enemy = content.enemies[enemy_id]
    count = rng.randint(BOUNTY_MIN_COUNT, BOUNTY_MAX_COUNT)
    avg_gold = (enemy.gold_min + enemy.gold_max) / 2
    gold = max(1, progression.round_half_up(avg_gold * count * BOUNTY_BONUS_FRACTION))
    xp = max(1, progression.round_half_up(enemy.xp_reward * count * BOUNTY_XP_FRACTION))
    return Quest(
        id=f"bounty_{slot}",
        title=f"Bounty: {enemy.name}",
        text=(f"The board carries a standing price on {enemy.name.lower()}s in "
              f"{zone_label(zone)}. Bring proof of {count} and the clerk pays "
              f"without asking questions."),
        giver_kind="bounty",
        objective=QuestObjective(kind="kill_enemy", target=enemy_id, count=count),
        rewards=({"kind": "gold", "amount": gold}, {"kind": "xp", "amount": xp}),
        zone=zone,
        repeatable=True,
    )


def bounty_board(player: Player, content: GameContent) -> tuple[Quest, ...]:
    """The bounties currently on offer — at most MAX_BOUNTY_SLOTS, all distinct
    species. A bounty the player has ACCEPTED keeps its posted species (its state
    is keyed on the slot), so the board is stable while you work on it."""
    out: list[Quest] = []
    taken: list[str] = []
    for slot in range(MAX_BOUNTY_SLOTS):
        bounty = generate_bounty(player, content, slot, tuple(taken))
        if bounty is not None:
            out.append(bounty)
            taken.append(bounty.objective.target)
    return tuple(out)


def reroll_bounty(player: Player, slot: int) -> None:
    """Bump one slot's counter so its next bounty is a fresh roll."""
    rolls = dict(player.bounty_rolls or {})
    rolls[str(slot)] = bounty_roll_count(player, slot) + 1
    player.bounty_rolls = rolls
    # A rerolled slot starts clean: the old bounty's state must not carry over.
    player.quest_states.pop(f"bounty_{slot}", None)


def slot_of_bounty(quest_id: str) -> int | None:
    if not quest_id.startswith("bounty_"):
        return None
    try:
        return int(quest_id.split("_", 1)[1])
    except ValueError:
        return None


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
