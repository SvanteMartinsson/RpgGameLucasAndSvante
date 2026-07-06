"""B65: zone bosses + main goal.

Locks: the five boss defs load and validate, boss enemies never spawn wild,
the challenge gate (prerequisites / already defeated), the one-time reward on
first defeat, defeat/flee leaving the lair open, phase AI via hp thresholds,
telegraph charge/release, persistence, and the pygame layer (solid lairs,
two-press challenge, boss nameplate, the ending screen). Pygame parts skip
without pygame.
"""

import os
import random
import tempfile
import unittest
from unittest import mock

from rpg_game.core import bosses, combat, data_loader
from rpg_game.core.entities import BossDef
from rpg_game.core.game import GameEngine

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

BOSS_IDS = ("rotfang", "briar_queen", "yagra", "barrow_king", "pale_sovereign")


def _engine() -> GameEngine:
    engine = GameEngine(rng=random.Random(0))
    engine.start_new_game("Hero", "fighter")
    return engine


def _win(engine: GameEngine, boss_id: str) -> None:
    enemy = engine.challenge_boss(boss_id)
    enemy.hp = 0
    engine._handle_victory(enemy, [])


class BossContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = data_loader.load_content()

    def test_five_bosses_load_and_the_final_requires_the_other_four(self):
        self.assertEqual(set(self.content.bosses), set(BOSS_IDS))
        final = self.content.bosses["pale_sovereign"]
        self.assertTrue(final.final)
        self.assertEqual(set(final.requires_defeated), set(BOSS_IDS) - {"pale_sovereign"})
        for boss_id in BOSS_IDS[:-1]:
            self.assertFalse(self.content.bosses[boss_id].final)

    def test_boss_enemies_are_flagged_and_never_in_wild_pools(self):
        boss_enemy_ids = {b.enemy_id for b in self.content.bosses.values()}
        for enemy_id in boss_enemy_ids:
            self.assertTrue(self.content.enemies[enemy_id].boss, enemy_id)
        for place in self.content.places.values():
            self.assertFalse(boss_enemy_ids & set(place.encounters), place.id)

    def test_validator_rejects_unknown_enemy_reference(self):
        bad = dict(self.content.bosses)
        bad["broken"] = BossDef(id="broken", enemy_id="no_such_enemy", zone="x",
                                lair_tile=(1, 1), requires_defeated=(),
                                reward_gold=0, reward_item_ids=(), intro="")
        with self.assertRaises(ValueError):
            data_loader._validate_bosses(bad, self.content.enemies, self.content.places,
                                         self.content.weapons, self.content.gear_items,
                                         self.content.items, self.content.chests)

    def test_reward_items_resolve_and_the_recurve_is_holy_ranged(self):
        for boss in self.content.bosses.values():
            for item_id in boss.reward_item_ids:
                self.assertTrue(item_id in self.content.weapons
                                or item_id in self.content.gear_items
                                or item_id in self.content.items, item_id)
        recurve = self.content.weapons["sanctified_recurve"]
        self.assertEqual((recurve.category, recurve.damage_type), ("ranged", "holy"))

    def test_boss_traits_give_the_designed_matchups(self):
        barrow = self.content.enemies["boss_barrow_king"]
        self.assertEqual(barrow.resistances["holy"], 2.0)      # bane
        self.assertEqual(barrow.resistances["poison"], 0.0)    # immune
        self.assertEqual(barrow.resistances["physical"], 0.65)  # resist
        briar = self.content.enemies["boss_briar_queen"]
        self.assertEqual(briar.resistances["fire"], 2.0)


