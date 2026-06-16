from __future__ import annotations

import random

from rpg_game.core import combat, inventory, progression, store, world
from rpg_game.core.data_loader import load_content
from rpg_game.core.entities import Enemy, GameContent, GameState, Inventory, Player


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
            base_damage=player_class.base_damage,
            armor=player_class.armor,
            gold=0,
            equipped_weapon_id=player_class.starting_weapon_id,
            inventory=Inventory(),
            current_place_id=start_place.id,
            respawn_place_id=start_place.respawn_place_id,
        )
        self.state = GameState(player=player, content=self.content)
        return self.state

    def current_place(self):
        return world.get_current_place(self.player, self.content)

    def available_destinations(self):
        return world.available_destinations(self.player, self.content)

    def available_connections(self):
        return world.available_connections(self.player, self.content)

    def travel(self, destination_id: str) -> str:
        return world.travel(self.player, self.content, destination_id)

    def create_encounter(self) -> Enemy | None:
        return world.create_encounter(self.player, self.content, self.rng)

    def run_combat_turn(self, enemy: Enemy, attack_id: str) -> combat.CombatTurnResult:
        player = self.player
        weapon = self.content.weapons[player.equipped_weapon_id]
        player_attack = combat.get_attack(attack_id)
        events: list[str] = []

        player_result = combat.resolve_player_attack(player, enemy, weapon, player_attack, self.rng)
        events.append(player_result.message())

        if not enemy.is_alive:
            gold = self.rng.randint(enemy.gold_min, enemy.gold_max)
            player.gold += gold
            levels_gained = progression.award_xp(player, enemy.xp_reward)
            events.append(f"{enemy.name} was defeated.")
            events.append(f"Gained {enemy.xp_reward} XP and {gold} gold.")
            if levels_gained:
                events.append(f"Gained {levels_gained} level(s).")
            return combat.CombatTurnResult(
                outcome="victory",
                events=events,
                player_hp=player.hp,
                enemy_hp=enemy.hp,
                xp_gained=enemy.xp_reward,
                gold_gained=gold,
                levels_gained=levels_gained,
                pending_stat_choices=player.pending_stat_choices,
            )

        enemy_attack = self.rng.choice(list(combat.ATTACKS.values()))
        enemy_result = combat.resolve_enemy_attack(enemy, player, enemy_attack, self.rng)
        events.append(enemy_result.message())

        if not player.is_alive:
            self._respawn_player()
            events.append(f"You died and respawned in {self.current_place().name}.")
            return combat.CombatTurnResult(
                outcome="defeat",
                events=events,
                player_hp=player.hp,
                enemy_hp=enemy.hp,
                pending_stat_choices=player.pending_stat_choices,
            )

        return combat.CombatTurnResult(
            outcome="ongoing",
            events=events,
            player_hp=player.hp,
            enemy_hp=enemy.hp,
            pending_stat_choices=player.pending_stat_choices,
        )

    def apply_stat_choice(self, stat: str) -> str:
        return progression.apply_stat_choice(self.player, stat)

    def store_entries(self) -> list[store.StoreEntry]:
        return store.get_store_entries(self.content, self.player.current_place_id)

    def buy_item(self, item_id: str) -> store.PurchaseResult:
        return store.buy_item(self.player, self.content, item_id)

    def use_consumable(self, item_id: str) -> inventory.UseItemResult:
        return inventory.use_consumable(self.player, self.content, item_id)

    def _respawn_player(self) -> None:
        player = self.player
        player.current_place_id = player.respawn_place_id
        player.hp = player.max_hp
