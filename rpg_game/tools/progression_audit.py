"""B102: progression audit (MEASURE-ONLY — changes no data, no constants).

Produces the numbers behind Lucas's difficulty-curve design round:

a) player curve per class L1-12: HP + empirical sustained DPS with the default
   loadout and a realistically optimised one (best buyable weapon tier +
   talent ranks spent). The L3-4 spike is decomposed into base-stat, weapon
   and talent contributions. (Tome-taught skills are NOT modelled — noted.)
b) enemy curve per zone at the zone band: HP / flat damage after
   ENEMY_HP_MULTIPLIER 2.0 + HP_GROWTH 0.20 + DAMAGE_GROWTH 0.12, plus each
   kit skill's expected magnitude and whether it scales with the rolled level
   (scale=basic_attack/power follows enemy.damage; FLAT magnitudes do not).
c) encounter quality per zone at the intended player level: winrate, TTK
   (rounds to kill), DTK (rounds to be killed at observed incoming damage)
   and damage taken as % of player max HP.

Outputs matplotlib PNGs + a markdown report to --out (default docs/nightly).

Run:
    python3 -m rpg_game.tools.progression_audit --trials 100
"""

from __future__ import annotations

import argparse
import os
import random
from collections import defaultdict

from rpg_game.core import combat, simulation, world
from rpg_game.core.game import GameEngine

CLASSES = ["fighter", "tank", "rogue", "mage", "cleric", "hunter"]
LEVELS = list(range(1, 13))
DPS_WINDOW = 6      # rounds of sustained output measured per seed
DPS_SEEDS = 30

# Zone specs: representative wild places from world.json + the level the
# player is expected to hold when fighting there (band midpoint, rounded).
ZONES = {
    "cainos": {"places": ["burg_54", "burg_379"], "band": (1, 5), "player_level": 3},
    "mork_skog": {"places": ["burg_146"], "band": (4, 9), "player_level": 6},
    "cursed_mire": {"places": ["burg_320"], "band": (5, 10), "player_level": 7},
    "grave_heath": {"places": ["burg_121"], "band": (6, 12), "player_level": 9},
}


def _class_weapon_category(content, class_id):
    starting = content.classes[class_id].starting_weapon_id
    return content.weapons[starting].category


def _spend_talents(engine, points):
    """Spend `points` greedily down the class's branches (rank-ups included),
    skipping nodes blocked by the 4-skill equip cap — a fair 'realistic build'
    without modelling every loadout choice."""
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
    return spent


def _dummy_target(content):
    dummy = content.enemies["giant_rat"].create_enemy()
    dummy.max_hp = dummy.hp = 10 ** 7
    dummy.armor = 0
    dummy.resistances = {}
    dummy.damage = 0
    dummy.action_ids = ("normal",)
    dummy.ai = []
    return dummy


def _build_engine(class_id, level, seed, *, weapon_id=None, talents=False):
    engine = GameEngine(rng=random.Random(seed))
    engine.start_new_game(f"{class_id.title()} Audit", class_id)
    if level > 1:
        simulation._level_player(engine, level, simulation._DEFAULT_MAIN[class_id])
    if weapon_id:
        engine.player.owned_weapon_ids = (*engine.player.owned_weapon_ids, weapon_id)
        engine.player.equipped_weapon_id = weapon_id
    if talents:
        _spend_talents(engine, max(0, level - 1))
        engine._sim_smart_skills = True
    engine.player.hp = engine.effective_stat("max_hp")
    engine.player.mana = engine.effective_stat("max_mana")
    return engine


def measure_dps(class_id, level, *, optimized, content_probe=None):
    """Sustained damage per round over DPS_WINDOW rounds vs an inert dummy,
    averaged over DPS_SEEDS seeds."""
    totals = []
    for seed in range(DPS_SEEDS):
        probe = GameEngine() if content_probe is None else content_probe
        weapon_id = None
        if optimized:
            weapon_id = simulation.best_weapon_for(
                probe.content, _class_weapon_category(probe.content, class_id), level)
        engine = _build_engine(class_id, level, 9000 + seed,
                               weapon_id=weapon_id, talents=optimized)
        dummy = _dummy_target(engine.content)
        for _ in range(DPS_WINDOW):
            simulation._take_turn(engine, dummy, use_skills=True)
            engine.player.hp = engine.effective_stat("max_hp")   # dummy chip damage is noise
        totals.append((dummy.max_hp - dummy.hp) / DPS_WINDOW)
    return sum(totals) / len(totals)


