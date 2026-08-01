"""B140: a portrait strip carries its own frame count, and the rails that enforce it.

The bug: Mirr's idle strips hold 4 frames (1024x340) and her talk strips 6
(1536x340). A hardcoded 4 cut the talk strip into four 384px slices of one and a
half mouths each — no crash, just a subtly wrong animation nobody notices in
review. B109's 4-frame contract is about ENEMIES, not portraits.

The measured surprise, and the reason this file exists: DIVISIBILITY ALONE CANNOT
CATCH THAT BUG. 1536 / 4 = 384 exactly, so declaring 4 on a 6-frame strip passes a
width % count check perfectly. Two more rails do catch it, and both are tested here
against the real art.
"""

import dataclasses
import json
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from rpg_game.core import characters
from rpg_game.core.data_loader import PORTRAIT_DIR, load_content

try:
    import pygame

    from rpg_game.presentation import battle_choreo
    from rpg_game.presentation import pygame_dialogue as pd

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False

PORTRAITS = str(PORTRAIT_DIR)
MIRR_SHEETS = {
    "mirr_warm_idle_sheet.png": (1024, 340, 4),
    "mirr_warm_talk_sheet.png": (1536, 340, 6),
    "mirr_cold_idle_sheet.png": (1024, 340, 4),
    "mirr_cold_talk_sheet.png": (1536, 340, 6),
}


def _state(sid, flag="", **kwargs):
    return characters.CharacterState(id=sid, requires_quest_flag=flag, **kwargs)


def _character(cid="who", states=None, **kwargs):
    fields = dict(id=cid, name=cid.title(), home_place_id="burg_5",
                  home_building="inn",
                  states=tuple(states if states is not None else [_state("only")]))
    fields.update(kwargs)
    return characters.Character(**fields)


