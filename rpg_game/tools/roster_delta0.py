"""Per-enemy on-level (Δ0) measurement across the whole wild roster.

Written for the enemy base-damage pass (2026-07-12 kväll). For every non-boss
wild enemy it sets player_level = the enemy's geo-band midpoint and scales the
enemy to that same level (Δ0), then runs the MEDIAN loadout policy across all
six classes and reports median / worst-class winrate, median TTK and cost-%HP.

It is the instrument behind the pass's STEG 0 finding: at Δ0 the per-class
median winrate is pinned high by the durable classes (tank/fighter/cleric win
on-level almost regardless), while the worst-class floor is the MAGE (low sim
single-target DPS + glass-cannon HP). So the on-level winrate gate cannot be
moved into 70-90% by enemy base-damage alone — every raise that would lower a
durable class first craters the mage and pushes Δ−2 below its floor. Closing
Δ0 is therefore class-side work, not an enemy-roster pass.

Run:
    python3 -m rpg_game.tools.roster_delta0 --trials 120
"""

from __future__ import annotations

import argparse
import statistics

from rpg_game.core import simulation, world
from rpg_game.core.data_loader import load_content
from rpg_game.tools import delta_curve as dc


def _zone_of(rect) -> str:
    cx = (rect[0] + rect[2]) // 2
    cy = (rect[1] + rect[3]) // 2
    if cy >= 100:
        return "grave_heath"
    if cx <= 82:
        return "cainos"
    if cx <= 158:
        return "mork_skog"
    return "cursed_mire"


def enemy_bands(content):
    """enemy_id -> (zone, (band_lo, band_hi)) unioned over its spawn areas."""
    band: dict = {}
    zone: dict = {}
    for area in content.spawn_areas:
        z = _zone_of(area.rect)
        for enemy_id, _w in area.enemies:
            zone.setdefault(enemy_id, z)
            if enemy_id in band:
                band[enemy_id] = (min(band[enemy_id][0], area.level_min),
                                  max(band[enemy_id][1], area.level_max))
            else:
                band[enemy_id] = (area.level_min, area.level_max)
    return {e: (zone[e], band[e]) for e in band}


def measure_cell(content, class_id, enemy_id, level, trials, seed):
    template = content.enemies[enemy_id]
    wins = 0
    ttks: list = []
    costs: list = []
    for i in range(trials):
        engine = dc._build_player(content, class_id, level, "median", seed + i)
        enemy = template.create_enemy()
        world.scale_enemy_to_level(enemy, template.level, level)
        start = engine.player.hp
        turns = 0
        outcome = "timeout"
        while turns < 50:
            turns += 1
            result = simulation._take_turn(engine, enemy, use_skills=True)
            if result.outcome in ("victory", "defeat"):
                outcome = result.outcome
                break
        if outcome == "victory":
            wins += 1
            ttks.append(turns)
            costs.append((start - engine.player.hp) / start)
    return {"win": wins / trials,
            "ttk": statistics.mean(ttks) if ttks else float("nan"),
            "cost": statistics.mean(costs) if costs else float("nan")}


def run(trials=120):
    content = load_content()
    bands = enemy_bands(content)
    rows = []
    for enemy_id in sorted(bands):
        template = content.enemies[enemy_id]
        if getattr(template, "boss", False):
            continue
        zone, (lo, hi) = bands[enemy_id]
        level = round((lo + hi) / 2)
        per = {c: measure_cell(content, c, enemy_id, level, trials, 7000 + i * 137)
               for i, c in enumerate(dc.CLASSES)}
        wins = [per[c]["win"] for c in dc.CLASSES]
        ttks = [per[c]["ttk"] for c in dc.CLASSES if per[c]["ttk"] == per[c]["ttk"]]
        costs = [per[c]["cost"] for c in dc.CLASSES if per[c]["cost"] == per[c]["cost"]]
        worst_class = min(dc.CLASSES, key=lambda c: per[c]["win"])
        rows.append((enemy_id, zone, level, statistics.median(wins), min(wins),
                     worst_class, statistics.median(ttks) if ttks else float("nan"),
                     statistics.median(costs) if costs else float("nan")))
    rows.sort(key=lambda r: -r[3])
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=120)
    args = parser.parse_args()
    rows = run(args.trials)
    print(f"{'enemy':20s} {'zone':12s} {'@L':3s} {'medW':5s} {'worst':5s} "
          f"{'floorClass':10s} {'TTK':5s} cost%")
    for eid, zone, lvl, mw, wo, wc, ttk, cost in rows:
        print(f"{eid:20s} {zone:12s} {lvl:3d} {mw*100:4.0f}% {wo*100:4.0f}% "
              f"{wc:10s} {ttk:5.1f} {cost*100:4.0f}%")


if __name__ == "__main__":
    main()