class BossChallengeTests(unittest.TestCase):
    def test_final_is_gated_until_all_four_are_down(self):
        engine = _engine()
        self.assertIsNone(engine.challenge_boss("pale_sovereign"))
        self.assertIn("Undefeated", engine.boss_challenge_blocker("pale_sovereign"))
        for boss_id in BOSS_IDS[:-1]:
            _win(engine, boss_id)
        self.assertEqual(engine.boss_challenge_blocker("pale_sovereign"), "")
        self.assertIsNotNone(engine.challenge_boss("pale_sovereign"))

    def test_first_defeat_grants_the_reward_once(self):
        engine = _engine()
        player = engine.player
        gold_before = player.gold
        enemy = engine.challenge_boss("rotfang")
        self.assertTrue(enemy.boss)
        enemy.hp = 0
        result = engine._handle_victory(enemy, [])
        self.assertIn("rotfang", player.defeated_boss_ids)
        self.assertIn("warren_signet", player.owned_gear_ids)
        self.assertIn("boss_rotfang", player.bestiary_identified)
        self.assertTrue(any("Boss reward" in line for line in result.events))
        # kill gold + the 150 reward
        self.assertGreaterEqual(player.gold - gold_before, 150 + enemy.gold_min)
        # felled: the lair is silent, no second reward possible
        self.assertEqual(engine.boss_challenge_blocker("rotfang"), "The lair lies silent.")
        self.assertIsNone(engine.challenge_boss("rotfang"))

    def test_defeat_and_flee_leave_the_lair_open(self):
        engine = _engine()
        enemy = engine.challenge_boss("rotfang")
        engine.player.hp = 0
        engine._defeat(enemy, [])
        self.assertNotIn("rotfang", engine.player.defeated_boss_ids)
        self.assertEqual(engine._active_boss_id, "")
        self.assertEqual(engine.boss_challenge_blocker("rotfang"), "")

        enemy = engine.challenge_boss("rotfang")
        engine.flee_chance = lambda enemy: 1.0   # deterministic escape
        result = engine.attempt_flee(enemy)
        self.assertEqual(result.outcome, "fled")
        self.assertEqual(engine._active_boss_id, "")
        self.assertEqual(engine.boss_challenge_blocker("rotfang"), "")

    def test_a_wild_victory_never_grants_boss_rewards(self):
        engine = _engine()
        engine.challenge_boss("rotfang")            # armed ...
        wild = engine.content.enemies["giant_rat"].create_enemy()
        engine._begin_encounter()                   # ... but a fresh fight disarms
        self.assertEqual(engine._active_boss_id, "")
        wild.hp = 0
        engine._handle_victory(wild, [])
        self.assertEqual(engine.player.defeated_boss_ids, set())

    def test_main_goal_helpers(self):
        engine = _engine()
        self.assertFalse(bosses.zone_bosses_defeated(engine.player, engine.content))
        self.assertFalse(engine.main_goal_complete())
        for boss_id in BOSS_IDS[:-1]:
            _win(engine, boss_id)
        self.assertTrue(bosses.zone_bosses_defeated(engine.player, engine.content))
        self.assertFalse(engine.main_goal_complete())
        _win(engine, "pale_sovereign")
        self.assertTrue(engine.main_goal_complete())

    def test_defeated_bosses_survive_save_load(self):
        engine = _engine()
        _win(engine, "rotfang")
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "save.json")
            engine.save(path)
            engine2 = GameEngine(rng=random.Random(1))
            self.assertTrue(engine2.load(path).success)
            self.assertIn("rotfang", engine2.player.defeated_boss_ids)


class BossAiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = data_loader.load_content()

    def _barrow(self):
        return self.content.enemies["boss_barrow_king"].create_enemy()

    def test_barrow_king_phases_by_hp(self):
        enemy = self._barrow()
        target = self._barrow()   # any Actor works as the target
        rng = random.Random(0)
        pick = combat.choose_enemy_action(enemy, target, self.content.actions, rng)
        self.assertEqual(pick.id, "barrow_soul_harvest")          # opening telegraph
        enemy.hp = int(enemy.max_hp * 0.5)
        pick = combat.choose_enemy_action(enemy, target, self.content.actions, rng)
        self.assertEqual(pick.id, "barrow_bone_shield")           # phase 2
        enemy.hp = int(enemy.max_hp * 0.2)
        pick = combat.choose_enemy_action(enemy, target, self.content.actions, rng)
        self.assertEqual(pick.id, "barrow_grave_storm")           # phase 3

    def test_rotfang_telegraph_charges_then_releases(self):
        enemy = self.content.enemies["boss_rotfang"].create_enemy()
        target = self.content.enemies["boss_rotfang"].create_enemy()
        rng = random.Random(0)
        first = combat.enemy_take_turn(enemy, target, self.content.actions, rng)
        self.assertEqual(enemy.charging_action_id, "rat_king_plague_leap")
        self.assertTrue(any("charges" in event for event in first.events))
        hp_before = target.hp
        combat.enemy_take_turn(enemy, target, self.content.actions, rng)
        self.assertEqual(enemy.charging_action_id, "")
        self.assertLess(target.hp, hp_before)                     # the leap landed


