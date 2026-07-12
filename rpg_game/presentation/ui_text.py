"""Single source of truth for player-facing UI text (Pygame presentation).

All translatable copy — messages, banners, hints, menu/button labels, panel
titles, section headers and the overworld gate messages — lives here so the
game's language can be checked and changed in one place instead of being
scattered across data files and screen code.

Out of scope on purpose:
- Pure numeric formatting (HP/mana/XP bars, stat-table numbers) stays in the
  renderers; it carries no translatable prose.
- Engine-produced messages (rest/save/store/combat events) stay in core; the
  presentation just displays them.

Gate messages are referenced from rpg_game/data/maps/core_zone.json by
``message_key`` and resolved via ``GATE_MESSAGES`` / ``gate_message()``.
"""

from __future__ import annotations

# --- window captions -------------------------------------------------------

CAPTION_OVERWORLD = "Svantrenish RPG — Overworld"
CAPTION_BATTLE = "Svantrenish RPG — Battle"
CAPTION_CREATE = "Svantrenish RPG — Create character"
CAPTION_START = "Svantrenish RPG"

# --- start menu ------------------------------------------------------------

START_TITLE = "Svantrenish RPG"
START_NEW_GAME = "New game"
START_LOAD_GAME = "Load game"
START_QUIT = "Quit"

# --- overworld gates (referenced by core_zone.json message_key) ------------

GATE_MESSAGES = {
    "gate_north": "The road north isn't safe yet — more of the world opens later.",
    "gate_east": "Unknown lands lie to the east. Blocked for now.",
    "gate_south": "South beyond Hordanita's reaches isn't ready yet.",
    "gate_deep_west": "The far west is uncharted. More of the world opens later.",
    # The old gate_south is now open into Verralda; the frontier moved further
    # south to the heath's far edge.
    "gate_verralda_south": "Beyond the heath the land is still unfinished — more opens later.",
}

# Soft warning when crossing into the western wilderness (zone 2) — flavor, not
# a wall.
WEST_BORDER_FLAVOR = "The road west feels desolate. Few return unscathed."

# Per-region soft signal shown when first crossing into a non-core region.
REGION_FLAVOR = {
    "burg_121": "Southward the villages thin out — the heaths of Verralda begin.",
}


def region_flavor(region_id: str) -> str:
    """Soft border flavor for a region; western regions share the desolate line."""
    return REGION_FLAVOR.get(region_id, WEST_BORDER_FLAVOR)


def gate_message(key: str) -> str:
    """Resolve a gate message key; fall back to the key itself if unknown."""
    return GATE_MESSAGES.get(key, key)


# --- overworld: HUD + hints ------------------------------------------------

HINT_TOWN = "Step to a building's door + Enter   C/I/K: panels   Esc: system"
HINT_WALK = "WASD/arrows to move   C/I/K: panels   Esc: system"
BUILDING_LOCKED = "This building seems to be locked."
BACK_TO_MAP = "Esc / Enter: back to map"
BACK = "Back"
BACK_KEY = "Esc"   # B106: hotkey renders as a badge chip, never "(Esc)"

# B106: the Controls table (settings) — (action, key) pairs rendered via
# ui.draw_controls_table; one source so hotkey hints never live in row labels.
CONTROLS = (
    ("Move", "WASD / arrows"),
    ("Interact", "E / Enter"),
    ("World map", "M"),
    ("Minimap", "N"),
    ("Bestiary", "B"),
    ("Character", "C"),
    ("Inventory", "I"),
    ("Skills & talents", "K"),
    ("Log size", "+ / -"),
    ("Scroll log", "PgUp / PgDn"),
    ("Fullscreen", "F11"),
    ("Menu / back", "Esc"),
)

# --- B65 zone bosses ---------------------------------------------------------

VICTORY_TITLE = "THE CURSE IS BROKEN"
VICTORY_LINES = (
    "The Pale Sovereign has fallen, and with it the curse over the land.",
    "The mire clears, the heath grows quiet, and the roads are safe again.",
    "",
    "Svantrenish RPG — by Lucas & Svante",
    "made with Claude",
    "",
    "The world remains yours to wander.",
)
VICTORY_CONTINUE = "Continue exploring"


def boss_challenge_prompt(name: str, level: int) -> str:
    return f"{name} (Lv {level}) lurks here. Press E again to challenge."


def wilds_near(place_name: str) -> str:
    return f"Wilds near {place_name}"


def near_direction(bearing: str, place_name: str) -> str:
    """Relative location near a town, e.g. 'south of Hordanita'."""
    return f"{bearing} of {place_name}"


# --- overworld: town menu --------------------------------------------------

