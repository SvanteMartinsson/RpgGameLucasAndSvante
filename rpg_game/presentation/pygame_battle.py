"""Pygame battle shell.

Det här är första grafiska presentation-lagret. Det renderar striden som redan
funkar i kärnan och skickar kommandon via ``GameEngine`` precis som terminal-UI:t.

Arkitekturregler (se PRESENTATION_API.md):
- Läs state via ``rpg_game.core.view.build_snapshot`` plus den runtime-enemy som
  ``engine.create_encounter`` returnerar.
- Mutera bara state via ``GameEngine``-metoder (``run_combat_turn``,
  ``attempt_flee``, ``apply_stat_choice`` ...).
- Ingen damage-, loot- eller cooldown-logik får dupliceras här.

Kör:

    python3 -m rpg_game.presentation.pygame_battle
"""

from __future__ import annotations

import collections
import os
import re
import sys
from dataclasses import dataclass, field

import pygame

from rpg_game.core import combat, entities
from rpg_game.core.game import GameEngine
from rpg_game.core.view import build_snapshot
from rpg_game.presentation.playtest_logger import PlaytestLogger
from rpg_game.presentation import settings as user_settings
from rpg_game.presentation import ui_text as T
from rpg_game.presentation import chatlog
from rpg_game.presentation import ui
from rpg_game.presentation.ui import Button
from rpg_game.presentation.pygame_canvas import acquire_display, present, set_display_mode, to_canvas

# --- Layout ----------------------------------------------------------------

WIDTH, HEIGHT = 1024, 680
FPS = 60

PAD = 16
# Three zones, rebalanced toward the fight: STAGE biggest (~53%), LOG slim
# (~19%), HUD compact (~19%). Heights sum to 680 with PAD between.
STAGE = pygame.Rect(PAD, PAD, WIDTH - 2 * PAD, 360)
LOG_PANEL = pygame.Rect(PAD, STAGE.bottom + PAD, WIDTH - 2 * PAD, 130)
HUD = pygame.Rect(PAD, LOG_PANEL.bottom + PAD, WIDTH - 2 * PAD, HEIGHT - LOG_PANEL.bottom - 2 * PAD)
VITALS = pygame.Rect(HUD.x, HUD.y, 600, HUD.height)          # player vitals (left)
ACTIONS = pygame.Rect(VITALS.right + PAD, HUD.y, HUD.right - VITALS.right - PAD, HUD.height)  # buttons (right)
GROUND_Y = STAGE.bottom - 28  # shared baseline both combatants stand on
HERO_BOX = (90, 120, 170)

# --- Colors ----------------------------------------------------------------

BG = (18, 20, 28)
PANEL = (30, 34, 46)
PANEL_EDGE = (60, 66, 86)
TEXT = (222, 226, 235)
TEXT_DIM = (140, 148, 166)
ACCENT = (120, 170, 255)
HP_FULL = (96, 200, 120)
HP_LOW = (210, 90, 90)
MANA = (90, 140, 230)
XP_COL = (180, 150, 240)
BTN = (46, 52, 70)
BTN_HOVER = (66, 76, 102)
BTN_DISABLED = (34, 38, 50)
BTN_EDGE = (90, 100, 130)
WARN = (235, 180, 90)
GOOD = (120, 220, 140)
BAD = (230, 110, 110)


# --- enemy battle sprites --------------------------------------------------
# CWD-safe path anchored to this module (not the process CWD), same lesson as the
# save-path/tileset fixes.
SPRITE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "sprites", "generated")
# Data-driven per-enemy size: raw sprites have wildly different pixel sizes, so
# each maps to a tier whose target height (canvas units) sets the on-screen scale.
# Sprites share a baseline so they stand on the ground rather than float.
ENEMY_SPRITE_TIER = {
    "giant_rat": "small",
    "undead": "medium",
    "undead_priest": "medium",
    "dire_wolf": "medium",
    "wild_boar": "medium",
    "mutated_mudcrab": "medium",
    "bog_wraith": "medium",
    "cave_bear": "large",
    "treant": "large",
    "tar_beast": "large",
    "hollow_worg": "large",
    # B42 new forest enemies (placeholder sprites reused from kin until art lands)
    "thornling": "small",
    "broodmother_spider": "large",
    "strangling_vine": "large",
    # B65 zone bosses (placeholder sprites copied from kin until art lands)
    "boss_rotfang": "large",
    "boss_briar_queen": "large",
    "boss_yagra": "large",
    "boss_barrow_king": "large",
    "boss_pale_sovereign": "large",
}
# Bigger on the roomier stage, but with air left in the band (not dominant).
TIER_HEIGHT = {"small": 150, "medium": 200, "large": 250}
_DEFAULT_SPRITE_TIER = "medium"
_sprite_cache: dict[str, "pygame.Surface | None"] = {}


def enemy_sprite_height(enemy_id: str) -> int:
    return TIER_HEIGHT.get(ENEMY_SPRITE_TIER.get(enemy_id, _DEFAULT_SPRITE_TIER), TIER_HEIGHT[_DEFAULT_SPRITE_TIER])


def enemy_sprite(enemy_id: str):
    """Scaled battle sprite for an enemy id, or None if there's no sprite file
    (the caller draws the box fallback). Cached; nearest-neighbor scaled so pixel
    edges stay crisp."""
    if enemy_id in _sprite_cache:
        return _sprite_cache[enemy_id]
    path = os.path.join(SPRITE_DIR, f"{enemy_id}.png")
    surface = None
    if os.path.exists(path):
        raw = pygame.image.load(path).convert_alpha()
        target_h = enemy_sprite_height(enemy_id)
        width = max(1, round(raw.get_width() * target_h / raw.get_height()))
        surface = pygame.transform.scale(raw, (width, target_h))  # nearest-neighbor
    _sprite_cache[enemy_id] = surface
    return surface


