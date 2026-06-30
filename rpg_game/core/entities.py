"""Serializable data structures shared by the game core.

Template classes represent authored JSON content. Runtime classes (`Player`,
`Enemy`, `GameState`) are mutable because combat, progression and inventory
systems update them in place.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Wisdom drives mana: effective max_mana = wisdom * MANA_PER_WISDOM + gear(max_mana).
# Placeholder ratio, tuned in Wisdom Slice B against the B37 sim.
MANA_PER_WISDOM = 5


@dataclass(frozen=True)
class PlayerClass:
    id: str
    name: str
    max_hp: int
    base_damage: int
    armor: int
    wisdom: int          # start wisdom; max_mana is derived (wisdom * MANA_PER_WISDOM)
    speed: int
    crit_chance: int
    starting_weapon_id: str
    starting_skill_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Weapon:
    id: str
    name: str
    damage_bonus: int
    price: int
    damage_type: str = "physical"
    tier: int = 1
    category: str = "melee"


@dataclass(frozen=True)
class EquipmentSlot:
    id: str
    name: str
    slot_type: str
    accepts: str
    order: int = 0


@dataclass(frozen=True)
class GearItem:
    id: str
    name: str
    slot_type: str
    tier: int
    rarity: str
    level_req: int
    stat_modifiers: dict[str, int]


@dataclass(frozen=True)
class EffectSpec:
    type: str
    magnitude: int = 0
    duration: int = 0
    tick_timing: str = "instant"
    multiplier: float = 1.0
    multiplier_min: float = 0.0
    multiplier_max: float = 0.0
    scale: str = "flat"
    damage_type: str = "physical"
    status_type: str = ""
    target: str = "enemy"
    stat: str = ""
    ratio: float = 0.0
    modifies_status_type: str = ""
    mod_magnitude: int = 0
    mod_duration: int = 0
    tag: str = ""
    crit_bonus: int = 0
    conditional: dict[str, object] = field(default_factory=dict)
    trigger: str = "on_hit"
    armor_pen: int = 0
    hits: int = 1
    max_stacks: int = 1
    on_event: str = ""


@dataclass(frozen=True)
class CombatAction:
    id: str
    name: str
    kind: str
    hit_chance: float = 1.0
    mana_cost: int = 0
    cooldown_rounds: int = 0
    telegraph: bool = False
    requires_weapon_category: str = ""
    effects: tuple[EffectSpec, ...] = ()


@dataclass(frozen=True)
class TalentNode:
    id: str
    class_id: str
    branch: str
    order: int
    name: str
    node_type: str
    # B36: how many ranks this node can hold. 3 for scalable nodes (passive with a
    # numeric magnitude, or active whose skill has a dmg/heal/DoT-tick magnitude),
    # 1 for binary nodes (pure unlock / toggle / immunity / stat-only utility).
    max_rank: int = 1
    action_id: str = ""
    requires: str = ""
    effects: tuple[EffectSpec, ...] = ()


@dataclass(frozen=True)
class TournamentReward:
    gold: int = 0
    item_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Tournament:
    id: str
    name: str
    place_id: str
    rank: str
    description: str
    opponent_ids: tuple[str, ...]
    reward: TournamentReward
    entry_fee: int = 0
    repeatable: bool = False


@dataclass(frozen=True)
class ConsumableItem:
    id: str
    name: str
    kind: str
    heal_amount: int
    price: int
    tier: int = 1
    mana_amount: int = 0
    cures: tuple[str, ...] = ()


@dataclass(frozen=True)
class LootDrop:
    item_id: str
    name: str
    kind: str
    tier: int
    rarity: str = "common"
    drop_rate_denominator: int = 1


@dataclass(frozen=True)
class EnemyTemplate:
    id: str
    name: str
    level: int
    max_hp: int
    damage: int
    armor: int
    speed: int
    resistances: dict[str, float]
    action_ids: tuple[str, ...]
    xp_reward: int
    gold_min: int
    gold_max: int
    tags: tuple[str, ...] = ()
    # Source of truth for elemental matchups; `resistances` above is derived
    # from these at load (see data_loader / core.traits). Max 2 per enemy.
    traits: tuple[str, ...] = ()
    mana: int = 0
    ai: tuple[dict[str, object], ...] = ()
    loot_table: tuple[dict[str, object], ...] = ()
    unique_table: tuple[dict[str, object], ...] = ()
    drop_chance: float = 0.0
    rare_table_access: bool = False
    # Wild spawn level range (0 = use `level`, i.e. no range). Stats are scaled
    # from the base `level` to the rolled level at spawn. Arena/tournament
    # opponents leave these at 0 so their hand-built fixed levels never roll.
    level_min: int = 0
    level_max: int = 0

    def create_enemy(self) -> "Enemy":
        # Late import avoids a circular import (progression imports entities).
        # The global HP multiplier is applied here, at creation, to every enemy
        # (wild and arena); per-level scaling (world.scale_enemy_to_level) stacks
        # on top of this for wild spawns.
        from rpg_game.core import progression

        max_hp = max(1, progression.round_half_up(self.max_hp * progression.ENEMY_HP_MULTIPLIER))
        return Enemy(
            id=self.id,
            name=self.name,
            level=self.level,
            max_hp=max_hp,
            hp=max_hp,
            damage=self.damage,
            armor=self.armor,
            speed=self.speed,
            resistances=dict(self.resistances),
            action_ids=self.action_ids,
            xp_reward=self.xp_reward,
            gold_min=self.gold_min,
            gold_max=self.gold_max,
            tags=set(self.tags),
            mana=self.mana,
            max_mana=self.mana,
            ai=self.ai,
            loot_table=self.loot_table,
            unique_table=self.unique_table,
            drop_chance=self.drop_chance,
            rare_table_access=self.rare_table_access,
        )


@dataclass
class Enemy:
    id: str
    name: str
    level: int
    max_hp: int
    hp: int
    damage: int
    armor: int
    speed: int
    resistances: dict[str, float]
    action_ids: tuple[str, ...]
    xp_reward: int
    gold_min: int
    gold_max: int
    mana: int = 0
    max_mana: int = 0
    ai: tuple[dict[str, object], ...] = ()
    loot_table: tuple[dict[str, object], ...] = ()
    unique_table: tuple[dict[str, object], ...] = ()
    drop_chance: float = 0.0
    rare_table_access: bool = False
    charging_action_id: str = ""
    identified: bool = False
    active_statuses: list["ActiveStatus"] = field(default_factory=list)
    cooldowns: dict[str, int] = field(default_factory=dict)
    accuracy_mod: int = 0
    immunity_tags: set[str] = field(default_factory=set)
    crit_chance: int = 0
    crit_mult: float = 2.0
    evasion_chance: int = 0
    damage_dealt_mod: int = 0
    damage_taken_mod: int = 0
    tags: set[str] = field(default_factory=set)
    conditional_damage_mods: list[dict[str, object]] = field(default_factory=list)

    @property
    def is_alive(self) -> bool:
        return self.hp > 0


@dataclass(frozen=True)
class Position:
    x: int
    y: int


@dataclass(frozen=True)
class Connection:
    to: str
    travel: str
    distance_px: int
    distance_km_approx: float


@dataclass(frozen=True)
class Place:
    id: str
    name: str
    type: str
    description: str
    has_store: bool
    mana_site: bool
    port: bool
    position: Position
    danger_tier: int
    encounters: tuple[str, ...]
    respawn: bool
    locked: bool
    connections: tuple[Connection, ...]
    store_inventory: tuple[str, ...]
    respawn_place_id: str
    # Optional regional wild level band (0 = unset). When set, it overrides the
    # enemy type's level_min/max for spawns in this region, so a shared enemy
    # (e.g. undead) can roll a higher band in the west without changing the core.
    level_min: int = 0
    level_max: int = 0
    # Optional rare encounter for this region: rolled before the uniform pool,
    # so a miniboss appears occasionally without changing the normal pool's
    # relative frequencies. Empty/0 = none.
    rare_encounter: str = ""
    rare_chance: float = 0.0


@dataclass
class Inventory:
    consumables: dict[str, int] = field(default_factory=dict)

    def add_consumable(self, item_id: str, count: int = 1) -> None:
        if count <= 0:
            raise ValueError("count must be positive")
        self.consumables[item_id] = self.consumables.get(item_id, 0) + count

    def remove_consumable(self, item_id: str, count: int = 1) -> None:
        if count <= 0:
            raise ValueError("count must be positive")
        current = self.consumables.get(item_id, 0)
        if current < count:
            raise ValueError(f"not enough {item_id}")
        remaining = current - count
        if remaining:
            self.consumables[item_id] = remaining
        else:
            del self.consumables[item_id]

    def count(self, item_id: str) -> int:
        return self.consumables.get(item_id, 0)


@dataclass
class Player:
    name: str
    player_class: str
    level: int
    xp: int
    xp_required: int
    hp: int
    max_hp: int
    base_damage: int
    armor: int
    gold: int
    equipped_weapon_id: str
    inventory: Inventory
    current_place_id: str
    respawn_place_id: str
    owned_weapon_ids: tuple[str, ...] = ()
    owned_gear_ids: tuple[str, ...] = ()
    equipped_gear: dict[str, str] = field(default_factory=dict)
    gear_stat_modifiers: dict[str, int] = field(default_factory=dict)
    mana: int = 0
    max_mana: int = 0          # NOT a stored base: max_mana is derived from wisdom
    wisdom: int = 0
    speed: int = 0
    crit_chance: int = 0
    crit_mult: float = 2.0
    evasion_chance: int = 0
    damage_dealt_mod: int = 0
    damage_taken_mod: int = 0
    equipped_skill_ids: tuple[str, ...] = ()
    talent_points: int = 0
    learned_talent_ids: set[str] = field(default_factory=set)
    # B36: per-node rank (1..max_rank). Source of truth for what is owned; the
    # invariant is `id in learned_talent_ids` iff `talent_ranks[id] >= 1`.
    talent_ranks: dict[str, int] = field(default_factory=dict)
    # Derived (NOT persisted): active skill action_id -> rank, rebuilt from
    # talent_ranks so combat can scale a talent skill's magnitude by its rank
    # without a content lookup. See talents.sync_runtime / combat.resolve_action.
    talent_skill_ranks: dict[str, int] = field(default_factory=dict)
    resistances: dict[str, float] = field(default_factory=dict)
    active_statuses: list["ActiveStatus"] = field(default_factory=list)
    stat_bonuses: dict[str, int] = field(default_factory=dict)
    applied_status_mods: dict[str, dict[str, int]] = field(default_factory=dict)
    cooldowns: dict[str, int] = field(default_factory=dict)
    accuracy_mod: int = 0
    immunity_tags: set[str] = field(default_factory=set)
    tags: set[str] = field(default_factory=set)
    conditional_damage_mods: list[dict[str, object]] = field(default_factory=list)
    elemental_attack_mods: list[dict[str, object]] = field(default_factory=list)
    pending_stat_choices: int = 0
    completed_tournament_ids: set[str] = field(default_factory=set)

    @property
    def is_alive(self) -> bool:
        return self.hp > 0

    def effective_stat(self, stat: str) -> int:
        # max_mana is DERIVED from wisdom (no stored base): effective wisdom (base +
        # gear) * MANA_PER_WISDOM, plus any direct max_mana gear bonus.
        if stat == "max_mana":
            wisdom = self.wisdom + self.gear_stat_modifiers.get("wisdom", 0)
            return int(wisdom * MANA_PER_WISDOM + self.gear_stat_modifiers.get("max_mana", 0))
        value = getattr(self, "base_damage" if stat == "damage" else stat)
        return int(value + self.gear_stat_modifiers.get(stat, 0))


@dataclass(frozen=True)
class GameContent:
    start_place_id: str
    classes: dict[str, PlayerClass]
    weapons: dict[str, Weapon]
    equipment_slots: dict[str, EquipmentSlot]
    gear_items: dict[str, GearItem]
    items: dict[str, ConsumableItem]
    actions: dict[str, CombatAction]
    talents: dict[str, TalentNode]
    tournaments: dict[str, Tournament]
    enemies: dict[str, EnemyTemplate]
    places: dict[str, Place]
    rare_loot_table: tuple[dict[str, object], ...] = ()


@dataclass
class GameState:
    player: Player
    content: GameContent


@dataclass
class ActiveStatus:
    type: str
    magnitude: int
    duration: int
    tick_timing: str
    stat: str = ""
    applied_delta: int = 0
    scale: str = "flat"
    multiplier: float = 1.0
    damage_type: str = "physical"
    tag: str = ""
    trigger: str = "on_hit"
    max_stacks: int = 1
    stacks: int = 1
    on_event: str = ""
    base_duration: int = 0
    weapon_bonus: int = 0
