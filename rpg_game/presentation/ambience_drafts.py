"""B73 S2 — ambience preset drafts (HISTORICAL).

These three proposal presets (cainos pollen, cursed_mire haze, grave_heath ash)
were rendered to docs/nightly/b73_preset_*.gif for review and APPROVED by Lucas
(2026-07-12). They now live in ambience.PRESETS and are wired into the game;
this dict is kept as a record and re-derived from PRESETS so it can never drift.
New proposals for future zones can be drafted here again before wiring.
"""

from rpg_game.presentation import ambience

# The zones that were proposed here and are now live (drift/mist/fall kinds).
_APPROVED = ("cainos", "cursed_mire", "grave_heath")
DRAFT_PRESETS: dict[str, dict] = {
    zone: ambience.PRESETS[zone] for zone in _APPROVED if zone in ambience.PRESETS
}