def player_curve(trials_unused=None):
    probe = GameEngine()
    rows = {}
    for class_id in CLASSES:
        hp, dps_def, dps_opt = [], [], []
        for level in LEVELS:
            engine = _build_engine(class_id, level, 1)
            hp.append(engine.effective_stat("max_hp"))
            dps_def.append(measure_dps(class_id, level, optimized=False, content_probe=probe))
            dps_opt.append(measure_dps(class_id, level, optimized=True, content_probe=probe))
        rows[class_id] = {"hp": hp, "dps_default": dps_def, "dps_optimized": dps_opt}
    return rows


def spike_decomposition():
    """L3->L4 optimized-DPS spike split into stats / weapon-tier / talents:
    each variant upgrades ONE component from its L3 state to L4."""
    probe = GameEngine()
    out = {}
    for class_id in CLASSES:
        cat = _class_weapon_category(probe.content, class_id)
        w3 = simulation.best_weapon_for(probe.content, cat, 3)
        w4 = simulation.best_weapon_for(probe.content, cat, 4)

        def dps(level, weapon_id, talent_points):
            totals = []
            for seed in range(DPS_SEEDS):
                engine = _build_engine(class_id, level, 9100 + seed, weapon_id=weapon_id)
                _spend_talents(engine, talent_points)
                engine._sim_smart_skills = True
                dummy = _dummy_target(engine.content)
                for _ in range(DPS_WINDOW):
                    simulation._take_turn(engine, dummy, use_skills=True)
                    engine.player.hp = engine.effective_stat("max_hp")
                totals.append((dummy.max_hp - dummy.hp) / DPS_WINDOW)
            return sum(totals) / len(totals)

        base = dps(3, w3, 2)
        full = dps(4, w4, 3)
        stats_only = dps(4, w3, 2)
        weapon_only = dps(3, w4, 2)
        talent_only = dps(3, w3, 3)
        out[class_id] = {
            "L3": base, "L4": full,
            "stats": stats_only - base,
            "weapon": weapon_only - base,
            "talents": talent_only - base,
        }
    return out


def enemy_curve():
    """Per zone: each pool enemy scaled to the zone band midpoint (x2.0 HP at
    creation + per-level growth), plus kit-skill magnitudes and their scaling."""
    probe = GameEngine()
    content = probe.content
    zones = {}
    for zone, spec in ZONES.items():
        mid = round(sum(spec["band"]) / 2)
        pool = []
        for place_id in spec["places"]:
            pool.extend(content.places[place_id].encounters)
        rows = []
        for enemy_id in sorted(set(pool)):
            template = content.enemies[enemy_id]
            enemy = template.create_enemy()
            rolled = max(min(mid, template.level_max or mid), template.level_min or mid)
            world.scale_enemy_to_level(enemy, template.level, rolled)
            skills = []
            for action_id in enemy.action_ids:
                action = content.actions.get(action_id)
                if action is None or action.kind != "skill":
                    continue
                for effect in action.effects:
                    if effect.type in ("instant_damage", "drain"):
                        expected = combat.round_half_up(enemy.damage * (effect.multiplier or 1.0))
                        skills.append((action.name, f"hit~{expected}", "scales"))
                    elif effect.type == "apply_status" and effect.magnitude:
                        skills.append((action.name, f"{effect.status_type or effect.stat} {effect.magnitude}x{effect.duration}", "FLAT"))
            rows.append({"id": enemy_id, "rolled": rolled, "hp": enemy.max_hp,
                         "damage": enemy.damage, "skills": skills})
        zones[zone] = {"mid": mid, "rows": rows}
    return zones


