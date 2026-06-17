import unittest
import random

from rpg_game.core.combat import (
    effective_hit_chance,
    get_attack,
    calculate_player_damage,
    resolve_action,
    tick_statuses,
)
from rpg_game.core.game import GameEngine
from rpg_game.core.entities import ActiveStatus, Enemy, Inventory, Player, Weapon
from rpg_game.core.progression import xp_required_for_level


class CombatMathTests(unittest.TestCase):
    def test_fighter_normal_attack_rounds_half_up_to_23_damage(self):
        player = Player(
            name="Test Fighter",
            player_class="fighter",
            level=1,
            xp=0,
            xp_required=xp_required_for_level(1),
            hp=100,
            max_hp=100,
            base_damage=15,
            armor=0,
            gold=0,
            equipped_weapon_id="knife",
            inventory=Inventory(),
            current_place_id="town",
            respawn_place_id="town",
        )
        weapon = Weapon(id="knife", name="Knife", damage_bonus=0, price=0)

        damage = calculate_player_damage(player, weapon, get_attack("normal"), target_armor=0)

        self.assertEqual(damage, 23)

    def test_victory_returns_pending_stat_choice_after_level_up(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Test Fighter", "fighter")
        engine.player.xp = 99
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        enemy.hp = 1

        result = engine.run_combat_turn(enemy, "normal")

        self.assertEqual(result.outcome, "victory")
        self.assertEqual(result.levels_gained, 1)
        self.assertEqual(result.pending_stat_choices, 1)
        self.assertEqual(engine.player.pending_stat_choices, 1)

    def test_fighter_and_tank_attack_damage_regression_after_pipeline_refactor(self):
        knife = Weapon(id="knife", name="Knife", damage_bonus=0, price=0)
        fighter = make_player("fighter", base_damage=15)
        tank = make_player("tank", base_damage=10)

        self.assertEqual(calculate_player_damage(fighter, knife, get_attack("power"), 0), 30)
        self.assertEqual(calculate_player_damage(fighter, knife, get_attack("normal"), 0), 23)
        self.assertEqual(calculate_player_damage(fighter, knife, get_attack("quick"), 0), 15)
        self.assertEqual(calculate_player_damage(tank, knife, get_attack("power"), 0), 20)
        self.assertEqual(calculate_player_damage(tank, knife, get_attack("normal"), 0), 15)
        self.assertEqual(calculate_player_damage(tank, knife, get_attack("quick"), 0), 10)

    def test_base_attack_hit_chances_power_is_50_normal_55_quick_75(self):
        self.assertEqual(effective_hit_chance(get_attack("power")), 0.50)
        self.assertEqual(effective_hit_chance(get_attack("normal")), 0.55)
        self.assertEqual(effective_hit_chance(get_attack("quick")), 0.75)

        content = GameEngine().content
        self.assertEqual(effective_hit_chance(content.actions["power"]), 0.50)
        self.assertEqual(effective_hit_chance(content.actions["normal"]), 0.55)
        self.assertEqual(effective_hit_chance(content.actions["quick"]), 0.75)

    def test_smite_deals_double_damage_to_undead_holy_weakness(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Test Cleric", "cleric")
        smite = engine.content.actions["smite"]
        dummy = make_enemy("dummy", resistances={"holy": 1.0})
        undead = engine.content.enemies["undead"].create_enemy()

        dummy_result = resolve_action(engine.player, dummy, smite, engine.rng)
        undead_result = resolve_action(engine.player, undead, smite, engine.rng)

        self.assertEqual(undead_result.total_damage, dummy_result.total_damage * 2)

    def test_smite_spends_mana_and_blocks_when_mana_is_missing(self):
        engine = GameEngine(rng=random.Random(1))
        engine.start_new_game("Test Cleric", "cleric")
        enemy = engine.content.enemies["undead"].create_enemy()
        starting_mana = engine.player.mana

        result = engine.run_combat_turn(enemy, "smite")

        self.assertEqual(result.outcome, "ongoing")
        self.assertEqual(engine.player.mana, starting_mana - engine.content.actions["smite"].mana_cost)

        enemy_hp = enemy.hp
        engine.player.mana = 0
        blocked = engine.run_combat_turn(enemy, "smite")

        self.assertEqual(blocked.outcome, "blocked")
        self.assertEqual(enemy.hp, enemy_hp)

    def test_poison_ticks_m_damage_for_d_rounds_and_then_expires(self):
        enemy = make_enemy("dummy", hp=50, resistances={"poison": 1.0})
        enemy.active_statuses.append(
            ActiveStatus(type="poison", magnitude=4, duration=3, tick_timing="round_end")
        )

        tick_statuses(enemy, "round_end")
        self.assertEqual(enemy.hp, 46)
        tick_statuses(enemy, "round_end")
        self.assertEqual(enemy.hp, 42)
        tick_statuses(enemy, "round_end")
        self.assertEqual(enemy.hp, 38)
        tick_statuses(enemy, "round_end")
        self.assertEqual(enemy.hp, 38)
        self.assertEqual(enemy.active_statuses, [])

    def test_higher_speed_acts_first(self):
        engine = GameEngine(rng=random.Random(2))
        engine.start_new_game("Slow Fighter", "fighter")
        engine.player.speed = 1
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        enemy.speed = 99
        enemy.action_ids = ("quick",)

        result = engine.run_combat_turn(enemy, "quick")

        self.assertTrue(result.events[0].startswith("Giant Rat's"))

def make_player(player_class: str, base_damage: int) -> Player:
    return Player(
        name=f"Test {player_class}",
        player_class=player_class,
        level=1,
        xp=0,
        xp_required=xp_required_for_level(1),
        hp=100,
        max_hp=100,
        base_damage=base_damage,
        armor=0,
        gold=0,
        equipped_weapon_id="knife",
        inventory=Inventory(),
        current_place_id="town",
        respawn_place_id="town",
    )


def make_enemy(
    enemy_id: str,
    hp: int = 100,
    resistances: dict[str, float] | None = None,
) -> Enemy:
    return Enemy(
        id=enemy_id,
        name=enemy_id.title(),
        level=1,
        max_hp=hp,
        hp=hp,
        damage=1,
        armor=0,
        speed=1,
        resistances=resistances or {},
        action_ids=("quick",),
        xp_reward=0,
        gold_min=0,
        gold_max=0,
    )


if __name__ == "__main__":
    unittest.main()
