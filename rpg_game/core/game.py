from __future__ import annotations

import random
from dataclasses import dataclass

from rpg_game.core import combat, inventory, progression, store, talents, world
from rpg_game.core.data_loader import load_content
from rpg_game.core.entities import Enemy, GameContent, GameState, Inventory, LootDrop, Player


@dataclass(frozen=True)
class RestResult:
    outcome: str
    message: str
    player_hp: int = 0
    player_mana: int = 0


class GameEngine:
    def __init__(self, content: GameContent | None = None, rng: random.Random | None = None) -> None:
        self.content = content or load_content()
        self.rng = rng or random.Random()
        self.state: GameState | None = None

    @property
    def player(self) -> Player:
        if self.state is None:
            raise RuntimeError("game has not been started")
        return self.state.player

    def start_new_game(
        self,
        player_name: str,
        class_id: str,
        start_place_id: str | None = None,
    ) -> GameState:
        normalized_class = class_id.strip().lower()
        start_place_id = start_place_id or self.content.start_place_id
        if normalized_class not in self.content.classes:
            raise ValueError(f"unknown class: {class_id}")
        if start_place_id not in self.content.places:
            raise ValueError(f"unknown start place: {start_place_id}")

        player_class = self.content.classes[normalized_class]
        start_place = self.content.places[start_place_id]
        player = Player(
            name=player_name.strip() or "Hero",
            player_class=player_class.id,
            level=1,
            xp=0,
            xp_required=progression.xp_required_for_level(1),
            hp=player_class.max_hp,
            max_hp=player_class.max_hp,
            mana=player_class.max_mana,
            max_mana=player_class.max_mana,
            base_damage=player_class.base_damage,
            armor=player_class.armor,
            speed=player_class.speed,
            crit_chance=player_class.crit_chance,
            gold=0,
            equipped_weapon_id=player_class.starting_weapon_id,
            inventory=Inventory(),
            current_place_id=start_place.id,
            respawn_place_id=start_place.respawn_place_id,
            owned_weapon_ids=(player_class.starting_weapon_id,),
            equipped_skill_ids=player_class.starting_skill_ids,
        )
        self.state = GameState(player=player, content=self.content)
        return self.state

    def current_place(self):
        return world.get_current_place(self.player, self.content)

    def rest(self) -> RestResult:
        place = self.current_place()
        if not place.has_store:
            return RestResult(
                outcome="not_allowed",
                message="You can only rest in a town with services.",
                player_hp=self.player.hp,
                player_mana=self.player.mana,
            )
        player = self.player
        player.hp = player.max_hp
        player.mana = player.max_mana
        return RestResult(
            outcome="rested",
            message=f"You rest at {place.name} and recover to full HP and mana.",
            player_hp=player.hp,
            player_mana=player.mana,
        )

    def available_destinations(self):
        return world.available_destinations(self.player, self.content)

    def available_connections(self):
        return world.available_connections(self.player, self.content)

    def travel(self, destination_id: str) -> str:
        return world.travel(self.player, self.content, destination_id)

    def create_encounter(self) -> Enemy | None:
        return world.create_encounter(self.player, self.content, self.rng)

    def loot_pool(self, enemy: Enemy) -> list[dict[str, object]]:
        max_tier = 6 if enemy.rare_table_access else 3
        pool = list(enemy.loot_table)
        if enemy.rare_table_access:
            pool += list(self.content.rare_loot_table)
        return [entry for entry in pool if int(entry.get("rarity_tier", 1)) <= max_tier]

    def roll_loot(self, enemy: Enemy) -> LootDrop | None:
        if not (self.rng.random() < enemy.drop_chance):
            return None
        pool = self.loot_pool(enemy)
        if not pool:
            return None
        entry = self._weighted_choice(pool)
        return self._make_loot_drop(entry)

    def collect_loot(self, drop: LootDrop) -> None:
        player = self.player
        if drop.kind == "weapon":
            if drop.item_id not in player.owned_weapon_ids:
                player.owned_weapon_ids = (*player.owned_weapon_ids, drop.item_id)
        else:
            player.inventory.add_consumable(drop.item_id)

    def _weighted_choice(self, pool: list[dict[str, object]]) -> dict[str, object]:
        total = sum(float(entry["weight"]) for entry in pool)
        roll = self.rng.random() * total
        upto = 0.0
        for entry in pool:
            upto += float(entry["weight"])
            if roll < upto:
                return entry
        return pool[-1]

    def _make_loot_drop(self, entry: dict[str, object]) -> LootDrop:
        item_id = str(entry["item_id"])
        tier = int(entry.get("rarity_tier", 1))
        if item_id in self.content.weapons:
            return LootDrop(item_id, self.content.weapons[item_id].name, "weapon", tier)
        if item_id in self.content.items:
            item = self.content.items[item_id]
            return LootDrop(item_id, item.name, item.kind, tier)
        raise ValueError(f"unknown loot item: {item_id}")

    def run_combat_turn(self, enemy: Enemy, attack_id: str) -> combat.CombatTurnResult:
        player = self.player
        events: list[str] = []
        enemy_reveal: combat.EnemyReveal | None = None
        normalized_action = attack_id.strip().lower()
        is_identify = normalized_action == "identify"
        missing_consumable = self._missing_consumable_from_action_id(attack_id)
        if missing_consumable:
            events.append(f"{player.name} does not have {missing_consumable}.")
            return combat.CombatTurnResult(
                outcome="blocked",
                events=events,
                player_hp=player.hp,
                enemy_hp=enemy.hp,
                pending_stat_choices=player.pending_stat_choices,
            )

        player_action = None if is_identify else self._build_player_action(attack_id)
        consumable_to_remove = "" if is_identify else self._consumable_from_action_id(attack_id)

        equipped_weapon = self.content.weapons[player.equipped_weapon_id]
        blocked_reason = (
            "" if player_action is None else combat.blocked_action_reason(player, player_action, weapon=equipped_weapon)
        )
        if blocked_reason:
            events.append(blocked_reason)
            return combat.CombatTurnResult(
                outcome="blocked",
                events=events,
                player_hp=player.hp,
                enemy_hp=enemy.hp,
                pending_stat_choices=player.pending_stat_choices,
            )

        events.extend(combat.tick_statuses(player, "round_start"))
        events.extend(combat.tick_statuses(enemy, "round_start"))
        if not enemy.is_alive:
            return self._handle_victory(enemy, events, enemy_reveal=enemy_reveal)
        if not player.is_alive:
            self._respawn_player()
            events.append(f"You died and respawned in {self.current_place().name}.")
            return self._combat_result("defeat", enemy, events)

        first, second = combat.ordered_by_speed(player, enemy)
        player_actions_used: set[str] = set()
        enemy_actions_used: set[str] = set()

        for actor in (first, second):
            if not player.is_alive or not enemy.is_alive:
                break

            skipped_events = combat.consume_skip_turn(actor)
            if skipped_events:
                events.extend(skipped_events)
                continue

            if actor is player:
                if is_identify:
                    enemy_reveal = combat.identify_enemy(enemy, self.content.actions)
                    events.append(f"Identified {enemy.name}.")
                else:
                    weapon = self.content.weapons[player.equipped_weapon_id]
                    resolution = combat.resolve_action(player, enemy, player_action, self.rng, weapon=weapon)
                    events.extend(resolution.events)
                    if resolution.blocked:
                        return self._combat_result("blocked", enemy, events, enemy_reveal=enemy_reveal)
                    if player_action.cooldown_rounds:
                        player_actions_used.add(player_action.id)
                    if consumable_to_remove:
                        player.inventory.remove_consumable(consumable_to_remove)
                        consumable_to_remove = ""
            else:
                resolution = combat.enemy_take_turn(enemy, player, self.content.actions, self.rng)
                events.extend(resolution.events)
                if resolution.blocked:
                    return self._combat_result("blocked", enemy, events, enemy_reveal=enemy_reveal)
                if resolution.action_id and enemy.cooldowns.get(resolution.action_id, 0) > 0:
                    enemy_actions_used.add(resolution.action_id)

        if not enemy.is_alive:
            return self._handle_victory(enemy, events, enemy_reveal=enemy_reveal)

        if not player.is_alive:
            self._respawn_player()
            events.append(f"You died and respawned in {self.current_place().name}.")
            return self._combat_result("defeat", enemy, events)

        events.extend(combat.tick_statuses(player, "round_end"))
        events.extend(combat.tick_statuses(enemy, "round_end"))
        combat.tick_cooldowns(player, skip=player_actions_used)
        combat.tick_cooldowns(enemy, skip=enemy_actions_used)

        if not enemy.is_alive:
            return self._handle_victory(enemy, events)

        if not player.is_alive:
            self._respawn_player()
            events.append(f"You died and respawned in {self.current_place().name}.")
            return self._combat_result("defeat", enemy, events, enemy_reveal=enemy_reveal)

        return self._combat_result("ongoing", enemy, events, enemy_reveal=enemy_reveal)

    def flee_chance(self, enemy: Enemy) -> float:
        diff = (self.player.speed - enemy.speed) + (self.player.level - enemy.level)
        return combat.clamp(0.5 + 0.05 * diff, 0.10, 0.95)

    def attempt_flee(self, enemy: Enemy) -> combat.CombatTurnResult:
        player = self.player
        events: list[str] = []
        if self.rng.random() < self.flee_chance(enemy):
            events.append(f"You fled from {enemy.name}.")
            return combat.CombatTurnResult(
                outcome="fled",
                events=events,
                player_hp=player.hp,
                enemy_hp=enemy.hp,
                pending_stat_choices=player.pending_stat_choices,
            )

        events.append(f"You failed to flee. {enemy.name} gets a free attack.")
        resolution = combat.enemy_take_turn(enemy, player, self.content.actions, self.rng)
        events.extend(resolution.events)
        if not player.is_alive:
            self._respawn_player()
            events.append(f"You died and respawned in {self.current_place().name}.")
            return self._combat_result("defeat", enemy, events)
        return self._combat_result("ongoing", enemy, events)

    def apply_stat_choice(self, stat: str) -> str:
        return progression.apply_stat_choice(self.player, stat)

    def available_actions(self):
        weapon = self.content.weapons[self.player.equipped_weapon_id]
        return combat.available_actions(self.player, self.content.actions, weapon=weapon)

    def available_talents(self):
        return talents.available_talents(self.player, self.content)

    def allocate_talent(self, node_id: str) -> str:
        return talents.allocate_talent(self.player, self.content, node_id)

    def equippable_skills(self):
        return talents.equippable_skills(self.player, self.content)

    def equipped_skills(self):
        return [
            self.content.actions[skill_id]
            for skill_id in self.player.equipped_skill_ids
            if skill_id in self.content.actions
        ]

    def equip_skill(self, action_id: str) -> str:
        return talents.equip_skill(self.player, self.content, action_id)

    def unequip_skill(self, action_id: str) -> str:
        return talents.unequip_skill(self.player, self.content, action_id)

    def owned_weapons(self):
        return [
            self.content.weapons[weapon_id]
            for weapon_id in self.player.owned_weapon_ids
            if weapon_id in self.content.weapons
        ]

    def store_entries(self) -> list[store.StoreEntry]:
        return store.get_store_entries(self.content, self.player.current_place_id)

    def buy_item(self, item_id: str) -> store.PurchaseResult:
        return store.buy_item(self.player, self.content, item_id)

    def sellable_entries(self) -> list[store.SellEntry]:
        return store.get_sellables(self.player, self.content)

    def sell_item(self, item_id: str) -> store.SellResult:
        return store.sell_item(self.player, self.content, item_id)

    def use_consumable(self, item_id: str) -> inventory.UseItemResult:
        return inventory.use_consumable(self.player, self.content, item_id)

    def _respawn_player(self) -> None:
        player = self.player
        player.current_place_id = player.respawn_place_id
        player.hp = player.max_hp
        player.mana = player.max_mana

    def _build_player_action(self, action_id: str) -> combat.CombatAction:
        normalized = action_id.strip().lower()
        if normalized.startswith("item:"):
            item_id = normalized.split(":", 1)[1]
            return combat.create_item_action(self.content.items[item_id])
        if normalized.startswith("swap:"):
            weapon_id = normalized.split(":", 1)[1]
            if weapon_id not in self.content.weapons:
                raise ValueError(f"unknown weapon: {weapon_id}")
            if weapon_id not in self.player.owned_weapon_ids:
                raise ValueError(f"weapon not owned: {weapon_id}")
            return combat.create_weapon_swap_action(self.content.weapons[weapon_id])
        return self.content.actions[normalized]

    def _consumable_from_action_id(self, action_id: str) -> str:
        normalized = action_id.strip().lower()
        if normalized.startswith("item:"):
            item_id = normalized.split(":", 1)[1]
            if self.player.inventory.count(item_id) > 0:
                return item_id
        return ""

    def _missing_consumable_from_action_id(self, action_id: str) -> str:
        normalized = action_id.strip().lower()
        if normalized.startswith("item:"):
            item_id = normalized.split(":", 1)[1]
            if self.player.inventory.count(item_id) <= 0:
                return item_id
        return ""

    def _handle_victory(
        self,
        enemy: Enemy,
        events: list[str],
        enemy_reveal: combat.EnemyReveal | None = None,
    ) -> combat.CombatTurnResult:
        player = self.player
        gold = self.rng.randint(enemy.gold_min, enemy.gold_max)
        player.gold += gold
        xp_gained = progression.level_scaled_xp(enemy.xp_reward, player.level, enemy.level)
        levels_gained = progression.award_xp(player, xp_gained)
        events.append(f"{enemy.name} was defeated.")
        events.append(f"Gained {xp_gained} XP and {gold} gold.")
        if levels_gained:
            events.append(f"Gained {levels_gained} level(s).")

        drop = self.roll_loot(enemy)
        if drop is not None:
            self.collect_loot(drop)
            events.append(f"{enemy.name} dropped: {drop.name} (tier {drop.tier})!")

        return combat.CombatTurnResult(
            outcome="victory",
            events=events,
            player_hp=player.hp,
            enemy_hp=enemy.hp,
            xp_gained=xp_gained,
            gold_gained=gold,
            levels_gained=levels_gained,
            pending_stat_choices=player.pending_stat_choices,
            loot_drop=drop,
            enemy_reveal=enemy_reveal,
        )

    def _combat_result(
        self,
        outcome: str,
        enemy: Enemy,
        events: list[str],
        enemy_reveal: combat.EnemyReveal | None = None,
    ) -> combat.CombatTurnResult:
        return combat.CombatTurnResult(
            outcome=outcome,
            events=events,
            player_hp=self.player.hp,
            enemy_hp=enemy.hp,
            pending_stat_choices=self.player.pending_stat_choices,
            enemy_reveal=enemy_reveal,
        )