class ShippedArtTests(unittest.TestCase):
    """Whether Mirr's files were in the repo at run time — asserted, not assumed."""

    @classmethod
    def setUpClass(cls):
        cls.content = load_content()

    def test_mirrs_four_strips_are_in_the_repo(self):
        for name in MIRR_SHEETS:
            self.assertTrue(os.path.exists(os.path.join(PORTRAITS, name)), name)

    def test_each_strip_is_the_size_the_data_claims(self):
        for name, (width, height, count) in MIRR_SHEETS.items():
            size = characters._png_size(os.path.join(PORTRAITS, name))
            self.assertEqual(size, (width, height), name)
            self.assertEqual(width % count, 0, name)
            self.assertEqual(width // count, 256, name)     # same face, same scale

    def test_the_declared_counts_are_four_idle_and_six_talk(self):
        for state in characters.character_by_id(self.content, "mirr").states:
            self.assertEqual(state.portrait_idle_frames, 4, state.id)
            self.assertEqual(state.portrait_talk_frames, 6, state.id)

    def test_the_shipped_content_trips_no_rail(self):
        self.assertEqual(characters.portrait_sheet_problems(
            self.content.characters, PORTRAITS), ())


class RailTests(unittest.TestCase):
    """Each rail, against the REAL art, so the numbers are not invented."""

    @classmethod
    def setUpClass(cls):
        cls.content = load_content()

    def _problems(self, idle_n, talk_n, states=("warm",)):
        person = _character("mirr", states=[
            _state(sid, "" if i == 0 else f"f{i}",
                   portrait_idle_sheet=f"mirr_{sid}_idle_sheet.png",
                   portrait_talk_sheet=f"mirr_{sid}_talk_sheet.png",
                   portrait_idle_frames=idle_n, portrait_talk_frames=talk_n)
            for i, sid in enumerate(states)])
        return characters.portrait_sheet_problems((person,), PORTRAITS)

    def test_the_correct_counts_pass(self):
        self.assertEqual(self._problems(4, 6), ())

    def test_divisibility_alone_would_have_MISSED_the_real_bug(self):
        # The finding this slice turns on: 1536 / 4 = 384 exactly.
        self.assertEqual(1536 % 4, 0)
        self.assertEqual(1536 % 6, 0)

    def test_the_real_bug_is_caught_anyway(self):
        problems = self._problems(4, 4)         # talk declared 4 on a 6-frame strip
        self.assertTrue(problems)
        joined = " ".join(problems)
        self.assertIn("mirr_warm_talk_sheet.png", joined)
        self.assertIn("384", joined)            # the wrong frame width
        self.assertIn("portrait_talk_frames", joined)

    def test_a_landscape_frame_is_refused(self):
        problems = self._problems(4, 4)
        self.assertTrue(any("WIDER than tall" in p for p in problems))

    def test_strips_disagreeing_on_frame_width_are_refused(self):
        # Rail 2, isolated: 1024/4 = 256 but 1536/4 = 384 for the same face.
        problems = self._problems(4, 4)
        self.assertTrue(any("disagree on frame width" in p for p in problems))

    def test_a_fractional_frame_width_is_refused(self):
        problems = self._problems(4, 5)         # 1536 / 5 = 307.2
        self.assertTrue(any("does not divide" in p for p in problems))
        self.assertTrue(any("307.20" in p for p in problems))

    def test_a_single_strip_character_is_still_covered(self):
        # Rail 2 has nothing to compare, so rail 3 has to carry it.
        person = _character("solo", states=[_state(
            "only", portrait_talk_sheet="mirr_warm_talk_sheet.png",
            portrait_talk_frames=4)])
        problems = characters.portrait_sheet_problems((person,), PORTRAITS)
        self.assertTrue(any("WIDER than tall" in p for p in problems))

    def test_an_absent_strip_is_not_a_problem(self):
        # Missing art degrades to a placeholder; that is not this rail's business.
        person = _character("ghost", states=[_state(
            "only", portrait_idle_sheet="does_not_exist.png",
            portrait_idle_frames=7)])
        self.assertEqual(characters.portrait_sheet_problems((person,), PORTRAITS), ())

    def test_a_non_png_is_reported_not_crashed_on(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            with open(os.path.join(folder, "fake.png"), "wb") as handle:
                handle.write(b"definitely not a png")
            person = _character("x", states=[_state(
                "only", portrait_idle_sheet="fake.png", portrait_idle_frames=4)])
            problems = characters.portrait_sheet_problems((person,), folder)
            self.assertTrue(any("unreadable" in p for p in problems))


class LoadTimeRailTests(unittest.TestCase):
    """The rail must stop the START, with the filename and the numbers."""

    @classmethod
    def setUpClass(cls):
        cls.content = load_content()

    def _validate(self, idle_n, talk_n):
        person = _character("mirr", states=[_state(
            "warm", portrait_idle_sheet="mirr_warm_idle_sheet.png",
            portrait_talk_sheet="mirr_warm_talk_sheet.png",
            portrait_idle_frames=idle_n, portrait_talk_frames=talk_n)])
        content = dataclasses.replace(self.content, quests=())
        characters.validate_characters((person,), content, portrait_dir=PORTRAITS)

    def test_the_correct_counts_validate(self):
        self._validate(4, 6)

    def test_a_mis_declared_count_refuses_to_start(self):
        with self.assertRaises(ValueError) as caught:
            self._validate(4, 4)
        message = str(caught.exception)
        self.assertIn("mis-declared", message)
        self.assertIn("mirr_warm_talk_sheet.png", message)   # the filename...
        self.assertIn("340", message)                        # ...and the numbers

    def test_the_shipped_data_starts_with_the_rail_live(self):
        # load_content() ran in setUpClass and passes the dir, so this proves the
        # rail is WIRED, not merely available.
        import inspect
        from rpg_game.core import data_loader
        source = inspect.getsource(data_loader.load_content)
        self.assertIn("portrait_dir=", source)

    def test_omitting_the_dir_skips_the_file_check(self):
        # Hand-built test/sim content has no assets and must still validate.
        person = _character("mirr", states=[_state(
            "warm", portrait_idle_sheet="mirr_warm_idle_sheet.png",
            portrait_idle_frames=999)])
        characters.validate_characters((person,), dataclasses.replace(
            self.content, quests=()))

    def test_a_non_positive_count_is_still_refused(self):
        for bad in (0, -1):
            with self.assertRaisesRegex(ValueError, "need >= 1"):
                characters.validate_characters(
                    (_character("x", states=[_state("only", portrait_idle_frames=bad)]),),
                    dataclasses.replace(self.content, quests=()))


class DataFileTests(unittest.TestCase):
    def test_characters_json_declares_a_count_beside_every_sheet(self):
        with open(os.path.join("rpg_game", "data", "characters.json"),
                  encoding="utf-8") as handle:
            data = json.load(handle)
        for character in data["characters"]:
            for state in character["states"]:
                for kind in ("idle", "talk"):
                    if state.get(f"portrait_{kind}_sheet"):
                        self.assertIn(f"portrait_{kind}_frames", state,
                                      f"{character['id']}/{state['id']} {kind}")

    def test_an_omitted_count_defaults_to_four(self):
        parsed = characters.parse_characters({"characters": [{
            "id": "c", "name": "C", "home_place_id": "burg_5", "home_building": "inn",
            "states": [{"id": "only", "portrait_idle_sheet": "x.png"}]}]})
        self.assertEqual(parsed[0].states[0].portrait_idle_frames, 4)
        self.assertEqual(parsed[0].states[0].portrait_talk_frames, 4)


@unittest.skipUnless(DEPS_OK, "pygame not installed")
class SlicingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))
        cls.content = load_content()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        pd._reset_portrait_cache()

    def test_a_six_frame_strip_yields_six_frames_at_the_right_width(self):
        frames = pd.portrait_frames("mirr_warm_talk_sheet.png", 6)
        self.assertEqual(len(frames), 6)
        # 256x340 source scaled to PORTRAIT_HEIGHT keeps the 0.75 aspect.
        expected_w = round(256 * pd.PORTRAIT_HEIGHT / 340)
        for frame in frames:
            self.assertEqual(frame.get_size(), (expected_w, pd.PORTRAIT_HEIGHT))

    def test_a_four_frame_strip_yields_four_frames_at_the_same_width(self):
        idle = pd.portrait_frames("mirr_warm_idle_sheet.png", 4)
        talk = pd.portrait_frames("mirr_warm_talk_sheet.png", 6)
        self.assertEqual(len(idle), 4)
        # Same face, same scale: idle and talk frames must be identically sized.
        self.assertEqual(idle[0].get_size(), talk[0].get_size())

    def test_the_six_frames_are_actually_different_slices(self):
        frames = pd.portrait_frames("mirr_warm_talk_sheet.png", 6)
        blobs = [pygame.image.tostring(f, "RGBA") for f in frames]
        # The strip is authored as a mirror (0=5, 1=4, 2=3), so there are three
        # distinct images across six frames — and NOT one image repeated.
        self.assertEqual(len(set(blobs)), 3)
        self.assertEqual(blobs[0], blobs[5])
        self.assertEqual(blobs[1], blobs[4])
        self.assertEqual(blobs[2], blobs[3])

    def test_slicing_as_four_would_have_produced_landscape_frames(self):
        # What the bug looked like, pinned so the shape of it is on record.
        wrong = pd.portrait_frames("mirr_warm_talk_sheet.png", 4)
        self.assertEqual(len(wrong), 4)
        source_aspect = (1536 / 4) / 340
        self.assertGreater(source_aspect, 1.0)        # landscape = a mis-slice

    def test_a_count_the_width_does_not_divide_is_refused(self):
        self.assertIsNone(pd.portrait_frames("mirr_warm_talk_sheet.png", 5))
        self.assertIsNone(pd.portrait_frames("mirr_warm_talk_sheet.png", 0))
        self.assertIsNone(pd.portrait_frames("mirr_warm_talk_sheet.png", -3))

    def test_the_count_is_required_so_no_hardcoded_four_can_leak(self):
        import inspect
        signature = inspect.signature(pd.portrait_frames)
        self.assertEqual(signature.parameters["count"].default,
                         inspect.Parameter.empty)

    def test_the_cache_keys_on_the_count_too(self):
        four = pd.portrait_frames("mirr_warm_idle_sheet.png", 4)
        five = pd.portrait_frames("mirr_warm_idle_sheet.png", 5)   # 1024/5 -> refused
        self.assertEqual(len(four), 4)
        self.assertIsNone(five)
        self.assertEqual(len(pd.portrait_frames("mirr_warm_idle_sheet.png", 4)), 4)


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class PlaybackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _app(self, flags=()):
        import random
        from rpg_game.core.game import GameEngine
        engine = GameEngine(content=load_content(), rng=random.Random(0))
        engine.start_new_game("Hero", "fighter")
        engine.player.quest_flags |= set(flags)
        return pd.DialogueApp(engine, engine.character_at("burg_5", "inn"))

    def test_the_talk_loop_runs_straight_through_and_wraps(self):
        # 0..N-1 in order, then back to 0 — no pendulum derived in code, because
        # the strip already authors its own mirror.
        app = self._app()
        self.assertTrue(app.is_typing)
        step = battle_choreo.frames(pd.PORTRAIT_TALK_FRAME_MS)
        seen = []
        for _ in range(step * 7):
            app.update()
            if not app.is_typing:
                break
            index = app.portrait_frame_index()
            if not seen or seen[-1] != index:
                seen.append(index)
        self.assertEqual(seen[:6], [0, 1, 2, 3, 4, 5])
        if len(seen) > 6:
            self.assertEqual(seen[6], 0)          # wrapped

    def test_the_idle_loop_reads_as_a_pendulum_from_the_strip_itself(self):
        app = self._app()
        app.skip_typing()
        self.assertFalse(app.is_typing)
        frames = pd.portrait_frames(*app.current_portrait())
        blobs = [pygame.image.tostring(f, "RGBA") for f in frames]
        # Frame 3 is byte-identical to frame 1, so a plain 0-1-2-3 loop plays
        # A-B-C-B — B109's pendulum, authored rather than derived.
        self.assertEqual(blobs[1], blobs[3])
        self.assertNotEqual(blobs[0], blobs[1])
        self.assertNotEqual(blobs[1], blobs[2])

    def test_the_rest_pose_is_shared_so_idle_and_talk_meet_seamlessly(self):
        app = self._app()
        talk = pd.portrait_frames(*app.current_portrait())
        app.skip_typing()
        idle = pd.portrait_frames(*app.current_portrait())
        self.assertEqual(pygame.image.tostring(talk[0], "RGBA"),
                         pygame.image.tostring(idle[0], "RGBA"))

    def test_both_strip_lengths_play_at_the_same_cadence(self):
        # THE point of per-frame timing: a 4- and a 6-frame strip advance at the
        # same rate, so no future strip length silently re-times the animation.
        self.assertEqual(battle_choreo.frames(pd.PORTRAIT_TALK_FRAME_MS), 11)
        self.assertAlmostEqual(11 * battle_choreo.MS_PER_FRAME, 183, delta=1)

    def test_the_idle_cadence_is_unchanged_from_before_b140(self):
        # The old cycle constant was 900 ms over 4 frames = 13 ticks per frame.
        self.assertEqual(battle_choreo.frames(pd.PORTRAIT_IDLE_FRAME_MS), 13)

    def test_the_talk_cycle_visits_every_frame_and_idle_every_frame(self):
        app = self._app()
        talking = set()
        for _ in range(800):
            app.update()
            if app.is_typing:
                talking.add(app.portrait_frame_index())
        self.assertEqual(talking, {0, 1, 2, 3, 4, 5})
        app.skip_typing()
        idling = set()
        for _ in range(800):
            app.update()
            idling.add(app.portrait_frame_index())
        self.assertEqual(idling, {0, 1, 2, 3})

    def test_a_stateless_screen_asks_for_no_frames(self):
        app = self._app()
        app.state = None
        self.assertEqual(app.current_portrait(), ("", 0))
        self.assertEqual(app.portrait_frame_index(), 0)
        app.draw()                                # placeholder, no crash


if __name__ == "__main__":
    unittest.main()
