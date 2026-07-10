"""B69: the sound engine + SFX wiring.

Locks: the mixer comes up headless (dummy driver) and degrades to a SILENT
no-crash mode when it can't; all 16 shipped WAVs load; volume = master × sfx
from the B70 settings with per-sound gain shaping; the naming rules (potion
drink / skill cast) read real content correctly; and the battle playback
plays the right sound for the right resolution — base attack is cast-less,
potions gulp instead of chiming, skipped rounds stay quiet, and the finale
carries level-up/death. The background .ogg loops on the separate music
stream, never restarts on shell hops, and rides master × music × MUSIC_GAIN.
Skips without pygame.
"""

import collections
import json
import os
import random
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.core import combat
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation import audio
    from rpg_game.presentation import settings as user_settings
    from rpg_game.presentation.pygame_battle import BattleApp
    HAVE_PYGAME = True
except Exception:  # pragma: no cover
    HAVE_PYGAME = False

try:
    from rpg_game.presentation.pygame_overworld import OverworldApp
    HAVE_OVERWORLD = HAVE_PYGAME
except Exception:  # pragma: no cover - pytmx missing
    HAVE_OVERWORLD = False

ALL_SOUNDS = (
    "menu_click", "hit_enemy", "get_hit", "magic_cast", "physical_cast",
    "heal", "health_pot", "mana_pot", "DoT", "level_up", "encounter",
    "open_chest", "brewing", "sell", "walk", "die",
)


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class AudioEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        audio._reset()
        pygame.quit()

    def setUp(self):
        audio._reset()

    def tearDown(self):
        audio._reset()

    def test_headless_dummy_mixer_goes_live_and_init_is_idempotent(self):
        self.assertTrue(audio.init())
        self.assertTrue(audio.init())

    def test_mixer_failure_means_silent_mode_not_a_crash(self):
        real_init = pygame.mixer.init
        pygame.mixer.quit()

        def refuse(*args, **kwargs):
            raise pygame.error("no audio device")

        pygame.mixer.init = refuse
        try:
            self.assertFalse(audio.init())
            audio.play("menu_click")          # silent no-op, no crash
            audio.ensure_music()              # music is a no-op too
            self.assertIsNone(audio._music_path)
            self.assertFalse(audio.init())    # stays down, never re-raises
        finally:
            pygame.mixer.init = real_init
            pygame.mixer.init()               # bring the mixer back for the rest

    def test_all_shipped_wavs_load(self):
        self.assertTrue(audio.init())
        for name in ALL_SOUNDS:
            self.assertIsNotNone(audio._load(name), name)

    def test_unknown_sound_is_a_silent_noop(self):
        self.assertTrue(audio.init())
        audio.play("no_such_sound")           # no crash
        self.assertIsNone(audio._cache["no_such_sound"])

    def test_volume_is_master_times_sfx_with_per_sound_gain(self):
        real_path = user_settings.SETTINGS_PATH
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "settings.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"sound_master": 0.5, "sound_sfx": 0.5}, fh)
            user_settings.SETTINGS_PATH = path
            try:
                self.assertTrue(audio.init())
                click = audio._load("menu_click")
                walk = audio._load("walk")
                self.assertAlmostEqual(click.get_volume(), 0.25, delta=0.02)
                self.assertAlmostEqual(walk.get_volume(), 0.25 * audio.GAIN["walk"], delta=0.02)
            finally:
                user_settings.SETTINGS_PATH = real_path

    def test_walk_and_dot_sit_low_in_the_mix(self):
        self.assertTrue(audio.init())
        loud = audio._load("menu_click").get_volume()
        self.assertLess(audio._load("walk").get_volume(), loud)
        self.assertLess(audio._load("DoT").get_volume(), loud)

    def test_music_track_is_discovered(self):
        path = audio.music_track()
        self.assertIsNotNone(path)
        self.assertTrue(path.lower().endswith(".ogg"))

    def test_music_loops_and_restarts_are_suppressed(self):
        self.assertTrue(audio.init())
        audio.ensure_music()
        self.assertIsNotNone(audio._music_path)
        self.assertTrue(pygame.mixer.music.get_busy())
        pos_probe = audio._music_path
        audio.ensure_music()   # a second shell hop must not restart the track
        self.assertEqual(audio._music_path, pos_probe)
        self.assertTrue(pygame.mixer.music.get_busy())

    def test_music_volume_is_master_times_music_with_gain(self):
        real_path = user_settings.SETTINGS_PATH
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "settings.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"sound_master": 0.5, "sound_music": 0.5}, fh)
            user_settings.SETTINGS_PATH = path
            try:
                self.assertTrue(audio.init())
                audio.ensure_music()
                self.assertAlmostEqual(pygame.mixer.music.get_volume(),
                                       0.25 * audio.MUSIC_GAIN, delta=0.02)
            finally:
                user_settings.SETTINGS_PATH = real_path

    def test_apply_music_volume_updates_live_and_clamps_junk(self):
        self.assertTrue(audio.init())
        audio.apply_music_volume(0.5, 0.5)
        self.assertAlmostEqual(audio._music_volume, 0.25 * audio.MUSIC_GAIN, places=4)
        self.assertAlmostEqual(pygame.mixer.music.get_volume(),
                               0.25 * audio.MUSIC_GAIN, delta=0.02)
        audio.apply_music_volume(2.0, -1.0)   # out-of-range clamps to 1.0 x 0.0
        self.assertEqual(audio._music_volume, 0.0)


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class SfxNamingRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        engine = GameEngine(rng=random.Random(0))
        engine.start_new_game("Hero", "mage")
        cls.content = engine.content

    def test_potion_sounds_follow_the_item_effect(self):
        items = self.content.items
        self.assertEqual(audio.potion_sound(items["hp_potion"]), "health_pot")
        self.assertEqual(audio.potion_sound(items["greater_hp_potion"]), "health_pot")
        self.assertEqual(audio.potion_sound(items["mana_potion"]), "mana_pot")
        self.assertEqual(audio.potion_sound(items["antidote"]), "health_pot")  # cure-only gulp
        self.assertIsNone(audio.potion_sound(None))

    def test_tomes_make_no_drink_sound(self):
        tome = next((item for item in self.content.items.values() if item.kind == "tome"), None)
        if tome is None:
            self.skipTest("no tome in content")
        self.assertIsNone(audio.potion_sound(tome))

    def test_nonphysical_skills_cast_magically_from_either_side(self):
        fireball = self.content.actions["fireball"]
        self.assertEqual(audio.cast_sound(fireball, True), "magic_cast")
        self.assertEqual(audio.cast_sound(fireball, False), "magic_cast")

    def test_physical_skills_cast_only_for_the_player(self):
        shot = self.content.actions["piercing_shot"]
        self.assertEqual(audio.cast_sound(shot, True), "physical_cast")
        self.assertIsNone(audio.cast_sound(shot, False))   # enemy special = just the hit

    def test_dot_payloads_count_as_magic_but_stat_buffs_do_not(self):
        dot_skill = next(
            (action for action in self.content.actions.values()
             if any(effect.type == "apply_status" and effect.magnitude and not effect.stat
                    and effect.damage_type not in ("physical", "weapon")
                    for effect in action.effects)
             and not any(effect.type in ("instant_damage", "drain") for effect in action.effects)),
            None)
        if dot_skill is not None:
            self.assertEqual(audio.cast_sound(dot_skill, False), "magic_cast")
        self.assertIsNone(audio.cast_sound(self.content.actions["evasion"], True))  # buff

    def test_heal_only_skills_defer_to_the_heal_sfx(self):
        heal = next(
            action for action in self.content.actions.values()
            if any(effect.type == "instant_heal" for effect in action.effects)
            and not any(effect.type in ("instant_damage", "drain") for effect in action.effects))
        self.assertIsNone(audio.cast_sound(heal, True))


