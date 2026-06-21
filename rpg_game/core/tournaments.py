"""Tournament progression and rewards.

Tournaments are authored as ordered opponent series. The presentation layer owns
the loop that runs each fight, while this module validates access and pays the
final reward only after the full series is cleared.
"""

from __future__ import annotations

from dataclasses import dataclass

from rpg_game.core import equipment
from rpg_game.core.entities import GameContent, Player, Tournament


@dataclass(frozen=True)
class TournamentStartResult:
    success: bool
    message: str
    tournament: Tournament | None = None


@dataclass(frozen=True)
class TournamentRewardResult:
    success: bool
    message: str
    gold_gained: int = 0
    item_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class TournamentIntermissionResult:
    message: str
    player_hp: int
    player_mana: int


def available_tournaments(player: Player, content: GameContent) -> list[Tournament]:
    return [
        tournament
        for tournament in content.tournaments.values()
        if tournament.place_id == player.current_place_id
    ]


def start_tournament(player: Player, content: GameContent, tournament_id: str) -> TournamentStartResult:
    tournament = content.tournaments.get(tournament_id)
    if tournament is None:
        return TournamentStartResult(False, f"Unknown tournament: {tournament_id}.")
    if tournament.place_id != player.current_place_id:
        return TournamentStartResult(False, f"{tournament.name} is not held here.")
    if not tournament.repeatable and tournament.id in player.completed_tournament_ids:
        return TournamentStartResult(False, f"{tournament.name} has already been cleared.")
    if player.gold < tournament.entry_fee:
        return TournamentStartResult(False, f"{tournament.name} requires {tournament.entry_fee} gold to enter.")
    if tournament.entry_fee:
        player.gold -= tournament.entry_fee
    return TournamentStartResult(True, f"Entered {tournament.name}.", tournament)


def complete_tournament(player: Player, content: GameContent, tournament: Tournament) -> TournamentRewardResult:
    if not tournament.repeatable and tournament.id in player.completed_tournament_ids:
        return TournamentRewardResult(False, f"{tournament.name} has already been rewarded.")

    player.gold += tournament.reward.gold
    awarded_items = []
    for item_id in tournament.reward.item_ids:
        if item_id in content.weapons:
            if item_id not in player.owned_weapon_ids:
                player.owned_weapon_ids = (*player.owned_weapon_ids, item_id)
            awarded_items.append(item_id)
        elif item_id in content.items:
            player.inventory.add_consumable(item_id)
            awarded_items.append(item_id)
        else:
            raise ValueError(f"unknown tournament reward item: {item_id}")

    if not tournament.repeatable:
        player.completed_tournament_ids.add(tournament.id)

    reward_bits = []
    if tournament.reward.gold:
        reward_bits.append(f"{tournament.reward.gold} gold")
    reward_bits.extend(content.weapons[item_id].name if item_id in content.weapons else content.items[item_id].name for item_id in awarded_items)
    reward_text = ", ".join(reward_bits) if reward_bits else "no reward"
    return TournamentRewardResult(
        True,
        f"Cleared {tournament.name}. Reward: {reward_text}.",
        gold_gained=tournament.reward.gold,
        item_ids=tuple(awarded_items),
    )


def recover_between_matches(player: Player) -> TournamentIntermissionResult:
    player.hp = equipment.effective_stat(player, "max_hp")
    player.mana = equipment.effective_stat(player, "max_mana")
    return TournamentIntermissionResult(
        "Tournament intermission: recovered to full HP and mana.",
        player_hp=player.hp,
        player_mana=player.mana,
    )