# (action id, button label) — labels are player-facing.
TOWN_ACTIONS = [
    ("store", "Store"),
    ("rest", "Rest"),
    ("character", "Character"),
    ("inventory", "Inventory"),
    ("skills_talents", "Skills & Talents"),
    ("system", "System"),
]

SCREEN_TITLES = {
    "character": "Character",
    "inventory": "Inventory",
    "skills_talents": "Skills & Talents",
    "system": "System",
    "store": "Store",
    "tournaments": "Tournaments",
}

TOWN_TOURNAMENTS = "Tournaments"

# Per-building store titles (the trade buildings each open one category slice).
STORE_TITLES = {
    "weapons": "Blacksmith — Weapons",
    "armor": "Barracks — Armour",
    "general": "Shop — Goods",
}


def relocate_respawn_label(cost: int, already: bool = False) -> str:
    # B106: label + right-aligned value — no parenthetical help text.
    if already:
        return "Respawn point", "here"
    if cost <= 0:
        return "Set respawn here", "free"
    return "Move respawn here", f"{cost}g"
TOURNAMENT_SERIES_WARNING = (
    "Locked series: fights in a row, no flee or weapon swap mid-match, "
    "full HP/mana and equipment changes between matches, reward only after full victory."
)
TOURNAMENT_SERIES_WARNING_LINES = (
    "Locked series: fights in a row; no flee or weapon swap mid-match.",
    "Between matches: full HP/mana and equipment changes.",
    "Reward only after full victory.",
)
TOURNAMENT_START = "Start tournament"
TOURNAMENT_NEXT = "Next match"
TOURNAMENT_EQUIP = "Change equipment"
TOURNAMENT_NONE = "No tournaments here."
TOURNAMENT_REWARD_NONE = "no reward"

# --- overworld: toasts -----------------------------------------------------

NO_STORE = "No store in this town."
ALREADY_EQUIPPED = "Already equipped."
CANNOT_EQUIP = "Cannot equip that."


def equipped_weapon(name: str) -> str:
    return f"Equipped {name}."


def weapon_needs_level(name: str, level: int) -> str:
    return f"{name} needs level {level}."


# --- weapon type + preview (B4) -------------------------------------------
# Weapon "type" is the gameplay category (drives weapon-gated skills); it is the
# field abilities check, so it is the type the player needs to see.
WEAPON_CATEGORY_LABELS = {"melee": "Melee", "magic": "Magic", "ranged": "Ranged"}


def weapon_type(category: str) -> str:
    return WEAPON_CATEGORY_LABELS.get(category, category.title())


def weapon_label(weapon) -> str:
    """One-line inventory/character label exposing the weapon TYPE (category)
    alongside its damage, so a named weapon's type is no longer invisible."""
    return f"{weapon.name} ({weapon_type(weapon.category)}) +{weapon.damage_bonus} {weapon.damage_type}"


def weapon_preview(weapon) -> str:
    """Full stat preview for the selected weapon — type spelled out explicitly."""
    return (f"{weapon.name} — {weapon_type(weapon.category)} weapon, {weapon.damage_type} damage  "
            f"(+{weapon.damage_bonus} dmg · tier {weapon.tier} · needs Lv {weapon.required_level})")


def defeat_respawn(place_name: str) -> str:
    return f"You fell. You wake at {place_name}."


def victory_over(enemy_name: str) -> str:
    return f"You defeated the {enemy_name}."


def fled_from(enemy_name: str) -> str:
    return f"You fled from the {enemy_name}."


# --- overworld: sub-screen copy -------------------------------------------

INV_HEADER_CONSUMABLES = "Consumables:"
INV_HEADER_MISC = "Miscellaneous:"
INV_HEADER_WEAPONS = "Weapons:"
INV_NONE = "  none"
# B40 S2: the old INVENTORY_HINT/EQUIP_HINT header strings are gone — the menu
# spec bans redundant subheaders (point 5); the hover tooltips explain instead.
INV_CATEGORY_LABELS = {
    "consumables": "Consumables",
    "miscellaneous": "Miscellaneous",
    "weapon": "Weapons",
    "head": "Head",
    "chest": "Chest",
    "hands": "Hands",
    "legs": "Legs",
    "feet": "Feet",
    "amulet": "Amulet",
    "ring": "Ring",
}
NO_SKILLS = "No skills unlocked yet — learn talents first."

# B40 S4: hover explanations for the character screen's stat grid. The Wisdom
# line reads the core constant so the copy can never drift from the rule.
def _mana_per_wisdom() -> int:
    from rpg_game.core.entities import MANA_PER_WISDOM
    return MANA_PER_WISDOM

