"""Deterministic combat simulations for tuning.

The simulator uses the public `GameEngine` combat API and seeded RNG. It is not
part of normal gameplay; it exists to turn balance questions into repeatable
numbers before manual playtesting.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from rpg_game.core import combat, progression
from rpg_game.core.game import GameEngine


# Per-class main stat the leveled-sim spends level-ups on (B35). Casters take Mana
# so a mana-mage is measured with the resource its skills need.
_DEFAULT_MAIN = {
    "fighter": "damage", "tank": "hp", "rogue": "damage",
    "mage": "wisdom", "cleric": "wisdom", "hunter": "damage",
}


def _offensive_multiplier(action) -> float:
    """Crude 'how hard does this hit' score: the biggest damage multiplier among
    a skill's instant_damage/drain effects (0 for pure buffs/heals/DoTs)."""
    best = 0.0
    for effect in action.effects:
        if effect.type in ("instant_damage", "drain"):
            best = max(best, effect.multiplier or 1.0)
    return best


def _is_enemy_dot(skill) -> bool:
    return any(effect.type == "apply_status"
               and (effect.status_type in combat.DAMAGE_TYPES
                    or (effect.tag or "") in combat.DAMAGE_TYPES)
               and effect.target != "self"
               for effect in skill.effects)


def _is_self_status(skill) -> bool:
    return any(effect.type == "apply_status" and effect.target == "self"
               for effect in skill.effects)


def _choose_skill(engine: GameEngine, enemy=None, smart: bool = False):
    """Skill policy: the highest-hitting equipped offensive skill the player can
    currently afford (mana). Cooldown/weapon gating is enforced by the engine — a
    blocked cast falls back to a basic attack in _take_turn. None -> just attack.

    B95 (`smart`, used by build sims): a DoT the target does not already suffer
    is cast first, then a self-status (buff/reflect/regen) the player does not
    already carry — both score 0 on the burst scale, so builds that took those
    branches would otherwise never cast their signature skills. The default
    policy is unchanged (default loadouts have no such skills)."""
    player = engine.player
    if smart and enemy is not None:
        for skill in engine.equipped_skills():
            if skill.mana_cost > player.mana:
                continue
            if _is_enemy_dot(skill) and not combat.action_reapplies_active_dot(skill, enemy):
                return skill
        for skill in engine.equipped_skills():
            if skill.mana_cost > player.mana or not _is_self_status(skill):
                continue
            applied_types = {e.status_type for e in skill.effects if e.type == "apply_status"}
            if not any(status.type in applied_types for status in player.active_statuses):
                return skill
    best, best_score = None, 0.0
    for skill in engine.equipped_skills():
        score = _offensive_multiplier(skill)
        if score <= 0.0 or skill.mana_cost > player.mana:
            continue
        if score > best_score:
            best, best_score = skill, score
    return best


def _take_turn(engine: GameEngine, enemy, use_skills: bool):
    """One player turn. Attack-only by default; with use_skills, cast the best
    affordable skill (falling back to attack if the engine blocks it)."""
    if use_skills:
        skill = _choose_skill(engine, enemy, smart=getattr(engine, "_sim_smart_skills", False))
        if skill is not None:
            result = engine.run_combat_turn(enemy, skill.id)
            if result.outcome != "blocked":   # blocked = mana/cooldown/weapon: no-op, retry
                return result
    return engine.run_combat_turn(enemy, "attack")


def best_weapon_for(content, category: str, level: int, damage_type: str | None = None):
    """Highest-damage weapon of `category` the player could equip at `level`
    (B37 weapon-aware sim). Models a player who upgrades as soon as the equip
    gate allows. Returns a weapon id, or None if nothing qualifies."""
    candidates = [
        w for w in content.weapons.values()
        if w.category == category
        and combat.weapon_required_level(w) <= level
        and (damage_type is None or w.damage_type == damage_type)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda w: w.damage_bonus).id


def _level_player(engine: GameEngine, level: int, main_stat: str) -> None:
    """Grow the simulated player to `level` via the real B35 path, spending every
    level-up on `main_stat`. No game-logic change — uses the public engine API."""
    while engine.player.level < level:
        engine.player.xp = 0  # award exactly one level's worth, deterministically
        progression.award_xp(engine.player, engine.player.xp_required)
        while engine.player.pending_stat_choices > 0:
            engine.apply_stat_choice(main_stat)


@dataclass(frozen=True)
class FightSimulation:
    class_id: str
    enemy_id: str
    seed: int
    outcome: str
    turns: int
    player_hp: int
    player_max_hp: int
    enemy_hp: int
    enemy_max_hp: int


@dataclass(frozen=True)
class MatchupSimulation:
    class_id: str
    enemy_id: str
    trials: int
    victories: int
    defeats: int
    timeouts: int
    average_turns: float
    average_victory_hp: float
    average_enemy_hp_on_loss: float

    @property
    def win_rate(self) -> float:
        return self.victories / self.trials if self.trials else 0.0


