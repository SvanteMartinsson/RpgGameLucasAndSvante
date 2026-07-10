"""B69: the sound engine — SFX playback for the pygame presentation layer.

Graceful by design: if the mixer cannot initialize (no audio device, a broken
driver, CI) the module drops into silent mode and every ``play()`` is a no-op —
audio must never crash or block the game. Under ``SDL_AUDIODRIVER=dummy`` the
mixer initializes and "plays" silently, so headless tests exercise the real
code path.

WAVs live in ``rpg_game/assets/sounds/`` and load lazily on first play, cached
for the process lifetime. Volume comes from the B70 settings file
(``sound_master`` × ``sound_sfx``), sampled at ``init()``; per-sound gains in
``GAIN`` keep the deliberately quiet effects (walk, DoT) quiet.

The walk sound owns a reserved channel: a new step replaces the previous one
instead of stacking, and rapid steps can never starve the combat sounds of
free channels.

Background music (the first .ogg in the same dir) streams on
``pygame.mixer.music`` — a separate stream from the SFX channels. Every shell
calls ``ensure_music()`` at init; it is idempotent, so the loop carries
straight through creation -> overworld -> battle without restarting.

This module also owns the two SFX *naming rules* the screens share — which
drink sound a consumable makes and which cast sound a skill makes — so the
mapping is tuned in one place. It knows content dataclass shapes, never game
rules.
"""

from __future__ import annotations

import os

import pygame

from rpg_game.presentation import settings as user_settings

SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "sounds")

# Per-sound gain shaping (1.0 = as authored). The spec calls for walk and DoT
# to sit low in the mix; tune here, not at the call sites.
GAIN = {
    "walk": 0.35,
    "DoT": 0.45,
}

# Background music streams on pygame.mixer.music — a separate stream that
# never competes with the SFX channels. One authored-level gain keeps the
# loop under the effects; the user knob is sound_master × sound_music.
# 0.48 = the original 0.6 dropped 20% on Lucas's listening pass.
MUSIC_GAIN = 0.48

_NUM_CHANNELS = 16      # headroom so a busy round never drops a sound
_WALK_CHANNEL = 0       # reserved: steps replace each other, never stack

_attempted = False      # mixer init tried (success or not) — try only once
_ready = False          # mixer is live; False = silent mode
_cache: dict[str, "pygame.mixer.Sound | None"] = {}
_volume = 1.0           # master × sfx, sampled from settings at init()
_music_volume = MUSIC_GAIN   # master × music × MUSIC_GAIN
_music_path: "str | None" = None   # the track currently looping (None = none)


def init() -> bool:
    """Bring the mixer up (idempotent). Returns True when sound is live.

    Called by the shells after ``pygame.init()`` and lazily by ``play()``, so
    no caller ever needs to check. Failure of any kind means silent mode."""
    global _attempted, _ready, _volume
    if _attempted:
        return _ready
    _attempted = True
    try:
        if pygame.mixer.get_init() is None:
            pygame.mixer.init()
        pygame.mixer.set_num_channels(_NUM_CHANNELS)
        pygame.mixer.set_reserved(_WALK_CHANNEL + 1)
        _ready = True
    except Exception:   # no device / no mixer module — the game plays silent
        _ready = False
    if _ready:
        reload_volume()
    return _ready


def reload_volume() -> None:
    """Re-read the B70 volumes (master × sfx for effects, master × music for
    the loop) and re-apply them (there is no volume UI yet; the file is the
    knob)."""
    global _volume, _music_volume
    values = user_settings.load()
    master = _clamp(values.get("sound_master", 1.0))
    sfx = _clamp(values.get("sound_sfx", 1.0))
    music = _clamp(values.get("sound_music", 1.0))
    _volume = master * sfx
    _music_volume = master * music * MUSIC_GAIN
    for name, sound in _cache.items():
        if sound is not None:
            sound.set_volume(_volume * GAIN.get(name, 1.0))
    if _ready:
        try:
            pygame.mixer.music.set_volume(_music_volume)
        except Exception:   # pragma: no cover - music stream without mixer
            pass


