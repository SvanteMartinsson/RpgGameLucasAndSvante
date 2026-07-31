"""B139c: dialogue — the data model, the availability rules and the cursor.

What lives here is everything about a conversation that is NOT drawing: the
authored shape (scripts of nodes, nodes of lines and choices), which choices a
player may take and why not, and where in a script the conversation currently
stands. The screen owns only how much of the current line is painted.

SCRIPT SELECTION mirrors the character model: a script names a character and
optionally a STATE, so warm-Mirr and cold-Mirr are different scripts for the same
person and the state machinery (B139b) picks between them. A script with no
state_id is the fallback for every state.

VOICE-READY. Every line carries a stable `id`, and the voice path is derived from
it. Nothing about the line's position in the file is part of that id, so inserting
a line above a recorded one does not silently point its audio somewhere else. No
audio is authored yet; playback looks for the file and is silent when it is
absent (see presentation.audio.play_voice).

CHOICES CAN ACT. A choice may accept or hand in one of the character's quests —
that is what makes B139b's character-given quests reachable at all. The action is
declared in the data and executed by the engine through the ORDINARY quest
pipeline, never by a second implementation.

Core purity: no print/input, no pygame, no file I/O, no rng.
"""

from __future__ import annotations

from dataclasses import dataclass

# Who is speaking. The screen colours the name from this (GOLD npc / BLUE player).
NPC = "npc"
PLAYER = "player"
SPEAKERS = frozenset({NPC, PLAYER})

# What a choice DOES besides moving to another node.
ACTION_NONE = ""
ACTION_ACCEPT = "accept_quest"
ACTION_TURN_IN = "turn_in_quest"
ACTION_END = "end"
ACTIONS = frozenset({ACTION_NONE, ACTION_ACCEPT, ACTION_TURN_IN, ACTION_END})
QUEST_ACTIONS = frozenset({ACTION_ACCEPT, ACTION_TURN_IN})


@dataclass(frozen=True)
class DialogueLine:
    """One spoken line. `id` is the VOICE KEY and must never be renumbered."""
    id: str
    speaker: str
    text: str


@dataclass(frozen=True)
class DialogueChoice:
    id: str
    text: str
    next_node_id: str = ""          # "" + no action -> the conversation ends
    action: str = ACTION_NONE
    quest_id: str = ""              # for the quest actions
    requires_quest_flag: str = ""
    requires_level: int = 0
    # Authored explanation shown when the choice is dimmed. Empty -> a generated
    # one, so a gated choice always says WHY (the B112 pattern).
    unavailable_reason: str = ""


@dataclass(frozen=True)
class DialogueNode:
    id: str
    lines: tuple[DialogueLine, ...] = ()
    choices: tuple[DialogueChoice, ...] = ()


@dataclass(frozen=True)
class DialogueScript:
    id: str
    character_id: str
    start_node_id: str
    nodes: tuple[DialogueNode, ...] = ()
    state_id: str = ""              # "" = fallback for every state

    def node(self, node_id: str) -> "DialogueNode | None":
        return next((n for n in self.nodes if n.id == node_id), None)


# --- parsing -----------------------------------------------------------------

def parse_dialogue(data: dict) -> tuple[DialogueScript, ...]:
    """dialogue.json -> DialogueScript tuple. Shape errors raise here, at load."""
    scripts = []
    for row in data.get("scripts", ()):
        nodes = []
        for node in row.get("nodes", ()):
            lines = tuple(
                DialogueLine(id=str(line["id"]), speaker=str(line.get("speaker", NPC)),
                             text=str(line.get("text", "")))
                for line in node.get("lines", ())
            )
            choices = tuple(
                DialogueChoice(
                    id=str(choice["id"]),
                    text=str(choice.get("text", "")),
                    next_node_id=str(choice.get("next_node_id", "")),
                    action=str(choice.get("action", ACTION_NONE)),
                    quest_id=str(choice.get("quest_id", "")),
                    requires_quest_flag=str(choice.get("requires_quest_flag", "")),
                    requires_level=int(choice.get("requires_level", 0)),
                    unavailable_reason=str(choice.get("unavailable_reason", "")),
                )
                for choice in node.get("choices", ())
            )
            nodes.append(DialogueNode(id=str(node["id"]), lines=lines, choices=choices))
        scripts.append(DialogueScript(
            id=str(row["id"]),
            character_id=str(row["character_id"]),
            state_id=str(row.get("state_id", "")),
            start_node_id=str(row.get("start_node_id", "")),
            nodes=tuple(nodes),
        ))
    return tuple(scripts)


