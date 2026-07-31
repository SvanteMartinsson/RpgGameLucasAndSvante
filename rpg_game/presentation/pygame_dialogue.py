"""B139c: the dialogue screen — the battle screen's chrome, talking instead of fighting.

Lucas-approved layout: the SAME three zones the battle screen already teaches the
player, so a conversation reads as a familiar place rather than a new one. The
rects are imported from pygame_battle, not re-typed, so they can never drift apart:

    STAGE       (16, 16, 992, 360)   the portrait, where the enemy stands
    TALK_PANEL  (16, 392, 460, 272)  the conversation, where the combat log sits
    CHOICES     (492, 392, 516, 272) the choices, the whole right-hand column
                                     (battle's VITALS + ACTIONS — a conversation
                                     has no vitals to show)

PORTRAITS ARE PLACEHOLDERS until Lucas's art lands, following the same pattern as
the hero sprite and the B121 character figure: primitives only, and marked on
screen as temporary so nobody mistakes it for finished work. When a state's sheet
appears in assets/sprites/generated/characters/ it is picked up automatically —
4-frame horizontal strip, B109's shape.

Two animations, chosen by what the screen is doing: the TALK sheet loops while a
line is being typed out, the IDLE sheet loops while it stands still. That is the
whole reason talk and idle are separate sheets.

VOICE-READY. Each line's stable id becomes a voice key; the screen asks audio for
it when the line starts and moves on silently when there is no recording. Nothing
here waits on audio or behaves differently with or without it.

No game rules live here. Availability comes from GameEngine.dialogue_choice_blocker,
actions from GameEngine.apply_dialogue_choice, and the cursor from core.dialogue.
"""

from __future__ import annotations

import os

import pygame

from rpg_game.core import dialogue as core_dialogue
from rpg_game.presentation import audio, battle_choreo, ui
from rpg_game.presentation.pygame_battle import (
    ACCENT, BG, LOG_PANEL, PANEL, PANEL_EDGE, PAD, STAGE, TEXT, TEXT_DIM, VITALS,
    WARN, WIDTH, HEIGHT, FPS, SKILL_CELL_GAP, ESC_CELL_W, SKILL_GRID_ROWS)
from rpg_game.presentation.pygame_canvas import acquire_display, present, to_canvas
from rpg_game.presentation.ui import Button

# The conversation panel takes the combat log's footprint; the choices take the
# WHOLE right column (battle's VITALS + ACTIONS) since there are no vitals here.
TALK_PANEL = LOG_PANEL
CHOICES = pygame.Rect(VITALS.x, VITALS.y, VITALS.width,
                      LOG_PANEL.bottom - VITALS.y)

# Design variant A: the speaker's name on its own line with a coloured marker, the
# line itself in full panel width underneath. GOLD is the NPC, blue is the player —
# the same accent the rest of the UI uses for "you".
NPC_COLOR = battle_choreo.GOLD
PLAYER_COLOR = ACCENT
SPEAKER_COLORS = {core_dialogue.NPC: NPC_COLOR, core_dialogue.PLAYER: PLAYER_COLOR}

# Typewriter speed. Fast enough to never feel like waiting, slow enough that the
# talk animation has something to play against; any key skips to the full line.
CHARS_PER_SECOND = 46.0

# B109's sheet shape, reused for portraits.
PORTRAIT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "assets", "sprites", "generated", "characters")
PORTRAIT_FRAMES = 4
PORTRAIT_PERIOD = battle_choreo.frames(900)     # idle: the hero-idle feel
PORTRAIT_TALK_PERIOD = battle_choreo.frames(320)   # talk: quicker, mouth-paced
PORTRAIT_HEIGHT = 300                           # inside STAGE's 360 with headroom

# Placeholder palette — deliberately flat and obviously unfinished.
PLACEHOLDER_BODY = (44, 48, 64)
PLACEHOLDER_EDGE = (86, 92, 116)
PLACEHOLDER_LABEL = (120, 128, 150)

_portrait_cache: dict = {}