def _resolution(actor="Hero", action_id="attack", rolled="quick_attack",
                components=(), healing=0, blocked=False):
    resolution = combat.ActionResolution(action_id, action_id.title(), actor, "T")
    resolution.rolled_style_id = rolled
    resolution.damage_components = [combat.DamageComponent(a, t) for a, t in components]
    resolution.total_healing = healing
    resolution.blocked = blocked
    return resolution


@unittest.skipUnless(HAVE_PYGAME, "pygame/pytmx not installed")
class BattleSfxWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.calls = []
        self._real_play = audio.play
        audio.play = self.calls.append

    def tearDown(self):
        audio.play = self._real_play

    def _battle(self):
        engine = GameEngine(rng=random.Random(0))
        engine.start_new_game("Hero", "fighter")
        enemy = engine.content.enemies["cave_bear"].create_enemy()
        battle = BattleApp(engine=engine, enemy=enemy, standalone=False,
                           event_log=collections.deque())
        self.calls.clear()   # drop the construction-time encounter sting
        return battle

    def test_battle_entry_plays_the_encounter_sting(self):
        engine = GameEngine(rng=random.Random(0))
        engine.start_new_game("Hero", "fighter")
        enemy = engine.content.enemies["cave_bear"].create_enemy()
        BattleApp(engine=engine, enemy=enemy, standalone=False,
                  event_log=collections.deque())
        self.assertIn("encounter", self.calls)

    def test_base_attack_is_castless_its_sound_is_the_hit(self):
        battle = self._battle()
        battle._play_resolution_sfx(_resolution(components=((12, "physical"),)))
        self.assertEqual(self.calls, ["hit_enemy"])

    def test_enemy_damage_lands_as_get_hit(self):
        battle = self._battle()
        battle._play_resolution_sfx(_resolution(
            actor="Cave Bear", action_id="maul", rolled="", components=((9, "physical"),)))
        self.assertEqual(self.calls, ["get_hit"])

    def test_player_fireball_casts_then_hits(self):
        battle = self._battle()
        battle._play_resolution_sfx(_resolution(
            action_id="fireball", rolled="", components=((14, "fire"),)))
        self.assertEqual(self.calls, ["magic_cast", "hit_enemy"])

    def test_miss_plays_the_cast_but_no_impact(self):
        battle = self._battle()
        battle._play_resolution_sfx(_resolution(action_id="fireball", rolled="", components=()))
        self.assertEqual(self.calls, ["magic_cast"])

    def test_potion_gulps_and_nothing_else(self):
        battle = self._battle()
        battle._play_resolution_sfx(_resolution(
            action_id="use_hp_potion", rolled="", healing=25))
        self.assertEqual(self.calls, ["health_pot"])

    def test_skill_heal_chimes(self):
        battle = self._battle()
        battle._play_resolution_sfx(_resolution(
            action_id="lesser_heal", rolled="", healing=7))
        self.assertEqual(self.calls, ["heal"])

    def test_blocked_resolution_stays_silent(self):
        battle = self._battle()
        battle._play_resolution_sfx(_resolution(blocked=True, components=((5, "physical"),)))
        self.assertEqual(self.calls, [])

    def test_dot_tick_step_plays_the_low_tick(self):
        battle = self._battle()
        battle._sequence = [(["Hero took 3 poison damage from Venom."], None)]
        battle._seq_finale = None
        battle._advance_step()
        self.assertEqual(self.calls, ["DoT"])

    def test_flushed_rounds_play_no_per_step_sfx(self):
        battle = self._battle()
        battle._sequence = [
            ([], _resolution(components=((12, "physical"),))),
            (["Hero took 3 poison damage from Venom."], None),
        ]
        battle._seq_finale = None
        battle.flush_sequence()
        self.assertEqual(self.calls, [])

    def test_defeat_finale_plays_the_death_knell(self):
        battle = self._battle()
        battle._finish_result(combat.CombatTurnResult(outcome="defeat"), False)
        self.assertIn("die", self.calls)

    def test_level_up_rides_the_victory_finale(self):
        battle = self._battle()
        battle._finish_result(
            combat.CombatTurnResult(outcome="victory", levels_gained=1), False)
        self.assertIn("level_up", self.calls)

    def test_plain_victory_has_no_level_ding(self):
        battle = self._battle()
        battle._finish_result(
            combat.CombatTurnResult(outcome="victory", levels_gained=0), False)
        self.assertNotIn("level_up", self.calls)