def validate_dialogue(scripts: tuple[DialogueScript, ...], content) -> None:
    """Load-time validation. A dialogue that dead-ends or points nowhere traps the
    player in a conversation, so every one of these fails at startup."""
    seen_scripts: set[str] = set()
    known_characters = {c.id for c in getattr(content, "characters", ()) or ()}
    known_quests = {q.id for q in getattr(content, "quests", ()) or ()}
    for script in scripts:
        if script.id in seen_scripts:
            raise ValueError(f"duplicate dialogue script id {script.id!r}")
        seen_scripts.add(script.id)
        if known_characters and script.character_id not in known_characters:
            raise ValueError(f"dialogue {script.id} belongs to unknown character "
                             f"{script.character_id!r}")
        character = next((c for c in getattr(content, "characters", ()) or ()
                          if c.id == script.character_id), None)
        if script.state_id and character is not None:
            if script.state_id not in {s.id for s in character.states}:
                raise ValueError(f"dialogue {script.id} targets unknown state "
                                 f"{script.state_id!r} of {script.character_id}")
        if not script.nodes:
            raise ValueError(f"dialogue {script.id} has no nodes")
        node_ids: set[str] = set()
        for node in script.nodes:
            if node.id in node_ids:
                raise ValueError(f"dialogue {script.id} has two nodes {node.id!r}")
            node_ids.add(node.id)
            if not node.lines and not node.choices:
                raise ValueError(f"dialogue {script.id} node {node.id!r} is empty")
        if script.start_node_id not in node_ids:
            raise ValueError(f"dialogue {script.id} starts at unknown node "
                             f"{script.start_node_id!r}")
        # Line ids are the VOICE KEYS: they must be unique across the whole script.
        line_ids: set[str] = set()
        for node in script.nodes:
            for line in node.lines:
                if not line.id:
                    raise ValueError(f"dialogue {script.id} has a line with no id")
                if line.id in line_ids:
                    raise ValueError(f"dialogue {script.id} reuses line id "
                                     f"{line.id!r} — line ids are voice keys "
                                     f"and must be unique")
                line_ids.add(line.id)
                if line.speaker not in SPEAKERS:
                    raise ValueError(f"dialogue {script.id} line {line.id} has "
                                     f"unknown speaker {line.speaker!r}")
                if not line.text.strip():
                    raise ValueError(f"dialogue {script.id} line {line.id} is empty")
        choice_ids: set[str] = set()
        for node in script.nodes:
            for choice in node.choices:
                if choice.id in choice_ids:
                    raise ValueError(f"dialogue {script.id} reuses choice id "
                                     f"{choice.id!r}")
                choice_ids.add(choice.id)
                if not choice.text.strip():
                    raise ValueError(f"dialogue {script.id} choice {choice.id} "
                                     f"has no text")
                if choice.action not in ACTIONS:
                    raise ValueError(f"dialogue {script.id} choice {choice.id} has "
                                     f"unknown action {choice.action!r}")
                if choice.next_node_id and choice.next_node_id not in node_ids:
                    raise ValueError(f"dialogue {script.id} choice {choice.id} "
                                     f"leads to unknown node "
                                     f"{choice.next_node_id!r}")
                if choice.action in QUEST_ACTIONS:
                    if not choice.quest_id:
                        raise ValueError(f"dialogue {script.id} choice {choice.id} "
                                         f"has action {choice.action} but no quest_id")
                    if known_quests and choice.quest_id not in known_quests:
                        raise ValueError(f"dialogue {script.id} choice {choice.id} "
                                         f"references unknown quest "
                                         f"{choice.quest_id!r}")
                elif choice.quest_id:
                    raise ValueError(f"dialogue {script.id} choice {choice.id} names "
                                     f"a quest but has no quest action")
        # A node with lines and no choices ENDS the conversation; that is fine. A
        # node with choices must be leaveable, which the checks above guarantee.


def script_for(scripts, character_id: str, state_id: str) -> "DialogueScript | None":
    """The script for a character in a state: an exact state match first, then the
    state-less fallback. None = this character has nothing to say yet."""
    exact = next((s for s in scripts
                  if s.character_id == character_id and s.state_id == state_id), None)
    if exact is not None:
        return exact
    return next((s for s in scripts
                 if s.character_id == character_id and not s.state_id), None)


