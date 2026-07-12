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


# --- gates (v2 archetype corridors, Lucas 2026-07-12) ------------------------
# Archetypes replace the single shared TTK gate. Glass cannons kill fast and
# die fast; the rogue is a sturdier utility+damage dealer; the defensive pair
# (tank/cleric) grind — their cost is time/mana, so their HP-cost floor is
# lower. Mage is treated as a frail caster (glass-cannon corridor).
ARCHETYPE = {
    "fighter": "glass", "hunter": "glass", "mage": "glass",
    "rogue": "rogue", "tank": "defensive", "cleric": "defensive",
}
# archetype -> (ttk_lo, ttk_hi, cost_lo, cost_hi, delta_minus4_ceiling)
CORRIDORS = {
    "glass": (3, 5, 0.20, 0.35, 0.10),      # glass cannons may bottom out ≤10% at Δ−4
    "rogue": (4, 6, 0.20, 0.35, 0.15),
    "defensive": (5, 8, 0.10, 0.25, 0.15),
}


def gate_summary(cells: dict) -> list[str]:
    """Evaluate the v2 archetype-corridor gates against the MEDIAN matrix.
    Returns human-readable PASS/FAIL lines (empty if median missing)."""
    if "median" not in cells:
        return []
    lines = []

    def _check(name, ok, detail):
        lines.append(f"{'PASS' if ok else 'FAIL'}  {name}: {detail}")

    for zone, by_delta in cells["median"].items():
        cainos = zone == "cainos"
        lo, hi = (0.85, 1.0) if cainos else (0.70, 0.90)
        for class_id in CLASSES:
            ttk_lo, ttk_hi, cost_lo, cost_hi, d4_ceiling = CORRIDORS[ARCHETYPE[class_id]]
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
            ttk_ok = med_ttk >= 2 if cainos else ttk_lo <= med_ttk <= ttk_hi
            _check(f"Δ0 TTK {zone}/{class_id}", ttk_ok,
                   f"median TTK {med_ttk:.1f} (corridor {ttk_lo}–{ttk_hi})")
            if not cainos:
                pcts = [c["taken_pct"] for c in row.values() if c["taken_pct"] == c["taken_pct"]]
                med_pct = statistics.median(pcts) if pcts else float("nan")
                _check(f"Δ0 cost {zone}/{class_id}", cost_lo <= med_pct <= cost_hi,
                       f"median cost {med_pct*100:.0f}% HP (corridor {cost_lo*100:.0f}–{cost_hi*100:.0f}%)")
        # Δ+3 (dominant), Δ−2 (contested), Δ−4 (archetype-floored) on the median enemy.
        for class_id in CLASSES:
            _, _, _, _, d4_ceiling = CORRIDORS[ARCHETYPE[class_id]]
            def _med(delta):
                row = by_delta[delta][class_id]
                med = statistics.median(sorted(c["win"] for c in row.values()))
                ttks = [c["ttk"] for c in row.values() if c["ttk"] == c["ttk"]]
                return med, (statistics.median(ttks) if ttks else 99.0)
            w3, t3 = _med(3)
            _check(f"Δ+3 {zone}/{class_id}", w3 >= 0.95 and t3 >= 2,
                   f"win {w3*100:.0f}%, TTK {t3:.1f}")
            w2, _ = _med(-2)
            _check(f"Δ−2 {zone}/{class_id}", 0.35 <= w2 <= 0.60,
                   f"win {w2*100:.0f}% (target 35–60%)")
            w4, _ = _med(-4)
            _check(f"Δ−4 {zone}/{class_id}", w4 <= d4_ceiling,
                   f"win {w4*100:.0f}% (ceiling {d4_ceiling*100:.0f}%)")
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


