"""High-level game orchestration.

`GameEngine` owns the mutable `GameState` and coordinates the smaller systems:
world travel, combat, loot, inventory, talents, progression and store actions.
It returns structured results so UI layers can decide how to present them.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass

from rpg_game.core import combat, equipment, inventory, persistence, progression, store, talents, tournaments, world
from rpg_game.core.data_loader import load_content
from rpg_game.core.entities import Enemy, GameContent, GameState, Inventory, LootDrop, Player, Tournament


@dataclass(frozen=True)
class RestResult:
    outcome: str
    message: str
    player_hp: int = 0
    player_mana: int = 0


@dataclass(frozen=True)
class RelocateRespawnResult:
    success: bool
    message: str
    cost: int = 0
    already_set: bool = False


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
            owned_gear_ids=(),
            equipped_gear={},
            equipped_skill_ids=player_class.starting_skill_ids,
        )
        equipment.recompute_gear_modifiers(player, self.content)
        self.state = GameState(player=player, content=self.content)
        return self.state

    def save(self, path: str) -> persistence.SaveResult:
        if self.state is None:
            raise RuntimeError("game has not been started")
        data = persistence.serialize_state(self.state)
        with open(path, "w", encoding="utf-8") as save_file:
            json.dump(data, save_file, indent=2)
        return persistence.SaveResult(True, f"Game saved to {path}.")

    def load(self, path: str) -> persistence.LoadResult:
        try:
            with open(path, encoding="utf-8") as save_file:
                data = json.load(save_file)
        except FileNotFoundError:
            return persistence.LoadResult(False, "No save file found.")
        except json.JSONDecodeError:
            return persistence.LoadResult(False, "Save file is corrupted.")
        player_data = data.get("player", data)
        player = persistence.deserialize_player(player_data, self.content.start_place_id)
        equipment.recompute_gear_modifiers(player, self.content)
        self.state = GameState(player=player, content=self.content)
        return persistence.LoadResult(True, "Game loaded.")

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
        player.hp = equipment.effective_stat(player, "max_hp")
        player.mana = equipment.effective_stat(player, "max_mana")
        # Resting only heals now. Moving the respawn point is a separate, paid
        # action (relocate_respawn) so you never respawn somewhere you didn't buy.
        return RestResult(
            outcome="rested",
            message=f"You rest at {place.name} and recover to full HP and mana.",
            player_hp=player.hp,
            player_mana=player.mana,
        )

    def relocate_respawn(self, zone: int) -> RelocateRespawnResult:
        """Buy a move of the respawn point to the current town. Zone 1 is free;
        higher zones cost progression.respawn_relocation_cost(zone). This is the
        ONLY thing that changes respawn_place_id — it never auto-moves with
        location/zone/death. Observation of gold/respawn only — combat/RNG
        untouched."""
        place = self.current_place()
        cost = progression.respawn_relocation_cost(zone)
        if not place.has_store:
            return RelocateRespawnResult(False, "You can only set your respawn point in a town with services.", cost)
        if self.player.respawn_place_id == place.id:
            return RelocateRespawnResult(False, f"{place.name} is already your respawn point.", cost, already_set=True)
        if self.player.gold < cost:
            return RelocateRespawnResult(False, f"Not enough gold. Moving your respawn to {place.name} costs {cost}.", cost)
        self.player.gold -= cost
        self.player.respawn_place_id = place.id
        message = (f"Respawn point moved to {place.name} for {cost} gold."
                   if cost else f"Respawn point set to {place.name}.")
        return RelocateRespawnResult(True, message, cost)

    def available_tournaments(self) -> list[Tournament]:
        return tournaments.available_tournaments(self.player, self.content)

    def start_tournament(self, tournament_id: str) -> tournaments.TournamentStartResult:
        return tournaments.start_tournament(self.player, self.content, tournament_id)

    def create_tournament_opponent(self, tournament: Tournament, index: int) -> Enemy:
        enemy_id = tournament.opponent_ids[index]
        return self.content.enemies[enemy_id].create_enemy()

    def complete_tournament(self, tournament: Tournament) -> tournaments.TournamentRewardResult:
        return tournaments.complete_tournament(self.player, self.content, tournament)

    def recover_between_tournament_matches(self) -> tournaments.TournamentIntermissionResult:
        return tournaments.recover_between_matches(self.player)

    def available_destinations(self):
        return world.available_destinations(self.player, self.content)

    def available_connections(self):
        return world.available_connections(self.player, self.content)

    def travel(self, destination_id: str) -> str:
        return world.travel(self.player, self.content, destination_id)

    def enter_place(self, place_id: str) -> str:
        """Set location directly for free-walk arrival (no adjacency gate)."""
        return world.enter_place(self.player, self.content, place_id)

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
        return self._make_loot_drop(entry, enemy, pool)

    def collect_loot(self, drop: LootDrop) -> None:
        player = self.player
        if drop.kind == "weapon":
            if drop.item_id not in player.owned_weapon_ids:
                player.owned_weapon_ids = (*player.owned_weapon_ids, drop.item_id)
        elif drop.kind == "gear":
            if drop.item_id not in player.owned_gear_ids:
                player.owned_gear_ids = (*player.owned_gear_ids, drop.item_id)
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

    def _make_loot_drop(
        self,
        entry: dict[str, object],
        enemy: Enemy,
        pool: list[dict[str, object]],
    ) -> LootDrop:
        item_id = str(entry["item_id"])
        tier = int(entry.get("rarity_tier", 1))
        denominator = self.loot_drop_denominator(enemy, entry, pool)
        rarity = loot_rarity_for_denominator(denominator)
        if item_id in self.content.weapons:
            return LootDrop(item_id, self.content.weapons[item_id].name, "weapon", tier, rarity, denominator)
        if item_id in self.content.gear_items:
            gear = self.content.gear_items[item_id]
            return LootDrop(item_id, gear.name, "gear", gear.tier, rarity, denominator)
        if item_id in self.content.items:
            item = self.content.items[item_id]
            return LootDrop(item_id, item.name, item.kind, tier, rarity, denominator)
        raise ValueError(f"unknown loot item: {item_id}")

    def loot_drop_denominator(
        self,
        enemy: Enemy,
        entry: dict[str, object],
        pool: list[dict[str, object]] | None = None,
    ) -> int:
        """Approximate the selected item's true 1/N drop rate within this fight.

        The player only sees the broad rarity label; the denominator exists so
        rarity can be derived consistently from the actual weighted chance.
        """
        pool = pool or self.loot_pool(enemy)
        total_weight = sum(float(pool_entry["weight"]) for pool_entry in pool)
        if enemy.drop_chance <= 0 or total_weight <= 0:
            return 0
        probability = enemy.drop_chance * (float(entry["weight"]) / total_weight)
        if probability <= 0:
            return 0
        return max(1, progression.round_half_up(1 / probability))

    def run_combat_turn(self, enemy: Enemy, attack_id: str) -> combat.CombatTurnResult:
        player = self.player
        events: list[str] = []
        action_resolutions: list[combat.ActionResolution] = []
        enemy_reveal: combat.EnemyReveal | None = None
        normalized_action = attack_id.strip().lower()
        is_identify = normalized_action == "identify"
        if normalized_action in combat.PLAYER_ATTACK_STYLE_IDS:
            events.append("Choose Attack instead of a specific attack style.")
            return combat.CombatTurnResult(
                outcome="blocked",
                events=events,
                player_hp=player.hp,
                enemy_hp=enemy.hp,
                pending_stat_choices=player.pending_stat_choices,
            )
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
            return self._handle_victory(enemy, events, enemy_reveal=enemy_reveal, action_resolutions=action_resolutions)
        if not player.is_alive:
            return self._defeat(enemy, events, action_resolutions=action_resolutions)

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
                    action_resolutions.append(resolution)
                    events.extend(resolution.events)
                    if resolution.blocked:
                        return self._combat_result(
                            "blocked", enemy, events, enemy_reveal=enemy_reveal, action_resolutions=action_resolutions
                        )
                    if player_action.cooldown_rounds:
                        player_actions_used.add(player_action.id)
                    if consumable_to_remove:
                        player.inventory.remove_consumable(consumable_to_remove)
                        consumable_to_remove = ""
            else:
                resolution = combat.enemy_take_turn(enemy, player, self.content.actions, self.rng)
                action_resolutions.append(resolution)
                events.extend(resolution.events)
                if resolution.blocked:
                    return self._combat_result(
                        "blocked", enemy, events, enemy_reveal=enemy_reveal, action_resolutions=action_resolutions
                    )
                if resolution.action_id and enemy.cooldowns.get(resolution.action_id, 0) > 0:
                    enemy_actions_used.add(resolution.action_id)

        if not enemy.is_alive:
            return self._handle_victory(enemy, events, enemy_reveal=enemy_reveal, action_resolutions=action_resolutions)

        if not player.is_alive:
            return self._defeat(enemy, events, action_resolutions=action_resolutions)

        events.extend(combat.tick_statuses(player, "round_end"))
        events.extend(combat.tick_statuses(enemy, "round_end"))
        combat.tick_cooldowns(player, skip=player_actions_used)
        combat.tick_cooldowns(enemy, skip=enemy_actions_used)

        if not enemy.is_alive:
            return self._handle_victory(enemy, events, action_resolutions=action_resolutions)

        if not player.is_alive:
            return self._defeat(enemy, events, enemy_reveal=enemy_reveal, action_resolutions=action_resolutions)

        return self._combat_result(
            "ongoing", enemy, events, enemy_reveal=enemy_reveal, action_resolutions=action_resolutions
        )

    def flee_chance(self, enemy: Enemy) -> float:
        # Scales with difficulty via level delta: easy to leave a trivial enemy,
        # a gamble against one well above you (enemies are level-scaled now).
        delta = enemy.level - self.player.level
        chance = progression.FLEE_BASE_CHANCE - progression.FLEE_CHANCE_PER_LEVEL * delta
        return combat.clamp(chance, progression.FLEE_CHANCE_FLOOR, progression.FLEE_CHANCE_CAP)

    def attempt_flee(self, enemy: Enemy) -> combat.CombatTurnResult:
        player = self.player
        events: list[str] = []
        chance = self.flee_chance(enemy)
        if self.rng.random() < chance:
            events.append(f"You fled from {enemy.name}.")
            result = combat.CombatTurnResult(
                outcome="fled",
                events=events,
                player_hp=player.hp,
                enemy_hp=enemy.hp,
                pending_stat_choices=player.pending_stat_choices,
            )
            result.flee_chance = chance
            return result

        # Failed flee costs the turn: the enemy gets a free attack.
        events.append(f"You failed to flee. {enemy.name} gets a free attack.")
        resolution = combat.enemy_take_turn(enemy, player, self.content.actions, self.rng)
        events.extend(resolution.events)
        if not player.is_alive:
            result = self._defeat(enemy, events, action_resolutions=[resolution])
        else:
            result = self._combat_result("ongoing", enemy, events, action_resolutions=[resolution])
        result.flee_chance = chance
        return result

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

    def effective_stat(self, stat: str) -> int:
        return equipment.effective_stat(self.player, stat)

    def gear_modifier_total(self, stat: str) -> int:
        return equipment.gear_modifier_total(self.player, stat)

    def owned_gear(self):
        return [
            self.content.gear_items[gear_id]
            for gear_id in self.player.owned_gear_ids
            if gear_id in self.content.gear_items
        ]

    def equip_gear(self, gear_id: str, slot_id: str = "") -> equipment.EquipmentResult:
        return equipment.equip_gear(self.player, self.content, gear_id, slot_id)

    def unequip_gear(self, slot_id: str) -> equipment.EquipmentResult:
        return equipment.unequip_gear(self.player, self.content, slot_id)

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

    def _respawn_player(self) -> progression.RespawnResult:
        player = self.player
        # Respawn at the persistent respawn point: Hordanita by default, changed
        # only by a purchased relocation. Never derived from where/how you died.
        player.current_place_id = player.respawn_place_id
        return progression.apply_death_penalty(player)

    def _defeat(
        self,
        enemy: Enemy,
        events: list[str],
        enemy_reveal: combat.EnemyReveal | None = None,
        action_resolutions: list[combat.ActionResolution] | None = None,
    ) -> combat.CombatTurnResult:
        penalty = self._respawn_player()
        events.append(
            f"You died and respawned in {self.current_place().name}. "
            f"Lost {penalty.xp_lost} XP and {penalty.gold_lost} gold."
        )
        return self._combat_result(
            "defeat", enemy, events, enemy_reveal=enemy_reveal, respawn=penalty, action_resolutions=action_resolutions
        )

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
        if normalized == combat.PLAYER_ATTACK_ID:
            return combat.player_attack_action()
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
        action_resolutions: list[combat.ActionResolution] | None = None,
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
            events.append(
                f"{enemy.name} dropped: {drop.name} "
                f"[{drop.rarity}] (tier {drop.tier})!"
            )

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
            action_resolutions=action_resolutions or [],
        )

    def _combat_result(
        self,
        outcome: str,
        enemy: Enemy,
        events: list[str],
        enemy_reveal: combat.EnemyReveal | None = None,
        respawn: progression.RespawnResult | None = None,
        action_resolutions: list[combat.ActionResolution] | None = None,
    ) -> combat.CombatTurnResult:
        return combat.CombatTurnResult(
            outcome=outcome,
            events=events,
            player_hp=self.player.hp,
            enemy_hp=enemy.hp,
            pending_stat_choices=self.player.pending_stat_choices,
            enemy_reveal=enemy_reveal,
            respawn=respawn,
            action_resolutions=action_resolutions or [],
        )


def loot_rarity_for_denominator(denominator: int) -> str:
    """Map an internal 1/N drop estimate to the label shown to the player."""
    if denominator <= 0:
        return "unknown"
    if denominator <= 20:
        return "common"
    if denominator <= 50:
        return "uncommon"
    if denominator <= 150:
        return "rare"
    if denominator <= 300:
        return "mega rare"
    return "legendary"