def portrait_frames(sheet_name: str):
    """The 4 scaled frames of a portrait sheet, or None when the file is absent.

    None is the NORMAL case right now and the caller draws its placeholder — the
    same contract as B109's enemy_idle_frames.
    """
    if not sheet_name:
        return None
    if sheet_name in _portrait_cache:
        return _portrait_cache[sheet_name]
    path = os.path.join(PORTRAIT_DIR, sheet_name)
    frames = None
    if os.path.exists(path):
        try:
            sheet = pygame.image.load(path).convert_alpha()
            frame_w = sheet.get_width() // PORTRAIT_FRAMES
            frame_h = sheet.get_height()
            width = max(1, round(frame_w * PORTRAIT_HEIGHT / frame_h))
            # Heavy downscale on authored art -> smoothscale, as B109 measured.
            scale = (pygame.transform.smoothscale if frame_h > PORTRAIT_HEIGHT
                     else pygame.transform.scale)
            frames = [scale(sheet.subsurface((i * frame_w, 0, frame_w, frame_h)),
                            (width, PORTRAIT_HEIGHT))
                      for i in range(PORTRAIT_FRAMES)]
        except Exception:   # unreadable/corrupt sheet -> placeholder, never a crash
            frames = None
    _portrait_cache[sheet_name] = frames
    return frames


def _reset_portrait_cache() -> None:
    """Test hook: forget loaded sheets (so a dropped-in file is picked up)."""
    _portrait_cache.clear()