def apply_music_volume(master, music) -> None:
    """Live update from the settings slider (no settings-file read) — the loop
    follows the drag in real time; the caller persists on mouse release."""
    global _music_volume
    _music_volume = _clamp(master) * _clamp(music) * MUSIC_GAIN
    if _ready:
        try:
            pygame.mixer.music.set_volume(_music_volume)
        except Exception:   # pragma: no cover - music stream without mixer
            pass


def play(name: str) -> None:
    """Fire-and-forget one SFX by name (filename without ``.wav``).

    Silent no-op when the mixer is down, the file is missing, or playback
    fails — sound must never take the game down with it."""
    if not init():
        return
    sound = _load(name)
    if sound is None:
        return
    try:
        if name == "walk":
            pygame.mixer.Channel(_WALK_CHANNEL).play(sound)
        else:
            sound.play()
    except Exception:   # pragma: no cover - device died mid-session
        pass


def music_track() -> "str | None":
    """The background track: the alphabetically first .ogg in the sounds dir
    (one track ships today; a per-context playlist is a later slice)."""
    try:
        names = sorted(n for n in os.listdir(SOUNDS_DIR) if n.lower().endswith(".ogg"))
    except OSError:
        return None
    return os.path.join(SOUNDS_DIR, names[0]) if names else None


def ensure_music() -> None:
    """Start the looping background music if it isn't already on. Idempotent —
    every shell (creation/overworld/battle) calls this at init, so the track
    carries straight through screen transitions instead of restarting.
    Dead mixer or no .ogg = silent no-op."""
    global _music_path
    if not init():
        return
    path = music_track()
    if path is None:
        return
    try:
        if _music_path == path and pygame.mixer.music.get_busy():
            return
        pygame.mixer.music.load(path)
        pygame.mixer.music.set_volume(_music_volume)
        pygame.mixer.music.play(-1)   # loop forever
        _music_path = path
    except Exception:   # unreadable/corrupt track -> the game plays without music
        _music_path = None


def _load(name: str) -> "pygame.mixer.Sound | None":
    if name in _cache:
        return _cache[name]
    path = os.path.join(SOUNDS_DIR, f"{name}.wav")
    sound = None
    try:
        if os.path.exists(path):
            sound = pygame.mixer.Sound(path)
            sound.set_volume(_volume * GAIN.get(name, 1.0))
    except Exception:   # unreadable/corrupt file -> stay silent for this name
        sound = None
    _cache[name] = sound
    return sound


def _clamp(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 1.0


def _reset() -> None:
    """Test hook: forget init state, cached sounds and the music loop."""
    global _attempted, _ready, _volume, _music_volume, _music_path
    _attempted = False
    _ready = False
    _volume = 1.0
    _music_volume = MUSIC_GAIN
    _music_path = None
    _cache.clear()
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass


# --- SFX naming rules (shared by battle + overworld) -------------------------

_DAMAGE_EFFECTS = {"instant_damage", "drain"}
_PHYSICALISH = {"physical", "weapon"}   # "weapon" inherits the equipped weapon


def potion_sound(item) -> str | None:
    """The drink SFX for a used item, by its effect: HP restores gulp as a
    health potion, mana restores as a mana potion, cure-only drinks (antidote)
    reuse the health gulp. Non-consumables (tomes) make no drink sound."""
    if item is None or getattr(item, "kind", "") != "consumable":
        return None
    if getattr(item, "heal_amount", 0):
        return "health_pot"
    if getattr(item, "mana_amount", 0):
        return "mana_pot"
    if getattr(item, "cures", ()):
        return "health_pot"
    return None


def cast_sound(action, is_player_actor: bool) -> str | None:
    """The cast SFX for a SKILL invocation (callers exclude the base attack):
    any non-physical damage — including DoT payloads — sounds magical from
    either side of the field; physical skills only announce the PLAYER's cast
    (an enemy's physical special just lands as the hit). Heal-only skills and
    pure buffs return None — the heal SFX / button click carries them."""
    if action is None:
        return None
    damage_types = set()
    for effect in action.effects:
        if effect.type in _DAMAGE_EFFECTS:
            damage_types.add(effect.damage_type)
        elif effect.type == "apply_status" and effect.magnitude and not effect.stat:
            damage_types.add(effect.damage_type)   # a DoT payload, not a stat buff
    if any(damage_type not in _PHYSICALISH for damage_type in damage_types):
        return "magic_cast"
    if damage_types and is_player_actor:
        return "physical_cast"
    return None