def simulate_fight(
    class_id: str,
    enemy_id: str,
    *,
    seed: int = 0,
    max_turns: int = 50,
    use_skills: bool = False,
    level: int = 1,
    main_stat: str | None = None,
    weapon_id: str | None = None,
    talent_plan: tuple[str, ...] = (),
    equip_skill_ids: tuple[str, ...] = (),
) -> FightSimulation:
    """Run one fight and return a compact result. Defaults reproduce the old
    attack-only L1 fight exactly; use_skills lets the player cast skills (mana +
    cooldown aware), level>1 grows it via the B35 level-up path, and weapon_id
    equips a specific weapon (B37 weapon-aware curve). B95: talent_plan spends
    one granted point per entry (repeat a node id to rank it up) and
    equip_skill_ids swaps the equipped loadout, so branch builds can be
    compared head-to-head."""
    engine = GameEngine(rng=random.Random(seed))
    engine.start_new_game(f"{class_id.title()} Sim", class_id)
    if weapon_id is not None:
        engine.player.owned_weapon_ids = (*engine.player.owned_weapon_ids, weapon_id)
        engine.player.equipped_weapon_id = weapon_id
    if level > 1:
        _level_player(engine, level, main_stat or _DEFAULT_MAIN.get(class_id, "damage"))
    for node_id in talent_plan:
        engine.player.talent_points += 1
        engine.allocate_talent(node_id)
    for skill_id in equip_skill_ids:
        if skill_id not in engine.player.equipped_skill_ids:
            engine.equip_skill(skill_id)
    if talent_plan or equip_skill_ids:
        engine._sim_smart_skills = True   # build sims use the B95 smart policy
    if level > 1 or talent_plan:
        engine.player.hp = engine.effective_stat("max_hp")    # start the fight full
        engine.player.mana = engine.effective_stat("max_mana")
    enemy = engine.content.enemies[enemy_id].create_enemy()

    outcome = "timeout"
    turns = 0
    while turns < max_turns and outcome == "timeout":
        turns += 1
        result = _take_turn(engine, enemy, use_skills)
        if result.outcome in {"victory", "defeat"}:
            outcome = result.outcome
            break
        outcome = "timeout"

    return FightSimulation(
        class_id=class_id,
        enemy_id=enemy_id,
        seed=seed,
        outcome=outcome,
        turns=turns,
        player_hp=engine.player.hp,
        player_max_hp=engine.player.max_hp,
        enemy_hp=enemy.hp,
        enemy_max_hp=enemy.max_hp,
    )


def simulate_matchup(
    class_id: str,
    enemy_id: str,
    *,
    trials: int = 100,
    seed: int = 0,
    max_turns: int = 50,
    use_skills: bool = False,
    level: int = 1,
    main_stat: str | None = None,
    weapon_id: str | None = None,
    talent_plan: tuple[str, ...] = (),
    equip_skill_ids: tuple[str, ...] = (),
) -> MatchupSimulation:
    """Run many seeded fights for one class/enemy matchup."""
    fights = [
        simulate_fight(class_id, enemy_id, seed=seed + index, max_turns=max_turns,
                       use_skills=use_skills, level=level, main_stat=main_stat,
                       weapon_id=weapon_id, talent_plan=talent_plan,
                       equip_skill_ids=equip_skill_ids)
        for index in range(trials)
    ]
    victories = [fight for fight in fights if fight.outcome == "victory"]
    defeats = [fight for fight in fights if fight.outcome == "defeat"]
    timeouts = [fight for fight in fights if fight.outcome == "timeout"]
    return MatchupSimulation(
        class_id=class_id,
        enemy_id=enemy_id,
        trials=trials,
        victories=len(victories),
        defeats=len(defeats),
        timeouts=len(timeouts),
        average_turns=_average(fight.turns for fight in fights),
        average_victory_hp=_average(fight.player_hp for fight in victories),
        average_enemy_hp_on_loss=_average(fight.enemy_hp for fight in defeats),
    )


def simulate_matrix(
    class_ids: list[str],
    enemy_ids: list[str],
    *,
    trials: int = 100,
    seed: int = 0,
    max_turns: int = 50,
    use_skills: bool = False,
    level: int = 1,
    main_stat: str | None = None,
    weapon_id: str | None = None,
) -> list[MatchupSimulation]:
    """Run a class-by-enemy matrix with stable per-cell seeds."""
    results = []
    for class_index, class_id in enumerate(class_ids):
        for enemy_index, enemy_id in enumerate(enemy_ids):
            cell_seed = seed + class_index * 10_000 + enemy_index * 1_000
            results.append(
                simulate_matchup(
                    class_id,
                    enemy_id,
                    trials=trials,
                    seed=cell_seed,
                    max_turns=max_turns,
                    use_skills=use_skills,
                    level=level,
                    main_stat=main_stat,
                    weapon_id=weapon_id,
                )
            )
    return results


def _average(values) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


# --- B62: economy / loot-flow measurement ------------------------------------
# A MEASURING harness, no balance rules: N seeded wild fights per zone band via
# the REAL spawn path (world.create_encounter incl. rare rolls), reporting gold
# in (kills + sell value of drops), drop rates per rarity, material inflow, and
# the rest-cost pressure (damage taken -> fights per rest -> gold out per fight).