class DialogueApp:
    """One conversation with one character, in their current state."""

    def __init__(self, engine, character, standalone: bool = False,
                 event_log=None) -> None:
        self.engine = engine
        self.character = character
        self.standalone = standalone
        self.event_log = event_log
        self.state = engine.character_state(character)
        self.conversation = engine.start_conversation(character)

        pygame.init()
        audio.init()
        audio.ensure_music()          # B137: the loop carries into the conversation
        self.screen = pygame.Surface((WIDTH, HEIGHT))
        self.display = acquire_display((WIDTH, HEIGHT))
        self._transform = (0, 0, 1.0)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("menlo,consolas,monospace", 16)
        self.font_sm = pygame.font.SysFont("menlo,consolas,monospace", 13)
        self.font_lg = pygame.font.SysFont("menlo,consolas,monospace", 22, bold=True)

        self.buttons: list[Button] = []
        self.focus = ui.FocusList()
        self.hover = ui.HoverTracker()
        self.scroll = ui.ScrollArea()
        self._anim_tick = 0
        self._typed = 0.0             # characters of the current line revealed
        self._typing_line_id = ""     # which line _typed refers to
        self.running = self.conversation is not None
        self.log_lines: list[str] = []     # quest events this conversation produced
        self._begin_line()

    # -- the current line ------------------------------------------------------

    def _begin_line(self) -> None:
        """Start typing a new line and ask for its voice (silent if unrecorded)."""
        line = self.conversation.current_line() if self.conversation else None
        if line is None or line.id == self._typing_line_id:
            return
        self._typing_line_id = line.id
        self._typed = 0.0
        audio.stop_voice()
        audio.play_voice(core_dialogue.voice_key(self.conversation.script, line))

    def _full_text(self) -> str:
        line = self.conversation.current_line()
        return line.text if line is not None else ""

    def _visible_text(self) -> str:
        return self._full_text()[:int(self._typed)]

    @property
    def is_typing(self) -> bool:
        return bool(self._full_text()) and int(self._typed) < len(self._full_text())

    def skip_typing(self) -> None:
        self._typed = float(len(self._full_text()))

    def advance(self) -> None:
        """Space/Enter/click: finish the line, or move to the next one."""
        if self.conversation is None:
            return
        if self.is_typing:
            self.skip_typing()          # first press reveals the rest
            return
        audio.stop_voice()
        if self.conversation.advance():
            self._begin_line()
        elif self.conversation.over:
            self.running = False

    # -- choices ---------------------------------------------------------------

    def take_choice(self, choice) -> None:
        """Run a choice: its action through the engine, then move the cursor."""
        blocker = self.engine.dialogue_choice_blocker(choice)
        if blocker:
            self._log(f"{choice.text}: {blocker}")
            return
        audio.play("menu_click")
        for line in self.engine.apply_dialogue_choice(choice):
            self._log(line)
        self.conversation.choose(choice)
        if self.conversation.over:
            self.running = False
        else:
            self._begin_line()
        self.focus.reset()

    def _log(self, text: str) -> None:
        self.log_lines.append(text)
        if self.event_log is not None:
            self.event_log.append(text)

    def end(self) -> None:
        audio.stop_voice()
        self.running = False

    # -- geometry --------------------------------------------------------------

    def choice_grid_rects(self, count: int):
        """B130/B134's shape, over the taller CHOICES band: two columns of choices
        with the Esc/Leave cell in its own narrow column to the right. `count`
        includes that trailing cell.

        Rows grow past the canonical two only when there are more than four
        choices, so the usual conversation looks exactly like the battle grid.
        """
        gap = SKILL_CELL_GAP
        n_choices = max(1, count - 1)
        columns = min(2, n_choices)
        rows = max(SKILL_GRID_ROWS, (n_choices + columns - 1) // columns)
        esc_w = min(ESC_CELL_W, max(1, CHOICES.width - (columns + 2) * gap - columns))
        cell_w = max(1, (CHOICES.width - (columns + 2) * gap - esc_w) // columns)
        cell_h = max(1, (CHOICES.height - (rows - 1) * gap) // rows)
        used_rows = (n_choices + columns - 1) // columns
        block_h = used_rows * cell_h + (used_rows - 1) * gap
        x0 = CHOICES.x + gap
        y0 = CHOICES.y + (CHOICES.height - block_h) // 2
        rects = []
        for index in range(n_choices):
            row, column = divmod(index, columns)
            rects.append(pygame.Rect(x0 + column * (cell_w + gap),
                                     y0 + row * (cell_h + gap), cell_w, cell_h))
        # The leave cell: its own column, vertically centred on the block.
        esc_x = x0 + columns * (cell_w + gap)
        rects.append(pygame.Rect(esc_x, y0 + (block_h - cell_h) // 2, esc_w, cell_h))
        return rects

    # -- events ----------------------------------------------------------------

    def handle_event(self, event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            position = to_canvas(event.pos, self._transform)
            for button in self.buttons:
                if button.rect.collidepoint(position):
                    button.on_click()
                    return
            self.advance()          # clicking anywhere else pushes the text on
            return
        if event.type == pygame.MOUSEWHEEL:
            self.scroll.scroll(event.y * 3)
            return
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.end()
            return
        if self.conversation is not None and self.conversation.awaiting_choice():
            if event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                # B130's geometric nav, shared via ui.focus_grid_step.
                dx = (event.key == pygame.K_RIGHT) - (event.key == pygame.K_LEFT)
                dy = (event.key == pygame.K_DOWN) - (event.key == pygame.K_UP)
                ui.focus_grid_step(self.focus, dx, dy)
                return
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                button = self.focus.focused()
                if button is not None:
                    button.on_click()
                return
        elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.advance()
            return
        if event.key == pygame.K_PAGEUP:
            self.scroll.scroll(3)
        elif event.key == pygame.K_PAGEDOWN:
            self.scroll.scroll(-3)

    def update(self) -> None:
        """One frame of typing. The talk animation is driven by is_typing."""
        self._anim_tick += 1
        if self.is_typing:
            self._typed = min(float(len(self._full_text())),
                              self._typed + CHARS_PER_SECOND / FPS)

    # -- rendering -------------------------------------------------------------

    def draw(self) -> None:
        self.screen.fill(BG)
        self.buttons = []
        self.hover.begin()
        self.focus.begin()
        self._draw_stage()
        self._draw_talk_panel()
        self._draw_choices()
        self._draw_buttons()
        mouse = to_canvas(pygame.mouse.get_pos(), self._transform)
        self.hover.update(mouse, pygame.time.get_ticks())
        if self.hover.active is not None:
            ui.draw_tooltip(self.screen, self.hover.active, mouse, self.font, self.font_sm)
        self._transform = present(self.display, self.screen, BG)

    def _panel(self, rect: pygame.Rect) -> None:
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=6)
        pygame.draw.rect(self.screen, PANEL_EDGE, rect, width=1, border_radius=6)

    def current_portrait_sheet(self) -> str:
        """Which sheet the current moment wants: TALK while a line types out, IDLE
        when it stands still. That is what the two sheets are for."""
        if self.state is None:
            return ""
        return (self.state.portrait_talk_sheet if self.is_typing
                else self.state.portrait_idle_sheet)

    def portrait_frame_index(self) -> int:
        period = PORTRAIT_TALK_PERIOD if self.is_typing else PORTRAIT_PERIOD
        step = max(1, period // PORTRAIT_FRAMES)
        return (self._anim_tick // step) % PORTRAIT_FRAMES

    def _draw_stage(self) -> None:
        self._panel(STAGE)
        name = self.character.name if self.character is not None else ""
        title = self.font_lg.render(name, True, NPC_COLOR)
        self.screen.blit(title, (STAGE.x + 16, STAGE.y + 12))
        if self.state is not None:
            tag = self.font_sm.render(f"({self.state.id})", True, TEXT_DIM)
            self.screen.blit(tag, (STAGE.x + 20 + title.get_width(), STAGE.y + 22))
        frames = portrait_frames(self.current_portrait_sheet())
        centre_x = STAGE.centerx
        baseline = STAGE.bottom - 12
        if frames:
            frame = frames[self.portrait_frame_index()]
            rect = frame.get_rect(midbottom=(centre_x, baseline))
            self.screen.blit(frame, rect)
        else:
            self._draw_portrait_placeholder(centre_x, baseline)

    def _draw_portrait_placeholder(self, centre_x: int, baseline: int) -> None:
        """A flat bust silhouette, LABELLED as temporary — the hero-sprite pattern.
        It is deliberately plain: nothing here should read as finished art, and the
        real sheet replaces it with no code change."""
        height = PORTRAIT_HEIGHT
        width = int(height * 0.62)
        body = pygame.Rect(0, 0, width, int(height * 0.66))
        body.midbottom = (centre_x, baseline)
        head_r = int(height * 0.17)
        head_centre = (centre_x, body.top - head_r + 6)
        pygame.draw.circle(self.screen, PLACEHOLDER_BODY, head_centre, head_r)
        pygame.draw.circle(self.screen, PLACEHOLDER_EDGE, head_centre, head_r, width=2)
        pygame.draw.rect(self.screen, PLACEHOLDER_BODY, body, border_radius=18)
        pygame.draw.rect(self.screen, PLACEHOLDER_EDGE, body, width=2, border_radius=18)
        # The mouth line moves with the talk/idle frame, so the placeholder still
        # shows that the animation seam is wired.
        if self.is_typing:
            open_by = (self.portrait_frame_index() % 2) * 4
            mouth = pygame.Rect(0, 0, head_r // 2, 3 + open_by)
            mouth.center = (head_centre[0], head_centre[1] + head_r // 3)
            pygame.draw.rect(self.screen, PLACEHOLDER_EDGE, mouth, border_radius=2)
        label = self.font_sm.render("portrait placeholder — art pending", True,
                                    PLACEHOLDER_LABEL)
        self.screen.blit(label, label.get_rect(midtop=(centre_x, STAGE.y + 14)))

    def _draw_talk_panel(self) -> None:
        """Design variant A: the speaker's name on its own line with a coloured
        marker, the line in full width beneath. Scrollable history (B113)."""
        self._panel(TALK_PANEL)
        inner = TALK_PANEL.inflate(-24, -20)
        blocks = self._talk_blocks(inner.width)
        line_h = self.font_sm.get_linesize()
        content_h = sum(len(block) for block in blocks) * line_h + len(blocks) * 6
        self.scroll.configure(content_h, inner.height)
        # Newest at the bottom: with the content taller than the panel the default
        # offset must show the END of the conversation, not its beginning.
        y = inner.y + min(0, inner.height - content_h) + self.scroll.offset * line_h
        for block in blocks:
            for text, color in block:
                if inner.y - line_h < y < inner.bottom:
                    self.screen.blit(self.font_sm.render(text, True, color), (inner.x, y))
                y += line_h
            y += 6
        ui.draw_scroll_indicators(self.screen, self.font_sm, inner, self.scroll,
                                  line_h, TEXT_DIM)

    def _talk_blocks(self, width: int):
        """One block per spoken line: a name row, then the wrapped line rows. The
        LAST block is the line currently typing, so it grows as it is revealed."""
        if self.conversation is None:
            return []
        blocks = []
        history = self.conversation.history
        current = self.conversation.current_line()
        for line in history:
            text = self._visible_text() if line is current else line.text
            if line is current and not text:
                continue
            blocks.append(self._one_block(line, text, width))
        return blocks

    def _one_block(self, line, text: str, width: int):
        color = SPEAKER_COLORS.get(line.speaker, TEXT)
        speaker = (self.character.name if line.speaker == core_dialogue.NPC
                   and self.character is not None else self.engine.player.name)
        rows = [(f"* {speaker}", color)]
        for wrapped in ui.wrap(text, self.font_sm, width):
            rows.append((wrapped, TEXT))
        return rows

    def _draw_choices(self) -> None:
        self._panel(CHOICES)
        if self.conversation is None:
            return
        choices = self.conversation.pending_choices()
        if not choices:
            hint = self.font_sm.render("Space / Enter to continue", True, TEXT_DIM)
            self.screen.blit(hint, hint.get_rect(center=CHOICES.center))
            return
        rects = self.choice_grid_rects(len(choices) + 1)
        for rect, choice in zip(rects, choices):
            blocker = self.engine.dialogue_choice_blocker(choice)
            # B132's lesson: whatever a cell cannot fit rides a tooltip, so a long
            # reason is never lost to truncation — and the reason is the whole point
            # of dimming a choice rather than hiding it.
            tip = ui.Tooltip(title=choice.text,
                             lines=[blocker] if blocker else [],
                             body="" if blocker else "")
            button = Button(rect, choice.text,
                            (lambda c=choice: self.take_choice(c)),
                            enabled=True, restricted=bool(blocker),
                            sublabel=blocker, custom=True,
                            tooltip=tip if blocker else None)
            self.buttons.append(button)
            # B126: a blocked choice stays FOCUSABLE, so confirming it explains why
            # instead of the row simply refusing to be reached.
            self.focus.add("choices", button)
        leave = Button(rects[len(choices)], "Leave", self.end, True,
                       hotkey="\x1b", custom=True)
        self.buttons.append(leave)
        self.focus.add("choices", leave)

    def _draw_buttons(self) -> None:
        mouse = to_canvas(pygame.mouse.get_pos(), self._transform)
        focused = self.focus.focused()
        for button in self.buttons:
            is_focused = button is focused
            hovered = button.rect.collidepoint(mouse)
            fill = PANEL_EDGE if (is_focused or hovered) else PANEL
            pygame.draw.rect(self.screen, fill, button.rect, border_radius=5)
            pygame.draw.rect(self.screen, ACCENT if is_focused else PANEL_EDGE,
                             button.rect, width=2 if is_focused else 1, border_radius=5)
            self._draw_choice_cell(button)

    def _draw_choice_cell(self, button: Button) -> None:
        """B134's cell look: the label centred as a block, with a dimmed reason
        beneath a blocked choice (B112 — a dimmed row always says why)."""
        label_color = TEXT_DIM if button.restricted else TEXT
        if button.hotkey:                       # the Esc / Leave cell
            badge_w = self.font_sm.size("Esc")[0] + 14
            ui.draw_key_badge(self.screen, self.font_sm, "Esc",
                              right=button.rect.centerx + badge_w // 2,
                              centery=button.rect.centery - 6)
            text = self.font_sm.render(button.label, True, TEXT)
            self.screen.blit(text, text.get_rect(
                center=(button.rect.centerx, button.rect.centery + 15)))
            return
        inner = button.rect.width - 16
        line_h = self.font_sm.get_linesize()
        # Budget the cell's lines between the label and the reason instead of
        # capping each blindly: the reason gets what it needs, the label keeps at
        # least two rows, and anything still over the edge rides the tooltip.
        max_rows = max(2, (button.rect.height - 8) // line_h)
        reason_rows = ui.wrap(button.sublabel, self.font_sm, inner) if button.sublabel else []
        label_budget = max(1, max_rows - len(reason_rows))
        rows = [(part, label_color)
                for part in ui.wrap(button.label, self.font_sm, inner)[:label_budget]]
        for part in reason_rows[:max(0, max_rows - len(rows))]:
            rows.append((part, WARN))
        y = button.rect.centery - (len(rows) * line_h) // 2
        for text, color in rows:
            surface = self.font_sm.render(text, True, color)
            self.screen.blit(surface, surface.get_rect(
                midtop=(button.rect.centerx, y)))
            y += line_h

    # -- loop ------------------------------------------------------------------

    def run(self) -> list[str]:
        """Talk until the conversation ends or the player leaves. Returns the quest
        log lines it produced, for the caller's chatbox."""
        if self.conversation is None:
            return []
        while self.running:
            for event in pygame.event.get():
                self.handle_event(event)
            self.update()
            self.draw()
            self.clock.tick(FPS)
            audio.ensure_music()        # B137: keep the playlist moving
        audio.stop_voice()
        if self.standalone:
            pygame.quit()
        return self.log_lines