STAT_HELP = {
    "max_hp": "Hit points. You fall at 0 — rest, potions and level-ups restore them.",
    "max_mana": "Your mana pool, derived from Wisdom. Skills and spells spend it.",
    "wisdom": "Each point of Wisdom grants {mana} max mana.",
    "damage": ("Your attacks and weapon-gated skills scale with this Power "
               "plus your equipped weapon's damage bonus."),
    "armor": ("Reduces physical damage taken. Other damage types check your "
              "resistances instead."),
    "speed": "Decides turn order — the faster side acts first.",
    "crit_chance": ("Chance to crit. A crit raises the top of your damage "
                    "range instead of doubling the hit."),
}


def stat_help(stat: str) -> str:
    text = STAT_HELP.get(stat, "")
    return text.format(mana=_mana_per_wisdom()) if "{mana}" in text else text


STORE_BUY = "Buy"
STORE_SELL = "Sell"
NO_TALENTS = "No talents available to learn right now."
SYSTEM_HINT = "Save is available anywhere in the overworld."
SYSTEM_SAVE = "Save"
SYSTEM_QUIT = "Quit"


def skills_hint(equipped_count: int) -> str:
    # Short — the hint must fit its 220px skills column (B78 collision fix).
    # B106: short enough for the 220px column — no mid-word "click to..." cut.
    return f"Equipped {equipped_count}/4"


def store_hint(gold: int) -> str:
    return f"Gold: {gold} — click to buy or sell one"


def talents_hint(points: int) -> str:
    return f"Talent points: {points} — click to learn."


# --- battle: panels --------------------------------------------------------

PANEL_ENEMY = "ENEMY"
PANEL_PLAYER = "YOU"
PANEL_LOG = "COMBAT LOG"
PANEL_ACTIONS = "ACTIONS"

UNIDENTIFIED = "Unidentified — use Identify to reveal stats"
NOTHING_AVAILABLE = "Nothing available."
NEXT_ENEMY_HINT = "Click / Space → next enemy"
QUIT_HINT = "Press Esc to quit"

# (label, hotkey) for the combat action bar.
ACTION_ATTACK = ("Attack", "a")
ACTION_SKILL = ("Skill", "s")
ACTION_ITEM = ("Item", "i")
ACTION_SWAP = ("Swap", "w")
ACTION_IDENTIFY = ("Identify", "d")
ACTION_FLEE = ("Flee", "f")

# --- battle: banners + log -------------------------------------------------

NO_ENEMIES = "No enemies here."
FLED_BANNER = "You fled the battle."
VICTORY_LOG = "Victory!"
VICTORY_NEXT = "Victory! Click to fight the next enemy."
DEFEATED_LOG = "You have been defeated."
DEFEAT_BANNER = "Defeat. Press Esc to quit."
LEVELUP_RESOLVED = "Level up resolved. Click to fight the next enemy."

# Single-battle result view (press to continue back to the overworld).
RESULT_VICTORY = "Victory! Press any key to continue."
RESULT_DEFEAT = "Defeated. Press any key to continue."
RESULT_FLED = "Fled. Press any key to continue."
CONTINUE_HINT = "Press any key / click to continue"

# --- battle: level-up choice ----------------------------------------------

LEVELUP_TITLE = "LEVEL UP — choose a bonus"
# B35: pick a main stat at level-up (no speed). Main +8/+8/+4/+4; all others get
# their baseline (+2/+2/+1/+1).
STAT_CHOICES = [("+8 max HP", "hp"), ("+1 Wisdom (+5 Mana)", "wisdom"),
                ("+4 damage", "damage"), ("+4 crit", "crit")]
LEVELUP_PROMPT = "Level up! Choose a main stat."


def appears(article: str, enemy_name: str) -> str:
    if not article:   # B65: named bosses carry no article ("Rotfang ... appears!")
        return f"{enemy_name} appears!"
    return f"{article.capitalize()} {enemy_name} appears!"


def xp_gain(amount: int) -> str:
    return f"+{amount} XP"


def gold_gain(amount: int) -> str:
    return f"+{amount} gold"


# --- character creation ----------------------------------------------------

CREATE_TITLE = "Create your character"
CREATE_NAME_LABEL = "Name:"
CREATE_PICK_CLASS = "Pick a class:"
CREATE_START = "Start"
CREATE_START_KEY = "Enter"
# B40 S5: starter-skill choice + read-only tree preview.
CREATE_STARTER_LABEL = "Choose a starting talent (click, or Left/Right):"
CREATE_TREE_LABEL = "Talent tree (hover a talent to read it):"


def unknown_class(class_id: str, valid: str) -> str:
    return f"Unknown class '{class_id}'. Choose one of: {valid}"