@dataclass(frozen=True)
class EconomyBandReport:
    class_id: str
    place_id: str
    level: int
    trials: int
    win_rate: float
    average_turns: float
    average_kill_gold: float        # gold per VICTORIOUS fight from the kill
    average_sell_value: float       # sell value of drops per victorious fight
    drop_rate: float                # share of victories that dropped an item
    rarity_counts: tuple[tuple[str, int], ...]   # sorted (rarity, count)
    material_counts: tuple[tuple[str, int], ...]  # sorted (item_id, count), consumables only
    average_damage_taken: float     # per fight (win or lose)
    player_max_hp: int
    rest_cost: int                  # a full rest in this band's zone
    fights_per_rest: float          # max_hp / avg damage taken
    rest_cost_per_fight: float      # rest_cost / fights_per_rest
    net_gold_per_fight: float       # kill + sell - rest share (victories weighted by win rate)


def simulate_economy_band(
    class_id: str,
    place_id: str,
    *,
    level: int,
    trials: int = 200,
    seed: int = 0,
    use_skills: bool = True,
    rest_zone: int = 1,
    max_turns: int = 50,
    content=None,
) -> EconomyBandReport:
    """Measure the gold/loot flow of `trials` wild fights at `place_id`'s pool
    with an on-`level` player. Deterministic per seed. Uses the public engine
    API + the real spawn path; nothing here changes game rules."""
    from rpg_game.core import store, world
    from rpg_game.core.data_loader import load_content

    content = content or load_content()
    category = {"fighter": "melee", "tank": "melee", "rogue": "melee",
                "cleric": "magic", "mage": "magic", "hunter": "ranged"}[class_id]
    weapon_id = best_weapon_for(content, category, level)

    wins = 0
    turns_total = 0
    kill_gold_total = 0
    sell_total = 0.0
    drops = 0
    rarity_counter: dict[str, int] = {}
    material_counter: dict[str, int] = {}
    damage_taken_total = 0
    player_max_hp = 0

    for index in range(trials):
        engine = GameEngine(content=content, rng=random.Random(seed + index))
        engine.start_new_game(f"{class_id.title()} Econ", class_id)
        if weapon_id is not None:
            engine.player.owned_weapon_ids = (*engine.player.owned_weapon_ids, weapon_id)
            engine.player.equipped_weapon_id = weapon_id
        if level > 1:
            _level_player(engine, level, _DEFAULT_MAIN.get(class_id, "damage"))
        engine.player.hp = engine.effective_stat("max_hp")
        engine.player.mana = engine.effective_stat("max_mana")
        engine.player.current_place_id = place_id
        player_max_hp = engine.effective_stat("max_hp")
        start_hp = engine.player.hp

        enemy = world.create_encounter(engine.player, engine.content, engine.rng)
        if enemy is None:
            continue
        outcome = "timeout"
        turns = 0
        final = None
        while turns < max_turns:
            turns += 1
            final = _take_turn(engine, enemy, use_skills)
            if final.outcome in {"victory", "defeat"}:
                outcome = final.outcome
                break
        turns_total += turns
        damage_taken_total += max(0, start_hp - engine.player.hp)

        if outcome != "victory" or final is None:
            continue
        wins += 1
        kill_gold_total += final.gold_gained
        drop = final.loot_drop
        if drop is not None:
            drops += 1
            rarity_counter[drop.rarity] = rarity_counter.get(drop.rarity, 0) + 1
            if drop.kind == "weapon":
                sell_total += store.sell_value(content.weapons[drop.item_id].price)
            elif drop.kind == "gear":
                sell_total += store.gear_sell_value(content.gear_items[drop.item_id])
            else:
                sell_total += store.sell_value(content.items[drop.item_id].price)
                material_counter[drop.item_id] = material_counter.get(drop.item_id, 0) + 1

    from rpg_game.core import progression
    win_rate = wins / trials if trials else 0.0
    average_damage = damage_taken_total / trials if trials else 0.0
    rest_cost = progression.rest_cost(rest_zone)
    fights_per_rest = (player_max_hp / average_damage) if average_damage > 0 else float("inf")
    rest_share = rest_cost / fights_per_rest if fights_per_rest else 0.0
    avg_kill_gold = kill_gold_total / wins if wins else 0.0
    avg_sell = sell_total / wins if wins else 0.0
    net = win_rate * (avg_kill_gold + avg_sell) - rest_share
    return EconomyBandReport(
        class_id=class_id,
        place_id=place_id,
        level=level,
        trials=trials,
        win_rate=win_rate,
        average_turns=turns_total / trials if trials else 0.0,
        average_kill_gold=avg_kill_gold,
        average_sell_value=avg_sell,
        drop_rate=drops / wins if wins else 0.0,
        rarity_counts=tuple(sorted(rarity_counter.items())),
        material_counts=tuple(sorted(material_counter.items())),
        average_damage_taken=average_damage,
        player_max_hp=player_max_hp,
        rest_cost=rest_cost,
        fights_per_rest=fights_per_rest,
        rest_cost_per_fight=rest_share,
        net_gold_per_fight=net,
    )
