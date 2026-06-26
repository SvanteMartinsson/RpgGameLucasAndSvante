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

import collections
import json
import os
import sys
from dataclasses import dataclass, field

import pygame
from pytmx.util_pygame import load_pygame

from rpg_game.core import combat, progression
from rpg_game.core.game import GameEngine
from rpg_game.core.view import build_snapshot
from rpg_game.presentation import ui_text as T
from rpg_game.presentation.pygame_canvas import (
    _debug_display, acquire_display, desktop_size, fit_size, open_window, present,
    set_display_mode, to_canvas)
from rpg_game.presentation.playtest_logger import PlaytestLogger
# WIDTH/HEIGHT are the pre-game window size, shared with the character-creation
# screen the start menu flows into — one source, no hardcoded duplicate. (The
# in-world view sizes itself to the map via OverworldApp.view_size instead.)
from rpg_game.presentation.pygame_battle import HEIGHT, WIDTH, BattleApp, character_creation
from rpg_game.presentation.talent_text import talent_detail, talent_status

MAPS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "maps")
DEFAULT_MAP = os.path.join(MAPS_DIR, "testmap.tmx")
ZONE_CONFIG = os.path.join(MAPS_DIR, "core_zone.json")
# Anchor the save to a stable, absolute location (project root) rather than the
# process CWD, so the start menu detects and loads it on a cold start regardless
# of where the game was launched from — not only within the play session.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SAVE_PATH = os.path.join(_PROJECT_ROOT, "savegame.json")

