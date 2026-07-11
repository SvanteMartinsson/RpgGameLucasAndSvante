"""Delta-curve simulation (progressionspasset, natt 2026-07-11→12).

Lucas's locked difficulty model: difficulty = the LEVEL DELTA (player level −
enemy level), not zone constants. This tool measures winrate / TTK / damage
taken (% of max HP) at Δ ∈ {+3, +1, 0, −2, −4} for all six classes under three
loadout policies, against representative enemies per zone, with the player at
the zone's intended level.

Policies:
- DEFAULT   — the start kit: starting weapon, no talents spent, stock skills.
- MEDIAN    — the gate currency: best SHOP weapon costing ≤ half the modelled
              accumulated gold at that level, greedy (non-optimal) talent
              spend, no tomes. All final gates are expressed against MEDIAN.
- OPTIMIZED — the B102 policy: best equippable weapon anywhere (loot-only
              included), greedy talents, smart skill policy.

Run:
    python3 -m rpg_game.tools.delta_curve --trials 200 --out docs/nightly \
        [--policies median] [--tag before_a]

Outputs a markdown+JSON report and PNG heatmaps tagged with --tag so lever-by-
lever runs can sit side by side. Measure-only: changes no data, no constants.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics

from rpg_game.core import combat, progression, simulation, world
from rpg_game.core.data_loader import load_content
from rpg_game.core.game import GameEngine

CLASSES = ["fighter", "tank", "rogue", "mage", "cleric", "hunter"]
DELTAS = [3, 1, 0, -2, -4]        # Δ = player level − enemy level
POLICIES = ["default", "median", "optimized"]

# Representative enemies per zone (bruiser / caster / weak / signature-DoT),
# player at the zone's intended level (B102's ZONES).
ZONES = {
    "cainos": {"player_level": 3,
               "enemies": ["cave_bear", "goblin_scrapper", "plague_acolyte", "undead"]},
    "mork_skog": {"player_level": 6,
                  "enemies": ["dire_wolf", "goblin_shaman", "razortusk_boar", "treant"]},
    "cursed_mire": {"player_level": 7,
                    "enemies": ["bog_leech", "mire_lurker", "tar_beast", "witchlight"]},
    "grave_heath": {"player_level": 9,
                    "enemies": ["ghoul", "shade", "skeleton_warrior",
                                "hollow_worg", "undead_priest"]},
}

# Which economy zone a player of level k grinds in (matches the geography's
# intended flow: cainos → skog → mire → heath).
def _zone_for_level(k: int) -> int:
    return 1 if k <= 4 else 2 if k <= 6 else 3 if k <= 8 else 4

# Net gold per fight per zone: the B62 N=300 measurement (progression.py).
_NET_GOLD = progression.FAST_TRAVEL_ZONE_NET
_ZONE_BY_INDEX = {1: "cainos", 2: "mork_skog", 3: "cursed_mire", 4: "grave_heath"}


def accumulated_gold(content, level: int) -> float:
    """Modelled gold earned reaching `level`: fights per level (XP requirement /
    the grinding zone's average enemy XP) × the zone's measured net gold/fight."""
    total = 0.0
    for k in range(1, level):
        zone = _zone_for_level(k)
        pool = ZONES[_ZONE_BY_INDEX[zone]]["enemies"]
        avg_xp = statistics.mean(content.enemies[e].xp_reward for e in pool)
        fights = progression.xp_required_for_level(k) / max(1.0, avg_xp)
        total += fights * _NET_GOLD[zone]
    return total


def _shop_weapon_ids(content) -> set[str]:
    ids: set[str] = set()
    for place in content.places.values():
        ids |= set(place.store_inventory)
    return {i for i in ids if i in content.weapons}


def median_weapon_for(content, category: str, level: int, budget: float) -> str | None:
    """Best shop-buyable weapon of `category` the MEDIAN player can equip at
    `level` AND afford with `budget` gold. None -> keep the starting weapon."""
    shop = _shop_weapon_ids(content)
    candidates = [w for w in content.weapons.values()
                  if w.id in shop and w.category == category
                  and combat.weapon_required_level(w) <= level
                  and w.price <= budget]
    if not candidates:
        return None
    return max(candidates, key=lambda w: w.damage_bonus).id


def _class_category(content, class_id: str) -> str:
    return content.weapons[content.classes[class_id].starting_weapon_id].category


def _spend_talents_greedy(engine, points: int) -> None:
    """The audit's greedy branch-order spend — realistic, deliberately not
    optimal (it never respecs or skips to a stronger deep node)."""
    nodes = sorted((n for n in engine.content.talents.values()
                    if n.class_id == engine.player.player_class),
                   key=lambda n: (n.branch, n.order))
    spent = 0
    while spent < points:
        progressed = False
        for node in nodes:
            if spent >= points:
                break
            try:
                engine.player.talent_points += 1
                engine.allocate_talent(node.id)
                spent += 1
                progressed = True
            except ValueError:
                engine.player.talent_points -= 1
        if not progressed:
            break


def _build_player(content, class_id: str, level: int, policy: str, seed: int) -> GameEngine:
    engine = GameEngine(content=content, rng=random.Random(seed))
    engine.start_new_game(f"{class_id.title()} Delta", class_id)
    if level > 1:
        simulation._level_player(engine, level, simulation._DEFAULT_MAIN[class_id])
    category = _class_category(content, class_id)
    weapon_id = None
    if policy == "median":
        budget = accumulated_gold(content, level) / 2
        weapon_id = median_weapon_for(content, category, level, budget)
        _spend_talents_greedy(engine, max(0, level - 1))
        engine._sim_smart_skills = True
    elif policy == "optimized":
        weapon_id = simulation.best_weapon_for(content, category, level)
        _spend_talents_greedy(engine, max(0, level - 1))
        engine._sim_smart_skills = True
    if weapon_id is not None:
        engine.player.owned_weapon_ids = (*engine.player.owned_weapon_ids, weapon_id)
        engine.player.equipped_weapon_id = weapon_id
    engine.player.hp = engine.effective_stat("max_hp")
    engine.player.mana = engine.effective_stat("max_mana")
    return engine


def run_cell(content, class_id: str, enemy_id: str, player_level: int,
             delta: int, policy: str, trials: int, seed: int = 0,
             max_turns: int = 50) -> dict:
    """One (class, enemy, Δ, policy) cell: `trials` seeded fights."""
    enemy_level = max(1, player_level - delta)
    template = content.enemies[enemy_id]
    wins = timeouts = 0
    ttks: list[int] = []
    taken_pcts: list[float] = []
    for index in range(trials):
        engine = _build_player(content, class_id, player_level, policy,
                               seed + index)
        enemy = template.create_enemy()
        world.scale_enemy_to_level(enemy, template.level, enemy_level)
        start_hp = engine.player.hp
        turns = 0
        outcome = "timeout"
        while turns < max_turns:
            turns += 1
            result = simulation._take_turn(engine, enemy, use_skills=True)
            if result.outcome in ("victory", "defeat"):
                outcome = result.outcome
                break
        if outcome == "victory":
            wins += 1
            ttks.append(turns)
            taken_pcts.append((start_hp - engine.player.hp) / start_hp)
        elif outcome == "timeout":
            timeouts += 1
    return {
        "win": wins / trials,
        "timeouts": timeouts,
        "ttk": statistics.mean(ttks) if ttks else float("nan"),
        "taken_pct": statistics.mean(taken_pcts) if taken_pcts else float("nan"),
        "enemy_level": enemy_level,
    }


def run_matrix(content, trials: int, policies=None, zones=None) -> dict:
    """cells[policy][zone][delta][class_id][enemy_id] -> cell dict."""
    out: dict = {}
    for policy in (policies or POLICIES):
        out[policy] = {}
        for zone, spec in ZONES.items():
            if zones and zone not in zones:
                continue
            level = spec["player_level"]
            out[policy][zone] = {}
            for delta in DELTAS:
                grid: dict = {}
                for ci, class_id in enumerate(CLASSES):
                    grid[class_id] = {}
                    for ei, enemy_id in enumerate(spec["enemies"]):
                        cell_seed = 31_000 + ci * 10_000 + ei * 1_000 + delta * 7
                        grid[class_id][enemy_id] = run_cell(
                            content, class_id, enemy_id, level, delta, policy,
                            trials, seed=cell_seed)
                out[policy][zone][delta] = grid
    return out


# --- gates -------------------------------------------------------------------

def gate_summary(cells: dict) -> list[str]:
    """Evaluate Lucas's locked gates against the MEDIAN matrix. Returns a list
    of human-readable PASS/FAIL lines (empty if median missing)."""
    if "median" not in cells:
        return []
    lines = []

    def _check(name, ok, detail):
        lines.append(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

    for zone, by_delta in cells["median"].items():
        cainos = zone == "cainos"
        lo, hi = (0.85, 1.0) if cainos else (0.70, 0.90)
        # Δ0: per class, the median enemy is 'neutral', the worst is the bad matchup.
        for class_id in CLASSES:
            row = by_delta[0][class_id]
            wins = sorted(c["win"] for c in row.values())
            med = statistics.median(wins)
            worst = wins[0]
            _check(f"Δ0 neutral {zone}/{class_id}", lo <= med <= hi,
                   f"median win {med*100:.0f}% (target {lo*100:.0f}–{hi*100:.0f}%)")
            if not cainos:
                _check(f"Δ0 floor {zone}/{class_id}", worst >= 0.25,
                       f"worst matchup {worst*100:.0f}% (floor 25%)")
            ttks = [c["ttk"] for c in row.values() if c["ttk"] == c["ttk"]]
            med_ttk = statistics.median(ttks) if ttks else float("nan")
            ttk_ok = med_ttk >= 2 if cainos else 3 <= med_ttk <= 6
            _check(f"Δ0 TTK {zone}/{class_id}", ttk_ok,
                   f"median TTK {med_ttk:.1f} (target {'≥2' if cainos else '3–6'})")
            if not cainos:
                pcts = [c["taken_pct"] for c in row.values() if c["taken_pct"] == c["taken_pct"]]
                med_pct = statistics.median(pcts) if pcts else float("nan")
                _check(f"Δ0 cost {zone}/{class_id}", 0.20 <= med_pct <= 0.35,
                       f"median cost {med_pct*100:.0f}% HP (target 20–35%)")
        # Δ+3 / Δ−2 / Δ−4 bands on the per-class median enemy.
        for delta, name, check in (
                (3, "Δ+3 win≥95%+TTK≥2",
                 lambda w, t: w >= 0.95 and t >= 2),
                (-2, "Δ−2 win 35–60%", lambda w, t: 0.35 <= w <= 0.60),
                (-4, "Δ−4 win ≤15%", lambda w, t: w <= 0.15)):
            for class_id in CLASSES:
                row = by_delta[delta][class_id]
                med = statistics.median(sorted(c["win"] for c in row.values()))
                ttks = [c["ttk"] for c in row.values() if c["ttk"] == c["ttk"]]
                med_ttk = statistics.median(ttks) if ttks else 99.0
                _check(f"{name} {zone}/{class_id}", check(med, med_ttk),
                       f"median win {med*100:.0f}%, TTK {med_ttk:.1f}")
        # no timeout cells anywhere in this zone
        n_timeout = sum(c["timeouts"] for grid in by_delta.values()
                        for row in grid.values() for c in row.values())
        _check(f"no-timeout {zone}", n_timeout == 0, f"{n_timeout} timed-out fights")

    # policy spread at Δ0 (per class, all zones pooled)
    if {"default", "optimized"} <= set(cells):
        for class_id in CLASSES:
            def _pool(policy):
                vals = []
                for zone in cells[policy]:
                    vals.extend(c["win"] for c in cells[policy][zone][0][class_id].values())
                return statistics.mean(vals) if vals else float("nan")
            med, opt, dflt = _pool("median"), _pool("optimized"), _pool("default")
            _check(f"OPTIMIZED ≤ median+15pp {class_id}", opt - med <= 0.15 + 1e-9,
                   f"opt {opt*100:.0f}% vs med {med*100:.0f}%")
            _check(f"DEFAULT ≥ median−15pp {class_id}", med - dflt <= 0.15 + 1e-9,
                   f"def {dflt*100:.0f}% vs med {med*100:.0f}%")
    return lines


# --- output ------------------------------------------------------------------

def write_outputs(cells: dict, out_dir: str, tag: str, trials: int) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"delta_{tag}.json"), "w") as fh:
        json.dump(cells, fh, indent=1)

    lines = [f"# Delta-curve matrix — {tag} (N={trials}/cell)", ""]
    for policy, zones in cells.items():
        lines.append(f"## policy: {policy}")
        for zone, by_delta in zones.items():
            level = ZONES[zone]["player_level"]
            lines.append(f"### {zone} (player L{level})")
            enemies = ZONES[zone]["enemies"]
            lines.append("| class | Δ | " + " | ".join(enemies) + " |")
            lines.append("|---|---|" + "---|" * len(enemies))
            for class_id in CLASSES:
                for delta in DELTAS:
                    row = by_delta[delta][class_id]
                    cellstr = []
                    for e in enemies:
                        c = row[e]
                        ttk = f"{c['ttk']:.1f}" if c["ttk"] == c["ttk"] else "-"
                        pct = f"{c['taken_pct']*100:.0f}%" if c["taken_pct"] == c["taken_pct"] else "-"
                        to = f" T{c['timeouts']}" if c["timeouts"] else ""
                        cellstr.append(f"{c['win']*100:.0f}% t{ttk} {pct}{to}")
                    lines.append(f"| {class_id} | {delta:+d} | " + " | ".join(cellstr) + " |")
    gates = gate_summary(cells)
    if gates:
        lines.append("\n## Gates (MEDIAN)")
        lines.extend(f"- {g}" for g in gates)
        fails = sum(1 for g in gates if g.startswith("FAIL"))
        lines.append(f"\n**{fails} FAIL / {len(gates)} checks**")
    with open(os.path.join(out_dir, f"delta_{tag}.md"), "w") as fh:
        fh.write("\n".join(lines))


def plot_matrix(cells: dict, out_dir: str, tag: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for policy, zones in cells.items():
        fig, axes = plt.subplots(1, len(zones), figsize=(5.2 * len(zones), 4.6),
                                 squeeze=False)
        for ax, (zone, by_delta) in zip(axes.flat, zones.items()):
            grid = []
            for class_id in CLASSES:
                row = []
                for delta in DELTAS:
                    wins = [c["win"] for c in by_delta[delta][class_id].values()]
                    row.append(statistics.median(wins) * 100)
                grid.append(row)
            im = ax.imshow(grid, vmin=0, vmax=100, cmap="RdYlGn", aspect="auto")
            ax.set_xticks(range(len(DELTAS)), [f"{d:+d}" for d in DELTAS])
            ax.set_yticks(range(len(CLASSES)), CLASSES, fontsize=8)
            for i in range(len(CLASSES)):
                for j in range(len(DELTAS)):
                    ax.text(j, i, f"{grid[i][j]:.0f}", ha="center", va="center", fontsize=8)
            ax.set_title(f"{zone} — median win% ({policy})", fontsize=10)
            ax.set_xlabel("Δ = player − enemy level")
        fig.colorbar(im, ax=axes, shrink=0.75)
        fig.savefig(os.path.join(out_dir, f"delta_{tag}_{policy}.png"), dpi=110)
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=200)
    parser.add_argument("--out", default="docs/nightly")
    parser.add_argument("--tag", default="baseline")
    parser.add_argument("--policies", nargs="*", default=None,
                        choices=POLICIES)
    parser.add_argument("--zones", nargs="*", default=None, choices=list(ZONES))
    args = parser.parse_args()

    content = load_content()
    cells = run_matrix(content, args.trials, policies=args.policies, zones=args.zones)
    write_outputs(cells, args.out, args.tag, args.trials)
    try:
        plot_matrix(cells, args.out, args.tag)
    except ImportError:
        pass
    for line in gate_summary(cells):
        print(line)


if __name__ == "__main__":
    main()