try:
    import pygame
    from rpg_game.core import saveslots
    from rpg_game.presentation import ui_text as T
    from rpg_game.presentation.pygame_battle import enemy_nameplate, _enemy_article
    from rpg_game.presentation.pygame_overworld import OverworldApp
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class BossOverworldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        auto = os.path.join(self._tmp.name, "autosave.json")
        slots = tuple(os.path.join(self._tmp.name, f"slot{i}.json") for i in (1, 2, 3))
        for patcher in (
            mock.patch.object(saveslots, "SAVES_DIR", self._tmp.name),
            mock.patch.object(saveslots, "SLOT_PATHS", slots),
            mock.patch.object(saveslots, "AUTOSAVE_PATH", auto),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)
        self.app = OverworldApp()

    def test_lair_tiles_are_solid_with_a_walkable_neighbour(self):
        for boss in self.app.engine.content.bosses.values():
            tile = tuple(boss.lair_tile)
            self.assertIn(tile, self.app.world.blocked, boss.id)
            x, y = tile
            neighbours = ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
            self.assertTrue(any(n not in self.app.world.blocked for n in neighbours), boss.id)

    def _stand_beside(self, boss_id: str):
        x, y = self.app.engine.content.bosses[boss_id].lair_tile
        for tile in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if tile not in self.app.world.blocked:
                self.app.world.set_tile(*tile)
                self.app.sync_location()
                return
        self.fail("no free tile beside the lair")

    def test_first_e_arms_and_second_e_starts_the_fight(self):
        started = []
        self.app.start_battle = started.append
        self._stand_beside("rotfang")
        self.assertTrue(self.app._try_challenge_boss())
        self.assertEqual(self.app._armed_boss_id, "rotfang")
        self.assertFalse(started)
        self.assertTrue(self.app._try_challenge_boss())
        self.assertEqual(len(started), 1)
        self.assertEqual(started[0].id, "boss_rotfang")

    def test_a_gated_lair_only_explains_itself(self):
        started = []
        self.app.start_battle = started.append
        self._stand_beside("pale_sovereign")
        self.assertTrue(self.app._try_challenge_boss())
        self.assertEqual(self.app._armed_boss_id, "")
        self.assertFalse(started)

    def test_felling_the_final_boss_opens_the_ending_once(self):
        engine = self.app.engine
        for boss_id in BOSS_IDS[:-1]:
            _win(engine, boss_id)
        enemy = engine.challenge_boss("pale_sovereign")
        enemy.hp = 0
        engine._handle_victory(enemy, [])
        self.app.resolve_battle_outcome("victory", enemy)
        self.assertEqual(self.app.mode, "victory")
        self.assertTrue(self.app._end_shown)
        # a later boss-tagged victory never re-triggers the ending
        self.app.mode = "walk"
        self.app.resolve_battle_outcome("victory", enemy)
        self.assertEqual(self.app.mode, "walk")

    def test_victory_screen_renders_its_button(self):
        self.app.screen = pygame.Surface((1024, 680))
        self.app.mode = "victory"
        self.app.buttons = []
        self.app.hover.begin()
        self.app._draw_victory_screen()
        self.assertTrue(any(b.label == T.VICTORY_CONTINUE for b in self.app.buttons))

    def test_boss_nameplate_and_article(self):
        enemy = self.app.engine.content.enemies["boss_rotfang"].create_enemy()
        self.assertIn("[BOSS]", enemy_nameplate(enemy))
        self.assertEqual(T.appears(_enemy_article(enemy), enemy.name),
                         "Rotfang, the Rat King appears!")


if __name__ == "__main__":
    unittest.main()