# --- choice availability (the B112 pattern: dim + say why) --------------------

def choice_blocker(player, content, quests_module, all_quests, choice: DialogueChoice) -> str:
    """Why this choice cannot be taken right now ('' = it can).

    Returns a SENTENCE, because a dimmed choice that does not say why is worse
    than no choice at all. An authored `unavailable_reason` always wins, so a
    writer can phrase it in the character's voice.
    """
    reason = ""
    if choice.requires_quest_flag and choice.requires_quest_flag not in player.quest_flags:
        reason = "Not yet."
    elif choice.requires_level and player.level < choice.requires_level:
        reason = f"Requires level {choice.requires_level}."
    elif choice.action == ACTION_ACCEPT:
        quest = next((q for q in all_quests if q.id == choice.quest_id), None)
        if quest is None:
            reason = "That work is not available."
        elif not quests_module.is_offerable(player, quest, all_quests):
            reason = ("You are already on that." if
                      quests_module.status_of(player, quest.id) != quests_module.AVAILABLE
                      else "Not available yet.")
    elif choice.action == ACTION_TURN_IN:
        quest = next((q for q in all_quests if q.id == choice.quest_id), None)
        if quest is None:
            reason = "That work is not available."
        elif quests_module.status_of(player, quest.id) not in (quests_module.ACTIVE,
                                                              quests_module.COMPLETED):
            reason = "You are not on that."
        elif not quests_module.is_objective_met(player, content, quest):
            reason = "That is not finished yet."
    if not reason:
        return ""
    return choice.unavailable_reason or reason


# --- the cursor ---------------------------------------------------------------

class Conversation:
    """Where a conversation currently stands. Pure state, no rendering.

    The screen asks `current_line()` for what to paint and calls `advance()` when
    the player presses on; `pending_choices()` is non-empty exactly when the lines
    of a node have run out and the player must pick.
    """

    def __init__(self, script: DialogueScript, node_id: str = "") -> None:
        self.script = script
        self.node_id = node_id or script.start_node_id
        self.line_index = 0
        self.over = False
        # Every line the player has already heard, for the scrollable history.
        self.history: list[DialogueLine] = []
        self._enter_line()

    # -- reading ---------------------------------------------------------------

    def node(self) -> "DialogueNode | None":
        return self.script.node(self.node_id)

    def current_line(self) -> "DialogueLine | None":
        node = self.node()
        if node is None or self.over or self.line_index >= len(node.lines):
            return None
        return node.lines[self.line_index]

    def lines_remaining(self) -> bool:
        return self.current_line() is not None

    def pending_choices(self) -> tuple[DialogueChoice, ...]:
        """The choices to show — only once this node's lines are exhausted."""
        node = self.node()
        if node is None or self.over or self.lines_remaining():
            return ()
        return node.choices

    def awaiting_choice(self) -> bool:
        return bool(self.pending_choices())

    # -- moving ----------------------------------------------------------------

    def _enter_line(self) -> None:
        line = self.current_line()
        if line is not None and (not self.history or self.history[-1] is not line):
            self.history.append(line)

    def advance(self) -> bool:
        """Move to the next line. Returns False when there is nothing to advance to
        (the node is waiting on a choice, or the conversation is finished)."""
        node = self.node()
        if node is None or self.over:
            return False
        if self.line_index + 1 < len(node.lines):
            self.line_index += 1
            self._enter_line()
            return True
        # Out of lines: either the player picks, or the conversation is done.
        if not node.choices:
            self.line_index = len(node.lines)
            self.over = True
            return False
        self.line_index = len(node.lines)
        return False

    def goto(self, node_id: str) -> None:
        if not node_id:
            self.over = True
            return
        if self.script.node(node_id) is None:
            self.over = True
            return
        self.node_id = node_id
        self.line_index = 0
        self._enter_line()

    def choose(self, choice: DialogueChoice) -> None:
        """Follow a choice. The ACTION is the engine's job — this only moves."""
        if choice.action == ACTION_END:
            self.over = True
            return
        self.goto(choice.next_node_id)


# --- voice keys ---------------------------------------------------------------

def voice_key(script: DialogueScript, line: DialogueLine) -> str:
    """The stable lookup key for a line's audio: '<script id>__<line id>'.

    Derived from ids only, never from position, so inserting a line above a
    recorded one cannot repoint its audio.
    """
    return f"{script.id}__{line.id}"