@unittest.skipUnless(HAVE_OVERWORLD, "pygame/pytmx not installed")
class MusicSliderTests(unittest.TestCase):
    """B69: the settings-overlay volume slider — geometry-to-volume mapping,
    live application, and that the settings screen registers the bar."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.app = OverworldApp()

    @classmethod
    def tearDownClass(cls):
        audio._reset()
        pygame.quit()

    def test_settings_overlay_registers_the_slider_bar(self):
        prior = self.app.overlay
        self.app.overlay = "settings"
        try:
            self.app.draw()
            self.assertIsNotNone(self.app._music_slider_rect)
            self.assertGreater(self.app._music_slider_rect.width, 0)
        finally:
            self.app.overlay = prior

    def test_slider_x_maps_to_0_100_clamped_and_applies_live(self):
        app = self.app
        audio._reset()
        audio.init()
        app._music_slider_rect = pygame.Rect(100, 0, 200, 20)
        app._set_music_volume_from_x(200)                     # the middle = 50
        self.assertAlmostEqual(app._settings["sound_music"], 0.5, places=2)
        master = float(app._settings.get("sound_master", 1.0))
        self.assertAlmostEqual(audio._music_volume,
                               master * 0.5 * audio.MUSIC_GAIN, places=3)
        app._set_music_volume_from_x(-50)                     # clamps left
        self.assertEqual(app._settings["sound_music"], 0.0)
        app._set_music_volume_from_x(999)                     # clamps right
        self.assertEqual(app._settings["sound_music"], 1.0)

    def test_slider_without_a_bar_is_a_noop(self):
        app = self.app
        app._music_slider_rect = None
        before = app._settings.get("sound_music")
        app._set_music_volume_from_x(500)
        self.assertEqual(app._settings.get("sound_music"), before)
