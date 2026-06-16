import unittest
import random

from rpg_game.core.combat import get_attack, calculate_player_damage
from rpg_game.core.game import GameEngine
from rpg_game.core.entities import Inventory, Player, Weapon
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


if __name__ == "__main__":
    unittest.main()