def encounter_quality(trials):
    """Winrate/TTK/DTK/damage-taken%% per zone at the intended player level.
    Enemy scaled to the zone band midpoint; player carries the best buyable
    weapon for its level (default skills)."""
    probe = GameEngine()
    content = probe.content
    out = {}
    for zone, spec in ZONES.items():
        player_level = spec["player_level"]
        mid = round(sum(spec["band"]) / 2)
        pool = sorted({e for p in spec["places"] for e in content.places[p].encounters})
        matrix = {}
        for class_id in CLASSES:
            cat = _class_weapon_category(content, class_id)
            weapon_id = simulation.best_weapon_for(content, cat, player_level)
            for enemy_id in pool:
                wins = ttks = 0
                dmg_taken = []
                turns_total = 0
                incoming_per_round = []
                for seed in range(trials):
                    engine = _build_engine(class_id, player_level, 4000 + seed,
                                           weapon_id=weapon_id)
                    template = content.enemies[enemy_id]
                    enemy = template.create_enemy()
                    rolled = max(min(mid, template.level_max or mid), template.level_min or mid)
                    world.scale_enemy_to_level(enemy, template.level, rolled)
                    start_hp = engine.player.hp
                    turns = 0
                    outcome = "timeout"
                    while turns < 50:
                        turns += 1
                        result = simulation._take_turn(engine, enemy, use_skills=True)
                        if result.outcome in ("victory", "defeat"):
                            outcome = result.outcome
                            break
                    taken = start_hp - engine.player.hp if outcome == "victory" else start_hp
                    turns_total += turns
                    if turns:
                        incoming_per_round.append(taken / turns)
                    if outcome == "victory":
                        wins += 1
                        ttks += turns
                        dmg_taken.append(taken / start_hp)
                avg_in = sum(incoming_per_round) / len(incoming_per_round) if incoming_per_round else 0
                player_hp = _build_engine(class_id, player_level, 1).effective_stat("max_hp")
                matrix[(class_id, enemy_id)] = {
                    "win": wins / trials,
                    "ttk": ttks / wins if wins else float("nan"),
                    "dtk": (player_hp / avg_in) if avg_in > 0 else float("inf"),
                    "taken_pct": (sum(dmg_taken) / len(dmg_taken)) if dmg_taken else float("nan"),
                }
        out[zone] = {"pool": pool, "player_level": player_level, "matrix": matrix}
    return out


# ---------------------------------------------------------------------------

def _plot_player(rows, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for class_id, data in rows.items():
        axes[0].plot(LEVELS, data["hp"], marker="o", label=class_id)
        axes[1].plot(LEVELS, data["dps_optimized"], marker="o", label=f"{class_id} (opt)")
        axes[1].plot(LEVELS, data["dps_default"], linestyle="--", alpha=0.5,
                     label=f"{class_id} (default)")
    axes[0].set_title("Player max HP per level")
    axes[1].set_title(f"Sustained DPS ({DPS_WINDOW}-round window)")
    for ax in axes:
        ax.set_xlabel("level")
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8)
    axes[1].legend(fontsize=6, ncol=2)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "b102_player_curve.png"), dpi=110)
    plt.close(fig)


def _plot_spike(spike, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 5))
    classes = list(spike)
    stats = [spike[c]["stats"] for c in classes]
    weap = [spike[c]["weapon"] for c in classes]
    tal = [spike[c]["talents"] for c in classes]
    x = range(len(classes))
    ax.bar(x, stats, label="base stats L3->L4")
    ax.bar(x, weap, bottom=stats, label="weapon tier")
    ax.bar(x, tal, bottom=[s + w for s, w in zip(stats, weap)], label="talent point")
    ax.set_xticks(list(x), classes)
    ax.set_title("L3->L4 optimized-DPS spike decomposition (additive one-at-a-time deltas)")
    ax.legend()
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "b102_l34_spike.png"), dpi=110)
    plt.close(fig)


def _plot_enemies(zones, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    for ax, (zone, data) in zip(axes.flat, zones.items()):
        rows = data["rows"]
        names = [r["id"] for r in rows]
        ax.bar(names, [r["hp"] for r in rows], color="#7aa6c2", label="HP (scaled)")
        ax2 = ax.twinx()
        ax2.plot(names, [r["damage"] for r in rows], color="#c25b4e", marker="o", label="flat damage")
        ax.set_title(f"{zone} @ L{data['mid']}")
        ax.tick_params(axis="x", rotation=60, labelsize=7)
        ax.grid(alpha=0.3, axis="y")
    fig.suptitle("Enemy HP + flat damage at zone band midpoint (x2.0 HP, growth applied)")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "b102_enemy_curve.png"), dpi=110)
    plt.close(fig)