FPS = 60
PLAYER_SIZE = 20
PLAYER_SPEED = 3
COLLISION_LAYER = "walls"
# Player-centered zoom: the world view is scaled so ~this many tiles are visible
# across the window (Platinum-style). Integer zoom only -> crisp pixel art.
ZOOM_TARGET_TILES_W = 10

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
XP_COL = (180, 150, 240)  # matches the battle HUD's XP bar
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
    wild_regions: tuple = ()  # ((place_id, min_x, max_x), ...) by tile x; else default
    ground_themes: tuple = ()  # ((theme, min_x, max_x), ...) in order; zone = index+1

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
        # Regions/themes can bound by tile-x AND tile-y (y defaults to the whole
        # column, so old x-band-only configs are unchanged). The southern Verralda
        # heath is a y-band (min_tile_y); core/west stay x-bands.
        wild_regions = tuple(
            (r["place_id"], r.get("min_tile_x", 0), r.get("max_tile_x", 10**9),
             r.get("min_tile_y", 0), r.get("max_tile_y", 10**9))
            for r in data.get("wild_regions", [])
        )
        ground_themes = tuple(
            (t["theme"], t.get("min_tile_x", 0), t.get("max_tile_x", 10**9),
             t.get("min_tile_y", 0), t.get("max_tile_y", 10**9))
            for t in data.get("ground_themes", [])
        )
        return ZoneConfig(
            map_path=os.path.join(MAPS_DIR, data["map"]),
            start_tile=tuple(data.get("start_tile", [1, 1])),
            encounter_rate_per_step=float(data.get("encounter_rate_per_step", 0.0)),
            wild_region_place_id=data["wild_region_place_id"],
            respawn_place_id=data.get("respawn_place_id", ""),
            towns=towns,
            town_labels=labels,
            gates=gates,
            wild_regions=wild_regions,
            ground_themes=ground_themes,
        )

    def wild_region_at(self, tile: tuple[int, int]) -> str:
        """Encounter/region source for a wilderness tile, by tile-x AND tile-y.
        First matching region wins, so list narrower/southern regions first. Lets
        the western area draw a tier-2 pool and the southern heath its own."""
        tx, ty = tile
        for place_id, min_x, max_x, min_y, max_y in self.wild_regions:
            if min_x <= tx <= max_x and min_y <= ty <= max_y:
                return place_id
        return self.wild_region_place_id

    def zone_for_tile(self, tile: tuple[int, int]) -> int:
        """1-based zone from the ground-theme band the tile falls in (for the
        respawn-relocation cost). Currently x-only; the y bounds are loaded but
        the 2D zone-number derivation is deferred to the enemy/faction slice, so
        the heath reads as the core zone (free relocation) for now."""
        tx = tile[0]
        for index, (_theme, min_x, max_x, _min_y, _max_y) in enumerate(self.ground_themes, start=1):
            if min_x <= tx <= max_x:
                return index
        return 1


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
        # Inherit the window the previous screen (start menu / creation / battle)
        # already opened — possibly maximized or on an external monitor — so
        # entering the overworld never shrinks to a tiny default. Only open a
        # throwaway video mode if none exists yet (needed for tile .convert()).
        prev = pygame.display.get_surface()
        self._inherited_size = prev.get_size() if prev is not None else None
        if prev is None:
            pygame.display.set_mode((1, 1))
        self.zone = zone or ZoneConfig.load()
        self.engine = engine or self._new_engine()
        self.world = Overworld(self.zone.map_path, dict(self.zone.gates), dict(self.zone.towns))
        self.town_tile_by_place = {place_id: tile for tile, place_id in self.zone.towns.items()}
        self.world.set_tile(*self.town_tile_by_place.get(self.engine.player.current_place_id, self.zone.start_tile))
        self.sync_location()
        self.view_size = (min(self.world.map_px_w, 960), min(self.world.map_px_h, 640))
        # Inherit the prior window's size (already a valid on-screen size) so the
        # overworld matches it instead of shrinking; cold start clamps a default.
        if self._inherited_size and self._inherited_size[0] > 1 and self._inherited_size[1] > 1:
            self.windowed_size = self._inherited_size
        else:
            self.windowed_size = fit_size(self.view_size)
        self.fullscreen = False
        # Initial canvas; draw() resizes it to the live display each frame (fluid
        # overworld) so the world fills the window and the camera shows more map.
        self.screen = pygame.Surface(self.view_size)
        self._transform = (0, 0, 1.0)
        self._cam_offset = (0, 0)  # world px offset from the last _draw_map (for screen_to_tile)
        self.display = None
        self._apply_display_mode()
        self.clock = pygame.time.Clock()
        self.encounter_rate = self.zone.encounter_rate_per_step
        self._last_tile = self.world.current_tile
        self._last_region = self.zone.wild_region_at(self._last_tile)
        self.font = pygame.font.SysFont("menlo,consolas,monospace", 16)
        self.font_sm = pygame.font.SysFont("menlo,consolas,monospace", 13)
        self.font_lg = pygame.font.SysFont("menlo,consolas,monospace", 22, bold=True)
        self.mode = "walk"  # walk | townmenu | store | tournaments | tournament_confirm | tournament_intermission
        self.overlay = ""  # character | inventory | skills_talents | system
        self.inventory_category = "consumables"  # selected category in the inventory overlay
        self.overlay_return_mode = ""
        self.selected_equipment_slot = "weapon"
        self.selected_talent_id = ""
        self.selected_tournament_id = ""
        self.tournament_run: TournamentRun | None = None
        self.buttons: list[Button] = []
        self.toast = ""
        self.toast_color = TEXT
        self.toast_timer = 0
        self.running = True
        self.exit_reason = ""
        self.playtest_logger = PlaytestLogger()
        self.playtest_logger.session_start(build_snapshot(self.engine))
        self._last_fills = None  # edge-trigger for anchoring changes in draw()
        self._log_display("init")

    def _log_display(self, trigger: str) -> None:
        """Record current window geometry to the playtest log, tagged with the
        action that triggered it — so a playtest shows which actions cause the
        window to resize / stop filling (the recurring fullscreen bug)."""
        logger = getattr(self, "playtest_logger", None)
        if logger is None or self.display is None:
            return
        try:
            window = pygame.display.get_window_size()
        except Exception:  # pragma: no cover - driver without window info
            window = self.display.get_size()
        try:
            desktops = pygame.display.get_desktop_sizes()
        except Exception:  # pragma: no cover
            desktops = None
        logger.display(
            trigger, self.display.get_size(), window, transform=self._transform,
            mode="fullscreen" if self.fullscreen else "windowed", desktops=desktops,
        )

    def _new_engine(self) -> GameEngine:
        engine = GameEngine()
        first_class = next(iter(engine.content.classes))
        engine.start_new_game("Hero", first_class)
        return engine

    # -- engine glue --------------------------------------------------------

    def sync_location(self) -> None:
        """Keep engine location in step with the tile under the player.

        Wilderness draws from the region under the player (western tiles use the
        zone-2 pool/respawn), towns set their own place.
        """
        place_id = self.world.town_place_id() or self.zone.wild_region_at(self.world.current_tile)
        if place_id != self.engine.player.current_place_id:
            self.engine.enter_place(place_id)

    def set_toast(self, message: str, color=TEXT) -> None:
        self.toast = message
        self.toast_color = color
        self.toast_timer = FPS * 3

    # -- display mode -------------------------------------------------------

    def _apply_display_mode(self) -> None:
        """(Re)create the display surface. Both modes are normal bordered,
        SCALED, resizable windows — never exclusive fullscreen, which on macOS
        hides the window controls and blocks app-switching. "Fullscreen" is just
        a large window (≈ desktop work area); the OS green button still gives true
        native fullscreen with Cmd+Tab and a clear way out. SCALED keeps pixel art
        crisp on HiDPI."""
        pygame.display.set_caption(T.CAPTION_OVERWORLD)
        if self.fullscreen:
            self.display = open_window(desktop_size())   # clamp big mode to the desktop
        else:
            # windowed_size is already valid (clamped on cold start, or inherited
            # from the previous screen) — open at exactly that, no re-clamp that
            # would shrink an external-monitor / maximized window.
            self.display = set_display_mode(self.windowed_size)
            self.windowed_size = self.display.get_size()
        # Pump one event cycle and re-read the OS-confirmed surface so the first
        # frame uses the real drawable size.
        pygame.event.pump()
        self.display = pygame.display.get_surface() or self.display
        _debug_display(f"overworld {'big' if self.fullscreen else 'windowed'}", self.display)

    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        self._apply_display_mode()
        self._log_display("toggle_fullscreen")

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
        # Re-assert the overworld display (preserves window/fullscreen state).
        self._apply_display_mode()
        self._log_display("after_battle")
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
        elif action == "relocate_respawn":
            zone = self.zone.zone_for_tile(self.world.current_tile)
            result = self.engine.relocate_respawn(zone)
            self.set_toast(result.message, GOOD if result.success else (TEXT_DIM if result.already_set else BAD))
        elif action == "tournaments":
            if self.engine.available_tournaments():
                self.mode = "tournaments"
            else:
                self.set_toast(T.TOURNAMENT_NONE, TEXT_DIM)
        elif action == "save":
            self.save_game()

    def toggle_overlay(self, name: str) -> None:
        if self.overlay == name:
            self.close_overlay()
        else:
            self.open_overlay(name)

    def open_overlay(self, name: str) -> None:
        if not self.overlay:
            self.overlay_return_mode = "" if self.mode == "walk" else self.mode
        self.overlay = name
        self.mode = "walk"

    def close_overlay(self) -> None:
        self.overlay = ""
        if self.overlay_return_mode:
            self.mode = self.overlay_return_mode
            self.overlay_return_mode = ""

    def save_game(self) -> None:
        result = self.engine.save(SAVE_PATH)
        self.set_toast(result.message, GOOD if result.success else BAD)

    def quit_game(self) -> None:
        self.exit_reason = "menu"
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
            self.playtest_logger.equip("weapon", weapon.id, damage_type=weapon.damage_type)

    def select_equipment_slot(self, slot_id: str) -> None:
        self.selected_equipment_slot = slot_id

    def equip_gear_to_slot(self, gear_id: str, slot_id: str | None = None) -> None:
        result = self.engine.equip_gear(gear_id, slot_id or self.selected_equipment_slot)
        self.set_toast(result.message, GOOD if result.success else BAD)
        if result.success:
            gear = self.engine.content.gear_items.get(result.gear_id)
            self.playtest_logger.equip(result.slot_id, result.gear_id, stats=gear.stat_modifiers if gear else None)

    def unequip_gear_from_slot(self, slot_id: str | None = None) -> None:
        result = self.engine.unequip_gear(slot_id or self.selected_equipment_slot)
        self.set_toast(result.message, GOOD if result.success else BAD)
        if result.success:
            self.playtest_logger.unequip(result.slot_id, result.gear_id)

    def use_inventory_item(self, item_id: str) -> None:
        result = self.engine.use_consumable(item_id)
        self.set_toast(result.message, GOOD if result.success else BAD)

    # -- inventory overview (everything owned) ------------------------------

    GEAR_SLOT_TYPES = ("head", "chest", "hands", "legs", "feet", "amulet", "ring")

    def inventory_counts(self) -> dict:
        """Count of everything owned, per category, from the same source the
        equip path reads (owned weapons/gear + the consumables bag). Consumables
        and junk count total quantity; equipment counts owned items."""
        snap = build_snapshot(self.engine)
        items = self.engine.content.items
        bag = self.engine.player.inventory.consumables
        counts = {
            "consumables": sum(c for i, c in bag.items() if c > 0 and items[i].kind == "consumable"),
            "junk": sum(c for i, c in bag.items() if c > 0 and items[i].kind != "consumable"),
            "weapon": len(snap.weapons),
        }
        gear_by_type = collections.Counter(g.slot_type for g in snap.gear)
        for slot_type in self.GEAR_SLOT_TYPES:
            counts[slot_type] = gear_by_type.get(slot_type, 0)
        return counts

    def slot_owned_count(self, slot, counts: dict | None = None) -> int:
        """Owned items for a slot's category, from the SAME source as the
        inventory (inventory_counts). Ring slots share one 'ring' pool, so all
        three ring slots report the same total. Equipped items are included,
        mirroring the inventory."""
        counts = self.inventory_counts() if counts is None else counts
        return counts.get(slot.slot_type, 0)

    def inventory_category_items(self, category: str):
        """Items in a category for display: (item_id, label, on_click) tuples.
        Equippable items hand off to the Character panel; consumables use; junk
        is inert."""
        snap = build_snapshot(self.engine)
        items = self.engine.content.items
        bag = self.engine.player.inventory.consumables
        rows = []
        if category in ("consumables", "junk"):
            want_consumable = category == "consumables"
            for item_id, count in sorted(bag.items()):
                if count <= 0 or (items[item_id].kind == "consumable") != want_consumable:
                    continue
                if want_consumable:
                    rows.append((item_id, f"{items[item_id].name} x{count}",
                                 (lambda iid=item_id: self.use_inventory_item(iid)), True))
                else:
                    rows.append((item_id, f"{items[item_id].name} x{count}", None, False))
            return rows
        if category == "weapon":
            for w in snap.weapons:
                mark = " [equipped]" if w.equipped else ""
                rows.append((w.id, f"{T.weapon_label(w)}{mark}",
                             (lambda: self.inventory_equip_handoff("weapon")), True))
            return rows
        for gear in snap.gear:
            if gear.slot_type != category:
                continue
            mark = " [equipped]" if gear.equipped_slot_id else ""
            rows.append((gear.id, f"{gear.name} [{gear.rarity}]{mark}",
                         (lambda st=gear.slot_type: self.inventory_equip_handoff(st)), True))
        return rows

    def open_inventory_category(self, category: str) -> None:
        self.inventory_category = category

    def inventory_equip_handoff(self, slot_type: str) -> None:
        """Navigate to the Character panel on the right slot — equip happens
        there, via the existing engine path. No equip logic in the inventory."""
        slots = build_snapshot(self.engine).equipment_slots
        matching = [s for s in slots if s.slot_type == slot_type]
        target = next((s for s in matching if not s.equipped_item_id), matching[0] if matching else None)
        if target is not None:
            self.selected_equipment_slot = target.id
        self.open_overlay("character")

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

    def select_talent(self, node_id: str) -> None:
        self.selected_talent_id = node_id

    def class_talent_nodes(self):
        return sorted(
            (node for node in self.engine.content.talents.values() if node.class_id == self.engine.player.player_class),
            key=lambda node: (node.branch, node.order),
        )

    def selected_talent_node(self):
        nodes = self.class_talent_nodes()
        if not nodes:
            return None
        if self.selected_talent_id not in {node.id for node in nodes}:
            self.selected_talent_id = nodes[0].id
        return next(node for node in nodes if node.id == self.selected_talent_id)

    def move_talent_selection(self, delta: int) -> None:
        nodes = self.class_talent_nodes()
        if not nodes:
            return
        current = self.selected_talent_node()
        index = nodes.index(current) if current in nodes else 0
        self.selected_talent_id = nodes[(index + delta) % len(nodes)].id

    def learn_selected_talent(self) -> None:
        node = self.selected_talent_node()
        if node is not None:
            self.learn_talent(node.id)

    def talent_detail_lines(self, node) -> list[str]:
        detail = talent_detail(self.engine, node)
        return [
            detail.name,
            detail.status,
            f"Effect: {detail.effect}",
            f"Cost: {detail.cost}",
            f"Requires: {detail.prerequisite}",
        ]

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
        self.overlay_return_mode = ""
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
        self._apply_display_mode()
        self._log_display("after_tournament_battle")
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
        self.overlay_return_mode = ""
        self.mode = "townmenu" if self.world.town_place_id() else "walk"

    # -- input --------------------------------------------------------------

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.exit_reason = "exit"
                self.running = False
            elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
                # Follow the user's resize / Mac maximize; present() re-centers the canvas.
                self.windowed_size = (event.w, event.h)
                self.display = set_display_mode(self.windowed_size)
                self._log_display("resize")
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = to_canvas(event.pos, self._transform)
                for button in self.buttons:
                    if button.enabled and button.rect.collidepoint(pos):
                        button.on_click()
                        break

    def _handle_key(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_F11:
            self.toggle_fullscreen()
            return
        if self.overlay == "skills_talents":
            if event.key in (pygame.K_DOWN, pygame.K_RIGHT):
                self.move_talent_selection(1)
                return
            if event.key in (pygame.K_UP, pygame.K_LEFT):
                self.move_talent_selection(-1)
                return
            if event.key == pygame.K_RETURN:
                self.learn_selected_talent()
                return
        if event.key == pygame.K_ESCAPE:
            if self.overlay:
                self.close_overlay()
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
                region = self.zone.wild_region_at(tile)
                if region != self._last_region and region != self.zone.wild_region_place_id:
                    self.set_toast(T.region_flavor(region), WARN)  # soft signal, not a wall
                self._last_region = region
                enemy = self.maybe_encounter()
                if enemy is not None:
                    self.start_battle(enemy)

    # -- rendering ----------------------------------------------------------

    def draw(self) -> None:
        self.buttons = []
        # Fluid overworld: the canvas tracks the live (logical) display size, so
        # the world fills the window instead of sitting as a centered island. The
        # camera (camera_offset) then shows more map; present() is the identity
        # transform. SCALED still upscales the logical surface crisply on HiDPI.
        if self.display is not None and self.screen.get_size() != self.display.get_size():
            self.screen = pygame.Surface(self.display.get_size())
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
        self._transform = present(self.display, self.screen, BG)
        # Edge-triggered: log only when the fills-state flips (window starts/stops
        # filling), so an anchoring glitch is captured with no per-frame spam.
        try:
            fills = self.display.get_size() == pygame.display.get_window_size()
        except Exception:  # pragma: no cover - driver without window info
            fills = True
        if fills != self._last_fills:
            self._last_fills = fills
            self._log_display("anchor_change")

    def _zoom_factor(self) -> int:
        """Integer zoom so the world view is ~ZOOM_TARGET_TILES_W tiles wide on any
        window (Platinum-style). Integer -> crisp nearest-neighbour pixel art."""
        w = self.screen.get_width()
        return max(2, min(5, round(w / (ZOOM_TARGET_TILES_W * self.world.tw))))

    def screen_to_tile(self, screen_pos: tuple[int, int]) -> tuple[int, int]:
        """Map a screen-space pixel back through the zoom + camera to a world tile."""
        zoom = self._zoom_factor()
        ox, oy = self._cam_offset
        wx = screen_pos[0] // zoom + ox
        wy = screen_pos[1] // zoom + oy
        return (wx // self.world.tw, wy // self.world.th)

    def _visible_tile_bounds(self, view_w: int, view_h: int,
                             ox: int, oy: int) -> tuple[int, int, int, int]:
        """Half-open tile range [left,right) x [top,bottom) overlapping the camera
        window, +1 tile margin, clamped to the map. Covers every on-surface tile
        (render-identical to a full sweep) while staying O(view), not O(map)."""
        tmx = self.world.tmx
        tw, th = self.world.tw, self.world.th
        left = max(0, ox // tw - 1)
        right = min(tmx.width, (ox + view_w) // tw + 2)
        top = max(0, oy // th - 1)
        bottom = min(tmx.height, (oy + view_h) // th + 2)
        return left, right, top, bottom

    def _draw_map(self) -> None:
        screen_w, screen_h = self.screen.get_size()
        zoom = self._zoom_factor()
        # Render the world at 1x onto a small surface (screen / zoom), then integer
        # nearest-neighbour scale it up -> a zoomed, crisp view. HUD/labels are drawn
        # later in unscaled screen space so text stays readable.
        view_w, view_h = max(1, screen_w // zoom), max(1, screen_h // zoom)
        world = pygame.Surface((view_w, view_h))
        world.fill(BG)
        ox, oy = self.world.camera_offset(view_w, view_h)
        self._cam_offset = (ox, oy)
        tmx = self.world.tmx
        tw, th = self.world.tw, self.world.th
        # Viewport culling: blit only the tiles overlapping the camera window
        # instead of the whole map. Render-identical to a full sweep — off-window
        # tiles blit off-surface and contribute no pixels — but the blit count is
        # bounded by the view, not the map area. Applies to all layers identically.
        left, right, top, bottom = self._visible_tile_bounds(view_w, view_h, ox, oy)
        get_image = tmx.get_tile_image_by_gid
        for layer in tmx.visible_layers:
            data = getattr(layer, "data", None)
            if data is None:  # not a tile layer (object/image layer)
                continue
            for y in range(top, bottom):
                row = data[y]
                for x in range(left, right):
                    gid = row[x]
                    if not gid:  # empty cell
                        continue
                    image = get_image(gid)
                    dest = (x * tw - ox, y * th - oy)
                    if image is None:  # tile without graphic -> placeholder block, never crash
                        pygame.draw.rect(world, PANEL_EDGE, pygame.Rect(dest, (tw, th)))
                    else:
                        world.blit(image, dest)
        labels = []  # (text, world_x, world_y) -> drawn unscaled after the zoom
        for (tx, ty), place_id in self.world.town_tiles.items():
            rect = pygame.Rect(tx * tw - ox + 4, ty * th - oy + 4, tw - 8, th - 8)
            color = TOWN_HUB if place_id == self.zone.respawn_place_id else TOWN_COLOR
            pygame.draw.rect(world, color, rect, border_radius=4)
            pygame.draw.rect(world, BG, rect, width=2, border_radius=4)
            labels.append((self.zone.town_labels.get((tx, ty), place_id),
                           tx * tw - ox + tw // 2, ty * th - oy - 8))
        for (tx, ty), _msg in self.world.gate_messages.items():
            rect = pygame.Rect(tx * tw - ox + 2, ty * th - oy + 2, tw - 4, th - 4)
            pygame.draw.rect(world, GATE_COLOR, rect, border_radius=3)
            for gx in range(rect.left + 5, rect.right, 8):
                pygame.draw.line(world, BG, (gx, rect.top), (gx, rect.bottom), 2)
        player = self.world.player.move(-ox, -oy)
        pygame.draw.rect(world, PLAYER_COLOR, player, border_radius=4)
        pygame.draw.rect(world, PLAYER_EDGE, player, width=2, border_radius=4)
        # Zoom the whole world surface up by an integer factor (crisp), then blit.
        self.screen.blit(pygame.transform.scale(world, (view_w * zoom, view_h * zoom)), (0, 0))
        # Town labels in unscaled screen space at the zoomed positions (readable).
        for text, wx, wy in labels:
            surf = self.font_sm.render(text, True, TEXT)
            self.screen.blit(surf, surf.get_rect(center=(wx * zoom, wy * zoom)))

    def _draw_hud(self) -> None:
        snap = build_snapshot(self.engine)
        place = self.engine.current_place()
        in_town = self.world.town_place_id() is not None
        # Two-line HUD: vitals row + a slim XP-progress row beneath it.
        bar = pygame.Rect(0, 0, self.screen.get_width(), 46)
        overlay = pygame.Surface(bar.size, pygame.SRCALPHA)
        overlay.fill((10, 12, 18, 200))
        self.screen.blit(overlay, (0, 0))
        where = place.name if in_town else T.wilds_near(place.name)
        left = f"{snap.player.name}  Lv{snap.player.level}  HP {snap.player.hp}/{snap.player.max_hp}  Gold {snap.player.gold}"
        self.screen.blit(self.font_sm.render(left, True, TEXT), (8, 6))
        right = self.font_sm.render(where, True, ACCENT if in_town else TEXT_DIM)
        self.screen.blit(right, right.get_rect(topright=(self.screen.get_width() - 8, 6)))
        self._draw_xp_bar(snap.player)
        if self.mode == "walk":
            hint = T.HINT_TOWN if in_town else T.HINT_WALK
            hsurf = self.font_sm.render(hint, True, TEXT_DIM)
            self.screen.blit(hsurf, hsurf.get_rect(midbottom=(self.screen.get_width() // 2, self.screen.get_height() - 6)))

    def _draw_xp_bar(self, player) -> None:
        """Compact progress bar toward the next level. Reads the snapshot's
        existing xp / xp_required (same numbers as the Character screen); no
        recompute. Guards xp_required == 0 (max level / unset) against div-by-0."""
        required = player.xp_required
        ratio = max(0.0, min(1.0, player.xp / required)) if required else 0.0
        track = pygame.Rect(8, 28, 170, 8)
        pygame.draw.rect(self.screen, (24, 26, 34), track, border_radius=3)
        if ratio > 0:
            fill = pygame.Rect(track.x, track.y, max(1, int(track.width * ratio)), track.height)
            pygame.draw.rect(self.screen, XP_COL, fill, border_radius=3)
        pygame.draw.rect(self.screen, PANEL_EDGE, track, width=1, border_radius=3)
        label = f"XP {player.xp}/{required}" if required else f"XP {player.xp}"
        self.screen.blit(self.font_sm.render(label, True, TEXT_DIM), (track.right + 8, track.y - 3))

    def _overlay_panel(self, title: str) -> pygame.Rect:
        w, h = self.screen.get_size()
        panel_w = min(920, w - 32)
        panel_h = min(580, h - 32)
        panel = pygame.Rect(w // 2 - panel_w // 2, h // 2 - panel_h // 2, panel_w, panel_h)
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
        mouse = to_canvas(pygame.mouse.get_pos(), self._transform)
        for b in self.buttons:
            if not b.enabled:
                color = BTN_DISABLED
            elif b.rect.collidepoint(mouse):
                color = BTN_HOVER
            else:
                color = BTN
            pygame.draw.rect(self.screen, color, b.rect, border_radius=6)
            pygame.draw.rect(self.screen, BTN_EDGE, b.rect, width=1, border_radius=6)
            fitted = self._fit_text(b.label, b.rect.width - 24, self.font)
            label = self.font.render(fitted, True, TEXT if b.enabled else TEXT_DIM)
            self.screen.blit(label, label.get_rect(midleft=(b.rect.x + 12, b.rect.centery)))

    def _draw_town_menu(self) -> None:
        panel = self._overlay_panel(self.engine.current_place().name)
        has_store = self.engine.current_place().has_store
        col_w = (panel.width - 60) // 2
        actions = list(T.TOWN_ACTIONS)
        already_respawn = False
        if has_store:
            zone = self.zone.zone_for_tile(self.world.current_tile)
            cost = progression.respawn_relocation_cost(zone)
            already_respawn = self.engine.player.respawn_place_id == self.engine.current_place().id
            actions.append(("relocate_respawn", T.relocate_respawn_label(cost, already=already_respawn)))
        if self.engine.available_tournaments():
            actions.append(("tournaments", T.TOWN_TOURNAMENTS))
        for i, (action, label) in enumerate(actions):
            col, row = i % 2, i // 2
            rect = pygame.Rect(panel.x + 20 + col * (col_w + 20), panel.y + 70 + row * 56, col_w, 44)
            enabled = not (action == "store" and not has_store) and not (action == "relocate_respawn" and already_respawn)
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
        self._add_button(back, T.BACK, self.close_overlay)
        self._draw_buttons()

    def _lines(self, panel, lines, color=TEXT, start=64, step=24) -> int:
        for i, line in enumerate(lines):
            self.screen.blit(self.font.render(line, True, color), (panel.x + 20, panel.y + start + i * step))
        return panel.y + start + len(lines) * step

    def _content_rect(self, panel: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(panel.x + 20, panel.y + 56, panel.width - 40, panel.height - 126)

    def _fit_text(self, text: str, max_width: int, font: pygame.font.Font | None = None) -> str:
        font = font or self.font
        if max_width <= 0 or font.size(text)[0] <= max_width:
            return text
        ellipsis = "..."
        if font.size(ellipsis)[0] > max_width:
            return ""
        fitted = text
        while fitted and font.size(f"{fitted}{ellipsis}")[0] > max_width:
            fitted = fitted[:-1]
        return f"{fitted.rstrip()}{ellipsis}"

    def _wrapped_lines_pixels(self, text: str, max_width: int, font: pygame.font.Font | None = None) -> list[str]:
        font = font or self.font
        if max_width <= 0:
            return [""]
        if not text:
            return [""]
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if font.size(candidate)[0] <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            if font.size(word)[0] <= max_width:
                current = word
            else:
                chunk = ""
                for char in word:
                    candidate = f"{chunk}{char}"
                    if font.size(candidate)[0] <= max_width:
                        chunk = candidate
                    else:
                        if chunk:
                            lines.append(chunk)
                        chunk = char
                current = chunk
        if current:
            lines.append(current)
        return lines or [""]

    def _draw_store_screen(self) -> None:
        panel = self._overlay_panel(T.SCREEN_TITLES["store"])
        self._screen_store(panel)
        back = pygame.Rect(panel.right - 130, panel.bottom - 54, 110, 40)
        self._add_button(back, T.BACK, lambda: setattr(self, "mode", "townmenu"))
        self._draw_buttons()

    def _character_regions(self, panel: pygame.Rect) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
        content = self._content_rect(panel)
        gap = 16
        if content.width >= 820:
            stats = pygame.Rect(content.x, content.y + 94, 230, content.height - 94)
            slots = pygame.Rect(stats.right + gap, stats.y, 220, stats.height)
            items = pygame.Rect(slots.right + gap, stats.y, content.right - slots.right - gap, stats.height)
            return stats, slots, items
        top_h = min(310, max(240, content.height - 130))
        stats_w = (content.width - gap) // 2
        stats = pygame.Rect(content.x, content.y + 94, stats_w, top_h - 94)
        slots = pygame.Rect(stats.right + gap, stats.y, content.right - stats.right - gap, stats.height)
        items = pygame.Rect(content.x, content.y + top_h + gap, content.width, content.bottom - content.y - top_h - gap)
        return stats, slots, items

    def _overlay_character(self, panel) -> None:
        snap = build_snapshot(self.engine)
        p = snap.player
        content = self._content_rect(panel)
        header_lines = [
            f"{p.name} — {p.class_name} (Lv {p.level})",
            f"HP {p.hp}/{p.max_hp}    Mana {p.mana}/{p.max_mana}",
            f"XP {p.xp}/{p.xp_required}    Talent points {p.talent_points}",
            f"Gold {p.gold}",
        ]
        for i, line in enumerate(header_lines):
            self.screen.blit(self.font.render(self._fit_text(line, content.width, self.font), True, TEXT),
                             (content.x, content.y + i * 20))

        stats_rect, slots_rect, items_rect = self._character_regions(panel)
        self.screen.blit(self.font_sm.render("Stats  base -> +gear -> total", True, TEXT_DIM), (stats_rect.x, stats_rect.y - 24))
        stat_rows = [
            ("max_hp", "HP", self.engine.player.max_hp),
            ("max_mana", "Mana", self.engine.player.max_mana),
            ("damage", "Damage", self.engine.player.base_damage),
            ("armor", "Armor", self.engine.player.armor),
            ("speed", "Speed", self.engine.player.speed),
            ("crit_chance", "Crit", self.engine.player.crit_chance),
        ]
        for i, (stat, label, base) in enumerate(stat_rows):
            gear_bonus = self.engine.gear_modifier_total(stat)
            total = self.engine.effective_stat(stat)
            suffix = f"  (+weapon {p.weapon_damage_bonus})" if stat == "damage" else ""
            self.screen.blit(
                self.font_sm.render(self._fit_text(f"{label}: {base} -> {gear_bonus:+} -> {total}{suffix}", stats_rect.width, self.font_sm), True, TEXT),
                (stats_rect.x, stats_rect.y + i * 22),
            )

        slots = snap.equipment_slots
        if self.selected_equipment_slot not in {slot.id for slot in slots}:
            self.selected_equipment_slot = "weapon"
        self.screen.blit(self.font_sm.render("Slots", True, TEXT_DIM), (slots_rect.x, slots_rect.y - 24))
        max_slots = max(1, min(len(slots), slots_rect.height // 28))
        counts = self.inventory_counts()  # one source, shared with the inventory view
        for i, slot in enumerate(slots[:max_slots]):
            rect = pygame.Rect(slots_rect.x, slots_rect.y + i * 28, slots_rect.width, 24)
            selected = slot.id == self.selected_equipment_slot
            item = slot.equipped_item_name or "[empty]"
            # Owned count per slot's category, so empty slots still signal options.
            label = f"{'> ' if selected else '  '}{slot.name}: {item} ({self.slot_owned_count(slot, counts)})"
            self._add_button(rect, label, (lambda sid=slot.id: self.select_equipment_slot(sid)), True)

        selected_slot = next((slot for slot in slots if slot.id == self.selected_equipment_slot), slots[0])
        self.screen.blit(self.font_sm.render(f"{selected_slot.name} options", True, TEXT_DIM), (items_rect.x, items_rect.y - 24))
        max_items = max(1, items_rect.height // 34)
        if selected_slot.id == "weapon":
            # Preview: the equipped weapon's type + full stats, above the options.
            equipped_w = next((w for w in snap.weapons if w.equipped), None)
            options_y = items_rect.y
            if equipped_w is not None:
                self.screen.blit(self.font_sm.render(self._fit_text(T.weapon_preview(equipped_w), items_rect.width, self.font_sm), True, TEXT_DIM),
                                 (items_rect.x, items_rect.y))
                options_y = items_rect.y + 24
            max_weapons = max(1, (items_rect.bottom - options_y) // 34)
            for i, w in enumerate(snap.weapons[:max_weapons]):
                rect = pygame.Rect(items_rect.x, options_y + i * 34, items_rect.width, 28)
                suffix = " [equipped]" if w.equipped else ("" if w.equippable else f" needs Lv {w.required_level}")
                label = f"{T.weapon_label(w)}{suffix}"
                self._add_button(rect, label, (lambda wid=w.id: self.equip_weapon(wid)), w.equippable and not w.equipped)
            return

        if selected_slot.equipped_item_id:
            self._add_button(
                pygame.Rect(items_rect.x, items_rect.y, items_rect.width, 28),
                f"Unequip {selected_slot.equipped_item_name}",
                lambda sid=selected_slot.id: self.unequip_gear_from_slot(sid),
                True,
            )
            start_y = items_rect.y + 38
        else:
            start_y = items_rect.y
        choices = [
            gear for gear in snap.gear
            if gear.slot_type == selected_slot.slot_type and not gear.equipped_slot_id
        ]
        max_choices = max(1, (items_rect.bottom - start_y) // 34)
        for i, gear in enumerate(choices[:max_choices]):
            rect = pygame.Rect(items_rect.x, start_y + i * 34, items_rect.width, 28)
            mods = ", ".join(f"{stat} {value:+}" for stat, value in gear.stat_modifiers)
            suffix = "" if gear.equippable else f" needs Lv {gear.required_level}"
            label = f"{gear.name} [{gear.rarity}] {mods}{suffix}"
            self._add_button(rect, label, (lambda gid=gear.id, sid=selected_slot.id: self.equip_gear_to_slot(gid, sid)), gear.equippable)

    def _overlay_inventory(self, panel) -> None:
        content = self._content_rect(panel)
        self.screen.blit(self.font_sm.render(T.INVENTORY_HINT, True, TEXT_DIM), (content.x, content.y))

        counts = self.inventory_counts()
        if self.inventory_category not in counts:
            self.inventory_category = "consumables"

        gap = 20
        list_top = content.y + 30
        overview_w = min(240, content.width // 2)
        overview = pygame.Rect(content.x, list_top, overview_w, content.bottom - list_top)
        items_rect = pygame.Rect(overview.right + gap, list_top, content.right - overview.right - gap, overview.height)

        # Overview: every category with its count; selecting one expands it.
        row_h = max(22, min(30, overview.height // max(1, len(T.INV_CATEGORY_LABELS))))
        for i, (key, label) in enumerate(T.INV_CATEGORY_LABELS.items()):
            rect = pygame.Rect(overview.x, overview.y + i * row_h, overview.width, row_h - 2)
            selected = key == self.inventory_category
            text = f"{'> ' if selected else '  '}{label} ({counts.get(key, 0)})"
            self._add_button(rect, text, (lambda k=key: self.open_inventory_category(k)), True)

        # Expanded: the selected category's items.
        label = T.INV_CATEGORY_LABELS.get(self.inventory_category, self.inventory_category)
        self.screen.blit(self.font_sm.render(f"{label} ({counts.get(self.inventory_category, 0)})",
                                             True, TEXT_DIM), (items_rect.x, items_rect.y - 24))
        rows = self.inventory_category_items(self.inventory_category)
        if not rows:
            self.screen.blit(self.font.render(T.INV_NONE, True, TEXT_DIM), (items_rect.x, items_rect.y))
            return
        max_rows = max(1, items_rect.height // 34)
        for i, (_item_id, text, on_click, enabled) in enumerate(rows[:max_rows]):
            rect = pygame.Rect(items_rect.x, items_rect.y + i * 34, items_rect.width, 30)
            if on_click is None:
                self.screen.blit(self.font.render(self._fit_text(text, items_rect.width, self.font), True, TEXT_DIM),
                                 (rect.x, rect.y + 4))
            else:
                self._add_button(rect, self._fit_text(text, items_rect.width - 24, self.font), on_click, enabled)

    def _skills_talents_regions(self, panel: pygame.Rect) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
        content = self._content_rect(panel)
        gap = 16
        if content.width >= 860:
            skills_w = 220
            talents_w = 280
            skills = pygame.Rect(content.x, content.y, skills_w, content.height)
            talents = pygame.Rect(skills.right + gap, content.y, talents_w, content.height)
            detail = pygame.Rect(talents.right + gap, content.y, content.right - talents.right - gap, content.height)
            return skills, talents, detail
        if content.height >= 380:
            top_h = min(245, max(190, content.height // 2))
            skills_w = max(220, (content.width - gap) // 2)
            talents_w = content.width - skills_w - gap
            skills = pygame.Rect(content.x, content.y, skills_w, top_h)
            talents = pygame.Rect(skills.right + gap, content.y, talents_w, top_h)
            detail = pygame.Rect(content.x, skills.bottom + gap, content.width, content.bottom - skills.bottom - gap)
            return skills, talents, detail
        row_h = max(96, (content.height - 2 * gap) // 3)
        skills = pygame.Rect(content.x, content.y, content.width, row_h)
        talents = pygame.Rect(content.x, skills.bottom + gap, content.width, row_h)
        detail = pygame.Rect(content.x, talents.bottom + gap, content.width, content.bottom - talents.bottom - gap)
        return skills, talents, detail

    def _overlay_skills_talents(self, panel) -> None:
        eng = self.engine
        equipped_ids = set(eng.player.equipped_skill_ids)
        left, middle, right = self._skills_talents_regions(panel)

        self.screen.blit(self.font_sm.render(T.skills_hint(len(equipped_ids)), True, TEXT_DIM),
                         (left.x, left.y))
        skills = eng.equippable_skills()
        if not skills:
            self.screen.blit(self.font.render(T.NO_SKILLS, True, TEXT_DIM), (left.x, left.y + 30))
        max_skills = max(1, (left.height - 32) // 34)
        for i, skill in enumerate(skills[:max_skills]):
            rect = pygame.Rect(left.x, left.y + 30 + i * 34, left.width, 28)
            is_eq = skill.id in equipped_ids
            label = f"{'[E] ' if is_eq else '[ ]'} {skill.name}"
            enabled = is_eq or len(equipped_ids) < 4
            self._add_button(rect, label, (lambda sid=skill.id, eq=is_eq: self.toggle_skill(sid, eq)), enabled)

        self.screen.blit(self.font_sm.render(T.talents_hint(eng.player.talent_points), True, WARN),
                         (middle.x, middle.y))
        class_nodes = self.class_talent_nodes()
        selected = self.selected_talent_node()
        max_nodes = max(1, (middle.height - 32) // 32)
        for i, node in enumerate(class_nodes[:max_nodes]):
            status = talent_status(eng, node)
            rect = pygame.Rect(middle.x, middle.y + 30 + i * 32, middle.width, 26)
            marker = "> " if selected is not None and node.id == selected.id else "  "
            label = f"{marker}{status} {node.name} ({node.branch} t{node.order})"
            self._add_button(rect, label, (lambda nid=node.id: self.select_talent(nid)), True)

        self._draw_talent_detail(right, selected)

    def _draw_talent_detail(self, rect: pygame.Rect, node) -> None:
        pygame.draw.rect(self.screen, (24, 28, 38), rect, border_radius=6)
        pygame.draw.rect(self.screen, PANEL_EDGE, rect, width=1, border_radius=6)
        self.screen.blit(self.font_sm.render("Talent detail", True, TEXT_DIM), (rect.x + 10, rect.y + 8))
        if node is None:
            self.screen.blit(self.font.render(T.NO_TALENTS, True, TEXT_DIM), (rect.x + 10, rect.y + 38))
            return

        lines = []
        for raw in self.talent_detail_lines(node):
            lines.extend(self._wrapped_lines_pixels(raw, rect.width - 20, self.font_sm))
        y = rect.y + 36
        line_height = self.font_sm.get_linesize() + 3
        max_y = rect.bottom - 52
        max_lines = max(1, (max_y - y) // line_height)
        visible_lines = lines[:max_lines]
        if len(lines) > max_lines and visible_lines:
            visible_lines[-1] = self._fit_text(f"{visible_lines[-1]} ...", rect.width - 20, self.font_sm)
        for line in visible_lines:
            color = ACCENT if y == rect.y + 36 else TEXT
            self.screen.blit(self.font_sm.render(line, True, color), (rect.x + 10, y))
            y += line_height

        can_learn = talent_status(self.engine, node) == "[CAN LEARN]" and self.engine.player.talent_points > 0
        learn_rect = pygame.Rect(rect.x + 10, rect.bottom - 42, rect.width - 20, 32)
        self._add_button(learn_rect, "Learn selected", self.learn_selected_talent, can_learn)

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

    def run(self) -> str:
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)
        if self.exit_reason == "exit":
            pygame.quit()
        return self.exit_reason or "menu"


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


def start_menu_layout(size: tuple[int, int], options) -> tuple[list[Button], tuple[int, int], tuple[int, int]]:
    """Center the title + button stack on the *live* surface size.

    Fluid pilot: layout is a function of the real display size, not a fixed
    1024x680 canvas, so the menu fills the screen in fullscreen instead of
    sitting as a small centered island. Returns the buttons plus the title and
    message anchor points (both horizontally centered)."""
    w, h = size
    button_w, button_h, gap = 320, 48, 60
    start_y = h // 2 - (len(options) * gap) // 2
    buttons = [
        Button(
            pygame.Rect(w // 2 - button_w // 2, start_y + index * gap, button_w, button_h),
            label,
            choice,
        )
        for index, (choice, label) in enumerate(options)
    ]
    title_pos = (w // 2, max(48, start_y - 90))   # title sits above the stack
    msg_pos = (w // 2, max(80, start_y - 48))      # error line just under the title
    return buttons, title_pos, msg_pos


def start_menu(save_path: str = SAVE_PATH, message: str = "") -> str:
    pygame.init()
    pygame.display.set_caption(T.CAPTION_START)
    display = acquire_display((WIDTH, HEIGHT))
    # Fluid: the canvas matches the display, so present() is the identity
    # transform (0, 0, 1.0) and content is authored at native resolution.
    screen = pygame.Surface(display.get_size())
    offset = (0, 0, 1.0)
    font = pygame.font.SysFont("menlo,consolas,monospace", 20)
    font_sm = pygame.font.SysFont("menlo,consolas,monospace", 14)
    font_lg = pygame.font.SysFont("menlo,consolas,monospace", 34, bold=True)
    clock = pygame.time.Clock()

    while True:
        if screen.get_size() != display.get_size():
            screen = pygame.Surface(display.get_size())  # follow resize / fullscreen
        options = start_menu_options(save_path)
        buttons, title_pos, msg_pos = start_menu_layout(display.get_size(), options)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit"
            if event.type == pygame.VIDEORESIZE:
                display = set_display_mode((event.w, event.h))
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                click = to_canvas(event.pos, offset)
                for button in buttons:
                    if button.rect.collidepoint(click):
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
        screen.blit(title, title.get_rect(center=title_pos))
        if message:
            msg = font_sm.render(message, True, BAD)
            screen.blit(msg, msg.get_rect(center=msg_pos))

        mouse = to_canvas(pygame.mouse.get_pos(), offset)
        for button in buttons:
            color = BTN_HOVER if button.rect.collidepoint(mouse) else BTN
            pygame.draw.rect(screen, color, button.rect, border_radius=8)
            pygame.draw.rect(screen, BTN_EDGE, button.rect, width=1, border_radius=8)
            label = font.render(button.label, True, TEXT)
            screen.blit(label, label.get_rect(center=button.rect.center))

        offset = present(display, screen, BG)
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
    class_id = argv[0] if argv else ""
    quickstart_engine: GameEngine | None = None
    if class_id:
        # Quick-start a class, skipping creation (same shortcut as the battle shell).
        quickstart_engine = GameEngine()
        if class_id not in quickstart_engine.content.classes:
            raise SystemExit(T.unknown_class(class_id, ", ".join(quickstart_engine.content.classes)))
        quickstart_engine.start_new_game("Hero", class_id)

    while True:
        if quickstart_engine is not None:
            engine = quickstart_engine
            quickstart_engine = None
        else:
            selected_engine = engine_from_start_menu(SAVE_PATH)
            if selected_engine is None:
                pygame.quit()
                return
            engine = selected_engine

        outcome = OverworldApp(engine=engine).run()
        if outcome == "exit":
            pygame.quit()
            return


if __name__ == "__main__":
    main()
