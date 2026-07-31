"""B135e / B62 economy check: do repeatable bounties become the optimal gold
source? They must not — bounties exist to give grinding DIRECTION, not income.

Two metrics per zone, both measured from the shipped data:

1. PER TARGET KILL — the naive view: a bounty asks for N of species X, and those
   N kills pay their own gold anyway, so the bounty's gold is a bonus on top.
   uplift = bounty_gold / (N * avg_gold_of_that_species).

2. PER FIGHT (the honest view) — a bounty names ONE species, but the wild pool
   serves the whole zone roster, so reaching N kills of X takes roughly
   N / share_of_X fights, and every one of those fights pays gold. This is what
   the player's clock actually sees.
   uplift = bounty_gold / (total gold earned across those fights).

HALT if either uplift means bounty gold beats free grinding (>= 100% would mean
the bounty doubles income; the rail is set far below that).

Run: python3 -m rpg_game.tools.check_bounty_economy
"""

from __future__ import annotations

from rpg_game.core import quests
from rpg_game.core.data_loader import load_content
from rpg_game.core.entities import Player

# Above this, a bounty stops being a bonus and starts being the income strategy.
FAIL_UPLIFT = 1.00
# The design intent: a comfortable bonus, nothing more.
TARGET_UPLIFT = 0.50


def _probe_player(content, level: int) -> Player:
    """A bare player at `level` — only the fields the bounty roll reads."""
    player = Player(
        name="probe", player_class="fighter", level=level, xp=0, xp_required=100,
        hp=1, max_hp=1, base_damage=1, armor=0, speed=1, crit_chance=0, gold=0,
        equipped_weapon_id="", inventory=None, current_place_id="",
        respawn_place_id="",
    )
    return player


def rows(content):
    """(zone, bounty, per-kill uplift, per-fight uplift) for every zone."""
    out = []
    for zone, (low, high) in sorted(content.zone_bands.items(),
                                    key=lambda kv: kv[1][0]):
        roster = content.zone_enemies.get(zone, ())
        if not roster:
            continue
        player = _probe_player(content, low)
        # force the roll onto THIS zone regardless of the probe's level band, and
        # dedupe species the way the real board does
        taken: list[str] = []
        for slot in range(quests.MAX_BOUNTY_SLOTS):
            bounty = quests.generate_bounty(player, content, slot,
                                            tuple(taken), zone=zone)
            if bounty is None:
                continue
            taken.append(bounty.objective.target)
            enemy = content.enemies[bounty.objective.target]
            count = bounty.objective.count
            gold = sum(int(r["amount"]) for r in bounty.rewards
                       if r["kind"] == "gold")
            avg_target = (enemy.gold_min + enemy.gold_max) / 2
            # metric 1: only the target kills count
            per_kill_base = avg_target * count
            # metric 2: every fight on the way counts. A uniform share is the
            # CONSERVATIVE assumption (a rarer target means even more fights and
            # an even smaller uplift).
            share = 1.0 / len(roster)
            fights = count / share
            avg_zone = sum((content.enemies[e].gold_min
                            + content.enemies[e].gold_max) / 2
                           for e in roster) / len(roster)
            per_fight_base = fights * avg_zone
            out.append((zone, (low, high), bounty, count, gold,
                        gold / per_kill_base if per_kill_base else 0.0,
                        gold / per_fight_base if per_fight_base else 0.0))
    return out


def main() -> int:
    content = load_content()
    data = rows(content)
    print(f"BOUNTY_BONUS_FRACTION = {quests.BOUNTY_BONUS_FRACTION}   "
          f"slots = {quests.MAX_BOUNTY_SLOTS}   "
          f"count range = {quests.BOUNTY_MIN_COUNT}-{quests.BOUNTY_MAX_COUNT}")
    print()
    header = (f"{'zone':13} {'band':7} {'target':20} {'N':>2} {'gold':>5} "
              f"{'+/kill':>7} {'+/fight':>8}")
    print(header)
    print("-" * len(header))
    worst_kill = worst_fight = 0.0
    for zone, band, bounty, count, gold, up_kill, up_fight in data:
        print(f"{zone:13} {band[0]:>2}-{band[1]:<4} "
              f"{bounty.objective.target:20} {count:>2} {gold:>5} "
              f"{up_kill * 100:>6.0f}% {up_fight * 100:>7.0f}%")
        worst_kill = max(worst_kill, up_kill)
        worst_fight = max(worst_fight, up_fight)
    print()
    print(f"worst per-target-kill uplift: {worst_kill * 100:.0f}%  "
          f"(target <= {TARGET_UPLIFT * 100:.0f}%, HALT at {FAIL_UPLIFT * 100:.0f}%)")
    print(f"worst per-FIGHT uplift:       {worst_fight * 100:.0f}%  "
          f"<- what the player's clock sees")
    verdict = "PASS" if worst_kill < FAIL_UPLIFT and worst_fight < FAIL_UPLIFT else "HALT"
    print()
    print(f"VERDICT: {verdict} — bounties are a bonus on grinding, not a "
          f"replacement for it." if verdict == "PASS" else
          f"VERDICT: {verdict} — bounties would become the optimal gold source.")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
