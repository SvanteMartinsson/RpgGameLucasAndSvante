"""B73 S2 — FÖRSLAGS-presets (UTKAST, inte inkopplade i spelet).

Lucas väljer på morgonen vilka som ska in i ambience.PRESETS; tills dess läses
den här filen bara av render-/review-verktyg. Renders i docs/nightly/
(b73_preset_*.gif). Flytta en post till ambience.PRESETS för att aktivera den.
"""

# Zon -> förslag. Fälten tolkas av ambience.ParticleLayer (kind != "firefly"):
#   count, colors, size (min,max px-radie), vx/vy (min,max px/frame),
#   sway (min,max px sinus-svaj), alpha (0-255 kärnalfa).
DRAFT_PRESETS: dict[str, dict] = {
    # Varmt pollen/frön som seglar långsamt i sidvinden — ljus, vänlig zon.
    "cainos": {
        "kind": "drift", "count": 22,
        "colors": ((235, 225, 170), (210, 220, 150)),
        "size": (1, 2), "vx": (0.08, 0.3), "vy": (0.02, 0.12),
        "sway": (4, 10), "alpha": 80,
    },
    # Låg, drivande dis — stora mjuka fläckar som kryper vågrätt.
    "cursed_mire": {
        "kind": "mist", "count": 10,
        "colors": ((150, 170, 150), (130, 150, 140)),
        "size": (28, 48), "vx": (0.04, 0.14), "vy": (-0.01, 0.01),
        "sway": (2, 6), "alpha": 26,
    },
    # Aska/dammkorn som faller sakta med svaj; enstaka glödkorn.
    "grave_heath": {
        "kind": "fall", "count": 26,
        "colors": ((150, 145, 140), (120, 115, 110), (200, 120, 60)),
        "size": (1, 2), "vx": (-0.06, 0.06), "vy": (0.15, 0.4),
        "sway": (2, 7), "alpha": 100,
    },
}
