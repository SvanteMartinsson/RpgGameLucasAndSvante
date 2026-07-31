"""B139b: characters — the people stories come from, and their STATES.

Lucas's locked design: a character is not a quest dispenser, it is someone with a
CONDITION. Mirr is warm when you meet her and cold after her husband dies, and
that state drives three things at once: which portrait renders, what tone the
writing takes, and which lines she says. So state is in the data model from the
very first commit rather than bolted on when the story needs it.

STATE SELECTION — the last state whose condition holds, in authored order.
Authored order is STORY order, so a later state overrides an earlier one the
moment its flag lands, and the first state (which carries no condition) is the
standing fallback. That is why only the FIRST state may omit a condition: a
later condition-less state would always win and silently kill everything above
it, so `validate_characters` rejects it.

The condition is a `quest_flag`. That primitive already exists (B135a reward kind
`flag`), already persists in `player.quest_flags`, and was until now written but
never read — so character state needed NO new persistent player state and no
save migration.

PORTRAITS ARE NAMES HERE, NOT FILES. Core stores the sheet filename and never
touches the disk; the dialogue screen resolves it and falls back to a placeholder
when it is absent, exactly as B109's enemy sheets do. That is what lets this whole
slice ship before any art exists. `missing_portrait_sheets` REPORTS the gaps for a
test/tool so "no art yet" is visible and measured rather than silently forgotten.

Core purity: no print/input, no pygame, no file I/O, no rng.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from rpg_game.core.entities import GameContent, Player

# A quest whose giver is a person, not a board. Character quests are offered AT
# the character; the board keeps the impersonal work (bounties, odd jobs). That
# split is the design: STORIES COME FROM PEOPLE.
GIVER_CHARACTER = "character"


@dataclass(frozen=True)
class CharacterState:
    """One condition a character can be in."""
    id: str
    # Sheet FILENAMES (B109's 4-frame horizontal strip shape). Empty = this state
    # has no art yet and the screen draws its placeholder.
    portrait_idle_sheet: str = ""
    portrait_talk_sheet: str = ""
    # A short tone note the WRITER follows — it never renders. It lives in the data
    # so the state's voice travels with the state instead of in someone's head.
    voice_in_text: str = ""
    # The condition. "" = unconditional (only legal on the first state).
    requires_quest_flag: str = ""

    def holds_for(self, player: Player) -> bool:
        if not self.requires_quest_flag:
            return True
        return self.requires_quest_flag in player.quest_flags


@dataclass(frozen=True)
class Character:
    id: str
    name: str
    home_place_id: str
    home_building: str          # which door in that town opens onto them
    states: tuple[CharacterState, ...] = ()
    # Longer/formal name, for a line that wants it ("Miranda" vs "Mirr").
    full_name: str = ""

    def state_for(self, player: Player) -> "CharacterState | None":
        """The LAST state whose condition holds — see the module note."""
        chosen = None
        for state in self.states:
            if state.holds_for(player):
                chosen = state
        return chosen or (self.states[0] if self.states else None)


def parse_characters(data: dict) -> tuple[Character, ...]:
    """characters.json -> Character tuple. Shape errors raise here, at load."""
    out = []
    for row in data.get("characters", ()):
        states = tuple(
            CharacterState(
                id=str(state["id"]),
                portrait_idle_sheet=str(state.get("portrait_idle_sheet", "")),
                portrait_talk_sheet=str(state.get("portrait_talk_sheet", "")),
                voice_in_text=str(state.get("voice_in_text", "")),
                requires_quest_flag=str(state.get("requires_quest_flag", "")),
            )
            for state in row.get("states", ())
        )
        out.append(Character(
            id=str(row["id"]),
            name=str(row["name"]),
            home_place_id=str(row.get("home_place_id", "")),
            home_building=str(row.get("home_building", "")),
            states=states,
            full_name=str(row.get("full_name", "")),
        ))
    return tuple(out)


def validate_characters(characters: tuple[Character, ...], content: GameContent) -> None:
    """Load-time validation. A broken character is a story that cannot be told, so
    every one of these fails at startup with a name rather than going quiet.

    NOT validated here: whether a portrait file exists (that is presentation's
    business and degrades to a placeholder — see missing_portrait_sheets), and
    whether some quest actually grants a state's flag (the stories are still being
    written — see unwired_state_flags).
    """
    by_id: dict[str, Character] = {}
    for character in characters:
        if not character.id:
            raise ValueError("character with no id in characters.json")
        if character.id in by_id:
            raise ValueError(f"duplicate character id {character.id!r}")
        by_id[character.id] = character
        if not character.name:
            raise ValueError(f"character {character.id} has no name")
        places = getattr(content, "places", {})
        if places and character.home_place_id not in places:
            raise ValueError(f"character {character.id} lives in unknown place "
                             f"{character.home_place_id!r}")
        if not character.home_building:
            raise ValueError(f"character {character.id} has no home_building")
        if not character.states:
            raise ValueError(f"character {character.id} has no states — a character "
                             f"must have at least one condition to be in")
        seen_states: set[str] = set()
        for index, state in enumerate(character.states):
            if not state.id:
                raise ValueError(f"character {character.id} has a state with no id")
            if state.id in seen_states:
                raise ValueError(f"character {character.id} has two states "
                                 f"named {state.id!r}")
            seen_states.add(state.id)
            # Only the FIRST state may be unconditional; a later one would always
            # win (last-match-wins) and silently kill every state above it.
            if index > 0 and not state.requires_quest_flag:
                raise ValueError(
                    f"character {character.id} state {state.id!r} has no "
                    f"requires_quest_flag — only the first state may be "
                    f"unconditional, or it would always override the others")
            if index == 0 and state.requires_quest_flag:
                raise ValueError(
                    f"character {character.id} first state {state.id!r} is "
                    f"conditional — the first state is the fallback and must "
                    f"always hold")

    # Quests may only name a character that exists, and the two ways of saying
    # "this is a character quest" must agree.
    for quest in getattr(content, "quests", ()) or ():
        named = getattr(quest, "giver_character_id", "")
        if named and named not in by_id:
            raise ValueError(f"quest {quest.id} is given by unknown character "
                             f"{named!r}")
        if named and quest.giver_kind != GIVER_CHARACTER:
            raise ValueError(f"quest {quest.id} names character {named!r} but its "
                             f"giver_kind is {quest.giver_kind!r}, not "
                             f"{GIVER_CHARACTER!r}")
        if quest.giver_kind == GIVER_CHARACTER and not named:
            raise ValueError(f"quest {quest.id} has giver_kind "
                             f"{GIVER_CHARACTER!r} but names no character")


# --- soft reports (validate, but degrade) ------------------------------------

def missing_portrait_sheets(characters: tuple[Character, ...],
                            portrait_dir: str) -> tuple[str, ...]:
    """Sheet filenames a character declares that are NOT on disk.

    Reported, never raised: a missing portrait must draw the placeholder, not take
    the game down. This exists so "the art has not landed yet" is a measured fact
    a test can assert, instead of an omission nobody notices.
    """
    missing = []
    for character in characters:
        for state in character.states:
            for sheet in (state.portrait_idle_sheet, state.portrait_talk_sheet):
                if sheet and not os.path.exists(os.path.join(portrait_dir, sheet)):
                    missing.append(sheet)
    return tuple(missing)


def unwired_state_flags(characters: tuple[Character, ...],
                        content: GameContent) -> tuple[tuple[str, str, str], ...]:
    """(character_id, state_id, flag) for every state whose flag NO quest grants.

    An unreachable state, i.e. a story beat not written yet. Reported rather than
    raised on purpose: the machinery ships before the text, and this is the list
    that says what text is still owed.
    """
    granted = set()
    for quest in getattr(content, "quests", ()) or ():
        for reward in quest.rewards:
            if str(reward.get("kind", "")) == "flag":
                granted.add(str(reward.get("flag", "")))
    out = []
    for character in characters:
        for state in character.states:
            if state.requires_quest_flag and state.requires_quest_flag not in granted:
                out.append((character.id, state.id, state.requires_quest_flag))
    return tuple(out)


# --- lookups the shells share -------------------------------------------------

def character_by_id(content: GameContent, character_id: str) -> "Character | None":
    return next((c for c in getattr(content, "characters", ()) or ()
                 if c.id == character_id), None)


def character_at(content: GameContent, place_id: str,
                 building_id: str) -> "Character | None":
    """Whoever is behind this town door, if anyone."""
    for character in getattr(content, "characters", ()) or ():
        if character.home_place_id == place_id and character.home_building == building_id:
            return character
    return None


def quests_from(quests, character_id: str) -> list:
    """Every quest this character gives (any status)."""
    return [quest for quest in quests
            if getattr(quest, "giver_character_id", "") == character_id]
