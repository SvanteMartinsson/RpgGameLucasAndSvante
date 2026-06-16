from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PlayerClass:
    id: str
    name: str
    max_hp: int
    base_damage: int
    armor: int
    max_mana: int
    speed: int
    starting_weapon_id: str
    starting_skill_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Weapon:
    id: str
    name: str
    damage_bonus: int
    price: int
    damage_type: str = "physical"


@dataclass(frozen=True)
class EffectSpec:
    type: str
    magnitude: int = 0
    duration: int = 0
    tick_timing: str = "instant"
    multiplier: float = 1.0
    scale: str = "flat"
    damage_type: str = "physical"
    status_type: str = ""


@dataclass(frozen=True)
class CombatAction:
    id: str
    name: str
    kind: str
    hit_chance: float = 1.0
    mana_cost: int = 0
    effects: tuple[EffectSpec, ...] = ()


@dataclass(frozen=True)
class ConsumableItem:
    id: str
    name: str
    kind: str
    heal_amount: int
    price: int


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

    def create_enemy(self) -> "Enemy":
        return Enemy(
            id=self.id,
            name=self.name,
            level=self.level,
            max_hp=self.max_hp,
            hp=self.max_hp,
            damage=self.damage,
            armor=self.armor,
            speed=self.speed,
            resistances=dict(self.resistances),
            action_ids=self.action_ids,
            xp_reward=self.xp_reward,
            gold_min=self.gold_min,
            gold_max=self.gold_max,
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
    active_statuses: list["ActiveStatus"] = field(default_factory=list)

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
    mana: int = 0
    max_mana: int = 0
    speed: int = 0
    equipped_skill_ids: tuple[str, ...] = ()
    resistances: dict[str, float] = field(default_factory=dict)
    active_statuses: list["ActiveStatus"] = field(default_factory=list)
    pending_stat_choices: int = 0

    @property
    def is_alive(self) -> bool:
        return self.hp > 0


@dataclass(frozen=True)
class GameContent:
    start_place_id: str
    classes: dict[str, PlayerClass]
    weapons: dict[str, Weapon]
    items: dict[str, ConsumableItem]
    actions: dict[str, CombatAction]
    enemies: dict[str, EnemyTemplate]
    places: dict[str, Place]


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
