"""B67 S1: travel events — a rare text choice instead of a wild encounter.

The RULE is core logic: when an encounter slot fires, a seeded roll decides
whether the slot becomes an event instead of a fight (authored chance,
~10% — the total interruption frequency does not increase). Events live in
data (`events.json`: zone, weight, choices -> outcomes) and their outcomes use
EXISTING primitives only: gold, healing, an ActiveStatus buff that lasts into
the next battle, or an encounter. The shell renders the choices as buttons and
applies the returned result; no game rule lives in the presentation.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from rpg_game.core import combat
from rpg_game.core.entities import ActiveStatus, Player


@dataclass(frozen=True)
class TravelEventChoice:
    id: str
    label: str
    cost_gold: int
    outcomes: tuple[dict, ...]


@dataclass(frozen=True)
class TravelEvent:
    id: str
    zone: str
    weight: int
    title: str
    text: str
    choices: tuple[TravelEventChoice, ...]


@dataclass
class TravelEventResult:
    text: str
    gold_delta: int = 0
    healed: int = 0
    start_encounter: bool = False
    buff_stat: str = ""


def parse_events(data: dict) -> tuple[float, tuple[TravelEvent, ...]]:
    """events.json -> (slot chance, events). Outcome chances must sum to 1."""
    events = []
    for row in data.get("events", ()):
        choices = []
        for choice in row["choices"]:
            outcomes = tuple(choice["outcomes"])
            total = sum(float(outcome.get("chance", 0.0)) for outcome in outcomes)
            if abs(total - 1.0) > 1e-9:
                raise ValueError(f"event {row['id']} choice {choice['id']}: outcome chances sum to {total}")
            choices.append(TravelEventChoice(
                id=choice["id"],
                label=choice["label"],
                cost_gold=int(choice.get("cost_gold", 0)),
                outcomes=outcomes,
            ))
        events.append(TravelEvent(
            id=row["id"],
            zone=row["zone"],
            weight=int(row.get("weight", 1)),
            title=row["title"],
            text=row["text"],
            choices=tuple(choices),
        ))
    return float(data.get("event_slot_chance", 0.1)), tuple(events)


def replaces_encounter(slot_chance: float, rng: random.Random) -> bool:
    """One draw per FIRED encounter slot: does the slot become an event?"""
    return rng.random() < slot_chance


def pick_event(events: tuple[TravelEvent, ...], zone: str, rng: random.Random) -> TravelEvent | None:
    """Weighted pick among the zone's events (None if the zone has none)."""
    pool = [event for event in events if event.zone == zone]
    if not pool:
        return None
    total = sum(event.weight for event in pool)
    roll = rng.random() * total
    cumulative = 0.0
    for event in pool:
        cumulative += event.weight
        if roll < cumulative:
            return event
    return pool[-1]


def resolve_choice(player: Player, event: TravelEvent, choice_id: str,
                   rng: random.Random) -> TravelEventResult:
    """Apply a choice's rolled outcome to the player via existing primitives."""
    choice = next(c for c in event.choices if c.id == choice_id)
    if choice.cost_gold > player.gold:
        return TravelEventResult(text="You cannot afford that.")
    player.gold -= choice.cost_gold

    roll = rng.random()
    cumulative = 0.0
    outcome = choice.outcomes[-1]
    for candidate in choice.outcomes:
        cumulative += float(candidate.get("chance", 0.0))
        if roll < cumulative:
            outcome = candidate
            break

    result = TravelEventResult(text=str(outcome.get("text", "")),
                               gold_delta=-choice.cost_gold)
    kind = outcome.get("kind", "nothing")
    if kind == "gold":
        amount = int(outcome["amount"])
        player.gold += amount
        result.gold_delta += amount
    elif kind == "heal":
        before = player.hp
        player.hp = min(combat.effective_max_hp(player), player.hp + int(outcome["amount"]))
        result.healed = player.hp - before
    elif kind == "buff":
        stat = str(outcome["stat"])
        delta = int(outcome["magnitude"])
        duration = int(outcome.get("duration", 3))
        combat.set_stat(player, stat, combat.get_stat(player, stat) + delta)
        player.active_statuses.append(ActiveStatus(
            type="buff", stat=stat, magnitude=delta, duration=duration,
            tick_timing="round_end", applied_delta=delta, base_duration=duration,
        ))
        result.buff_stat = stat
    elif kind == "encounter":
        result.start_encounter = True
    return result