def _plot_quality(quality, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    for ax, (zone, data) in zip(axes.flat, quality.items()):
        pool = data["pool"]
        grid = [[data["matrix"][(c, e)]["win"] * 100 for e in pool] for c in CLASSES]
        im = ax.imshow(grid, vmin=0, vmax=100, cmap="RdYlGn", aspect="auto")
        ax.set_xticks(range(len(pool)), pool, rotation=60, fontsize=7)
        ax.set_yticks(range(len(CLASSES)), CLASSES, fontsize=8)
        for i, c in enumerate(CLASSES):
            for j, e in enumerate(pool):
                cell = data["matrix"][(c, e)]
                label = f"{cell['win']*100:.0f}"
                ax.text(j, i, label, ha="center", va="center", fontsize=7)
        ax.set_title(f"{zone}: win% @ player L{data['player_level']}")
    fig.colorbar(im, ax=axes, shrink=0.6, label="win %")
    fig.savefig(os.path.join(out_dir, "b102_encounter_quality.png"), dpi=110)
    plt.close(fig)


def write_report(rows, spike, zones, quality, out_dir):
    lines = ["# B102 progression audit", ""]
    lines.append("## a) Player curve (HP / sustained DPS default -> optimized)")
    for class_id, data in rows.items():
        lines.append(f"### {class_id}")
        lines.append("| L | HP | DPS default | DPS optimized |")
        lines.append("|---|----|-------------|---------------|")
        for i, level in enumerate(LEVELS):
            lines.append(f"| {level} | {data['hp'][i]} | {data['dps_default'][i]:.1f} "
                         f"| {data['dps_optimized'][i]:.1f} |")
    lines.append("\n## L3->L4 spike decomposition (DPS delta per component)")
    lines.append("| class | L3 DPS | L4 DPS | stats | weapon | talents |")
    lines.append("|-------|--------|--------|-------|--------|---------|")
    for c, d in spike.items():
        lines.append(f"| {c} | {d['L3']:.1f} | {d['L4']:.1f} | {d['stats']:+.1f} "
                     f"| {d['weapon']:+.1f} | {d['talents']:+.1f} |")
    lines.append("\n## b) Enemy curve per zone (band midpoint; FLAT effects do not scale with rolled level)")
    for zone, data in zones.items():
        lines.append(f"### {zone} @ L{data['mid']}")
        lines.append("| enemy | HP | flat dmg | kit skills |")
        lines.append("|-------|----|----------|------------|")
        for r in data["rows"]:
            skills = "; ".join(f"{n} {v} [{s}]" for n, v, s in r["skills"]) or "-"
            lines.append(f"| {r['id']} | {r['hp']} | {r['damage']} | {skills} |")
    lines.append("\n## c) Encounter quality (win% / TTK / DTK / damage taken % of max HP)")
    for zone, data in quality.items():
        lines.append(f"### {zone} @ player L{data['player_level']}")
        lines.append("| class | " + " | ".join(data["pool"]) + " |")
        lines.append("|" + "---|" * (len(data["pool"]) + 1))
        for c in CLASSES:
            cells = []
            for e in data["pool"]:
                m = data["matrix"][(c, e)]
                dtk = f"{m['dtk']:.0f}" if m["dtk"] != float("inf") else "inf"
                ttk = f"{m['ttk']:.1f}" if m["ttk"] == m["ttk"] else "-"
                pct = f"{m['taken_pct']*100:.0f}%" if m["taken_pct"] == m["taken_pct"] else "-"
                cells.append(f"{m['win']*100:.0f}% ttk{ttk} dtk{dtk} {pct}")
            lines.append(f"| {c} | " + " | ".join(cells) + " |")
    lines.append("\n*Limitations: tome-taught skills are not part of the optimized loadout; "
                 "'optimized' talents are spent greedily down the branch order.*")
    path = os.path.join(out_dir, "b102_report.md")
    with open(path, "w") as fh:
        fh.write("\n".join(lines))
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--out", default="docs/nightly")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)

    print("player curve...")
    rows = player_curve()
    print("spike decomposition...")
    spike = spike_decomposition()
    print("enemy curve...")
    zones = enemy_curve()
    print("encounter quality...")
    quality = encounter_quality(args.trials)

    _plot_player(rows, args.out)
    _plot_spike(spike, args.out)
    _plot_enemies(zones, args.out)
    _plot_quality(quality, args.out)
    path = write_report(rows, spike, zones, quality, args.out)
    print(f"report: {path}")


if __name__ == "__main__":
    main()