@dataclass
class BattleApp:
    engine: GameEngine
    display: pygame.Surface = field(init=False)  # real window/fullscreen surface
    screen: pygame.Surface = field(init=False)   # fixed-size canvas drawn to
    clock: pygame.time.Clock = field(init=False)
    font: pygame.font.Font = field(init=False)
    font_sm: pygame.font.Font = field(init=False)
    font_lg: pygame.font.Font = field(init=False)

    enemy: object | None = None
    # standalone=True: demo mode (bootstrap a fight, spawn endless encounters,
    # own the pygame lifecycle). standalone=False: run a single battle against
    # the given enemy on a shared engine, then return control via self.outcome
    # without quitting pygame — used by the overworld loop.
    standalone: bool = True
    log_scroll: int = 0
    mode: str = "combat"  # combat | submenu | stat_choice | game_over | victory_idle
    submenu_kind: str = ""
    buttons: list[Button] = field(default_factory=list)
    banner: str = ""
    banner_color: tuple[int, int, int] = TEXT
    running: bool = True
    outcome: str = ""  # set when a non-standalone battle resolves
    _pending_outcome: str = ""  # single-battle result awaiting press-to-continue
    playtest_logger: PlaytestLogger | None = None
    location_id: str = ""
    allow_flee: bool = True
    allow_swap: bool = True
    _transform: tuple[int, int, float] = (0, 0, 1.0)  # canvas->display offset+scale
    # The ONE shared log: a deque of (text, color). The overworld passes its own so
    # combat/drops/level-ups continue in the same chatbox after the fight; a
    # standalone battle gets its own. Battle renders the SAME chatbox component.
    event_log: object | None = None

    # -- lifecycle ----------------------------------------------------------

    def __post_init__(self) -> None:
        if self.event_log is None:            # standalone fight: own the shared log
            self.event_log = collections.deque(maxlen=chatlog.LOG_HISTORY_MAX)
        # B72 combat feel: floating damage numbers + hit feedback (toggleable).
        self._combat_fx = bool(user_settings.load().get("combat_fx", True))
        self._floaters: list = []       # [x, y, age, max_age, surface]
        self._blink_enemy = 0           # frames of white flash left
        self._blink_hero = 0
        self._shake = 0                 # frames of screen shake left
        self._freeze = 0                # hit-pause frames (floaters hold still)
        # Shared hover timer -> tooltip. No menu registers zones yet (Slice 1 is
        # infra only), so it stays a no-op until an apply-slice calls hover.add().
        self.hover = ui.HoverTracker()
        pygame.init()
        pygame.display.set_caption(T.CAPTION_BATTLE)
        # Inherit the caller's display (window or fullscreen); draw to a fixed
        # canvas that present() blits centered onto it.
        self.display = acquire_display((WIDTH, HEIGHT))
        # Pump one event cycle and re-read the OS-confirmed surface so the first
        # frame centers against the real drawable size instead of a stale window
        # size (which otherwise anchors top-left until the first VIDEORESIZE).
        pygame.event.pump()
        self.display = pygame.display.get_surface() or self.display
        self.screen = pygame.Surface((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("menlo,consolas,monospace", 16)
        self.font_sm = pygame.font.SysFont("menlo,consolas,monospace", 13)
        self.font_lg = pygame.font.SysFont("menlo,consolas,monospace", 22, bold=True)
        if self.playtest_logger is None:
            self.playtest_logger = PlaytestLogger()
            self.playtest_logger.session_start(build_snapshot(self.engine))
        self.location_id = self.location_id or self.engine.player.current_place_id
        if self.enemy is not None:
            # Single battle against a supplied enemy (e.g. a wild encounter).
            self.set_mode("combat")
            self.push_log(T.appears(_enemy_article(self.enemy), self.enemy.name), ACCENT)
            self.playtest_logger.encounter_start(self.enemy, build_snapshot(self.engine), self.location_id)
        elif self.standalone:
            self._ensure_dangerous_place()
            self.next_encounter()

    def _finish(self, outcome: str) -> None:
        """End a single (non-standalone) battle, handing control back."""
        self.outcome = outcome
        self.running = False

    def _show_result(self, outcome: str) -> None:
        """Single-battle: pause on a result view until the player continues, so
        fast fights don't vanish before the log can be read."""
        self._pending_outcome = outcome
        if outcome == "victory":
            self.banner, self.banner_color = T.RESULT_VICTORY, GOOD
        elif outcome == "defeat":
            self.banner, self.banner_color = T.RESULT_DEFEAT, BAD
        else:
            self.banner, self.banner_color = T.RESULT_FLED, WARN
        self.set_mode("result")

    def _ensure_dangerous_place(self) -> None:
        """Move the demo character to somewhere encounters can spawn."""
        if self.engine.current_place().encounters:
            return
        for place_id, place in self.engine.content.places.items():
            if place.encounters:
                self.engine.player.current_place_id = place_id
                return

    def next_encounter(self) -> None:
        self.enemy = self.engine.create_encounter()
        if self.enemy is None:
            self.set_mode("game_over")
            self.banner = T.NO_ENEMIES
            self.banner_color = TEXT_DIM
            return
        self.set_mode("combat")
        self.banner = ""
        self.push_log(T.appears(_enemy_article(self.enemy), self.enemy.name), ACCENT)
        self.location_id = self.engine.player.current_place_id
        if self.playtest_logger is not None:
            self.playtest_logger.encounter_start(self.enemy, build_snapshot(self.engine), self.location_id)

    # -- logging ------------------------------------------------------------

    def push_log(self, text: str, color: tuple[int, int, int] = TEXT) -> None:
        # B16.1: every battle line is channel-tagged so the overworld log can filter.
        chatlog.push(self.event_log, text, color, channel=chatlog.CHANNEL_COMBAT)

    def push_rich(self, parts, color: tuple[int, int, int] = TEXT) -> None:
        chatlog.push_rich(self.event_log, parts, color, channel=chatlog.CHANNEL_COMBAT)

    def _push_combat_event(self, event: str) -> None:
        """B44: colourize core narration by its canonical shape — the damage
        numbers turn red when YOU are the target, heal lines go green; anything
        unrecognized passes through unchanged."""
        match = _DEALT_RE.match(event)
        if match and match.group("target") == self.engine.player.name:
            self.push_rich([(match.group("head"), TEXT),
                            (match.group("body"), chatlog.DAMAGE),
                            (match.group("tail"), TEXT)])
            return
        if _HEALED_RE.match(event):
            self.push_log(event, chatlog.HEAL)
            return
        # B77: statuses that land on YOU are called out (amber apply, red ticks).
        match = _AFFECTED_RE.match(event)
        if match:
            self.push_log(event, WARN if match.group("who") == self.engine.player.name else TEXT)
            return
        match = _TICK_RE.match(event)
        if match and match.group("who") == self.engine.player.name:
            self.push_log(event, chatlog.DAMAGE)
            return
        self.push_log(event)

    # -- command dispatch ---------------------------------------------------

    def issue_turn(self, action_id: str) -> None:
        if self.enemy is None or self.mode not in {"combat", "submenu"}:
            return
        result = self.engine.run_combat_turn(self.enemy, action_id)
        self._consume_result(result)

    def issue_flee(self) -> None:
        if not self.allow_flee:
            return
        if self.enemy is None or self.mode != "combat":
            return
        result = self.engine.attempt_flee(self.enemy)
        self._consume_result(result, fled_action=True)

    def _suppressed_narration(self, result: combat.CombatTurnResult) -> set[str]:
        """Exact core victory-narration strings the chatbox must NOT echo, since the
        presentation re-emits short equivalents (and the verbose "X dropped: ..."
        line is dropped entirely in favour of the "Loot:" line). Reconstructed to
        match game._handle_victory; "Gained N level(s)." is kept (not duplicated)."""
        if result.outcome != "victory" or self.enemy is None:
            return set()
        lines = {
            f"{self.enemy.name} was defeated.",
            f"Gained {result.xp_gained} XP and {result.gold_gained} gold.",
        }
        drop = result.loot_drop
        if drop is not None:
            lines.add(f"{self.enemy.name} dropped: {drop.name} [{drop.rarity}] (tier {drop.tier})!")
        return lines

    def _consume_result(self, result: combat.CombatTurnResult, fled_action: bool = False) -> None:
        if self.playtest_logger is not None and self.enemy is not None:
            self.playtest_logger.combat_result(result, self.enemy, build_snapshot(self.engine), self.location_id)
        # B39: the core still RETURNS its battle-end narration (kept for tests), but
        # the chatbox shows only the short presentation lines below ("Victory!" /
        # "+N XP" / "+N gold" / "Loot: ..."). Suppress the core duplicates so each
        # outcome logs exactly one set of lines.
        suppressed = self._suppressed_narration(result)
        for event in result.events:
            if event in suppressed:
                continue
            if result.loot_drop is not None and "dropped:" in event:
                continue   # shown as a rarity-coloured loot line instead of "[rare]" text
            self._push_combat_event(event)   # B44: red vs-you damage, green heals
        if result.enemy_reveal is not None:
            for line in _reveal_lines(result.enemy_reveal):
                self.push_log(line, ACCENT)
        if result.loot_drop is not None:
            # B44: only the item NAME carries the rarity colour, not the whole row.
            drop = result.loot_drop
            name = getattr(drop, "item_name", None) or getattr(drop, "name", "loot")
            self.push_rich([("Loot: ", TEXT), (name, chatlog.rarity_color(drop.rarity))])

        self._spawn_combat_fx(result)   # B72: floaters / blink / shake / hit-pause

        self.set_mode("combat")

        if result.outcome == "blocked":
            return
        if result.outcome == "fled":
            self.enemy = None
            if self.standalone:
                self.banner = T.FLED_BANNER
                self.banner_color = WARN
                self.set_mode("victory_idle")
            else:
                self._show_result("fled")
            return
        if result.outcome == "victory":
            self.push_log(T.VICTORY_LOG, chatlog.HEAL)
            # B44: XP and gold share ONE row, each part in its own colour.
            reward_parts = []
            if result.xp_gained:
                reward_parts.append((T.xp_gain(result.xp_gained), chatlog.XP))
            if result.gold_gained:
                if reward_parts:
                    reward_parts.append(("   ", TEXT))
                reward_parts.append((T.gold_gain(result.gold_gained), chatlog.GOLD))
            if reward_parts:
                self.push_rich(reward_parts)
            self.enemy = None
            if result.pending_stat_choices > 0:
                self.set_mode("stat_choice")  # resolve choices before returning
                self.banner, self.banner_color = T.LEVELUP_PROMPT, XP_COL
            elif self.standalone:
                self.banner = T.VICTORY_NEXT
                self.banner_color = GOOD
                self.set_mode("victory_idle")
            else:
                self._show_result("victory")
            return
        if result.outcome == "defeat":
            self.push_log(T.DEFEATED_LOG, chatlog.DAMAGE)
            self.enemy = None
            if self.standalone:
                self.banner = T.DEFEAT_BANNER
                self.banner_color = BAD
                self.set_mode("game_over")
            else:
                self._show_result("defeat")

    def apply_stat(self, stat: str) -> None:
        if self.engine.player.pending_stat_choices <= 0:
            return
        message = self.engine.apply_stat_choice(stat)
        self.push_log(message, chatlog.LEVELUP)
        if self.engine.player.pending_stat_choices <= 0:
            if self.standalone:
                self.banner = T.LEVELUP_RESOLVED
                self.banner_color = GOOD
                self.set_mode("victory_idle")
            else:
                self._show_result("victory")  # stat choice only follows a victory

    # -- mode / submenu -----------------------------------------------------

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.submenu_kind = ""

    def open_submenu(self, kind: str) -> None:
        self.submenu_kind = kind
        self.mode = "submenu"

    # -- input --------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return
        if event.type == pygame.VIDEORESIZE:
            self.display = set_display_mode((event.w, event.h))
            return
        if event.type == pygame.MOUSEWHEEL:
            self.scroll_log(event.y * chatlog.LOG_SCROLL_STEP)   # B50: wheel up = older
            return
        if event.type == pygame.KEYDOWN:
            self._handle_key(event)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = to_canvas(event.pos, self._transform)
            for button in self.buttons:
                if button.enabled and button.rect.collidepoint(pos):
                    button.on_click()
                    return
            # Clicking anywhere advances out of idle/result states.
            if self.mode == "victory_idle":
                self.next_encounter()
            elif self.mode == "result":
                self._finish(self._pending_outcome)

    def _handle_key(self, event: pygame.event.Event) -> None:
        if self.mode == "result":
            self._finish(self._pending_outcome)
            return
        if event.key == pygame.K_ESCAPE:
            if self.mode == "submenu":
                self.set_mode("combat")
            elif self.mode in {"game_over"}:
                self.running = False
            return
        if self.mode == "victory_idle" and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.next_encounter()
            return
        if event.key == pygame.K_PAGEUP:            # B50: scroll the combat log
            self.scroll_log(chatlog.LOG_SCROLL_STEP)
            return
        if event.key == pygame.K_PAGEDOWN:
            self.scroll_log(-chatlog.LOG_SCROLL_STEP)
            return
        key_char = event.unicode.lower() if event.unicode else ""
        for button in self.buttons:
            if button.enabled and button.hotkey and button.hotkey == key_char:
                button.on_click()
                return

    # -- rendering ----------------------------------------------------------

    def draw(self) -> None:
        self.screen.fill(BG)
        snapshot = build_snapshot(self.engine)
        self._draw_stage()
        self._draw_combat_fx()          # B72: floaters over the stage
        self._draw_chatbox()
        self._draw_hud_vitals(snapshot)
        self.buttons = []
        self.hover.begin()   # menus re-register their hoverable rects each frame
        if self.mode == "submenu":
            self._build_submenu(snapshot)
        elif self.mode == "stat_choice":
            self._build_stat_buttons()
        else:
            self._build_action_buttons(snapshot)
        self._draw_buttons()
        if self.banner:
            self._draw_banner()
        # Tooltip on the very top, once the mouse has dwelt on a registered row.
        mouse = to_canvas(pygame.mouse.get_pos(), self._transform)
        self.hover.update(mouse, pygame.time.get_ticks())
        if self.hover.active is not None:
            ui.draw_tooltip(self.screen, self.hover.active, mouse, self.font, self.font_sm)
        if self._shake > 0:             # B72: brief screen shake on crits
            self._shake -= 1
            offset = (-2, 2)[self._shake % 2], (1, -1)[self._shake % 2]
            shifted = self.screen.copy()
            self.screen.fill(BG)
            self.screen.blit(shifted, offset)
        self._transform = present(self.display, self.screen, BG)

    # -- B72: combat feel (floating numbers + hit feedback) -------------------

    FX_TYPE_COLORS = {
        "physical": (235, 235, 235), "fire": (240, 140, 70),
        "frost": (120, 190, 240), "poison": (120, 205, 120),
        "holy": (235, 210, 120), "lightning": (250, 230, 90),
    }

    def _fx_anchor(self, over_enemy: bool) -> tuple[int, int]:
        if over_enemy:
            return (STAGE.right - 48 - 70, GROUND_Y - 170)
        return (STAGE.x + 48 + 50, GROUND_Y - 140)

    def _spawn_floater(self, text: str, color, over_enemy: bool, big: bool = False) -> None:
        font = self.font_lg if big else self.font
        surface = font.render(text, True, color)
        x, y = self._fx_anchor(over_enemy)
        jitter = (len(self._floaters) % 3 - 1) * 16   # deterministic spread
        self._floaters.append([x + jitter, y, 0, 45, surface])

    def _spawn_combat_fx(self, result) -> None:
        """Turn a consumed CombatTurnResult into stage feedback: one floater per
        damage component (colour by type, crits big), heal floaters, a white
        blink on whoever was hit, shake on crits and a short hit-pause on a
        kill. Everything behind the combat_fx setting."""
        if not self._combat_fx:
            return
        player_name = self.engine.player.name
        for resolution in result.action_resolutions:
            actor_is_player = resolution.actor_name == player_name
            hits_enemy = actor_is_player   # self-target heals handled separately
            crit = resolution.critical_hits > 0
            for component in resolution.damage_components:
                color = self.FX_TYPE_COLORS.get(component.damage_type, (235, 235, 235))
                text = f"-{component.amount}" + ("!" if crit else "")
                self._spawn_floater(text, color, over_enemy=hits_enemy, big=crit)
            if resolution.damage_components:
                if hits_enemy:
                    self._blink_enemy = 2
                else:
                    self._blink_hero = 2
                if crit:
                    self._shake = 6
            if resolution.total_healing:
                self._spawn_floater(f"+{resolution.total_healing}", (120, 205, 140),
                                    over_enemy=not actor_is_player)
        if result.outcome in ("victory", "defeat"):
            self._freeze = 3   # a short hit-pause lands the final blow

    def _draw_combat_fx(self) -> None:
        """Age + draw the floaters (they rise and fade); frozen during hit-pause."""
        if self._freeze > 0:
            self._freeze -= 1
        else:
            for floater in self._floaters:
                floater[1] -= 1.2          # rise
                floater[2] += 1            # age
            self._floaters = [f for f in self._floaters if f[2] < f[3]]
        for x, y, age, max_age, surface in self._floaters:
            faded = surface.copy()
            faded.set_alpha(max(0, 255 - int(255 * age / max_age)))
            self.screen.blit(faded, (int(x), int(y)))

    def _blit_blink(self, sprite, rect) -> None:
        flash = sprite.copy()
        flash.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_MAX)
        self.screen.blit(flash, rect)

    def _panel(self, rect: pygame.Rect, title: str = "") -> None:
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=8)
        pygame.draw.rect(self.screen, PANEL_EDGE, rect, width=1, border_radius=8)
        if title:
            self._text(title, (rect.x + 12, rect.y + 8), self.font_sm, TEXT_DIM)

    def _text(self, text, pos, font=None, color=TEXT):
        font = font or self.font
        surf = font.render(text, True, color)
        self.screen.blit(surf, pos)
        return surf.get_rect(topleft=pos)

    def _bar(self, rect, ratio, color, label):
        ratio = max(0.0, min(1.0, ratio))
        pygame.draw.rect(self.screen, (24, 26, 34), rect, border_radius=5)
        fill = rect.copy()
        fill.width = int(rect.width * ratio)
        if fill.width > 0:
            pygame.draw.rect(self.screen, color, fill, border_radius=5)
        pygame.draw.rect(self.screen, PANEL_EDGE, rect, width=1, border_radius=5)
        label_surf = self.font_sm.render(label, True, TEXT)
        self.screen.blit(label_surf, label_surf.get_rect(center=rect.center))

    def _draw_stage(self):
        self._panel(STAGE)
        pygame.draw.line(self.screen, PANEL_EDGE, (STAGE.x + 8, GROUND_Y + 2), (STAGE.right - 8, GROUND_Y + 2), 2)
        enemy = self.enemy
        if enemy is None:
            self._draw_hero_sprite()
            self._text("—", (STAGE.x + 14, STAGE.y + 8), self.font_lg, TEXT_DIM)
            return
        self._draw_hero_sprite()
        self._draw_enemy_sprite(enemy)
        # Compact nameplate (not a thick panel): name + level + HP bar + status/identify.
        nameplate_color = WARN if getattr(enemy, "boss", False) else TEXT   # B65: gold boss plate
        self._text(enemy_nameplate(enemy), (STAGE.x + 14, STAGE.y + 8), self.font_lg, nameplate_color)
        bar = pygame.Rect(STAGE.x + 14, STAGE.y + 42, 320, 20)
        hp_ratio = enemy.hp / enemy.max_hp if enemy.max_hp else 0
        self._bar(bar, hp_ratio, _hp_color(hp_ratio), f"HP {enemy.hp}/{enemy.max_hp}")
        info_y = bar.bottom + 6
        statuses = _status_text(enemy.active_statuses)
        if getattr(enemy, "charging_action_id", ""):
            action = self.engine.content.actions.get(enemy.charging_action_id)
            statuses = (statuses + " | " if statuses else "") + f"CHARGING {action.name if action else '?'}!"
        if statuses:
            self._text(statuses, (STAGE.x + 14, info_y), self.font_sm, WARN)
            info_y += 18
        if getattr(enemy, "identified", False):
            line = f"Lvl {enemy.level} | Power {enemy.damage} | Armor {enemy.armor} | Speed {enemy.speed}"
            self._text(line, (STAGE.x + 14, info_y), self.font_sm, TEXT_DIM)
        else:
            self._text(T.UNIDENTIFIED, (STAGE.x + 14, info_y), self.font_sm, TEXT_DIM)

    def _enemy_sprite_rect(self, width: int, height: int) -> pygame.Rect:
        """Bottom-RIGHT anchored on the stage groundline (enemy stands right,
        facing left). Shared baseline regardless of size."""
        rect = pygame.Rect(0, 0, width, height)
        rect.bottomright = (STAGE.right - 48, GROUND_Y)
        return rect

    def _hero_sprite_rect(self, width: int, height: int) -> pygame.Rect:
        """Bottom-LEFT anchored on the same groundline (hero stands left)."""
        rect = pygame.Rect(0, 0, width, height)
        rect.bottomleft = (STAGE.x + 48, GROUND_Y)
        return rect

    def _draw_enemy_sprite(self, enemy) -> None:
        sprite = enemy_sprite(enemy.id)
        if sprite is not None:
            rect = self._enemy_sprite_rect(*sprite.get_size())
            self.screen.blit(sprite, rect)
            if self._blink_enemy > 0:            # B72: white hit-flash
                self._blink_enemy -= 1
                self._blit_blink(sprite, rect)
        else:
            # No sprite file (hollow_worg, arena duelists) -> placeholder block at
            # the enemy's tier size, same baseline. No crash.
            height = enemy_sprite_height(enemy.id)
            rect = self._enemy_sprite_rect(int(height * 0.7), height)
            pygame.draw.rect(self.screen, PANEL, rect, border_radius=6)
            pygame.draw.rect(self.screen, PANEL_EDGE, rect, width=2, border_radius=6)

    def _draw_hero_sprite(self) -> None:
        # No side-view hero sprite authored yet -> placeholder block on the left,
        # same groundline. Drops in when hero art arrives.
        height = TIER_HEIGHT["medium"]
        rect = self._hero_sprite_rect(int(height * 0.5), height)
        box = HERO_BOX if self._blink_hero <= 0 else (245, 245, 245)   # B72 flash
        if self._blink_hero > 0:
            self._blink_hero -= 1
        pygame.draw.rect(self.screen, box, rect, border_radius=6)
        pygame.draw.rect(self.screen, PANEL_EDGE, rect, width=2, border_radius=6)

    def _log_visible(self) -> int:
        line_h = self.font_sm.get_height() + 3
        return max(1, (LOG_PANEL.height - 16) // line_h)

    def _log_scroll_max(self) -> int:
        # B50: in VISUAL-line units (a wrapped entry counts as its rendered rows),
        # so scrolling matches what the overworld log does.
        lines = chatlog.visual_lines(self.event_log, LOG_PANEL.width - 16, self.font_sm)
        return max(0, len(lines) - self._log_visible())

    def scroll_log(self, lines: int) -> None:
        """B50: scroll the combat log — +lines = older (up), -lines = newer (down)."""
        self.log_scroll = max(0, min(self.log_scroll + lines, self._log_scroll_max()))

    def _draw_chatbox(self):
        """The SAME chatbox component the overworld uses, drawn in the battle's log
        band so the combat log and the overworld log are one surface."""
        self.log_scroll = chatlog.draw(
            self.screen, LOG_PANEL, self.event_log, self.font_sm,
            visible=self._log_visible(), scroll=self.log_scroll, interactive=False,
            edge=PANEL_EDGE, accent=ACCENT)

    def _draw_hud_vitals(self, snapshot):
        # Compact vitals; the YOU name/class header is gone — only a discreet
        # level label sits by the XP bar.
        p = snapshot.player
        x = VITALS.x
        bar_w = VITALS.width - 56  # leave room for the "Lvl N" label beside XP
        hp_bar = pygame.Rect(x, VITALS.y + 4, bar_w, 16)
        self._bar(hp_bar, p.hp / p.max_hp if p.max_hp else 0, _hp_color(p.hp / p.max_hp if p.max_hp else 0), f"HP {p.hp}/{p.max_hp}")
        mana_bar = pygame.Rect(x, hp_bar.bottom + 4, bar_w, 14)
        self._bar(mana_bar, p.mana / p.max_mana if p.max_mana else 0, MANA, f"Mana {p.mana}/{p.max_mana}")
        xp_bar = pygame.Rect(x, mana_bar.bottom + 4, bar_w, 12)
        self._bar(xp_bar, p.xp / p.xp_required if p.xp_required else 0, XP_COL, f"XP {p.xp}/{p.xp_required}")
        self._text(f"Lvl {p.level}", (xp_bar.right + 8, xp_bar.y - 1), self.font_sm, TEXT_DIM)
        weapon = self.engine.content.weapons[p.equipped_weapon_id]
        line = f"DMG {p.total_damage}  ARM {p.armor}  SPD {p.speed}  CRIT {p.crit_chance}%  GOLD {p.gold}"
        self._text(line, (x, xp_bar.bottom + 6), self.font_sm, TEXT_DIM)
        info_y = xp_bar.bottom + 24
        weapon_line = f"Weapon: {weapon.name}"
        statuses = _status_text(p.statuses)
        if statuses:
            weapon_line += f"   Status: {statuses}"
        self._text(weapon_line, (x, info_y), self.font_sm, TEXT_DIM)

    # -- buttons ------------------------------------------------------------

    def _action_rects(self, count, columns=3):
        # Compact grid packed into the small ACTIONS region; row height shrinks to
        # fit so more options (submenus) still stay inside the HUD band.
        gap = 6
        rows = max(1, (count + columns - 1) // columns)
        col_w = (ACTIONS.width - (columns + 1) * gap) // columns
        row_h = min(34, (ACTIONS.height - (rows + 1) * gap) // rows)
        rects = []
        for i in range(count):
            col, row = i % columns, i // columns
            x = ACTIONS.x + gap + col * (col_w + gap)
            y = ACTIONS.y + gap + row * (row_h + gap)
            rects.append(pygame.Rect(x, y, col_w, row_h))
        return rects

    def _build_action_buttons(self, snapshot):
        if self.mode != "combat" or self.enemy is None:
            if self.mode == "victory_idle":
                self._text(T.NEXT_ENEMY_HINT, (ACTIONS.x + 4, ACTIONS.y + 8), self.font_sm, GOOD)
            elif self.mode == "game_over":
                self._text(T.QUIT_HINT, (ACTIONS.x + 4, ACTIONS.y + 8), self.font_sm, BAD)
            elif self.mode == "result":
                self._text(T.CONTINUE_HINT, (ACTIONS.x + 4, ACTIONS.y + 8), self.font_sm, self.banner_color)
            return
        specs = [
            (*T.ACTION_ATTACK, lambda: self.issue_turn("attack"), True),
            (*T.ACTION_SKILL, lambda: self.open_submenu("skill"), bool(snapshot.skills)),
            (*T.ACTION_ITEM, lambda: self.open_submenu("item"), self._has_consumables()),
            (*T.ACTION_IDENTIFY, lambda: self.issue_turn("identify"), not getattr(self.enemy, "identified", False)),
        ]
        if self.allow_swap:
            specs.insert(3, (*T.ACTION_SWAP, lambda: self.open_submenu("swap"), self._has_swappable(snapshot)))
        if self.allow_flee:
            specs.append((*T.ACTION_FLEE, self.issue_flee, True))
        for rect, (label, hotkey, cb, enabled) in zip(self._action_rects(len(specs)), specs):
            self.buttons.append(Button(rect, f"[{hotkey}] {label}", cb, enabled, hotkey=hotkey))

    def _build_submenu(self, snapshot):
        options = self._submenu_options(snapshot)
        if not options:
            self._text(T.NOTHING_AVAILABLE, (ACTIONS.x + 4, ACTIONS.y + 8), self.font_sm, TEXT_DIM)
        rects = self._action_rects(len(options) + 1)
        for rect, (label, action_id, enabled, sub) in zip(rects, options):
            # Inline the sub-detail so each option fits one compact line.
            text = f"{label} ({sub})" if sub else label
            self.buttons.append(Button(rect, text, (lambda a=action_id: self.issue_turn(a)), enabled))
        self.buttons.append(Button(rects[len(options)], "[Esc] Back", lambda: self.set_mode("combat"), True, hotkey="\x1b"))

    def _build_stat_buttons(self):
        specs = T.STAT_CHOICES
        for rect, (label, stat) in zip(self._action_rects(len(specs)), specs):
            self.buttons.append(Button(rect, label, (lambda s=stat: self.apply_stat(s)), True))

    def _draw_buttons(self):
        mouse = to_canvas(pygame.mouse.get_pos(), self._transform)
        for b in self.buttons:
            if not b.enabled:
                color = BTN_DISABLED
            elif b.rect.collidepoint(mouse):
                color = BTN_HOVER
            else:
                color = BTN
            pygame.draw.rect(self.screen, color, b.rect, border_radius=5)
            pygame.draw.rect(self.screen, BTN_EDGE, b.rect, width=1, border_radius=5)
            label_color = TEXT if b.enabled else TEXT_DIM
            label = self.font_sm.render(b.label, True, label_color)  # compact buttons
            self.screen.blit(label, label.get_rect(midleft=(b.rect.x + 8, b.rect.centery)))

    def _draw_banner(self):
        surf = self.font_lg.render(self.banner, True, self.banner_color)
        rect = surf.get_rect(center=(WIDTH // 2, LOG_PANEL.centery))
        bg = rect.inflate(40, 24)
        overlay = pygame.Surface(bg.size, pygame.SRCALPHA)
        overlay.fill((10, 12, 18, 220))
        self.screen.blit(overlay, bg.topleft)
        pygame.draw.rect(self.screen, PANEL_EDGE, bg, width=1, border_radius=8)
        self.screen.blit(surf, rect)

    # -- submenu data -------------------------------------------------------

    def _submenu_options(self, snapshot):
        if self.submenu_kind == "skill":
            opts = []
            for skill in snapshot.skills:
                enabled = not skill.blocked_reason
                cost = f"mana {skill.mana_cost}" if skill.mana_cost else "free"
                sub = skill.blocked_reason or f"{cost}, cd {skill.cooldown_rounds}"
                opts.append((skill.name, skill.id, enabled, sub))
            return opts
        if self.submenu_kind == "item":
            opts = []
            for item_id, count in sorted(self.engine.player.inventory.consumables.items()):
                item = self.engine.content.items.get(item_id)
                if item is None or item.kind != "consumable" or count <= 0:
                    continue
                opts.append((f"{item.name} x{count}", f"item:{item_id}", True, ""))
            return opts
        if self.submenu_kind == "swap":
            if not self.allow_swap:
                return []
            opts = []
            for weapon in snapshot.weapons:
                if weapon.equipped:
                    continue
                sub = "" if weapon.equippable else f"needs level {weapon.required_level}"
                opts.append((weapon.name, f"swap:{weapon.id}", weapon.equippable, sub))
            return opts
        return []

    def _has_consumables(self):
        return any(
            count > 0 and self.engine.content.items.get(item_id) and self.engine.content.items[item_id].kind == "consumable"
            for item_id, count in self.engine.player.inventory.consumables.items()
        )

    def _has_swappable(self, snapshot):
        return any(w.equippable and not w.equipped for w in snapshot.weapons)

    # -- main loop ----------------------------------------------------------

    def run(self) -> str:
        while self.running:
            for event in pygame.event.get():
                self.handle_event(event)
            self.draw()
            self.clock.tick(FPS)
        if self.standalone:
            pygame.quit()
        return self.outcome


# --- formatting helpers ----------------------------------------------------


# B44: the canonical core narration shapes (combat.format_damage_event and the
# heal handlers). Colour rides on the SHAPE — unmatched lines pass through plain.
_DEALT_RE = re.compile(
    r"^(?P<head>.+?'s .+? (?:dealt|drained) )(?P<body>.+?)(?P<tail> (?:to|from) (?P<target>.+?)\.)$")
_HEALED_RE = re.compile(r"^.+? healed \d+ HP\.$")
# B77: status events — the apply line (now source-tagged by core) and the DoT tick.
_AFFECTED_RE = re.compile(r"^(?P<who>.+?) is affected by .+\.$")
_TICK_RE = re.compile(r"^(?P<who>.+?) took \d+ .+? damage from .+\.$")


def _article(noun: str) -> str:
    return "an" if noun[:1].lower() in "aeiou" else "a"


def _enemy_article(enemy) -> str:
    """B65: named bosses take no article — 'Rotfang ... appears!', not 'A ...'."""
    return "" if getattr(enemy, "boss", False) else _article(enemy.name)


def _hp_color(ratio):
    return HP_LOW if ratio <= 0.3 else HP_FULL


def _status_text(statuses):
    parts = []
    for s in statuses:
        name = getattr(s, "name", None) or getattr(s, "tag", "") or getattr(s, "type", "")
        stacks = getattr(s, "stacks", 1)
        parts.append(f"{name} x{stacks}" if stacks and stacks > 1 else name)
    return ", ".join(p for p in parts if p)


def _reveal_lines(reveal):
    resistances = ", ".join(f"{k} {v:g}x" for k, v in sorted(reveal.resistances.items())) or "none"
    return [
        f"Identify: {reveal.name} (Lvl {reveal.level})",
        f"  Power {reveal.power} | Armor {reveal.armor} | Speed {reveal.speed}",
        f"  Resistances: {resistances}",
        f"  Tags: {', '.join(reveal.tags) if reveal.tags else 'none'}",
        f"  Skills: {', '.join(reveal.skills) if reveal.skills else 'none'}",
    ]


def enemy_nameplate(enemy) -> str:
    """B49: the combat nameplate — enemy name + its level. B65: bosses are
    marked so the wall reads as intentional."""
    if getattr(enemy, "boss", False):
        return f"{enemy.name}   Lv {enemy.level}  [BOSS]"
    return f"{enemy.name}   Lv {enemy.level}"




# --- entry point -----------------------------------------------------------


NAME_MAX_LEN = 18


def _class_stat_lines(engine: GameEngine, cls) -> list[str]:
    weapon = engine.content.weapons.get(cls.starting_weapon_id)
    weapon_name = weapon.name if weapon else cls.starting_weapon_id
    skill_names = [
        engine.content.actions[a].name
        for a in cls.starting_skill_ids
        if a in engine.content.actions
    ]
    return [
        f"Max HP      {cls.max_hp}",
        f"Base damage {cls.base_damage}",
        f"Armor       {cls.armor}",
        f"Wisdom      {cls.wisdom}  (Mana {cls.wisdom * entities.MANA_PER_WISDOM})",
        f"Speed       {cls.speed}",
        f"Crit chance {cls.crit_chance}%",
        "",
        f"Weapon: {weapon_name}",
        f"Skills: {', '.join(skill_names) if skill_names else 'none'}",
    ]


def character_creation(engine: GameEngine) -> tuple[str, str]:
    """Name entry + class selection with a live stat preview.

    Returns (name, class_id). Mutates nothing — caller drives start_new_game.
    """
    classes = list(engine.content.classes.values())
    pygame.init()
    pygame.display.set_caption(T.CAPTION_CREATE)
    display = acquire_display((WIDTH, HEIGHT))
    screen = pygame.Surface((WIDTH, HEIGHT))  # fixed canvas, centered on display
    offset = (0, 0, 1.0)
    font = pygame.font.SysFont("menlo,consolas,monospace", 17)
    font_sm = pygame.font.SysFont("menlo,consolas,monospace", 14)
    font_lg = pygame.font.SysFont("menlo,consolas,monospace", 28, bold=True)
    clock = pygame.time.Clock()

    name = ""
    selected = 0
    name_box = pygame.Rect(PAD + 110, 96, 380, 40)
    list_rects = [pygame.Rect(PAD, 200 + i * 50, 360, 42) for i in range(len(classes))]
    preview = pygame.Rect(list_rects[0].right + PAD, 200, WIDTH - list_rects[0].right - 2 * PAD, 380)
    start_rect = pygame.Rect(WIDTH // 2 - 130, HEIGHT - 70, 260, 46)
    cursor_on = True
    cursor_ticks = 0

    def finish():
        return (name.strip() or "Hero", classes[selected].id)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            if event.type == pygame.VIDEORESIZE:
                display = set_display_mode((event.w, event.h))
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                click = to_canvas(event.pos, offset)
                for i, rect in enumerate(list_rects):
                    if rect.collidepoint(click):
                        selected = i
                if start_rect.collidepoint(click):
                    return finish()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit(0)
                if event.key == pygame.K_RETURN:
                    return finish()
                if event.key == pygame.K_BACKSPACE:
                    name = name[:-1]
                elif event.key == pygame.K_TAB or event.key == pygame.K_DOWN:
                    selected = (selected + 1) % len(classes)
                elif event.key == pygame.K_UP:
                    selected = (selected - 1) % len(classes)
                elif event.unicode and event.unicode.isprintable() and len(name) < NAME_MAX_LEN:
                    name += event.unicode

        cursor_ticks += 1
        if cursor_ticks >= FPS // 2:
            cursor_on = not cursor_on
            cursor_ticks = 0

        screen.fill(BG)
        title = font_lg.render(T.CREATE_TITLE, True, ACCENT)
        screen.blit(title, title.get_rect(center=(WIDTH // 2, 50)))

        # Name field
        screen.blit(font.render(T.CREATE_NAME_LABEL, True, TEXT), (PAD, 106))
        pygame.draw.rect(screen, PANEL, name_box, border_radius=6)
        pygame.draw.rect(screen, ACCENT, name_box, width=2, border_radius=6)
        shown = name if name else "Hero"
        name_color = TEXT if name else TEXT_DIM
        name_surf = font.render(shown + ("|" if cursor_on else ""), True, name_color)
        screen.blit(name_surf, name_surf.get_rect(midleft=(name_box.x + 12, name_box.centery)))

        screen.blit(font_sm.render(T.CREATE_PICK_CLASS, True, TEXT_DIM), (PAD, 176))
        mouse = to_canvas(pygame.mouse.get_pos(), offset)
        for i, (cls, rect) in enumerate(zip(classes, list_rects)):
            if i == selected:
                color = ACCENT
            elif rect.collidepoint(mouse):
                color = BTN_HOVER
            else:
                color = BTN
            pygame.draw.rect(screen, color, rect, border_radius=6)
            pygame.draw.rect(screen, BTN_EDGE, rect, width=1, border_radius=6)
            label_color = BG if i == selected else TEXT
            label = font.render(cls.name, True, label_color)
            screen.blit(label, label.get_rect(midleft=(rect.x + 16, rect.centery)))

        # Preview panel
        pygame.draw.rect(screen, PANEL, preview, border_radius=8)
        pygame.draw.rect(screen, PANEL_EDGE, preview, width=1, border_radius=8)
        cls = classes[selected]
        screen.blit(font_lg.render(cls.name, True, ACCENT), (preview.x + 16, preview.y + 14))
        for j, line in enumerate(_class_stat_lines(engine, cls)):
            screen.blit(font.render(line, True, TEXT), (preview.x + 16, preview.y + 64 + j * 26))

        # Start button
        color = BTN_HOVER if start_rect.collidepoint(mouse) else BTN
        pygame.draw.rect(screen, color, start_rect, border_radius=8)
        pygame.draw.rect(screen, GOOD, start_rect, width=2, border_radius=8)
        start_label = font.render(T.CREATE_START, True, TEXT)
        screen.blit(start_label, start_label.get_rect(center=start_rect.center))

        offset = present(display, screen, BG)
        clock.tick(FPS)


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    class_id = argv[0] if argv else ""
    engine = GameEngine()
    if class_id:
        if class_id not in engine.content.classes:
            valid = ", ".join(engine.content.classes)
            raise SystemExit(T.unknown_class(class_id, valid))
        name = "Hero"
    else:
        name, class_id = character_creation(engine)
    engine.start_new_game(name, class_id)
    BattleApp(engine).run()


if __name__ == "__main__":
    main()
