"""B137: the background music cycles through every .ogg instead of looping one.

The interesting behaviour is a state machine over pygame.mixer.music, so most of
these drive `ensure_music()` with `get_busy()` stubbed — that is the poll the
pump reads, and stubbing it is the only way to make "the track ended" happen in a
test without waiting minutes for a real one.

The property that must NOT regress is idempotence: a screen transition calls
ensure_music() and the music has to carry through unchanged. B69 relied on that
and so does every shell hop.

Skips without pygame.
"""

import os
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame

    from rpg_game.presentation import audio
    from rpg_game.presentation import settings as user_settings

    HAVE_PYGAME = True
except Exception:  # pragma: no cover - import guard
    HAVE_PYGAME = False


@unittest.skipUnless(HAVE_PYGAME, "pygame not installed")
class PlaylistContentsTests(unittest.TestCase):
    def setUp(self):
        audio._reset()

    def tearDown(self):
        audio._reset()

    def test_the_playlist_holds_every_shipped_ogg(self):
        tracks = audio.music_tracks()
        names = [os.path.basename(path) for path in tracks]
        for expected in ("Pixel Heart.ogg", "moss_gate.ogg", "dark_forest.ogg"):
            self.assertIn(expected, names)
        self.assertGreaterEqual(len(tracks), 3)

    def test_the_order_is_deterministic_sorted_filenames(self):
        names = [os.path.basename(path) for path in audio.music_tracks()]
        self.assertEqual(names, sorted(names))
        # Two scans agree (and the second is served from the cache).
        self.assertEqual(audio.music_tracks(), audio.music_tracks())

    def test_the_starting_track_is_unchanged_from_the_single_track_era(self):
        # music_track() used to BE the whole feature; it must still name the
        # track a fresh session opens on.
        self.assertEqual(audio.music_track(), audio.music_tracks()[0])
        self.assertEqual(os.path.basename(audio.music_track()), "Pixel Heart.ogg")

    def test_an_empty_directory_is_a_silent_no_op(self):
        with tempfile.TemporaryDirectory() as empty:
            original = audio.SOUNDS_DIR
            audio.SOUNDS_DIR = empty
            try:
                audio._reset()
                self.assertEqual(audio.music_tracks(), ())
                self.assertIsNone(audio.music_track())
                audio.ensure_music()               # must not raise
                self.assertIsNone(audio._music_path)
            finally:
                audio.SOUNDS_DIR = original
                audio._reset()

    def test_an_unreadable_directory_is_not_cached_as_empty(self):
        original = audio.SOUNDS_DIR
        audio.SOUNDS_DIR = os.path.join(original, "no_such_subdir")
        try:
            audio._reset()
            self.assertEqual(audio.music_tracks(), ())
            self.assertIsNone(audio._playlist)     # left unset, so it can retry
        finally:
            audio.SOUNDS_DIR = original
            audio._reset()


