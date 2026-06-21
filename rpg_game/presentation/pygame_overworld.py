"""Pygame overworld — free-walk world connected to the engine (Model B).

Presentation layer. Core (`rpg_game/core`) holds all rules; here we only render
state via `build_snapshot()` and mutate via existing `GameEngine` methods, same
contract as the battle and character-creation shells.

Model B = free walk (WASD) over a walkable world. Towns are tiles you step onto;
entering one sets the engine's current location (`engine.enter_place`). Pressing
Enter on a town opens the location menu for local services. Character,
inventory, skills/talents and system actions are overworld overlays opened with
hotkeys from anywhere outside battle.

The playable core zone (around Hordanita) is data-driven via
`rpg_game/data/maps/core_zone.json`. The rest of the world is intended but not
playable yet: the edges are GATED — blocked tiles with a one-line explanation.
The gate is meant to be MOVED outward (open more tiles/towns) when a future zone
ships, not deleted.

Wild encounters and the overworld<->battle loop are added in the next slice.

Run:

    python3 -m rpg_game.presentation.pygame_overworld
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field

import pygame
from pytmx.util_pygame import load_pygame

from rpg_game.core import combat
from rpg_game.core.game import GameEngine
from rpg_game.core.view import build_snapshot
from rpg_game.presentation import ui_text as T
from rpg_game.presentation.playtest_logger import PlaytestLogger
from rpg_game.presentation.pygame_battle import BattleApp, character_creation

MAPS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "maps")
DEFAULT_MAP = os.path.join(MAPS_DIR, "testmap.tmx")
ZONE_CONFIG = os.path.join(MAPS_DIR, "core_zone.json")
SAVE_PATH = "savegame.json"

FPS = 60
PLAYER_SIZE = 20
PLAYER_SPEED = 3
COLLISION_LAYER = "walls"

# Colors (shared palette with the battle shell)
BG = (18, 20, 28)
PANEL = (30, 34, 46)
PANEL_EDGE = (60, 66, 86)
TEXT = (222, 226, 235)
TEXT_DIM = (140, 148, 166)
ACCENT = (120, 170, 255)
GOOD = (120, 220, 140)
WARN = (235, 180, 90)
BAD = (230, 110, 110)
BTN = (46, 52, 70)
BTN_HOVER = (66, 76, 102)
BTN_DISABLED = (34, 38, 50)
BTN_EDGE = (90, 100, 130)
PLAYER_COLOR = (235, 200, 90)
PLAYER_EDGE = (40, 36, 16)
TOWN_COLOR = (90, 150, 230)
TOWN_HUB = (120, 220, 140)
GATE_COLOR = (150, 90, 70)


# --- zone config -----------------------------------------------------------


@dataclass(frozen=True)
class ZoneConfig:
    map_path: str
    start_tile: tuple[int, int]
    encounter_rate_per_step: float
    wild_region_place_id: str
    respawn_place_id: str
    towns: dict  # (tx, ty) -> place_id
    town_labels: dict  # (tx, ty) -> label
    gates: dict  # (tx, ty) -> message

    @staticmethod
    def load(path: str = ZONE_CONFIG) -> "ZoneConfig":
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        towns = {tuple(t["tile"]): t["place_id"] for t in data.get("towns", [])}
        labels = {tuple(t["tile"]): t.get("label", t["place_id"]) for t in data.get("towns", [])}
        # Gate copy lives in ui_text; JSON references it by message_key (inline
        # "message" still honored as a fallback).
        gates = {
            tuple(g["tile"]): g["message"] if "message" in g else T.gate_message(g.get("message_key", ""))
            for g in data.get("gates", [])
        }
        return ZoneConfig(
            map_path=os.path.join(MAPS_DIR, data["map"]),
            start_tile=tuple(data.get("start_tile", [1, 1])),
            encounter_rate_per_step=float(data.get("encounter_rate_per_step", 0.0)),
            wild_region_place_id=data["wild_region_place_id"],
            respawn_place_id=data.get("respawn_place_id", ""),
            towns=towns,
            town_labels=labels,
            gates=gates,
        )


# --- movement model (pure, headless-testable) ------------------------------


@dataclass
class Overworld:
    map_path: str = DEFAULT_MAP
    gate_messages: dict = field(default_factory=dict)  # (tx, ty) -> message
    town_tiles: dict = field(default_factory=dict)     # (tx, ty) -> place_id
    tmx: object = field(init=False)
    tw: int = field(init=False)
    th: int = field(init=False)
    map_px_w: int = field(init=False)
    map_px_h: int = field(init=False)
    blocked: set = field(init=False)
    player: pygame.Rect = field(init=False)

    def __post_init__(self) -> None:
        self.tmx = load_pygame(self.map_path)
        self.tw, self.th = self.tmx.tilewidth, self.tmx.tileheight
        self.map_px_w = self.tmx.width * self.tw
        self.map_px_h = self.tmx.height * self.th
        self.blocked = self._load_blocked() | set(self.gate_messages)
        self.player = pygame.Rect(0, 0, PLAYER_SIZE, PLAYER_SIZE)
        self._place_player_at_first_free_tile()

    def _load_blocked(self) -> set:
        try:
            layer = self.tmx.get_layer_by_name(COLLISION_LAYER)
        except (ValueError, KeyError):
            return set()
        return {(x, y) for x, y, _img in layer.tiles()}

    def _place_player_at_first_free_tile(self) -> None:
        for ty in range(self.tmx.height):
            for tx in range(self.tmx.width):
                if (tx, ty) not in self.blocked:
                    self.set_tile(tx, ty)
                    return

    def set_tile(self, tx: int, ty: int) -> None:
        self.player.center = (tx * self.tw + self.tw // 2, ty * self.th + self.th // 2)

    @property
    def current_tile(self) -> tuple[int, int]:
        return (self.player.centerx // self.tw, self.player.centery // self.th)

    def town_place_id(self) -> str | None:
        return self.town_tiles.get(self.current_tile)

    def is_blocked(self, rect: pygame.Rect) -> bool:
        if rect.left < 0 or rect.top < 0 or rect.right > self.map_px_w or rect.bottom > self.map_px_h:
            return True
        return any(t in self.blocked for t in self._overlapped_tiles(rect))

    def _overlapped_tiles(self, rect: pygame.Rect):
        left, right = rect.left // self.tw, (rect.right - 1) // self.tw
        top, bottom = rect.top // self.th, (rect.bottom - 1) // self.th
        for ty in range(top, bottom + 1):
            for tx in range(left, right + 1):
                yield (tx, ty)

    def try_move(self, dx: int, dy: int) -> str:
        """Move per-axis; return a gate message if a gate blocked the attempt."""
        message = ""
        for ax, ay in ((dx, 0), (0, dy)):
            if not (ax or ay):
                continue
            moved = self.player.move(ax, ay)
            if self.is_blocked(moved):
                for tile in self._overlapped_tiles(moved):
                    if tile in self.gate_messages:
                        message = self.gate_messages[tile]
            else:
                self.player = moved
        return message

    def camera_offset(self, view_w: int, view_h: int) -> tuple[int, int]:
        if self.map_px_w <= view_w:
            ox = (self.map_px_w - view_w) // 2
        else:
            ox = max(0, min(self.player.centerx - view_w // 2, self.map_px_w - view_w))
        if self.map_px_h <= view_h:
            oy = (self.map_px_h - view_h) // 2
        else:
            oy = max(0, min(self.player.centery - view_h // 2, self.map_px_h - view_h))
        return ox, oy


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    on_click: object
    enabled: bool = True


@dataclass
class TournamentRun:
    tournament: object
    next_index: int = 0
    message: str = ""


# --- app -------------------------------------------------------------------


class OverworldApp:
    def __init__(self, engine: GameEngine | None = None, zone: ZoneConfig | None = None) -> None:
        pygame.init()
        pygame.display.set_caption(T.CAPTION_OVERWORLD)
        pygame.display.set_mode((1, 1))  # video mode for tile .convert() during load
        self.zone = zone or ZoneConfig.load()
        self.engine = engine or self._new_engine()
        self.world = Overworld(self.zone.map_path, dict(self.zone.gates), dict(self.zone.towns))
        self.town_tile_by_place = {place_id: tile for tile, place_id in self.zone.towns.items()}
        self.world.set_tile(*self.town_tile_by_place.get(self.engine.player.current_place_id, self.zone.start_tile))
        self.sync_location()
        self.view_size = (min(self.world.map_px_w, 960), min(self.world.map_px_h, 640))
        self.screen = pygame.display.set_mode(self.view_size)
        self.clock = pygame.time.Clock()
        self.encounter_rate = self.zone.encounter_rate_per_step
        self._last_tile = self.world.current_tile
        self.font = pygame.font.SysFont("menlo,consolas,monospace", 16)
        self.font_sm = pygame.font.SysFont("menlo,consolas,monospace", 13)
        self.font_lg = pygame.font.SysFont("menlo,consolas,monospace", 22, bold=True)
        self.mode = "walk"  # walk | townmenu | store | tournaments | tournament_confirm | tournament_intermission
        self.overlay = ""  # character | inventory | skills_talents | system
        self.selected_tournament_id = ""
        self.tournament_run: TournamentRun | None = None
        self.buttons: list[Button] = []
        self.toast = ""
        self.toast_color = TEXT
        self.toast_timer = 0
        self.running = True
        self.playtest_logger = PlaytestLogger()
        self.playtest_logger.session_start(build_snapshot(self.engine))

    def _new_engine(self) -> GameEngine:
        engine = GameEngine()
        first_class = next(iter(engine.content.classes))
        engine.start_new_game("Hero", first_class)
        return engine

    # -- engine glue --------------------------------------------------------

    def sync_location(self) -> None:
        """Keep engine location in step with the tile under the player."""
        place_id = self.world.town_place_id() or self.zone.wild_region_place_id
        if place_id != self.engine.player.current_place_id:
            self.engine.enter_place(place_id)

    def set_toast(self, message: str, color=TEXT) -> None:
        self.toast = message
        self.toast_color = color
        self.toast_timer = FPS * 3

    # -- wild encounters + battle loop --------------------------------------

    def maybe_encounter(self):
        """Roll a per-step wild encounter. Returns an enemy or None.

        Only in wilderness; uses the engine's seeded RNG and its existing
        encounter generation for the current region (set by sync_location).
        """
        if self.world.town_place_id() is not None:
            return None
        if self.engine.rng.random() < self.encounter_rate:
            return self.engine.create_encounter()
        return None

    def start_battle(self, enemy) -> None:
        """Hand off to the battle shell, then return to the overworld."""
        location_id = self.engine.player.current_place_id
        outcome = BattleApp(
            engine=self.engine,
            enemy=enemy,
            standalone=False,
            playtest_logger=self.playtest_logger,
            location_id=location_id,
        ).run()
        # The battle resized the window; restore the overworld view.
        pygame.display.set_caption(T.CAPTION_OVERWORLD)
        self.screen = pygame.display.set_mode(self.view_size)
        self.resolve_battle_outcome(outcome, enemy)

    def resolve_battle_outcome(self, outcome: str, enemy) -> None:
        if outcome == "defeat":
            # Engine already respawned the player; move the sprite to match.
            respawn_place = self.engine.player.current_place_id
            tile = self.town_tile_by_place.get(respawn_place)
            if tile is not None:
                self.world.set_tile(*tile)
            self.sync_location()
            self.set_toast(T.defeat_respawn(self.engine.current_place().name), BAD)
        else:
            # Victory or flee: stay where we are; location is still the wilds.
            self.sync_location()
            if outcome == "fled":
                self.set_toast(T.fled_from(enemy.name), WARN)
            else:
                self.set_toast(T.victory_over(enemy.name), GOOD)
        self._last_tile = self.world.current_tile

    # -- town actions (all go through the engine) ---------------------------

    def do_action(self, action: str) -> None:
        if action in {"character", "inventory", "skills_talents", "system"}:
            self.toggle_overlay(action)
        elif action == "store":
            if self.engine.current_place().has_store:
                self.mode = "store"
            else:
                self.set_toast(T.NO_STORE, TEXT_DIM)
        elif action == "rest":
            result = self.engine.rest()
            self.set_toast(result.message, GOOD if result.outcome == "rested" else TEXT_DIM)
        elif action == "tournaments":
            if self.engine.available_tournaments():
                self.mode = "tournaments"
            else:
                self.set_toast(T.TOURNAMENT_NONE, TEXT_DIM)
        elif action == "save":
            self.save_game()

    def toggle_overlay(self, name: str) -> None:
        self.overlay = "" if self.overlay == name else name

    def save_game(self) -> None:
        result = self.engine.save(SAVE_PATH)
        self.set_toast(result.message, GOOD if result.success else BAD)

    def quit_game(self) -> None:
        self.running = False

    def equip_weapon(self, weapon_id: str) -> None:
        player = self.engine.player
        if weapon_id == player.equipped_weapon_id:
            self.set_toast(T.ALREADY_EQUIPPED, TEXT_DIM)
            return
        weapon = self.engine.content.weapons[weapon_id]
        action = combat.create_weapon_swap_action(weapon)
        result = combat.resolve_action(player, player, action, self.engine.rng, weapon=weapon)
        if result.blocked:
            self.set_toast(" ".join(result.events) or T.CANNOT_EQUIP, BAD)
        else:
            self.set_toast(T.equipped_weapon(weapon.name), GOOD)

    def use_inventory_item(self, item_id: str) -> None:
        result = self.engine.use_consumable(item_id)
        self.set_toast(result.message, GOOD if result.success else BAD)

    def toggle_skill(self, action_id: str, equipped: bool) -> None:
        try:
            message = self.engine.unequip_skill(action_id) if equipped else self.engine.equip_skill(action_id)
            self.set_toast(message, GOOD)
        except ValueError as error:
            self.set_toast(str(error), BAD)

    def buy(self, item_id: str) -> None:
        result = self.engine.buy_item(item_id)
        self.set_toast(result.message, GOOD if result.success else BAD)

    def sell(self, item_id: str) -> None:
        result = self.engine.sell_item(item_id)
        self.set_toast(result.message, GOOD if result.success else BAD)

    def learn_talent(self, node_id: str) -> None:
        try:
            message = self.engine.allocate_talent(node_id)
            self.set_toast(message, GOOD)
        except ValueError as error:
            self.set_toast(str(error), BAD)

    # -- tournament flow ----------------------------------------------------

    def select_tournament(self, tournament_id: str) -> None:
        self.selected_tournament_id = tournament_id
        self.mode = "tournament_confirm"

    def start_tournament_series(self, tournament_id: str | None = None) -> None:
        tournament_id = tournament_id or self.selected_tournament_id
        start = self.engine.start_tournament(tournament_id)
        self.set_toast(start.message, GOOD if start.success else BAD)
        if not start.success or start.tournament is None:
            return
        self.tournament_run = TournamentRun(start.tournament)
        self.overlay = ""
        self._start_next_tournament_match()

    def continue_tournament(self) -> None:
        if self.tournament_run is None:
            self.mode = "townmenu"
            return
        self.overlay = ""
        self._start_next_tournament_match()

    def run_tournament_battle(self, enemy) -> str:
        location_id = self.engine.player.current_place_id
        outcome = BattleApp(
            engine=self.engine,
            enemy=enemy,
            standalone=False,
            allow_flee=False,
            allow_swap=False,
            playtest_logger=self.playtest_logger,
            location_id=location_id,
        ).run()
        pygame.display.set_caption(T.CAPTION_OVERWORLD)
        self.screen = pygame.display.set_mode(self.view_size)
        return outcome

    def _start_next_tournament_match(self) -> None:
        run = self.tournament_run
        if run is None:
            return
        enemy = self.engine.create_tournament_opponent(run.tournament, run.next_index)
        outcome = self.run_tournament_battle(enemy)
        if outcome != "victory":
            self.set_toast(f"Eliminated from {run.tournament.name}.", BAD)
            self._clear_tournament_run()
            return

        run.next_index += 1
        if run.next_index >= len(run.tournament.opponent_ids):
            reward = self.engine.complete_tournament(run.tournament)
            self.set_toast(reward.message, GOOD if reward.success else BAD)
            self._clear_tournament_run()
            return

        recovery = self.engine.recover_between_tournament_matches()
        next_enemy = self.engine.content.enemies[run.tournament.opponent_ids[run.next_index]].name
        run.message = f"{recovery.message} Next opponent: {next_enemy}."
        self.mode = "tournament_intermission"

    def _clear_tournament_run(self) -> None:
        self.tournament_run = None
        self.selected_tournament_id = ""
        self.overlay = ""
        self.mode = "townmenu" if self.world.town_place_id() else "walk"

    # -- input --------------------------------------------------------------

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for button in self.buttons:
                    if button.enabled and button.rect.collidepoint(event.pos):
                        button.on_click()
                        break

    def _handle_key(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_ESCAPE:
            if self.overlay:
                self.overlay = ""
            elif self.mode == "store":
                self.mode = "townmenu"
            elif self.mode in {"tournaments", "tournament_confirm"}:
                self.mode = "townmenu"
            elif self.mode == "tournament_intermission":
                self.overlay = "system"
            elif self.mode == "townmenu":
                self.mode = "walk"
            else:
                self.overlay = "system"
            return
        if event.key == pygame.K_c:
            self.toggle_overlay("character")
            return
        if event.key == pygame.K_i:
            self.toggle_overlay("inventory")
            return
        if event.key == pygame.K_k:
            self.toggle_overlay("skills_talents")
            return
        if event.key in (pygame.K_RETURN, pygame.K_e):
            if self.mode == "walk" and self.world.town_place_id():
                self.mode = "townmenu"
            elif self.mode == "townmenu":
                self.mode = "walk"

    def update(self) -> None:
        if self.toast_timer > 0:
            self.toast_timer -= 1
            if self.toast_timer == 0:
                self.toast = ""
        if self.overlay or self.mode != "walk":
            return
        keys = pygame.key.get_pressed()
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        if dx or dy:
            message = self.world.try_move(dx * PLAYER_SPEED, dy * PLAYER_SPEED)
            if message:
                self.set_toast(message, WARN)
            self.sync_location()
            tile = self.world.current_tile
            if tile != self._last_tile:
                self._last_tile = tile
                enemy = self.maybe_encounter()
                if enemy is not None:
                    self.start_battle(enemy)

    # -- rendering ----------------------------------------------------------

    def draw(self) -> None:
        self.buttons = []
        self.screen.fill(BG)
        self._draw_map()
        self._draw_hud()
        if self.mode == "townmenu":
            self._draw_town_menu()
        elif self.mode == "store":
            self._draw_store_screen()
        elif self.mode == "tournaments":
            self._draw_tournament_list_screen()
        elif self.mode == "tournament_confirm":
            self._draw_tournament_confirm_screen()
        elif self.mode == "tournament_intermission":
            self._draw_tournament_intermission_screen()
        if self.overlay:
            self._draw_overlay_screen()
        if self.toast:
            self._draw_toast()
        pygame.display.flip()

    def _draw_map(self) -> None:
        view_w, view_h = self.screen.get_size()
        ox, oy = self.world.camera_offset(view_w, view_h)
        tmx = self.world.tmx
        tw, th = self.world.tw, self.world.th
        for layer in tmx.visible_layers:
            if hasattr(layer, "tiles"):
                for x, y, image in layer.tiles():
                    self.screen.blit(image, (x * tw - ox, y * th - oy))
        for (tx, ty), place_id in self.world.town_tiles.items():
            rect = pygame.Rect(tx * tw - ox + 4, ty * th - oy + 4, tw - 8, th - 8)
            color = TOWN_HUB if place_id == self.zone.respawn_place_id else TOWN_COLOR
            pygame.draw.rect(self.screen, color, rect, border_radius=4)
            pygame.draw.rect(self.screen, BG, rect, width=2, border_radius=4)
            label = self.zone.town_labels.get((tx, ty), place_id)
            surf = self.font_sm.render(label, True, TEXT)
            self.screen.blit(surf, surf.get_rect(center=(tx * tw - ox + tw // 2, ty * th - oy - 8)))
        for (tx, ty), _msg in self.world.gate_messages.items():
            rect = pygame.Rect(tx * tw - ox + 2, ty * th - oy + 2, tw - 4, th - 4)
            pygame.draw.rect(self.screen, GATE_COLOR, rect, border_radius=3)
            for gx in range(rect.left + 5, rect.right, 8):
                pygame.draw.line(self.screen, BG, (gx, rect.top), (gx, rect.bottom), 2)
        player = self.world.player.move(-ox, -oy)
        pygame.draw.rect(self.screen, PLAYER_COLOR, player, border_radius=4)
        pygame.draw.rect(self.screen, PLAYER_EDGE, player, width=2, border_radius=4)

    def _draw_hud(self) -> None:
        snap = build_snapshot(self.engine)
        place = self.engine.current_place()
        in_town = self.world.town_place_id() is not None
        bar = pygame.Rect(0, 0, self.screen.get_width(), 26)
        overlay = pygame.Surface(bar.size, pygame.SRCALPHA)
        overlay.fill((10, 12, 18, 200))
        self.screen.blit(overlay, (0, 0))
        where = place.name if in_town else T.wilds_near(place.name)
        left = f"{snap.player.name}  Lv{snap.player.level}  HP {snap.player.hp}/{snap.player.max_hp}  Gold {snap.player.gold}"
        self.screen.blit(self.font_sm.render(left, True, TEXT), (8, 6))
        right = self.font_sm.render(where, True, ACCENT if in_town else TEXT_DIM)
        self.screen.blit(right, right.get_rect(topright=(self.screen.get_width() - 8, 6)))
        if self.mode == "walk":
            hint = T.HINT_TOWN if in_town else T.HINT_WALK
            hsurf = self.font_sm.render(hint, True, TEXT_DIM)
            self.screen.blit(hsurf, hsurf.get_rect(midbottom=(self.screen.get_width() // 2, self.screen.get_height() - 6)))

    def _overlay_panel(self, title: str) -> pygame.Rect:
        w, h = self.screen.get_size()
        panel = pygame.Rect(w // 2 - 320, h // 2 - 220, 640, 440)
        shade = pygame.Surface((w, h), pygame.SRCALPHA)
        shade.fill((6, 8, 12, 180))
        self.screen.blit(shade, (0, 0))
        pygame.draw.rect(self.screen, PANEL, panel, border_radius=10)
        pygame.draw.rect(self.screen, PANEL_EDGE, panel, width=1, border_radius=10)
        self.screen.blit(self.font_lg.render(title, True, ACCENT), (panel.x + 20, panel.y + 16))
        return panel

    def _add_button(self, rect, label, cb, enabled=True) -> None:
        self.buttons.append(Button(rect, label, cb, enabled))

    def _draw_buttons(self) -> None:
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
            label = self.font.render(b.label, True, TEXT if b.enabled else TEXT_DIM)
            self.screen.blit(label, label.get_rect(midleft=(b.rect.x + 12, b.rect.centery)))

    def _draw_town_menu(self) -> None:
        panel = self._overlay_panel(self.engine.current_place().name)
        has_store = self.engine.current_place().has_store
        col_w = (panel.width - 60) // 2
        actions = list(T.TOWN_ACTIONS)
        if self.engine.available_tournaments():
            actions.append(("tournaments", T.TOWN_TOURNAMENTS))
        for i, (action, label) in enumerate(actions):
            col, row = i % 2, i // 2
            rect = pygame.Rect(panel.x + 20 + col * (col_w + 20), panel.y + 70 + row * 56, col_w, 44)
            enabled = not (action == "store" and not has_store)
            self._add_button(rect, label, (lambda a=action: self.do_action(a)), enabled)
        self.screen.blit(self.font_sm.render(T.BACK_TO_MAP, True, TEXT_DIM),
                         (panel.x + 20, panel.bottom - 30))
        self._draw_buttons()

    def _draw_tournament_list_screen(self) -> None:
        panel = self._overlay_panel(T.SCREEN_TITLES["tournaments"])
        tournaments = build_snapshot(self.engine).tournaments
        if not tournaments:
            self._lines(panel, [T.TOURNAMENT_NONE], TEXT_DIM)
        for i, tournament in enumerate(tournaments[:8]):
            reward = _tournament_reward_text(tournament)
            cleared = " [CLEARED]" if tournament.completed else ""
            label = f"{tournament.name} ({tournament.opponent_count} fights) - {reward}{cleared}"
            rect = pygame.Rect(panel.x + 20, panel.y + 70 + i * 44, panel.width - 40, 36)
            self._add_button(rect, label, (lambda tid=tournament.id: self.select_tournament(tid)), not tournament.completed)
        back = pygame.Rect(panel.right - 130, panel.bottom - 54, 110, 40)
        self._add_button(back, T.BACK, lambda: setattr(self, "mode", "townmenu"))
        self._draw_buttons()

    def _draw_tournament_confirm_screen(self) -> None:
        panel = self._overlay_panel(T.SCREEN_TITLES["tournaments"])
        tournament = self.engine.content.tournaments.get(self.selected_tournament_id)
        if tournament is None:
            self._lines(panel, [T.TOURNAMENT_NONE], TEXT_DIM)
        else:
            reward = _tournament_reward_text_by_data(self.engine, tournament)
            lines = [
                tournament.name,
                f"{len(tournament.opponent_ids)} fights in a row. Reward: {reward}.",
                "",
                *T.TOURNAMENT_SERIES_WARNING_LINES,
                "",
                tournament.description,
            ]
            self._lines(panel, lines, start=64, step=26)
            self._add_button(
                pygame.Rect(panel.x + 20, panel.bottom - 54, 190, 40),
                T.TOURNAMENT_START,
                lambda: self.start_tournament_series(tournament.id),
            )
        self._add_button(pygame.Rect(panel.right - 130, panel.bottom - 54, 110, 40),
                         T.BACK, lambda: setattr(self, "mode", "tournaments"))
        self._draw_buttons()

    def _draw_tournament_intermission_screen(self) -> None:
        panel = self._overlay_panel(T.SCREEN_TITLES["tournaments"])
        run = self.tournament_run
        if run is None:
            self._lines(panel, [T.TOURNAMENT_NONE], TEXT_DIM)
        else:
            total = len(run.tournament.opponent_ids)
            lines = [
                f"{run.tournament.name}: match {run.next_index + 1}/{total}",
                run.message,
                "",
                *T.TOURNAMENT_SERIES_WARNING_LINES,
            ]
            self._lines(panel, lines, start=64, step=26)
            self._add_button(
                pygame.Rect(panel.x + 20, panel.bottom - 54, 180, 40),
                T.TOURNAMENT_NEXT,
                self.continue_tournament,
            )
            self._add_button(
                pygame.Rect(panel.x + 220, panel.bottom - 54, 210, 40),
                T.TOURNAMENT_EQUIP,
                lambda: self.toggle_overlay("character"),
            )
        self._draw_buttons()

    def _draw_overlay_screen(self) -> None:
        panel = self._overlay_panel(T.SCREEN_TITLES.get(self.overlay, self.overlay.capitalize()))
        renderer = getattr(self, f"_overlay_{self.overlay}")
        renderer(panel)
        back = pygame.Rect(panel.right - 130, panel.bottom - 54, 110, 40)
        self._add_button(back, T.BACK, lambda: setattr(self, "overlay", ""))
        self._draw_buttons()

    def _lines(self, panel, lines, color=TEXT, start=64, step=24) -> int:
        for i, line in enumerate(lines):
            self.screen.blit(self.font.render(line, True, color), (panel.x + 20, panel.y + start + i * step))
        return panel.y + start + len(lines) * step

    def _draw_store_screen(self) -> None:
        panel = self._overlay_panel(T.SCREEN_TITLES["store"])
        self._screen_store(panel)
        back = pygame.Rect(panel.right - 130, panel.bottom - 54, 110, 40)
        self._add_button(back, T.BACK, lambda: setattr(self, "mode", "townmenu"))
        self._draw_buttons()

    def _overlay_character(self, panel) -> None:
        snap = build_snapshot(self.engine)
        p = snap.player
        y = self._lines(panel, [
            f"{p.name} — {p.class_name} (Lv {p.level})",
            f"HP {p.hp}/{p.max_hp}    Mana {p.mana}/{p.max_mana}",
            f"XP {p.xp}/{p.xp_required}    Talent points {p.talent_points}",
            f"Damage {p.total_damage} (base {p.base_damage} + weapon {p.weapon_damage_bonus})",
            f"Armor {p.armor}    Speed {p.speed}    Crit {p.crit_chance}%",
            f"Gold {p.gold}",
            "",
            T.EQUIP_HINT,
        ], step=22)
        for i, w in enumerate(snap.weapons[:6]):
            rect = pygame.Rect(panel.x + 20, y + 8 + i * 38, panel.width - 40, 32)
            suffix = " [equipped]" if w.equipped else ("" if w.equippable else f"  needs Lv {w.required_level}")
            self._add_button(rect, f"{w.name} (+{w.damage_bonus} {w.damage_type}, tier {w.tier}){suffix}",
                             (lambda wid=w.id: self.equip_weapon(wid)), w.equippable and not w.equipped)

    def _overlay_inventory(self, panel) -> None:
        eng = self.engine
        self.screen.blit(self.font_sm.render(T.INVENTORY_HINT, True, TEXT_DIM),
                         (panel.x + 20, panel.y + 56))
        consumables = [
            (item_id, count)
            for item_id, count in sorted(eng.player.inventory.consumables.items())
            if count > 0 and eng.content.items[item_id].kind == "consumable"
        ]
        junk = [
            (item_id, count)
            for item_id, count in sorted(eng.player.inventory.consumables.items())
            if count > 0 and eng.content.items[item_id].kind != "consumable"
        ]

        self.screen.blit(self.font.render(T.INV_HEADER_CONSUMABLES, True, TEXT), (panel.x + 20, panel.y + 86))
        if consumables:
            for i, (item_id, count) in enumerate(consumables[:6]):
                item = eng.content.items[item_id]
                rect = pygame.Rect(panel.x + 20, panel.y + 114 + i * 36, panel.width - 40, 30)
                self._add_button(rect, f"{item.name} x{count}", (lambda iid=item_id: self.use_inventory_item(iid)))
        else:
            self._lines(panel, [T.INV_NONE], TEXT_DIM, start=114)

        junk_y = panel.y + 114 + max(1, len(consumables[:6])) * 36 + 10
        self.screen.blit(self.font.render(T.INV_HEADER_JUNK, True, TEXT), (panel.x + 20, junk_y))
        if junk:
            for i, (item_id, count) in enumerate(junk[:5]):
                item = eng.content.items[item_id]
                rect = pygame.Rect(panel.x + 20, junk_y + 28 + i * 32, panel.width - 40, 28)
                self._add_button(rect, f"{item.name} x{count} [not usable]", lambda: None, enabled=False)
        else:
            self.screen.blit(self.font.render(T.INV_NONE, True, TEXT_DIM), (panel.x + 20, junk_y + 28))

    def _overlay_skills_talents(self, panel) -> None:
        eng = self.engine
        equipped_ids = set(eng.player.equipped_skill_ids)
        left = pygame.Rect(panel.x + 20, panel.y + 56, (panel.width - 60) // 2, panel.height - 126)
        right = pygame.Rect(left.right + 20, panel.y + 56, (panel.width - 60) // 2, panel.height - 126)

        self.screen.blit(self.font_sm.render(T.skills_hint(len(equipped_ids)), True, TEXT_DIM),
                         (left.x, left.y))
        skills = eng.equippable_skills()
        if not skills:
            self.screen.blit(self.font.render(T.NO_SKILLS, True, TEXT_DIM), (left.x, left.y + 30))
        for i, skill in enumerate(skills[:8]):
            rect = pygame.Rect(left.x, left.y + 30 + i * 34, left.width, 28)
            is_eq = skill.id in equipped_ids
            label = f"{'[E] ' if is_eq else '[ ]'} {skill.name}"
            enabled = is_eq or len(equipped_ids) < 4
            self._add_button(rect, label, (lambda sid=skill.id, eq=is_eq: self.toggle_skill(sid, eq)), enabled)

        self.screen.blit(self.font_sm.render(T.talents_hint(eng.player.talent_points), True, WARN),
                         (right.x, right.y))
        class_nodes = sorted(
            (node for node in eng.content.talents.values() if node.class_id == eng.player.player_class),
            key=lambda node: (node.branch, node.order),
        )
        available_ids = {node.id for node in eng.available_talents()}
        for i, node in enumerate(class_nodes[:10]):
            if node.id in eng.player.learned_talent_ids:
                status = "[LEARNED]"
                enabled = False
            elif node.id in available_ids:
                status = "[CAN LEARN]"
                enabled = eng.player.talent_points > 0
            else:
                status = "[LOCKED]"
                enabled = False
            rect = pygame.Rect(right.x, right.y + 30 + i * 32, right.width, 26)
            label = f"{status} {node.name} ({node.branch} t{node.order})"
            self._add_button(rect, label, (lambda nid=node.id: self.learn_talent(nid)), enabled)

    def _screen_store(self, panel) -> None:
        eng = self.engine
        gold = build_snapshot(eng).player.gold
        self.screen.blit(self.font_sm.render(T.store_hint(gold), True, WARN),
                         (panel.x + 20, panel.y + 56))
        col_w = (panel.width - 60) // 2
        self.screen.blit(self.font.render(T.STORE_BUY, True, TEXT), (panel.x + 20, panel.y + 80))
        for i, entry in enumerate(eng.store_entries()[:6]):
            rect = pygame.Rect(panel.x + 20, panel.y + 106 + i * 38, col_w, 32)
            self._add_button(rect, f"{entry.name}  {entry.price}g", (lambda iid=entry.id: self.buy(iid)), gold >= entry.price)
        self.screen.blit(self.font.render(T.STORE_SELL, True, TEXT), (panel.x + 40 + col_w, panel.y + 80))
        for i, entry in enumerate(eng.sellable_entries()[:6]):
            rect = pygame.Rect(panel.x + 40 + col_w, panel.y + 106 + i * 38, col_w, 32)
            self._add_button(rect, f"{entry.name} x{entry.count}  {entry.value}g", (lambda iid=entry.id: self.sell(iid)))

    def _overlay_system(self, panel) -> None:
        self.screen.blit(self.font_sm.render(T.SYSTEM_HINT, True, TEXT_DIM),
                         (panel.x + 20, panel.y + 56))
        self._add_button(pygame.Rect(panel.x + 20, panel.y + 92, panel.width - 40, 42),
                         T.SYSTEM_SAVE, self.save_game)
        self._add_button(pygame.Rect(panel.x + 20, panel.y + 144, panel.width - 40, 42),
                         T.SYSTEM_QUIT, self.quit_game)

    def _screen_talents(self, panel) -> None:
        eng = self.engine
        points = build_snapshot(eng).player.talent_points
        self.screen.blit(self.font_sm.render(T.talents_hint(points), True, WARN),
                         (panel.x + 20, panel.y + 56))
        nodes = eng.available_talents()
        if not nodes:
            self._lines(panel, [T.NO_TALENTS], TEXT_DIM, start=88)
            return
        for i, node in enumerate(nodes[:8]):
            rect = pygame.Rect(panel.x + 20, panel.y + 84 + i * 40, panel.width - 40, 34)
            self._add_button(rect, f"{node.name}", (lambda nid=node.id: self.learn_talent(nid)), points > 0)

    def _draw_toast(self) -> None:
        surf = self.font.render(self.toast, True, self.toast_color)
        rect = surf.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() - 40))
        bg = rect.inflate(28, 16)
        overlay = pygame.Surface(bg.size, pygame.SRCALPHA)
        overlay.fill((10, 12, 18, 230))
        self.screen.blit(overlay, bg.topleft)
        pygame.draw.rect(self.screen, PANEL_EDGE, bg, width=1, border_radius=6)
        self.screen.blit(surf, rect)

    # -- main loop ----------------------------------------------------------

    def run(self) -> None:
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()


def _tournament_reward_text(tournament) -> str:
    bits = []
    if tournament.reward_gold:
        bits.append(f"{tournament.reward_gold} gold")
    bits.extend(tournament.reward_item_names)
    return ", ".join(bits) if bits else T.TOURNAMENT_REWARD_NONE


def _tournament_reward_text_by_data(engine: GameEngine, tournament) -> str:
    bits = []
    if tournament.reward.gold:
        bits.append(f"{tournament.reward.gold} gold")
    for item_id in tournament.reward.item_ids:
        if item_id in engine.content.weapons:
            bits.append(engine.content.weapons[item_id].name)
        elif item_id in engine.content.items:
            bits.append(engine.content.items[item_id].name)
    return ", ".join(bits) if bits else T.TOURNAMENT_REWARD_NONE


def start_menu_options(save_path: str = SAVE_PATH) -> list[tuple[str, str]]:
    options = [("new", T.START_NEW_GAME)]
    if os.path.exists(save_path):
        options.append(("load", T.START_LOAD_GAME))
    options.append(("quit", T.START_QUIT))
    return options


def engine_from_start_choice(
    choice: str,
    save_path: str = SAVE_PATH,
    creation_fn=character_creation,
) -> GameEngine | None:
    engine = GameEngine()
    if choice == "new":
        name, class_id = creation_fn(engine)
        engine.start_new_game(name, class_id)
        return engine
    if choice == "load":
        result = engine.load(save_path)
        if not result.success:
            raise ValueError(result.message)
        return engine
    if choice == "quit":
        return None
    raise ValueError(f"unknown start menu choice: {choice}")


def start_menu(save_path: str = SAVE_PATH, message: str = "") -> str:
    pygame.init()
    pygame.display.set_caption(T.CAPTION_START)
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    font = pygame.font.SysFont("menlo,consolas,monospace", 20)
    font_sm = pygame.font.SysFont("menlo,consolas,monospace", 14)
    font_lg = pygame.font.SysFont("menlo,consolas,monospace", 34, bold=True)
    clock = pygame.time.Clock()

    while True:
        options = start_menu_options(save_path)
        button_w, button_h = 320, 48
        start_y = HEIGHT // 2 - (len(options) * 60) // 2
        buttons = [
            Button(
                pygame.Rect(WIDTH // 2 - button_w // 2, start_y + index * 60, button_w, button_h),
                label,
                choice,
            )
            for index, (choice, label) in enumerate(options)
        ]

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                for button in buttons:
                    if button.rect.collidepoint(event.pos):
                        return button.on_click
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return "quit"
                key = event.unicode.lower() if event.unicode else ""
                for choice, label in options:
                    if key and key == label[0].lower():
                        return choice

        screen.fill(BG)
        title = font_lg.render(T.START_TITLE, True, ACCENT)
        screen.blit(title, title.get_rect(center=(WIDTH // 2, 150)))
        if message:
            msg = font_sm.render(message, True, BAD)
            screen.blit(msg, msg.get_rect(center=(WIDTH // 2, 198)))

        mouse = pygame.mouse.get_pos()
        for button in buttons:
            color = BTN_HOVER if button.rect.collidepoint(mouse) else BTN
            pygame.draw.rect(screen, color, button.rect, border_radius=8)
            pygame.draw.rect(screen, BTN_EDGE, button.rect, width=1, border_radius=8)
            label = font.render(button.label, True, TEXT)
            screen.blit(label, label.get_rect(center=button.rect.center))

        pygame.display.flip()
        clock.tick(FPS)


def engine_from_start_menu(save_path: str = SAVE_PATH) -> GameEngine | None:
    message = ""
    while True:
        choice = start_menu(save_path, message)
        try:
            return engine_from_start_choice(choice, save_path)
        except ValueError as error:
            message = str(error)


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    engine = GameEngine()
    class_id = argv[0] if argv else ""
    if class_id:
        # Quick-start a class, skipping creation (same shortcut as the battle shell).
        if class_id not in engine.content.classes:
            raise SystemExit(T.unknown_class(class_id, ", ".join(engine.content.classes)))
        engine.start_new_game("Hero", class_id)
    else:
        selected_engine = engine_from_start_menu(SAVE_PATH)
        if selected_engine is None:
            pygame.quit()
            return
        engine = selected_engine
    OverworldApp(engine=engine).run()


if __name__ == "__main__":
    main()