# --- known residuals (frozen 2026-07-12, post class-identity pass) -----------
# Lucas's decision: the Δ0 on-level gate and its closely-related Δ−2 cells are a
# STRUCTURAL residual, not a bug. At Δ0 the per-class median is pinned high by
# the durable classes (tank/fighter/cleric win on-level almost regardless) while
# the frail worst-case (mage / bad matchup) sinks below the 25% floor; at Δ−2 the
# +2 enemy levels ride HP_GROWTH_PER_LEVEL=0.38 into a base-stat HP ceiling no
# player weapon closes. Measured per enemy by rpg_game/tools/roster_delta0.py.
# The remaining bands (Δ+3 dominant fast-kills, Δ−4 off-level ceiling, the
# default-kit spread) are the progression-pass residuals — documented, accepted;
# cross-class will churn the balance anyway.
#
# The WHOLE current baseline is frozen by exact check name (identical at N=120
# and N=200, captured 2026-07-12) so a NEW regression surfaces as a new fail
# instead of drowning in these 92. A per-gate-type rule would be too coarse — it
# would hide a genuinely new Δ0/Δ−2 fail among the accepted ones. Regenerate with
# tools/delta_curve after an intentional balance change, then re-freeze here.
KNOWN_RESIDUAL_CHECKS: frozenset = frozenset({
    "DEFAULT ≥ median−15pp cleric",
    "DEFAULT ≥ median−15pp fighter",
    "DEFAULT ≥ median−15pp hunter",
    "DEFAULT ≥ median−15pp mage",
    "Δ+3 cainos/cleric",
    "Δ+3 cainos/fighter",
    "Δ+3 cainos/hunter",
    "Δ+3 cainos/mage",
    "Δ+3 cursed_mire/fighter",
    "Δ+3 cursed_mire/hunter",
    "Δ+3 cursed_mire/mage",
    "Δ+3 grave_heath/fighter",
    "Δ+3 grave_heath/hunter",
    "Δ+3 grave_heath/mage",
    "Δ+3 mork_skog/cleric",
    "Δ+3 mork_skog/fighter",
    "Δ+3 mork_skog/hunter",
    "Δ+3 mork_skog/mage",
    "Δ0 TTK cursed_mire/hunter",
    "Δ0 TTK cursed_mire/mage",
    "Δ0 TTK grave_heath/hunter",
    "Δ0 TTK mork_skog/cleric",
    "Δ0 TTK mork_skog/hunter",
    "Δ0 TTK mork_skog/mage",
    "Δ0 cost cursed_mire/cleric",
    "Δ0 cost cursed_mire/hunter",
    "Δ0 cost cursed_mire/mage",
    "Δ0 cost cursed_mire/rogue",
    "Δ0 cost grave_heath/cleric",
    "Δ0 cost grave_heath/hunter",
    "Δ0 cost grave_heath/mage",
    "Δ0 cost grave_heath/rogue",
    "Δ0 cost grave_heath/tank",
    "Δ0 cost mork_skog/cleric",
    "Δ0 cost mork_skog/mage",
    "Δ0 cost mork_skog/rogue",
    "Δ0 cost mork_skog/tank",
    "Δ0 floor cursed_mire/mage",
    "Δ0 floor grave_heath/hunter",
    "Δ0 floor grave_heath/mage",
    "Δ0 floor grave_heath/rogue",
    "Δ0 floor mork_skog/cleric",
    "Δ0 neutral cursed_mire/cleric",
    "Δ0 neutral cursed_mire/fighter",
    "Δ0 neutral cursed_mire/hunter",
    "Δ0 neutral cursed_mire/mage",
    "Δ0 neutral cursed_mire/rogue",
    "Δ0 neutral cursed_mire/tank",
    "Δ0 neutral grave_heath/cleric",
    "Δ0 neutral grave_heath/fighter",
    "Δ0 neutral grave_heath/hunter",
    "Δ0 neutral grave_heath/mage",
    "Δ0 neutral grave_heath/rogue",
    "Δ0 neutral grave_heath/tank",
    "Δ0 neutral mork_skog/cleric",
    "Δ0 neutral mork_skog/fighter",
    "Δ0 neutral mork_skog/hunter",
    "Δ0 neutral mork_skog/mage",
    "Δ0 neutral mork_skog/rogue",
    "Δ0 neutral mork_skog/tank",
    "Δ−2 cainos/cleric",
    "Δ−2 cainos/fighter",
    "Δ−2 cainos/hunter",
    "Δ−2 cainos/rogue",
    "Δ−2 cainos/tank",
    "Δ−2 cursed_mire/cleric",
    "Δ−2 cursed_mire/fighter",
    "Δ−2 cursed_mire/hunter",
    "Δ−2 cursed_mire/mage",
    "Δ−2 cursed_mire/tank",
    "Δ−2 grave_heath/cleric",
    "Δ−2 grave_heath/fighter",
    "Δ−2 grave_heath/hunter",
    "Δ−2 grave_heath/mage",
    "Δ−2 grave_heath/rogue",
    "Δ−2 grave_heath/tank",
    "Δ−2 mork_skog/fighter",
    "Δ−2 mork_skog/hunter",
    "Δ−2 mork_skog/tank",
    "Δ−4 cainos/cleric",
    "Δ−4 cainos/fighter",
    "Δ−4 cainos/hunter",
    "Δ−4 cainos/rogue",
    "Δ−4 cainos/tank",
    "Δ−4 cursed_mire/fighter",
    "Δ−4 cursed_mire/hunter",
    "Δ−4 cursed_mire/tank",
    "Δ−4 grave_heath/fighter",
    "Δ−4 grave_heath/tank",
    "Δ−4 mork_skog/fighter",
    "Δ−4 mork_skog/hunter",
    "Δ−4 mork_skog/tank",
})