@unittest.skipUnless(HAVE_PYGAME, "pygame not installed")
class PlaylistAdvanceTests(unittest.TestCase):
    """`get_busy` is stubbed so "the track ended" is expressible in a test."""

    def setUp(self):
        audio._reset()
        self.real_get_busy = pygame.mixer.music.get_busy
        self.busy = True

    def tearDown(self):
        pygame.mixer.music.get_busy = self.real_get_busy
        audio._reset()

    def _stub_busy(self):
        pygame.mixer.music.get_busy = lambda: self.busy

    def _current(self):
        return os.path.basename(audio._music_path) if audio._music_path else None

    def test_the_next_track_starts_when_the_previous_one_ends(self):
        self.assertTrue(audio.init())
        self._stub_busy()
        self.busy = False                 # nothing playing yet
        audio.ensure_music()
        first = self._current()
        self.assertIsNotNone(first)

        self.busy = False                 # the track ended
        audio.ensure_music()
        second = self._current()
        self.assertIsNotNone(second)
        self.assertNotEqual(second, first)

        self.busy = False
        audio.ensure_music()
        third = self._current()
        self.assertNotIn(third, (first, second))

    def test_the_playlist_wraps_around_to_the_start(self):
        self.assertTrue(audio.init())
        self._stub_busy()
        self.busy = False
        count = len(audio.music_tracks())
        seen = []
        for _ in range(count):
            audio.ensure_music()
            seen.append(self._current())
        self.assertEqual(len(set(seen)), count)      # every track, once
        audio.ensure_music()                         # one past the end
        self.assertEqual(self._current(), seen[0])   # back to the first

    def test_it_plays_the_whole_playlist_in_sorted_order(self):
        self.assertTrue(audio.init())
        self._stub_busy()
        self.busy = False
        expected = [os.path.basename(p) for p in audio.music_tracks()]
        played = []
        for _ in range(len(expected)):
            audio.ensure_music()
            played.append(self._current())
        self.assertEqual(played, expected)

    def test_a_screen_transition_does_not_restart_the_track(self):
        # THE regression guard. B69's idempotence must survive the playlist.
        self.assertTrue(audio.init())
        self._stub_busy()
        self.busy = False
        audio.ensure_music()
        playing = audio._music_path
        index = audio._playlist_index

        self.busy = True                  # a track is playing...
        for _ in range(200):              # ...and every shell hop / frame polls
            audio.ensure_music()
        self.assertEqual(audio._music_path, playing)
        self.assertEqual(audio._playlist_index, index)

    def test_a_track_that_will_not_load_is_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            good = os.path.join(folder, "b_good.ogg")
            bad = os.path.join(folder, "a_bad.ogg")
            with open(bad, "wb") as handle:
                handle.write(b"this is not an ogg stream")
            # A real, loadable ogg copied out of the shipped assets.
            with open(audio.music_tracks()[0], "rb") as src, open(good, "wb") as dst:
                dst.write(src.read())

            original = audio.SOUNDS_DIR
            audio.SOUNDS_DIR = folder
            try:
                audio._reset()
                self.assertTrue(audio.init())
                self._stub_busy()
                self.busy = False
                # a_bad sorts first; the pump must step over it to b_good.
                audio.ensure_music()
                self.assertEqual(self._current(), "b_good.ogg")
            finally:
                audio.SOUNDS_DIR = original
                audio._reset()

    def test_a_directory_of_only_broken_tracks_stays_silent_without_spinning(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ("a.ogg", "b.ogg"):
                with open(os.path.join(folder, name), "wb") as handle:
                    handle.write(b"not audio")
            original = audio.SOUNDS_DIR
            audio.SOUNDS_DIR = folder
            try:
                audio._reset()
                self.assertTrue(audio.init())
                self._stub_busy()
                self.busy = False
                audio.ensure_music()          # must return, not loop forever
                self.assertIsNone(audio._music_path)
            finally:
                audio.SOUNDS_DIR = original
                audio._reset()

    def test_a_volume_change_applies_to_the_next_track_immediately(self):
        self.assertTrue(audio.init())
        self._stub_busy()
        self.busy = False
        audio.apply_music_volume(0.5, 0.5)
        expected = 0.5 * 0.5 * audio.MUSIC_GAIN
        audio.ensure_music()                       # a NEW track starts here
        self.assertAlmostEqual(pygame.mixer.music.get_volume(), expected, delta=0.02)
        self.busy = False
        audio.ensure_music()                       # and so does the one after it
        self.assertAlmostEqual(pygame.mixer.music.get_volume(), expected, delta=0.02)

    def test_the_settings_volume_reaches_a_track_started_later(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "settings.json")
            with open(path, "w") as handle:
                handle.write('{"sound_master": 1.0, "sound_music": 0.25}')
            original = user_settings.SETTINGS_PATH
            user_settings.SETTINGS_PATH = path
            try:
                audio._reset()
                self.assertTrue(audio.init())
                self._stub_busy()
                self.busy = False
                audio.ensure_music()
                self.busy = False
                audio.ensure_music()               # the SECOND track
                self.assertAlmostEqual(pygame.mixer.music.get_volume(),
                                       0.25 * audio.MUSIC_GAIN, delta=0.02)
            finally:
                user_settings.SETTINGS_PATH = original
                audio._reset()


@unittest.skipUnless(HAVE_PYGAME, "pygame not installed")
class PumpWiringTests(unittest.TestCase):
    def test_both_shells_pump_the_playlist_from_their_run_loop(self):
        # The mechanism only works if the loops actually poll it.
        import inspect

        from rpg_game.presentation import pygame_battle

        self.assertIn("ensure_music", inspect.getsource(pygame_battle.BattleApp.run))
        self.assertIn("ensure_music", inspect.getsource(pygame_battle.character_creation))

    def test_the_overworld_pumps_the_playlist_too(self):
        import inspect
        try:
            from rpg_game.presentation.pygame_overworld import OverworldApp
        except Exception:                      # pragma: no cover - pytmx missing
            self.skipTest("pytmx not installed")
        self.assertIn("ensure_music", inspect.getsource(OverworldApp.run))

    def test_no_end_event_is_registered_on_the_music_stream(self):
        # The chosen mechanism is polling, so nothing may depend on an end event
        # reaching a shell's event loop — those loops discard unknown types, and a
        # dropped event would silently stop the playlist. Asserted on the mixer's
        # actual state rather than on the source text.
        audio._reset()
        try:
            self.assertTrue(audio.init())
            audio.ensure_music()
            self.assertEqual(pygame.mixer.music.get_endevent(), pygame.NOEVENT)
        finally:
            audio._reset()

    def test_a_track_is_started_once_so_the_playlist_can_advance(self):
        # play(-1) would never end and the list could never move on. Observed via
        # behaviour: once the stream reports idle, the index advances.
        audio._reset()
        real_get_busy = pygame.mixer.music.get_busy
        try:
            self.assertTrue(audio.init())
            pygame.mixer.music.get_busy = lambda: False
            audio.ensure_music()
            first = audio._playlist_index
            audio.ensure_music()
            self.assertEqual(audio._playlist_index,
                             (first + 1) % len(audio.music_tracks()))
        finally:
            pygame.mixer.music.get_busy = real_get_busy
            audio._reset()


if __name__ == "__main__":
    unittest.main()
