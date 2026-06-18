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

import sys
from dataclasses import dataclass, field
from typing import Callable

import pygame

from rpg_game.core import combat
from rpg_game.core.game import GameEngine
from rpg_game.core.view import build_snapshot
from rpg_game.presentation import ui_text as T

# --- Layout ----------------------------------------------------------------

WIDTH, HEIGHT = 1024, 680
FPS = 60

PAD = 16
ENEMY_PANEL = pygame.Rect(PAD, PAD, WIDTH - 2 * PAD, 150)
LOG_PANEL = pygame.Rect(PAD, ENEMY_PANEL.bottom + PAD, WIDTH - 2 * PAD, 300)
PLAYER_PANEL = pygame.Rect(PAD, LOG_PANEL.bottom + PAD, 600, HEIGHT - LOG_PANEL.bottom - 2 * PAD)
ACTION_PANEL = pygame.Rect(PLAYER_PANEL.right + PAD, PLAYER_PANEL.top, WIDTH - PLAYER_PANEL.right - 2 * PAD, PLAYER_PANEL.height)

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


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    on_click: Callable[[], None]
    enabled: bool = True
    hotkey: str = ""
    sublabel: str = ""


@dataclass
class BattleApp:
    engine: GameEngine
    screen: pygame.Surface = field(init=False)
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
    log: list[tuple[str, tuple[int, int, int]]] = field(default_factory=list)
    mode: str = "combat"  # combat | submenu | stat_choice | game_over | victory_idle
    submenu_kind: str = ""
    buttons: list[Button] = field(default_factory=list)
    banner: str = ""
    banner_color: tuple[int, int, int] = TEXT
    running: bool = True
    outcome: str = ""  # set when a non-standalone battle resolves
    _pending_outcome: str = ""  # single-battle result awaiting press-to-continue

    # -- lifecycle ----------------------------------------------------------

    def __post_init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(T.CAPTION_BATTLE)
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("menlo,consolas,monospace", 16)
        self.font_sm = pygame.font.SysFont("menlo,consolas,monospace", 13)
        self.font_lg = pygame.font.SysFont("menlo,consolas,monospace", 22, bold=True)
        if self.enemy is not None:
            # Single battle against a supplied enemy (e.g. a wild encounter).
            self.set_mode("combat")
            self.push_log(T.appears(_article(self.enemy.name), self.enemy.name), ACCENT)
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
        self.push_log(T.appears(_article(self.enemy.name), self.enemy.name), ACCENT)

    # -- logging ------------------------------------------------------------

    def push_log(self, text: str, color: tuple[int, int, int] = TEXT) -> None:
        self.log.append((text, color))
        del self.log[:-300]

    # -- command dispatch ---------------------------------------------------

    def issue_turn(self, action_id: str) -> None:
        if self.enemy is None or self.mode not in {"combat", "submenu"}:
            return
        result = self.engine.run_combat_turn(self.enemy, action_id)
        self._consume_result(result)

    def issue_flee(self) -> None:
        if self.enemy is None or self.mode != "combat":
            return
        result = self.engine.attempt_flee(self.enemy)
        self._consume_result(result, fled_action=True)

    def _consume_result(self, result: combat.CombatTurnResult, fled_action: bool = False) -> None:
        for event in result.events:
            self.push_log(event)
        if result.enemy_reveal is not None:
            for line in _reveal_lines(result.enemy_reveal):
                self.push_log(line, ACCENT)
        if result.loot_drop is not None:
            self.push_log(_loot_line(result.loot_drop), GOOD)

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
            self.push_log(T.VICTORY_LOG, GOOD)
            if result.xp_gained:
                self.push_log(T.xp_gain(result.xp_gained), XP_COL)
            if result.gold_gained:
                self.push_log(T.gold_gain(result.gold_gained), WARN)
            self.enemy = None
            if result.pending_stat_choices > 0:
                self.set_mode("stat_choice")  # resolve choices before returning
            elif self.standalone:
                self.banner = T.VICTORY_NEXT
                self.banner_color = GOOD
                self.set_mode("victory_idle")
            else:
                self._show_result("victory")
            return
        if result.outcome == "defeat":
            self.push_log(T.DEFEATED_LOG, BAD)
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
        self.push_log(message, XP_COL)
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
        if event.type == pygame.KEYDOWN:
            self._handle_key(event)
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for button in self.buttons:
                if button.enabled and button.rect.collidepoint(event.pos):
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
        key_char = event.unicode.lower() if event.unicode else ""
        for button in self.buttons:
            if button.enabled and button.hotkey and button.hotkey == key_char:
                button.on_click()
                return

    # -- rendering ----------------------------------------------------------

    def draw(self) -> None:
        self.screen.fill(BG)
        snapshot = build_snapshot(self.engine)
        self._draw_enemy_panel()
        self._draw_log_panel()
        self._draw_player_panel(snapshot)
        self.buttons = []
        if self.mode == "submenu":
            self._build_submenu(snapshot)
        elif self.mode == "stat_choice":
            self._build_stat_buttons()
        else:
            self._build_action_buttons(snapshot)
        self._draw_buttons()
        if self.banner:
            self._draw_banner()
        pygame.display.flip()

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

    def _draw_enemy_panel(self):
        self._panel(ENEMY_PANEL, T.PANEL_ENEMY)
        enemy = self.enemy
        if enemy is None:
            self._text("—", (ENEMY_PANEL.x + 12, ENEMY_PANEL.y + 34), self.font_lg, TEXT_DIM)
            return
        self._text(enemy.name, (ENEMY_PANEL.x + 12, ENEMY_PANEL.y + 28), self.font_lg)
        bar = pygame.Rect(ENEMY_PANEL.x + 12, ENEMY_PANEL.y + 64, ENEMY_PANEL.width - 24, 26)
        hp_ratio = enemy.hp / enemy.max_hp if enemy.max_hp else 0
        self._bar(bar, hp_ratio, _hp_color(hp_ratio), f"HP {enemy.hp}/{enemy.max_hp}")
        info_y = bar.bottom + 8
        statuses = _status_text(enemy.active_statuses)
        if getattr(enemy, "charging_action_id", ""):
            action = self.engine.content.actions.get(enemy.charging_action_id)
            statuses = (statuses + " | " if statuses else "") + f"CHARGING {action.name if action else '?'}!"
        if statuses:
            self._text(statuses, (ENEMY_PANEL.x + 12, info_y), self.font_sm, WARN)
            info_y += 18
        if getattr(enemy, "identified", False):
            line = f"Lvl {enemy.level} | Power {enemy.damage} | Armor {enemy.armor} | Speed {enemy.speed}"
            self._text(line, (ENEMY_PANEL.x + 12, info_y), self.font_sm, TEXT_DIM)
        else:
            self._text(T.UNIDENTIFIED, (ENEMY_PANEL.x + 12, info_y), self.font_sm, TEXT_DIM)

    def _draw_log_panel(self):
        self._panel(LOG_PANEL, T.PANEL_LOG)
        line_h = 18
        top = LOG_PANEL.y + 28
        max_lines = (LOG_PANEL.height - 36) // line_h
        visible = self.log[-max_lines:]
        for i, (text, color) in enumerate(visible):
            self._text(text[:120], (LOG_PANEL.x + 12, top + i * line_h), self.font_sm, color)

    def _draw_player_panel(self, snapshot):
        self._panel(PLAYER_PANEL, T.PANEL_PLAYER)
        p = snapshot.player
        x = PLAYER_PANEL.x + 12
        self._text(f"{p.name} — {p.class_name} (Lvl {p.level})", (x, PLAYER_PANEL.y + 28), self.font, TEXT)
        hp_bar = pygame.Rect(x, PLAYER_PANEL.y + 54, PLAYER_PANEL.width - 24, 22)
        self._bar(hp_bar, p.hp / p.max_hp if p.max_hp else 0, _hp_color(p.hp / p.max_hp if p.max_hp else 0), f"HP {p.hp}/{p.max_hp}")
        mana_bar = pygame.Rect(x, hp_bar.bottom + 6, PLAYER_PANEL.width - 24, 18)
        self._bar(mana_bar, p.mana / p.max_mana if p.max_mana else 0, MANA, f"Mana {p.mana}/{p.max_mana}")
        xp_bar = pygame.Rect(x, mana_bar.bottom + 6, PLAYER_PANEL.width - 24, 14)
        self._bar(xp_bar, p.xp / p.xp_required if p.xp_required else 0, XP_COL, f"XP {p.xp}/{p.xp_required}")
        weapon = self.engine.content.weapons[p.equipped_weapon_id]
        line = f"DMG {p.total_damage}  ARM {p.armor}  SPD {p.speed}  CRIT {p.crit_chance}%  GOLD {p.gold}"
        self._text(line, (x, xp_bar.bottom + 8), self.font_sm, TEXT_DIM)
        self._text(f"Weapon: {weapon.name}", (x, xp_bar.bottom + 26), self.font_sm, TEXT_DIM)
        statuses = _status_text(p.statuses)
        if statuses:
            self._text(f"Status: {statuses}", (x, xp_bar.bottom + 44), self.font_sm, WARN)

    # -- buttons ------------------------------------------------------------

    def _action_rects(self, count):
        rects = []
        col_w = (ACTION_PANEL.width - 36) // 2
        row_h = 44
        for i in range(count):
            col, row = i % 2, i // 2
            x = ACTION_PANEL.x + 12 + col * (col_w + 12)
            y = ACTION_PANEL.y + 28 + row * (row_h + 8)
            rects.append(pygame.Rect(x, y, col_w, row_h))
        return rects

    def _build_action_buttons(self, snapshot):
        self._panel(ACTION_PANEL, T.PANEL_ACTIONS)
        if self.mode != "combat" or self.enemy is None:
            if self.mode == "victory_idle":
                self._text(T.NEXT_ENEMY_HINT, (ACTION_PANEL.x + 12, ACTION_PANEL.y + 34), self.font_sm, GOOD)
            elif self.mode == "game_over":
                self._text(T.QUIT_HINT, (ACTION_PANEL.x + 12, ACTION_PANEL.y + 34), self.font_sm, BAD)
            elif self.mode == "result":
                self._text(T.CONTINUE_HINT, (ACTION_PANEL.x + 12, ACTION_PANEL.y + 34), self.font_sm, self.banner_color)
            return
        specs = [
            (*T.ACTION_ATTACK, lambda: self.issue_turn("attack"), True),
            (*T.ACTION_SKILL, lambda: self.open_submenu("skill"), bool(snapshot.skills)),
            (*T.ACTION_ITEM, lambda: self.open_submenu("item"), self._has_consumables()),
            (*T.ACTION_SWAP, lambda: self.open_submenu("swap"), self._has_swappable(snapshot)),
            (*T.ACTION_IDENTIFY, lambda: self.issue_turn("identify"), not getattr(self.enemy, "identified", False)),
            (*T.ACTION_FLEE, self.issue_flee, True),
        ]
        for rect, (label, hotkey, cb, enabled) in zip(self._action_rects(len(specs)), specs):
            self.buttons.append(Button(rect, f"[{hotkey}] {label}", cb, enabled, hotkey))

    def _build_submenu(self, snapshot):
        self._panel(ACTION_PANEL, f"{self.submenu_kind.upper()}  (Esc to back)")
        options = self._submenu_options(snapshot)
        if not options:
            self._text(T.NOTHING_AVAILABLE, (ACTION_PANEL.x + 12, ACTION_PANEL.y + 34), self.font_sm, TEXT_DIM)
        rects = self._action_rects(len(options) + 1)
        for rect, (label, action_id, enabled, sub) in zip(rects, options):
            self.buttons.append(Button(rect, label, (lambda a=action_id: self.issue_turn(a)), enabled, sublabel=sub))
        back_rect = rects[len(options)] if len(rects) > len(options) else self._action_rects(len(options) + 1)[-1]
        self.buttons.append(Button(back_rect, "[Esc] Back", lambda: self.set_mode("combat"), True, "\x1b"))

    def _build_stat_buttons(self):
        self._panel(ACTION_PANEL, "LEVEL UP — choose a bonus")
        specs = T.STAT_CHOICES
        for rect, (label, stat) in zip(self._action_rects(len(specs)), specs):
            self.buttons.append(Button(rect, label, (lambda s=stat: self.apply_stat(s)), True))

    def _draw_buttons(self):
        mouse = pygame.mouse.get_pos()
        for b in self.buttons:
            if not b.enabled:
                color = BTN_DISABLED
            elif b.rect.collidepoint(mouse):
                color = BTN_HOVER
            else:
                color = BTN
            pygame.draw.rect(self.screen, color, b.rect, border_radius=6)
            pygame.draw.rect(self.screen, BTN_EDGE, b.rect, width=1, border_radius=6)
            label_color = TEXT if b.enabled else TEXT_DIM
            label = self.font.render(b.label, True, label_color)
            if b.sublabel:
                self.screen.blit(label, (b.rect.x + 10, b.rect.y + 6))
                self._text(b.sublabel, (b.rect.x + 10, b.rect.y + 24), self.font_sm, TEXT_DIM)
            else:
                self.screen.blit(label, label.get_rect(midleft=(b.rect.x + 12, b.rect.centery)))

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


def _article(noun: str) -> str:
    return "an" if noun[:1].lower() in "aeiou" else "a"


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


def _loot_line(loot):
    name = getattr(loot, "item_name", None) or getattr(loot, "name", "loot")
    rarity = getattr(loot, "rarity_label", None) or getattr(loot, "rarity", "")
    return f"Loot: {name}" + (f" [{rarity}]" if rarity else "")


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
        f"Max mana    {cls.max_mana}",
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
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
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
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for i, rect in enumerate(list_rects):
                    if rect.collidepoint(event.pos):
                        selected = i
                if start_rect.collidepoint(event.pos):
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
        mouse = pygame.mouse.get_pos()
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

        pygame.display.flip()
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