def residual_reason(check: str) -> str:
    """The structural cause tag for an accepted residual check name."""
    if check.startswith("Δ0 floor"):
        return "mage/bad-matchup floor: the frail worst-case sinks below 25% on-level"
    if check.startswith("Δ0"):
        return ("durable-median: tank/fighter/cleric pin the on-level median "
                "(cost/TTK ride the same base-stat tank)")
    if check.startswith("Δ−2"):
        return ("delta2 base-stat ceiling: +2 enemy levels ride HP_GROWTH 0.38 "
                "past what a player weapon closes")
    if check.startswith("Δ+3"):
        return "plus3 dominant fast-kill: a +3 player kills below the TTK>=2 floor"
    if check.startswith("Δ−4"):
        return "delta4 off-level ceiling: a -4 player wins above the archetype ceiling"
    if check.startswith("DEFAULT"):
        return "default-kit gap: the no-talent/start-weapon floor trails the median by >15pp"
    return "prep-2026-07-12 residual"


def _gate_name(line: str) -> str:
    """'FAIL  Δ0 neutral mork_skog/tank: ...' -> 'Δ0 neutral mork_skog/tank'."""
    body = line.split(None, 1)[1] if " " in line else line   # drop PASS/FAIL
    return body.split(":", 1)[0].strip()


def classify_gates(gates: list) -> tuple:
    """Split gate FAIL lines into (known_residuals, new_fails). A known residual
    is a FAIL whose check name is in the frozen KNOWN_RESIDUAL_CHECKS baseline;
    every other FAIL is a NEW regression that must stay visible. known_residuals
    is a list of (name, reason)."""
    known, new = [], []
    for line in gates:
        if not line.startswith("FAIL"):
            continue
        name = _gate_name(line)
        if name in KNOWN_RESIDUAL_CHECKS:
            known.append((name, residual_reason(name)))
        else:
            new.append(name)
    return known, new


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
        known, new = classify_gates(gates)
        lines.append(f"\n**{len(known)} known residuals + {len(new)} NEW fails "
                     f"/ {len(gates)} checks**")
        if new:
            lines.append("\n### ⚠ NEW fails — regressions, investigate")
            lines.extend(f"- {n}" for n in new)
        else:
            lines.append("\n_No new fails: every FAIL is a frozen known residual._")
        if known:
            by_reason: dict = {}
            for name, reason in known:
                by_reason.setdefault(reason, []).append(name)
            lines.append("\n### Known residuals (accepted, structural)")
            for reason, names in sorted(by_reason.items()):
                lines.append(f"- **{reason}** ({len(names)}): " + ", ".join(sorted(names)))
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
    gates = gate_summary(cells)
    for line in gates:
        print(line)
    if gates:
        known, new = classify_gates(gates)
        print(f"\n{len(known)} known residuals + {len(new)} NEW fails "
              f"/ {len(gates)} checks")
        for name in new:
            print(f"  NEW: {name}")


if __name__ == "__main__":
    main()
