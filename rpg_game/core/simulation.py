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
    "mage": "mana", "cleric": "mana", "hunter": "damage",
}


def _offensive_multiplier(action) -> float:
    """Crude 'how hard does this hit' score: the biggest damage multiplier among
    a skill's instant_damage/drain effects (0 for pure buffs/heals/DoTs)."""
    best = 0.0
    for effect in action.effects:
        if effect.type in ("instant_damage", "drain"):
            best = max(best, effect.multiplier or 1.0)
    return best


def _choose_skill(engine: GameEngine):
    """Skill policy: the highest-hitting equipped offensive skill the player can
    currently afford (mana). Cooldown/weapon gating is enforced by the engine — a
    blocked cast falls back to a basic attack in _take_turn. None -> just attack."""
    player = engine.player
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
        skill = _choose_skill(engine)
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
) -> FightSimulation:
    """Run one fight and return a compact result. Defaults reproduce the old
    attack-only L1 fight exactly; use_skills lets the player cast skills (mana +
    cooldown aware), level>1 grows it via the B35 level-up path, and weapon_id
    equips a specific weapon (B37 weapon-aware curve)."""
    engine = GameEngine(rng=random.Random(seed))
    engine.start_new_game(f"{class_id.title()} Sim", class_id)
    if weapon_id is not None:
        engine.player.owned_weapon_ids = (*engine.player.owned_weapon_ids, weapon_id)
        engine.player.equipped_weapon_id = weapon_id
    if level > 1:
        _level_player(engine, level, main_stat or _DEFAULT_MAIN.get(class_id, "damage"))
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
) -> MatchupSimulation:
    """Run many seeded fights for one class/enemy matchup."""
    fights = [
        simulate_fight(class_id, enemy_id, seed=seed + index, max_turns=max_turns,
                       use_skills=use_skills, level=level, main_stat=main_stat,
                       weapon_id=weapon_id)
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
