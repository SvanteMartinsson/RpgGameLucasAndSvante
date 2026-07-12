"""Pygame overworld — free-walk world connected to the engine (Model B).

Presentation layer. Core (`rpg_game/core`) holds all rules; here we only render
state via `build_snapshot()` and mutate via existing `GameEngine` methods, same
contract as the battle and character-creation shells.

Model B = free walk (WASD) over a walkable world. Towns are tiles you step onto;
entering one sets the engine's current location (`engine.enter_place`). Each town
building has its own door tile — standing on a door and pressing Enter opens that
building's service (inn -> Rest, shop/blacksmith/barracks -> Store, church -> set
respawn, town_hall -> Tournaments). Character, inventory, skills/talents and
system actions are overworld overlays opened with hotkeys from anywhere outside
battle.

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
import math
import os
import sys
from dataclasses import dataclass, field

import pygame
from pytmx.util_pygame import load_pygame

from rpg_game.core import combat, encounters, progression, saveslots, spawns, store
from rpg_game.core import events as core_events
from rpg_game.presentation import ambience
from rpg_game.core.game import GameEngine
from rpg_game.core.view import build_snapshot
from rpg_game.presentation import audio
from rpg_game.presentation import settings as user_settings
from rpg_game.presentation import ui_text as T
from rpg_game.presentation.pygame_canvas import (
    _debug_display, acquire_display, desktop_size, fit_size, open_window, present,
    set_display_mode, to_canvas)
from rpg_game.presentation.playtest_logger import PlaytestLogger
# WIDTH/HEIGHT are the pre-game window size, shared with the character-creation
# screen the start menu flows into — one source, no hardcoded duplicate. (The
# in-world view sizes itself to the map via OverworldApp.view_size instead.)
from rpg_game.presentation.pygame_battle import HEIGHT, WIDTH, BattleApp, character_creation
from rpg_game.presentation.talent_text import (
    grouped_class_talents as talent_text_grouped,
    talent_action_label,
    talent_can_allocate,
    talent_detail,
    talent_rank_label,
    talent_status,
)
from rpg_game.presentation import town_cluster
from rpg_game.presentation.overworld_overlays import (  # noqa: F401 — re-export
    OverlaysMixin,
)
from rpg_game.presentation.overworld_buildings import (  # noqa: F401 — re-exports
    BuildingMenusMixin,
    BUILDING_FUNCTION,
    BUILDING_TITLES,
    STORE_CATEGORY,
)
from rpg_game.presentation.overworld_render import (  # noqa: F401 — re-exports
    player_facing,
    MapRenderMixin,
    BG,
    PANEL_EDGE,
    TEXT,
    TEXT_DIM,
    ACCENT,
    GOOD,
    WARN,
    BAD,
    TOWN_COLOR,
    TOWN_HUB,
    GATE_COLOR,
    PLAYER_COLOR,
    PLAYER_EDGE,
    MAP_BG,
    MAP_FOG,
    MAP_LAND_DEFAULT,
    MAP_WATER,
    MAP_OBSTACLE,
    MAP_BUSH,
    MAP_FAMILY_COLORS,
    MINIMAP_TILES,
    MINIMAP_BOX,
    MINIMAP_MARGIN,
    ZOOM_TARGET_TILES_W,
    COLLISION_LAYER,
    WATER_TILESET,
    GRAVE_TILESET,
    GRAVE_SHEET_INDICES,
    GRAVE_TILES_TALL,
    BUILDINGS_DIR,
    BUILDING_SCALE,
    BUILDING_SCALE_OVERRIDE,
    COBBLE_BLOB,
    BRIDGE_TILESETS,
    PROPS_DIR,
    CHEST_CLOSED_RECT,
    CHEST_OPEN_RECT,
    SPRITE_DIR,
    TILES_DIR,
    GRASS_SHEET,
    _grass_sheet_path,
    _AUTOTILE_BLOB,
)
from rpg_game.presentation import fog
from rpg_game.presentation import chatlog
from rpg_game.presentation import item_text
from rpg_game.presentation import settings as user_settings
from rpg_game.presentation import ui
from rpg_game.presentation.ui import Button

MAPS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "maps")
DEFAULT_MAP = os.path.join(MAPS_DIR, "testmap.tmx")


# B8 proved the anchored building-cluster model on the start town. B28 reuses the
# SAME hub template on more cities. A town qualifies as a hub only if it is a real
# service city (a store town) AND the template places cleanly at its tile — on
# land, in-bounds, footprints clear of water/walls, doors reachable, no overlap
# with another hub (all asserted by test_town_cluster). burg_5 stays the primary
# hub (and the start town); burg_121 (Alherralba) and burg_67 (Fongorinos) are the
# verified zone-1/zone-2 store cities that pass every placement property. Towns
# whose tile sits against water (e.g. Rotequero), which crowd a neighbour (the
# hub at Alherralba would overrun nearby Salles), or which are store-less villages
# need a tiered/terrain design pass and are deliberately NOT hubs yet.
CLUSTER_TOWN_ID = "burg_5"
CLUSTER_TOWN_IDS = ("burg_5", "burg_67")
ZONE_CONFIG = os.path.join(MAPS_DIR, "core_zone.json")
# Anchor the save to a stable, absolute location (project root) rather than the
# process CWD, so the start menu detects and loads it on a cold start regardless
# of where the game was launched from — not only within the play session.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SAVE_PATH = os.path.join(_PROJECT_ROOT, "savegame.json")

FPS = 60
PLAYER_SIZE = 20
# 20% slower than the old 3 px/frame (0.8 * 3). It is a FLOAT, but the player is an
# integer pygame.Rect, so the app keeps a per-axis sub-pixel accumulator (see
# update()): each move-frame adds PLAYER_SPEED, the rect moves by the integer part,
# the fraction carries to the next frame. Setting the rect step to int(2.4)=2 would
# instead be ~33% slower, not 20%.
PLAYER_SPEED = 2.4
# A water autotile cell blocks only if >= this fraction of it is water. Measured
# fractions: outer corner ~0.22, edge ~0.58, channel ~0.76, inner corner ~0.89,
# full 1.0 -> 0.6 makes shore (edge + outer) walkable while deep water still blocks.
WATER_BLOCK_THRESHOLD = 0.6
# Encounter heatmap (B12): wilderness gets safer near towns and along roads.
# B55: the RULE lives in core/encounters.py (engine logic, simulable); the shell
# builds the tile geometry (EncounterMap) once and asks per step. Aliased here
# so there is ONE source of truth for the numbers.
# B99 S2: menu modes where keyboard focus drives the buttons ("walk" and the
# bestiary overlay excluded — walking has no buttons, the bestiary keeps B66).
FOCUS_MODES = frozenset({
    "building", "store", "tome_shop", "apothecary", "fast_travel",
    "upgrade_station", "tournaments", "tournament_confirm",
    "tournament_intermission", "death", "victory", "travel_event",
})

ENCOUNTER_SAFE_RADIUS = encounters.SAFE_RADIUS
ENCOUNTER_RAMP_TILES = encounters.RAMP_TILES
ENCOUNTER_PATH_FACTOR = encounters.PATH_FACTOR
# B32: a hub is a whole CLUSTER, not one tile. Encounters are zero on every cluster
# tile (footprints, plaza, doors, cobble) plus this many tiles of margin around it,
# so you can never be ambushed on a town's own streets or its doorstep.
SAFE_TILE_MARGIN = 2

# Action log / chatbox (B16 + B29): the bottom-left panel is the SINGLE place all
# on-screen text goes (no floating toasts). It keeps deep scrollback, shows a
# resizable number of lines (player grows/shrinks it, clamped), and can be scrolled
# up to read older lines.
# Chatbox sizing lives in the shared chatlog component (single source); aliased
# here so existing references/imports keep working.
LOG_HISTORY_MAX = chatlog.LOG_HISTORY_MAX
LOG_VISIBLE_DEFAULT = chatlog.LOG_VISIBLE_DEFAULT
LOG_VISIBLE_MIN = chatlog.LOG_VISIBLE_MIN
LOG_VISIBLE_MAX = chatlog.LOG_VISIBLE_MAX
LOG_SCROLL_STEP = chatlog.LOG_SCROLL_STEP

# Location indicator (top-right): within this many tiles of a hub's plaza the label
# reads relative ("south of Hordanita") instead of the generic wilds text.
NEAR_RADIUS = 8

PANEL = (30, 34, 46)
BTN = (46, 52, 70)
BTN_HOVER = (66, 76, 102)
BTN_DISABLED = (34, 38, 50)
BTN_EDGE = (90, 100, 130)
XP_COL = (180, 150, 240)  # matches the battle HUD's XP bar
HP_COL = (96, 200, 120)   # vitals bars (B31), matching the battle HUD
MANA_COL = (90, 140, 230)
BAR_TRACK = (24, 26, 34)



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
    town_meta: dict = None  # place_id -> {"tier","shop_category","prop"} (B8 Slice 2a)

    @staticmethod
    def load(path: str = ZONE_CONFIG) -> "ZoneConfig":
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        towns = {tuple(t["tile"]): t["place_id"] for t in data.get("towns", [])}
        labels = {tuple(t["tile"]): t.get("label", t["place_id"]) for t in data.get("towns", [])}
        # B8 Slice 2a: per-town cluster tier + provisional shop category / cosmetic
        # prop (Lucas tunes the values in 2b; the code only reads them).
        town_meta = {
            t["place_id"]: {"tier": t.get("tier", "village"),
                            "shop_category": t.get("shop_category"),
                            "prop": t.get("prop")}
            for t in data.get("towns", [])
        }
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
            town_meta=town_meta,
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

    def theme_for_tile(self, tile: tuple[int, int]) -> str:
        """B67: the ground-theme NAME for a tile ('cainos', 'mork_skog', ...) —
        the key travel-event tables are authored against. The southern y-band
        (grave heath) wins first, mirroring economy_zone_for_tile."""
        tx, ty = tile
        for theme, _min_x, _max_x, min_y, _max_y in self.ground_themes:
            if min_y > 0 and ty >= min_y:
                return theme
        for theme, min_x, max_x, _min_y, _max_y in self.ground_themes:
            if min_x <= tx <= max_x:
                return theme
        return self.ground_themes[0][0] if self.ground_themes else "cainos"

    def economy_zone_for_tile(self, tile: tuple[int, int]) -> int:
        """B8 2b: the ECONOMY zone for fast-travel pricing. Unlike zone_for_tile
        (x-only, kept for rest/respawn costs), the southern grave-heath band
        wins on y FIRST, then the west->east x-bands apply. Indexes line up
        with progression.FAST_TRAVEL_ZONE_NET (1..3 = x-bands, 4 = heath)."""
        tx, ty = tile
        x_bands = [t for t in self.ground_themes if t[3] <= 0]
        for _theme, _min_x, _max_x, min_y, _max_y in self.ground_themes:
            if min_y > 0 and ty >= min_y:
                return len(x_bands) + 1
        for index, (_theme, min_x, max_x, _min_y, _max_y) in enumerate(x_bands, start=1):
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
        # Majority-water collision: a water autotile cell blocks only if at least
        # WATER_BLOCK_THRESHOLD of it is actually water. Shore/edge (~0.58) and outer-
        # corner (~0.22) tiles are mostly land -> walkable, so the player can step up
        # to the water's edge; full (1.0), inner corner (~0.89) and channel (~0.76)
        # tiles still block. The tiles are STILL rendered (from this layer) — only
        # membership in `blocked` changes. Non-water collision tiles always block.
        blocked = set()
        frac: dict[int, float] = {}
        for x, y, img in layer.tiles():
            gid = layer.data[y][x]
            ts = self.tmx.get_tileset_from_gid(gid) if gid else None
            if ts is not None and ts.name == WATER_TILESET and img is not None:
                f = frac.get(gid)
                if f is None:
                    f = self._water_fraction(img)
                    frac[gid] = f
                if f < WATER_BLOCK_THRESHOLD:
                    continue  # mostly-land shore tile: drawn, but walkable
            blocked.add((x, y))
        blocked |= self._decor_bush_cells()
        return blocked

    def _decor_bush_cells(self) -> set:
        """Bush thickets live on the decor_over layer (the *_plant sheets) as
        single-tile shrubs — they render there (above walls, under the player) and
        are now SOLID obstacles the player can't walk through. Decks on the same
        layer (water_bridge / bridge_halfdeck) are NOT bushes and stay walkable."""
        cells: set = set()
        try:
            decor = self.tmx.get_layer_by_name("decor_over")
        except (ValueError, KeyError):
            return cells
        get_ts = self.tmx.get_tileset_from_gid
        for y, row in enumerate(decor.data):
            for x, gid in enumerate(row):
                if not gid:
                    continue
                ts = get_ts(gid)
                if ts is not None and ts.name.endswith("_plant"):
                    cells.add((x, y))
        return cells

    @staticmethod
    def _water_fraction(img: "pygame.Surface") -> float:
        w, h = img.get_size()
        opaque = sum(1 for yy in range(h) for xx in range(w) if img.get_at((xx, yy))[3] > 0)
        return opaque / (w * h) if w and h else 1.0

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
class TournamentRun:
    tournament: object
    next_index: int = 0
    message: str = ""


# --- app -------------------------------------------------------------------


class OverworldApp(OverlaysMixin, BuildingMenusMixin, MapRenderMixin):
    def __init__(self, engine: GameEngine | None = None, zone: ZoneConfig | None = None) -> None:
        pygame.init()
        audio.init()          # B69: graceful — silent mode when no device
        audio.ensure_music()  # background loop; idempotent across shell hops
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
        # B8 Slice 1: the start town renders as a building cluster. The cluster is
        # anchored to its tile (template offsets), its footprints become solid
        # collision, and the anchor tile stays the walkable plaza/menu trigger.
        self._cobble_tiles = self._load_cobble_tiles(GRASS_SHEET)   # cainos default
        self._cobble_tiles_by_theme: dict = {"cainos": self._cobble_tiles}
        self._cobble_cell_theme: dict = {}   # (cx,cy) -> zone theme of its cluster
        # B8 Slice 2a: EVERY town anchors its own cluster, sized by its tier (read
        # from core_zone). town_hall appears only where a tournament lives. Resolve a
        # concrete template per town, then add ALL footprints to collision first so
        # each cluster's cobble routes around every building (its own and neighbours').
        tournament_places = {t.place_id for t in self.engine.content.tournaments.values()}
        self.cluster_anchors = {
            pid: tile for pid in self.town_tile_by_place
            if (tile := self.town_tile_by_place.get(pid)) is not None
        }
        self.cluster_templates = {
            pid: self._resolve_town_template(pid, pid in tournament_places)
            for pid in self.cluster_anchors
        }
        # Sprites are loaded for every (building, facing) that appears across all the
        # resolved templates (a building can face differently per tier, e.g. inn is
        # q1 in a capital but front in a town).
        self._building_sprites = self._load_building_sprites()
        # Graves render as full 2-tile stones, y-sorted with the player + buildings
        # so the player can walk BEHIND the upper tile (the bottom cell still blocks).
        self._grave_cells, self._grave_sprites = self._load_graves()
        # Backward-compatible single-anchor handle for the primary/start hub.
        self.cluster_anchor = self.cluster_anchors.get(CLUSTER_TOWN_ID)
        for pid, anchor in self.cluster_anchors.items():
            self.world.blocked |= town_cluster.cluster_footprints(anchor, self.cluster_templates[pid])
        # Comb cobble that never sits on OR borders water (shore water is walkable
        # post-B19 but must not be cobbled over, and no cobble points into a river).
        # blocked keeps it off other terrain; water drives the no-border rule.
        water = self._water_tiles()
        self._cobble_net = set()
        # B-doors: map each hub building's door tile -> (place_id, building_id) so
        # standing on a door and pressing Enter opens that building's service.
        # hub_interior: every standable tile that reads as "inside" a hub (its
        # plaza, doors and cobble) -> place_id, so the location label names the city
        # anywhere on its cluster, not only on the single anchor tile.
        self.door_index: dict[tuple[int, int], tuple[str, str]] = {}
        self.hub_interior: dict[tuple[int, int], str] = {}
        for pid, anchor in self.cluster_anchors.items():
            tmpl = self.cluster_templates[pid]
            cobble = town_cluster.cobble_network(anchor, self.world.blocked, water, tmpl)
            self._cobble_net |= cobble
            # This cluster's cobble reads on its zone's grass (matches the roads).
            theme = self._cluster_ground_theme(anchor)
            for cell in cobble:
                self._cobble_cell_theme[cell] = theme
            entrances = town_cluster.cluster_entrances(anchor, tmpl)
            for bid, ent in entrances.items():
                self.door_index[ent] = (pid, bid)
            for tile in ({anchor} | set(entrances.values()) | cobble):
                self.hub_interior[tile] = pid
        # B32: zero-encounter zone = every cluster tile (footprints + plaza + doors +
        # cobble) dilated by SAFE_TILE_MARGIN, so no ambush on a town's streets/edge.
        self._safe_tiles: set[tuple[int, int]] = set()
        for pid, anchor in self.cluster_anchors.items():
            tmpl = self.cluster_templates[pid]
            cluster = town_cluster.cluster_footprints(anchor, tmpl) | {anchor}
            cluster |= set(town_cluster.cluster_entrances(anchor, tmpl).values())
            cluster |= {t for t, p in self.hub_interior.items() if p == pid}
            for (cx, cy) in cluster:
                for dx in range(-SAFE_TILE_MARGIN, SAFE_TILE_MARGIN + 1):
                    for dy in range(-SAFE_TILE_MARGIN, SAFE_TILE_MARGIN + 1):
                        self._safe_tiles.add((cx + dx, cy + dy))
        # B63: chests are solid world objects — block their tiles (before the
        # encounter map freezes) and load the per-theme closed/open sprites.
        self.chest_tiles = {tuple(chest.tile): chest.id
                            for chest in self.engine.content.chests.values()}
        self.world.blocked |= set(self.chest_tiles)
        self._chest_sprites = self._load_chest_sprites()
        # B65/B80: boss lairs are solid landmarks while the boss LIVES — a felled
        # boss disappears entirely and its tile unblocks (Lucas: no husk).
        self.lair_tiles = {}
        self._sync_lairs()
        self._lair_sprites: dict = {}   # boss_id -> sprite | None, lazy
        # B83: the animated player (walk 7.5 fps / idle 4 fps, 8 directions).
        self._player_frames = self._load_player_frames()
        self._player_facing = 4          # start facing the camera (S)
        self._player_frame = 0
        self._player_anim_clock = 0
        self._player_moving = False
        # B55: freeze the tile geometry the CORE pacing rule reads (towns, the
        # B32 no-encounter zone, road tiles). The base rate stays a live attribute
        # (self.encounter_rate) so runtime tuning and tests keep working.
        self._encounter_map = encounters.EncounterMap(
            town_tiles=frozenset(self.world.town_tiles),
            safe_tiles=frozenset(self._safe_tiles),
            path_tiles=frozenset(self._build_path_tiles()),
        )
        # B47: zone-seam crossfade — synthetic gids built ONCE, after the road
        # scan froze (it must read original gids) and before any rendering.
        self._apply_zone_blend()
        # B74: a loaded engine restores its exact saved tile; otherwise the
        # place's town tile (fresh games, legacy saves).
        start_tile = self._restore_tile() or self.zone.start_tile
        self.world.set_tile(*start_tile)
        self.sync_location()
        self.view_size = (min(self.world.map_px_w, 960), min(self.world.map_px_h, 640))
        # Inherit the prior window's size (already a valid on-screen size) so the
        # overworld matches it instead of shrinking; cold start clamps a default.
        if self._inherited_size and self._inherited_size[0] > 1 and self._inherited_size[1] > 1:
            self.windowed_size = self._inherited_size
        else:
            self.windowed_size = fit_size(self.view_size)
        # B70: user settings apply at startup (fullscreen must precede the first
        # _apply_display_mode; log rows/minimap are applied where they init).
        self._settings = user_settings.load()
        self.fullscreen = bool(self._settings.get("fullscreen", False))
        # Initial canvas; draw() resizes it to the live display each frame (fluid
        # overworld) so the world fills the window and the camera shows more map.
        self.screen = pygame.Surface(self.view_size)
        self._transform = (0, 0, 1.0)
        self._cam_offset = (0, 0)  # world px offset from the last _draw_map (for screen_to_tile)
        self.display = None
        self._apply_display_mode()
        self.clock = pygame.time.Clock()
        # B104: post-battle grace — 1s of accumulated movement time before the
        # shared encounter/event slot can fire again. Rule lives in core.
        self.encounter_cooldown = encounters.EncounterCooldown()
        self._focus_surface = ("", "walk")   # B99 S2: reset focus on surface change
        self.encounter_rate = self.zone.encounter_rate_per_step
        self._last_tile = self.world.current_tile
        self._last_region = self.zone.wild_region_at(self._last_tile)
        self._walk_sfx_steps = 0   # B69: footstep every 2nd tile, not a machine gun
        self._music_slider_rect = None   # B69: set each frame the settings overlay draws
        self._music_dragging = False
        # Sub-pixel movement remainder (float) per axis; the int part moves the rect
        # each frame, the fraction carries over -> a non-integer PLAYER_SPEED. Zeroed
        # on any teleport so no drift accumulates across a reposition.
        self._move_accum_x = 0.0
        self._move_accum_y = 0.0
        self.font = pygame.font.SysFont("menlo,consolas,monospace", 16)
        self.font_sm = pygame.font.SysFont("menlo,consolas,monospace", 13)
        self.font_lg = pygame.font.SysFont("menlo,consolas,monospace", 22, bold=True)
        self.font_italic = pygame.font.SysFont("menlo,consolas,monospace", 13, italic=True)
        # Shared hover timer -> tooltip (B40 S1 infra). S2 wired the buttons in:
        # any button with a tooltip payload registers its rect via _draw_buttons.
        self.hover = ui.HoverTracker()
        self._row_style_cache = None   # built lazily (fonts above must exist)
        self.mode = "walk"  # walk | store | tournaments | tournament_confirm | tournament_intermission
        self.overlay = ""  # character | inventory | skills_talents | system
        self.inventory_category = "consumables"  # selected category in the inventory overlay
        self.overlay_return_mode = ""
        self.selected_equipment_slot = "weapon"
        self.selected_talent_id = ""
        self.active_event = None          # B67: the travel event being shown
        self._ambience = None             # B73: zone particle layer (lazy)
        self._ambience_theme = ""         # B73 S2: which preset the layer runs
        self.selected_tournament_id = ""
        self.tournament_run: TournamentRun | None = None
        self.store_category: str | None = None  # which trade building's store slice is open
        self.building_menu: tuple[str, str] | None = None  # (place_id, building_id) of the open door menu
        self.upgrade_building: str | None = None     # B37 Slice 2: open station building id
        self.selected_upgrade_item: str | None = None  # item being inspected at the station
        self.tome_building: str | None = None        # B38: open mage-tower tome shop building id
        self._bridge_img_cache: dict = {}            # B52: gid -> rotated deck image (or None)
        self.bestiary_index = 0                      # B66: selected codex row
        self._bestiary_sprite_cache: dict = {}       # enemy_id -> (thumb, silhouette)
        self._armed_boss_id = ""                     # B65: first E arms, second E fights
        self._end_shown = self.engine.main_goal_complete()   # B65: ending shows ONCE
        # B71: which manual slot this run saves to (the start menu tags the engine
        # when it loads a slot; a fresh game takes the first empty slot).
        self.save_path = getattr(self.engine, "_save_slot_path", None) or _first_free_slot()
        self._playtime_accum = 0.0                   # fractional seconds carry
        self._was_in_town = self.world.town_place_id() is not None
        self.show_minimap = bool(self._settings.get("minimap", True))   # B11/B70 (N toggles)
        # B11 fullscreen map caches: terrain texture (built once) + fog composite
        # (rebuilt only when the revealed-tile count changes).
        self._map_terrain = None
        self._map_composite = None
        self._map_composite_count = -1
        self.buttons: list[Button] = []
        # B99 S1: keyboard focus over the inventory + skills screens' buttons.
        self.focus = ui.FocusList()
        # B16 + B29: the chatbox is the ONLY on-screen text. Combat lines flow in via
        # the shared deque passed to BattleApp; world events flow in through set_toast
        # -> push_log. Deep scrollback (LOG_HISTORY_MAX), a player-resizable visible
        # height (log_visible), and a scroll offset for reading older lines.
        self.event_log: "collections.deque" = collections.deque(maxlen=LOG_HISTORY_MAX)
        self.log_visible = max(LOG_VISIBLE_MIN, min(int(self._settings.get("log_visible", LOG_VISIBLE_DEFAULT)), LOG_VISIBLE_MAX))
        self.log_scroll = 0      # lines scrolled up from the bottom (0 = newest visible)
        self.log_tab = "all"     # B16.1: "all" | "combat" — chatbox channel filter
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
        # B74: the save carries the EXACT tile (sync_location is the choke point
        # every movement/teleport passes), so loads never snap to the region's
        # pool-container town again.
        self.engine.player.overworld_tile = tuple(self.world.current_tile)
        if place_id != self.engine.player.current_place_id:
            self.engine.enter_place(place_id)
        in_town = self.world.town_place_id() is not None
        # getattr: sync_location runs during __init__ before the flag exists; the
        # True default also means "no autosave for merely starting in town".
        if in_town and not getattr(self, "_was_in_town", True):
            self.autosave("town")                     # B71: autosave on town entry
        self._was_in_town = in_town

    def set_toast(self, message: str, color=TEXT, log: bool = True) -> None:
        # B29: no floating toasts — every on-screen message goes to the chatbox log.
        # log=False keeps the B29.3 contract: a message the battle shell already
        # logged into the shared event_log is dropped here so it appears only once.
        if log:
            self.push_log(message, color)

    def push_log(self, message: str, color=TEXT, channel: str = chatlog.CHANNEL_WORLD) -> None:
        """Append a line to the shared chatbox log (deduping immediate repeats).
        Stays pinned to the newest line unless the player scrolled up to read
        history."""
        if chatlog.push(self.event_log, message, color, channel=channel) and self.log_scroll:
            self.log_scroll = min(self.log_scroll + 1, self._log_scroll_max())

    def _log_scroll_max(self) -> int:
        # In VISUAL-line units (a wrapped entry counts as its rendered rows), so
        # scrolling never strands wrapped text half-off the panel.
        return max(0, len(self._visual_log_lines()) - self.log_visible)

    def _log_interactive(self) -> bool:
        """The chatbox accepts scroll/resize only in free-walk; under menus/overlays
        it is drawn but read-only."""
        return self.mode == "walk" and not self.overlay

    def scroll_log(self, lines: int) -> None:
        """Scroll the chatbox: +lines = older (up), -lines = newer (down)."""
        self.log_scroll = max(0, min(self.log_scroll + lines, self._log_scroll_max()))

    def resize_log(self, delta: int) -> None:
        """Grow/shrink the chatbox by `delta` visible lines, clamped."""
        self.log_visible = max(LOG_VISIBLE_MIN, min(self.log_visible + delta, LOG_VISIBLE_MAX))
        self._persist_settings()
        self.log_scroll = min(self.log_scroll, self._log_scroll_max())

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

    def _persist_settings(self) -> None:
        """B70: write the current display/HUD prefs to settings.json."""
        self._settings.update(fullscreen=self.fullscreen, log_visible=self.log_visible,
                              minimap=self.show_minimap)
        user_settings.save(self._settings)

    def _set_music_volume_from_x(self, x: int) -> None:
        """B69: map a click/drag x on the settings slider to 0..100, apply to
        the live music stream immediately; the caller persists on release."""
        bar = self._music_slider_rect
        if bar is None or bar.width <= 0:
            return
        volume = round(100 * min(max(x - bar.x, 0), bar.width) / bar.width) / 100.0
        self._settings["sound_music"] = volume
        audio.apply_music_volume(self._settings.get("sound_master", 1.0), volume)

    def adjust_music_volume(self, direction: int) -> None:
        """B99 S2: keyboard slider adjustment — ±5 points per left/right press,
        applied live and persisted (there is no 'release' on a keyboard)."""
        try:
            current = float(self._settings.get("sound_music", 1.0))
        except (TypeError, ValueError):
            current = 1.0
        volume = min(1.0, max(0.0, round(current * 100 + 5 * direction) / 100.0))
        self._settings["sound_music"] = volume
        audio.apply_music_volume(self._settings.get("sound_master", 1.0), volume)
        user_settings.save(self._settings)

    def toggle_fullscreen(self) -> None:
        self.fullscreen = not self.fullscreen
        self._apply_display_mode()
        self._log_display("toggle_fullscreen")
        self._persist_settings()

    # -- wild encounters + battle loop --------------------------------------

    def maybe_encounter(self):
        """Roll a per-step wild encounter. Returns an enemy or None.

        B55: the pacing RULE (rate heatmap + the roll) lives in core/encounters;
        this shell provides the geometry and the engine's seeded RNG. In town no
        rng draw is consumed — stream-identical to the pre-B55 behaviour.
        B48: WHAT spawns comes from the tile's drawn areas (union of overlaps,
        core/spawns) — the shell owns the tile, the core owns the rule.
        """
        if self.world.town_place_id() is not None:
            return None      # in town: no rng draw (stream-identical to pre-B55)
        if self.encounter_cooldown.active:
            return None      # B104: post-battle grace — no rng draw consumed
        tile = self.world.current_tile
        if self.engine.rng.random() < self.encounter_rate_at(tile):
            # B67: a fired slot RARELY becomes a travel event instead of a fight
            # (the total interruption frequency does not increase). Core owns
            # the rule; the shell owns the tile/theme.
            if core_events.replaces_encounter(
                    self.engine.content.travel_event_slot_chance, self.engine.rng):
                event = core_events.pick_event(
                    self.engine.content.travel_events,
                    self.zone.theme_for_tile(tile), self.engine.rng)
                if event is not None:
                    self.active_event = event
                    self.mode = "travel_event"
                    return None
            pool = spawns.pool_at(self.engine.content.spawn_areas,
                                  self.engine.content.spawn_fallbacks,
                                  tile, self.zone.wild_region_at(tile))
            band = spawns.band_at(self.engine.content.spawn_areas, tile)
            return self.engine.create_encounter(pool=pool, band=band)
        return None

    def _build_path_tiles(self) -> set:
        """Scan the ground layer ONCE for road/cobble tiles (the autotile road
        indices of the grass sheets) — the core pacing rule reads a plain set."""
        try:
            ground = self.world.tmx.get_layer_by_name("ground")
        except (ValueError, KeyError):
            return set()
        tiles = set()
        for y, row in enumerate(ground.data):
            for x, gid in enumerate(row):
                if any(fg <= gid < fg + 64 and (gid - fg) >= 32 for fg in (3, 387)):
                    tiles.add((x, y))
        return tiles

    def _nearest_town_dist(self, tile) -> int:
        return encounters.nearest_town_dist(self._encounter_map, tile)

    def _on_path(self, tile) -> bool:
        return tile in self._encounter_map.path_tiles

    def encounter_rate_at(self, tile) -> float:
        """Per-step encounter chance at a tile (B12 heatmap; RULE in core). The
        road check routes through self._on_path so that seam stays mockable."""
        return encounters.encounter_rate_at(self._encounter_map, tile,
                                            self.encounter_rate, on_path=self._on_path(tile))

    def start_battle(self, enemy) -> None:
        """Hand off to the battle shell, then return to the overworld."""
        location_id = self.engine.player.current_place_id
        outcome = BattleApp(
            engine=self.engine,
            enemy=enemy,
            standalone=False,
            playtest_logger=self.playtest_logger,
            location_id=location_id,
            event_log=self.event_log,  # B16: mirror combat/drops/level-ups into the overworld log
        ).run()
        # Re-assert the overworld display (preserves window/fullscreen state).
        self._apply_display_mode()
        self._log_display("after_battle")
        self.resolve_battle_outcome(outcome, enemy)

    def resolve_battle_outcome(self, outcome: str, enemy) -> None:
        self.encounter_cooldown.start()   # B104: 1s of movement before the next roll
        if outcome == "defeat":
            # Engine already respawned the player; move the sprite to match.
            respawn_place = self.engine.player.current_place_id
            tile = self.town_tile_by_place.get(respawn_place)
            if tile is not None:
                self.world.set_tile(*tile)
            self._move_accum_x = self._move_accum_y = 0.0  # teleport -> no carried drift
            self.sync_location()
            self.set_toast(T.defeat_respawn(self.engine.current_place().name), BAD)
            self.mode = "death"                       # B71: a dignified death screen
        else:
            # Victory or flee: stay where we are; location is still the wilds. The
            # battle shell already logged the outcome into the shared event_log, so
            # these are toast-only (log=False) to avoid a duplicate log line.
            self.sync_location()
            if outcome == "fled":
                self.set_toast(T.fled_from(enemy.name), WARN, log=False)
            else:
                self.set_toast(T.victory_over(enemy.name), GOOD, log=False)
                self.autosave("battle")               # B71: autosave after a victory
                if getattr(enemy, "boss", False):
                    self._sync_lairs()   # B80: the felled boss vanishes from the world
                # B65: felling the final boss ends the main goal — show the ending
                # once (a loaded finished save never re-triggers it).
                if getattr(enemy, "boss", False) and not self._end_shown \
                        and self.engine.main_goal_complete():
                    self._end_shown = True
                    self.mode = "victory"
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
            result = self.engine.rest(self.zone.zone_for_tile(self.world.current_tile))
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
        elif action == "brew":            # B8 2b: the apothecary door
            self._open_apothecary()
        elif action == "fast_travel":     # B8 2b: the stable door
            self._open_fast_travel()
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
        self.focus.reset()   # B99: keyboard focus starts at the first row

    def close_overlay(self) -> None:
        self.overlay = ""
        if self.overlay_return_mode:
            self.mode = self.overlay_return_mode
            self.overlay_return_mode = ""

    def save_game(self) -> None:
        saveslots.ensure_saves_dir()
        result = self.engine.save(self.save_path)
        self.set_toast(result.message, GOOD if result.success else BAD)

    def autosave(self, reason: str) -> None:
        """B71: write the separate autosave slot (town entry / after battle)."""
        saveslots.ensure_saves_dir()
        result = self.engine.save(saveslots.AUTOSAVE_PATH)
        if result.success:
            self.push_log(f"Autosaved ({reason}).", TEXT_DIM)

    def _load_save(self, path: str) -> None:
        """B71: load a save (death screen / slot picker) and resync the sprite."""
        result = self.engine.load(path)
        if not result.success:
            self.push_log(result.message, BAD)
            return
        tile = self._restore_tile()
        if tile is not None:
            self.world.set_tile(*tile)
        self._move_accum_x = self._move_accum_y = 0.0
        self._sync_lairs()   # B80: the loaded run decides which lairs still stand
        self.sync_location()
        self.mode = "walk"
        self._end_shown = self.engine.main_goal_complete()   # B65: track the loaded run
        self.push_log("Game loaded.", GOOD)

    def _restore_tile(self) -> tuple[int, int] | None:
        """B74: where a loaded save puts the player — the saved EXACT tile when
        present and still walkable, else the place's town tile (legacy saves,
        or a tile that content changes have since blocked)."""
        saved = tuple(getattr(self.engine.player, "overworld_tile", ()) or ())
        if len(saved) == 2 and saved not in self.world.blocked:
            return saved
        return self.town_tile_by_place.get(self.engine.player.current_place_id)

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
            # Name the weapon ("Rimebrand needs level 5.") instead of the raw action
            # text ("... needs level N for Swap weapon.").
            self.set_toast(T.weapon_needs_level(weapon.name, combat.weapon_required_level(weapon)), BAD)
        else:
            self.engine.recompute_equipment()   # reattach the new weapon's upgrade deltas
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
        if result.success:
            sound = audio.potion_sound(self.engine.content.items.get(item_id))
            if sound:
                audio.play(sound)   # B69: tomes and misc stay silent
        item = self.engine.content.items.get(item_id)
        if result.success and item is not None and item.kind == "tome":
            # B100: studying a tome acquires a skill — it lands on the Loot tab.
            self.push_log(result.message, chatlog.loot_source_color("study"),
                          channel=chatlog.CHANNEL_LOOT)
        else:
            self.set_toast(result.message, GOOD if result.success else BAD)

    # -- inventory overview (everything owned) ------------------------------

    GEAR_SLOT_TYPES = ("head", "chest", "hands", "legs", "feet", "amulet", "ring")

    def inventory_counts(self) -> dict:
        """Count of everything owned, per category, from the same source the
        equip path reads (owned weapons/gear + the consumables bag). Consumables
        and miscellaneous count total quantity; equipment counts owned items."""
        snap = build_snapshot(self.engine)
        items = self.engine.content.items
        bag = self.engine.player.inventory.consumables
        counts = {
            # B38: tomes are usable items -> live with consumables, not inert misc.
            "consumables": sum(c for i, c in bag.items() if c > 0 and items[i].kind in ("consumable", "tome")),
            "miscellaneous": sum(c for i, c in bag.items() if c > 0 and items[i].kind not in ("consumable", "tome")),
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
        Equippable items hand off to the Character panel; consumables use;
        miscellaneous is inert. B40 S2: labels are bare NAMES — counts, rarity
        and stats ride as row value / name colour / hover tooltip instead."""
        snap = build_snapshot(self.engine)
        items = self.engine.content.items
        bag = self.engine.player.inventory.consumables
        rows = []
        if category in ("consumables", "miscellaneous"):
            want_consumable = category == "consumables"
            for item_id, count in sorted(bag.items()):
                usable = items[item_id].kind in ("consumable", "tome")  # B38: tomes are usable
                if count <= 0 or usable != want_consumable:
                    continue
                if want_consumable:
                    rows.append((item_id, items[item_id].name,
                                 (lambda iid=item_id: self.use_inventory_item(iid)), True))
                else:
                    rows.append((item_id, items[item_id].name, None, False))
            return rows
        if category == "weapon":
            for w in snap.weapons:
                rows.append((w.id, w.name,
                             (lambda: self.inventory_equip_handoff("weapon")), True))
            return rows
        for gear in snap.gear:
            if gear.slot_type != category:
                continue
            rows.append((gear.id, gear.name,
                         (lambda st=gear.slot_type: self.inventory_equip_handoff(st)), True))
        return rows

    def inventory_row_extras(self, item_id: str):
        """B40 S2: the (value, label_color, tooltip) trio for an inventory row.
        The action-relevant figure stays on the row (count, damage, 'equipped');
        rarity becomes the name's colour; everything else moves to the hover
        tooltip built by item_text."""
        content = self.engine.content
        player = self.engine.player
        if item_id in content.weapons:
            weapon = content.weapons[item_id]
            tip = item_text.weapon_tooltip(weapon, price_line=item_text.sell_line(weapon.price))
            self._append_upgrade_line(tip, item_id)
            value = "equipped" if player.equipped_weapon_id == item_id else f"+{weapon.damage_bonus} dmg"
            return value, chatlog.rarity_color(weapon.rarity), tip
        if item_id in content.gear_items:
            gear = content.gear_items[item_id]
            price_line = f"Sells for {store.gear_sell_value(gear)} gold"
            tip = item_text.gear_tooltip(gear, price_line=price_line)
            self._append_upgrade_line(tip, item_id)
            value = "equipped" if item_id in player.equipped_gear.values() else ""
            return value, chatlog.rarity_color(gear.rarity), tip
        item = content.items.get(item_id)
        if item is not None:
            # Only miscellaneous is shop-sellable (store CATEGORY_RULES), so only
            # its tooltip talks money.
            price_line = item_text.sell_line(item.price) if item.kind == "miscellaneous" else ""
            tip = item_text.consumable_tooltip(item, content, price_line=price_line)
            count = player.inventory.count(item_id)
            return (f"x{count}" if count > 1 else ""), None, tip
        return "", None, None

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




    def learn_talent(self, node_id: str) -> None:
        try:
            message = self.engine.allocate_talent(node_id)
            self.set_toast(message, GOOD)
        except ValueError as error:
            self.set_toast(str(error), BAD)

    def select_talent(self, node_id: str) -> None:
        self.selected_talent_id = node_id

    def class_talent_nodes(self):
        # B105: flat selection order follows the grouped display (branch
        # sections with cross-passives attached under their parent branch).
        return [node for _, nodes in
                talent_text_grouped(self.engine.content, self.engine.player.player_class)
                for node in nodes]

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
        # B106: plain words in the detail panel — "[LOCKED]" reads as "Locked".
        status = detail.status.strip("[]").capitalize()
        lines = [
            detail.name,
            status,
            f"Rank: {detail.rank}/{detail.max_rank}",
            f"Effect: {detail.effect}",
        ]
        # B90: every rank spelled out with its computed values, current marked.
        if detail.max_rank > 1:
            lines.extend(detail.rank_lines)
        lines.extend([
            f"Cost: {detail.cost}",
            f"Requires: {detail.prerequisite}",
        ])
        return lines

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
            self.mode = "walk"
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
            if reward.success:   # B100: the series payout lands on the Loot tab
                self.push_log(reward.message, chatlog.loot_source_color("tournament"),
                              channel=chatlog.CHANNEL_LOOT)
            else:
                self.set_toast(reward.message, BAD)
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
        self.mode = "walk"

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
            elif event.type == pygame.MOUSEWHEEL:
                if self.overlay == "bestiary":
                    self.move_bestiary_selection(-event.y)   # B79: wheel browses the codex
                elif self._log_interactive():   # scroll only in walk; read-only under menus
                    self.scroll_log(event.y * LOG_SCROLL_STEP)   # wheel up = older lines
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                pos = to_canvas(event.pos, self._transform)
                # B69: the settings slider grabs the click before the buttons
                # (its knob overhangs the bar, hence the inflated hit zone).
                if (self.overlay == "settings" and self._music_slider_rect is not None
                        and self._music_slider_rect.inflate(16, 16).collidepoint(pos)):
                    self._music_dragging = True
                    self._set_music_volume_from_x(pos[0])
                    continue
                for button in self.buttons:
                    if button.enabled and button.rect.collidepoint(pos):
                        audio.play("menu_click")
                        button.on_click()
                        break
            elif event.type == pygame.MOUSEMOTION and self._music_dragging:
                self._set_music_volume_from_x(to_canvas(event.pos, self._transform)[0])
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self._music_dragging:      # B69: persist once, on release
                    self._music_dragging = False
                    user_settings.save(self._settings)

    def _handle_key(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_F11:
            self.toggle_fullscreen()
            return
        if self.overlay == "bestiary":              # B66: arrow-key row selection
            if event.key in (pygame.K_DOWN, pygame.K_RIGHT):
                self.move_bestiary_selection(1)
                return
            if event.key in (pygame.K_UP, pygame.K_LEFT):
                self.move_bestiary_selection(-1)
                return
        # B99 S2: keyboard focus on every menu surface. The bestiary keeps its
        # own arrow model (B66, handled above); the world map has no buttons so
        # the keys are a no-op there.
        if (self.overlay and self.overlay != "bestiary") or self.mode in FOCUS_MODES:
            if self._handle_focus_key(event):
                return
        if event.key == pygame.K_ESCAPE:
            if self.overlay:
                self.close_overlay()
            elif self.mode == "building":
                self._close_building_menu()
            elif self.mode == "upgrade_station":
                self._close_upgrade_station()
            elif self.mode == "store":
                self.mode = "walk"
            elif self.mode == "tome_shop":
                self._close_tome_shop()
            elif self.mode in ("apothecary", "fast_travel"):
                self.mode = "walk"
            elif self.mode == "travel_event":
                pass   # B67: an event demands a choice — Esc does not skip it
            elif self.mode == "death":
                self.mode = "walk"
            elif self.mode == "victory":
                self.mode = "walk"
            elif self.mode in {"tournaments", "tournament_confirm"}:
                self.mode = "walk"
            elif self.mode == "tournament_intermission":
                self.overlay = "system"
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
        if event.key == pygame.K_m:
            self.toggle_overlay("map")
            return
        if event.key == pygame.K_n:
            self.show_minimap = not self.show_minimap   # B11 Slice 2
            self._persist_settings()
            return
        if event.key == pygame.K_b:
            self.toggle_overlay("bestiary")             # B66 codex
            return
        # Chatbox resize/scroll: walk-only. Under menus the chatbox is visible but
        # read-only ('+' grows, '-' shrinks; PageUp/PageDown scroll).
        if self._log_interactive():
            if event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self.resize_log(1)
                return
            if event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.resize_log(-1)
                return
            if event.key == pygame.K_PAGEUP:
                self.scroll_log(LOG_SCROLL_STEP)
                return
            if event.key == pygame.K_PAGEDOWN:
                self.scroll_log(-LOG_SCROLL_STEP)
                return
        if event.key in (pygame.K_RETURN, pygame.K_e):
            if self.mode == "walk":
                door = self.door_index.get(self.world.current_tile)
                if door is not None:
                    self._interact_door(*door)
                    return
                if self._try_challenge_boss():   # B65: lair beside the player
                    return
                self._try_open_chest()   # B63: open an adjacent chest

    def update(self) -> None:
        self._player_moving = False      # B83: proven again each walk frame
        if self.overlay or self.mode != "walk":
            return
        keys = pygame.key.get_pressed()
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        if dx or dy:
            self._player_moving = True
            # B104: only frames with actual movement count down the cooldown.
            self.encounter_cooldown.tick_movement(self.clock.get_time() / 1000.0)
            self._player_facing = player_facing(dx, dy, self._player_facing)
            # B87: normalize so diagonal speed equals cardinal speed (was sqrt(2) faster).
            speed = PLAYER_SPEED / math.sqrt(2) if dx and dy else PLAYER_SPEED
            # Accumulate sub-pixel movement; move the integer part, carry the rest.
            # int() truncates toward zero so the fraction keeps its sign both ways.
            self._move_accum_x += dx * speed
            self._move_accum_y += dy * speed
            step_x, step_y = int(self._move_accum_x), int(self._move_accum_y)
            self._move_accum_x -= step_x
            self._move_accum_y -= step_y
            if step_x or step_y:
                message = self.world.try_move(step_x, step_y)
                if message:
                    self.set_toast(message, WARN)
                self.sync_location()
                tile = self.world.current_tile
                if tile != self._last_tile:
                    self._last_tile = tile
                    self._walk_sfx_steps += 1        # B69: soft step every 2nd tile
                    if self._walk_sfx_steps % 2 == 0:
                        audio.play("walk")
                    self._armed_boss_id = ""   # B65: stepping away disarms the challenge
                    region = self.zone.wild_region_at(tile)
                    if region != self._last_region and region != self.zone.wild_region_place_id:
                        self.set_toast(T.region_flavor(region), WARN)  # soft signal, not a wall
                    self._last_region = region
                    enemy = self.maybe_encounter()
                    if enemy is not None:
                        self.start_battle(enemy)

    # -- rendering ----------------------------------------------------------

    def _draw_ambience(self) -> None:
        """B73/B110: the zone's world-space particle preset over the map.

        Themes without a wired preset
        draw nothing; the whole layer sits behind the Ambience toggle."""
        if not self._settings.get("ambience", True):
            return
        theme = self.zone.theme_for_tile(self.world.current_tile)
        preset = ambience.PRESETS.get(theme)
        if preset is None:
            return
        zoom = self._zoom_factor()
        view_size = (max(1, self.screen.get_width() // zoom),
                     max(1, self.screen.get_height() // zoom))
        center = self.world.player.center
        if self._ambience is None or self._ambience_theme != theme:
            self._ambience = ambience.ParticleLayer(view_size, preset=preset, world_center=center)
            self._ambience_theme = theme
        self._ambience.resize(view_size, center)
        self._ambience.update(center)
        self._ambience.draw(self.screen, self._cam_offset, zoom)

    def draw(self) -> None:
        self.buttons = []
        self._tick_player_anim()   # B83: one animation tick per rendered frame
        self.hover.begin()   # menus re-register their hoverable rects each frame
        self.focus.begin()   # B99: focusable buttons re-register each frame too
        # B99 S2: a new surface starts focused at its first row (mode-based
        # screens have no single entry point, so the reset is detected here).
        if (self.overlay, self.mode) != self._focus_surface:
            self._focus_surface = (self.overlay, self.mode)
            self.focus.reset()
        # Fluid overworld: the canvas tracks the live (logical) display size, so
        # the world fills the window instead of sitting as a centered island. The
        # camera (camera_offset) then shows more map; present() is the identity
        # transform. SCALED still upscales the logical surface crisply on HiDPI.
        if self.display is not None and self.screen.get_size() != self.display.get_size():
            self.screen = pygame.Surface(self.display.get_size())
        self.screen.fill(BG)
        self._draw_map()
        self._draw_ambience()   # B73: zone particles above the world, below HUD
        self._draw_hud()
        if self.mode == "walk" and not self.overlay:
            self._draw_vitals()
            if self.show_minimap:
                self._draw_minimap()
        if self.mode == "building":
            self._draw_building_menu()
        elif self.mode == "upgrade_station":
            self._draw_upgrade_station()
        elif self.mode == "store":
            self._draw_store_screen()
        elif self.mode == "tome_shop":
            self._draw_tome_shop()
        elif self.mode == "apothecary":
            self._draw_apothecary()
        elif self.mode == "fast_travel":
            self._draw_fast_travel()   # B8 2b: the stable coach board
        elif self.mode == "death":
            self._draw_death_screen()
        elif self.mode == "victory":
            self._draw_victory_screen()   # B65: the ending
        elif self.mode == "tournaments":
            self._draw_tournament_list_screen()
        elif self.mode == "tournament_confirm":
            self._draw_tournament_confirm_screen()
        elif self.mode == "tournament_intermission":
            self._draw_tournament_intermission_screen()
        elif self.mode == "travel_event":
            self._draw_travel_event()         # B67: choices as button rows
        if self.overlay == "map":
            self._draw_map_overlay()      # fullscreen, not the standard panel
        elif self.overlay:
            self._draw_overlay_screen()
        # Chatbox LAST so it stays visible (read-only) over overlays and menus, not
        # only in walk — the player always sees why an action was blocked.
        self._draw_log()
        # Tooltip on the very top, once the mouse has dwelt on a registered row.
        mouse = to_canvas(pygame.mouse.get_pos(), self._transform)
        self.hover.update(mouse, pygame.time.get_ticks())
        if self.hover.active is not None:
            ui.draw_tooltip(self.screen, self.hover.active, mouse, self.font, self.font_sm)
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




    # -- B11 fullscreen map + fog of war ------------------------------------







    def _resolve_town_template(self, place_id: str, has_tournament: bool):
        """Concrete building list for a town from its core_zone tier/shop_category/
        prop (provisional data) + whether a tournament lives here (town_hall gate)."""
        meta = (self.zone.town_meta or {}).get(place_id, {})
        return town_cluster.resolve_template(
            meta.get("tier", "village"),
            shop_category=meta.get("shop_category"),
            prop=meta.get("prop"),
            has_tournament=has_tournament,
        )










    # -- B66: bestiary codex --------------------------------------------------






    def _try_open_chest(self) -> bool:
        """E/Enter: open a chest on an adjacent tile (chests are solid, so the
        player always stands next to one). Returns True if a chest was there."""
        px, py = self.world.current_tile
        for tile in ((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)):
            chest_id = self.chest_tiles.get(tile)
            if chest_id is None:
                continue
            result = self.engine.open_chest(chest_id)
            if not result.success:
                self.push_log(result.message, TEXT_DIM)
                return True
            audio.play("open_chest")
            self.push_log(result.message, TEXT)
            # B44/B100: gold and the rarity-coloured item name share ONE row,
            # tagged with the chest source on the Loot tab.
            source_color = chatlog.loot_source_color("chest")
            parts = [("Opened chest: ", source_color), (f"+{result.gold} gold", chatlog.GOLD)]
            if result.drop is not None:
                parts.append(("   ", TEXT))
                parts.append((result.drop.name, chatlog.rarity_color(result.drop.rarity)))
            chatlog.push_rich(self.event_log, parts, channel=chatlog.CHANNEL_LOOT)
            return True
        return False

    def _sync_lairs(self) -> None:
        """B80: (re)derive the living lairs from the player's defeated set —
        felled bosses vanish and their tiles unblock. Runs at init, after a
        boss victory and after every load (each may change the set)."""
        defeated = self.engine.player.defeated_boss_ids
        living = {tuple(boss.lair_tile): boss.id
                  for boss in self.engine.content.bosses.values()
                  if boss.id not in defeated}
        self.world.blocked -= set(self.lair_tiles) - set(living)
        self.world.blocked |= set(living)
        self.lair_tiles = living

    def _try_challenge_boss(self) -> bool:
        """B65 E/Enter: a lair on an adjacent tile. First press announces the
        boss (arming the challenge), the second press starts the fight; walking
        away disarms. Gated lairs (defeated / prerequisites) just explain why.
        Returns True if a lair was there."""
        px, py = self.world.current_tile
        for tile in ((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)):
            boss_id = self.lair_tiles.get(tile)
            if boss_id is None:
                continue
            blocker = self.engine.boss_challenge_blocker(boss_id)
            if blocker:
                self.push_log(blocker, TEXT_DIM)
                return True
            boss = self.engine.content.bosses[boss_id]
            template = self.engine.content.enemies[boss.enemy_id]
            if self._armed_boss_id != boss_id:
                self._armed_boss_id = boss_id
                if boss.intro:
                    self.push_log(boss.intro, WARN)
                self.push_log(T.boss_challenge_prompt(template.name, template.level), WARN)
                return True
            self._armed_boss_id = ""
            enemy = self.engine.challenge_boss(boss_id)
            if enemy is not None:
                self.start_battle(enemy)
            return True
        return False






    @staticmethod
    def _compass(ax: int, ay: int, px: int, py: int) -> str:
        """Cardinal/intercardinal bearing FROM an anchor (ax,ay) TO the player
        (px,py). Map y grows downward, so dy>0 reads as south."""
        dx, dy = px - ax, py - ay
        ns = "north" if dy < 0 else "south" if dy > 0 else ""
        ew = "west" if dx < 0 else "east" if dx > 0 else ""
        # Keep only the dominant axis unless the offset is near-diagonal.
        if ns and ew and min(abs(dx), abs(dy)) * 2 < max(abs(dx), abs(dy)):
            if abs(dx) > abs(dy):
                ns = ""
            else:
                ew = ""
        return (ns + ew) or "near"

    def _location_label(self) -> tuple[str, bool]:
        """(text, in_town) for the top-right indicator: names the city when the
        player stands anywhere on its cluster, a relative bearing ("south of
        Hordanita") when near a hub, else the generic wilds text."""
        tile = self.world.current_tile
        pid = self.hub_interior.get(tile) or self.world.town_place_id()
        if pid is not None:
            return self.engine.content.places[pid].name, True
        nearest, best = None, NEAR_RADIUS + 1
        for hub_id, (ax, ay) in self.cluster_anchors.items():
            d = max(abs(ax - tile[0]), abs(ay - tile[1]))   # Chebyshev distance
            if d < best:
                nearest, best = (hub_id, (ax, ay)), d
        if nearest is not None:
            hub_id, (ax, ay) = nearest
            bearing = self._compass(ax, ay, *tile)
            return T.near_direction(bearing, self.engine.content.places[hub_id].name), False
        return T.wilds_near(self.engine.current_place().name), False

    def _draw_hud(self) -> None:
        # B31: no top bar, no name/gold/level text. Only the town indicator (top
        # right) plus the bottom-centre control hint. Vitals are bars above the
        # chatbox. B31-polish: a small faint plate behind the indicator keeps it
        # legible over bright map tiles (no full dark top bar).
        where, in_town = self._location_label()
        color = ACCENT if in_town else TEXT_DIM
        label = self.font_sm.render(where, True, color)
        rect = label.get_rect(topright=(self.screen.get_width() - 10, 8))
        plate = rect.inflate(12, 8)
        plate_surf = pygame.Surface(plate.size, pygame.SRCALPHA)
        plate_surf.fill((10, 12, 18, 150))   # faint, semi-transparent
        self.screen.blit(plate_surf, plate.topleft)
        pygame.draw.rect(self.screen, (*PANEL_EDGE, 120), plate, width=1, border_radius=4)
        self.screen.blit(label, rect)
        if self.mode == "walk":
            hint = T.HINT_TOWN if in_town else T.HINT_WALK
            hsurf = self.font_sm.render(hint, True, TEXT_DIM)
            self.screen.blit(hsurf, hsurf.get_rect(midbottom=(self.screen.get_width() // 2, self.screen.get_height() - 6)))

    def _draw_vitals(self) -> None:
        """B31/B39: a compact "Lv N    Gold G" line above thicker HP/Mana/XP bars,
        stacked just ABOVE the chatbox (no name). Bars are tall enough for their
        inline current/max text to sit comfortably centred."""
        p = build_snapshot(self.engine).player
        log = self._log_rect()
        bar_h, gap = 18, 3
        rows = [
            ("HP", p.hp, p.max_hp, HP_COL),
            ("Mana", p.mana, p.max_mana, MANA_COL),
            ("XP", p.xp, p.xp_required, XP_COL),
        ]
        head_h = self.font_sm.get_height() + 3
        total = head_h + len(rows) * (bar_h + gap)
        x, w = log.x, log.width
        y = log.y - total - 4
        # Lv + Gold header (no name).
        self.screen.blit(self.font_sm.render(f"Lv {p.level}    Gold {p.gold}", True, TEXT), (x + 2, y))
        y += head_h
        text_dy = max(0, (bar_h - self.font_sm.get_height()) // 2)
        for name, cur, mx, col in rows:
            ratio = max(0.0, min(1.0, cur / mx)) if mx else 0.0
            track = pygame.Rect(x, y, w, bar_h)
            pygame.draw.rect(self.screen, BAR_TRACK, track, border_radius=3)
            if ratio > 0:
                pygame.draw.rect(self.screen, col,
                                 pygame.Rect(x, y, max(2, int(w * ratio)), bar_h), border_radius=3)
            pygame.draw.rect(self.screen, PANEL_EDGE, track, width=1, border_radius=3)
            text = f"{name} {cur}/{mx}" if mx else f"{name} {cur}"
            self.screen.blit(self.font_sm.render(text, True, TEXT), (x + 6, y + text_dy))
            y += bar_h + gap

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

    def _handle_focus_key(self, event: pygame.event.Event) -> bool:
        """B99 S1: keyboard focus in the inventory + skills screens. Up/down move
        within the section, left/right (or Tab) jump between sections, Enter
        activates the focused button (same path as a click). Returns True when
        the key was consumed; anything else (e.g. Esc) falls through."""
        if event.key == pygame.K_DOWN:
            self.focus.move(1)
            return True
        if event.key == pygame.K_UP:
            self.focus.move(-1)
            return True
        if event.key == pygame.K_RIGHT:
            # B99 S2: a focused slider row consumes left/right as adjustment.
            focused = self.focus.focused()
            if isinstance(focused, ui.FocusSlider):
                focused.adjust(1)
                return True
            self.focus.move_section(1)
            return True
        if event.key == pygame.K_LEFT:
            focused = self.focus.focused()
            if isinstance(focused, ui.FocusSlider):
                focused.adjust(-1)
                return True
            self.focus.move_section(-1)
            return True
        if event.key == pygame.K_TAB:
            self.focus.move_section(-1 if event.mod & pygame.KMOD_SHIFT else 1)
            return True
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            button = self.focus.focused()
            if (button is not None and getattr(button, "enabled", False)
                    and callable(getattr(button, "on_click", None))):
                audio.play("menu_click")
                button.on_click()
            return True
        return False

    def _add_button(self, rect, label, cb, enabled=True, restricted=False, *,
                    value="", label_color=None, tooltip=None, focus_section="",
                    badge="") -> None:
        button = Button(rect, label, cb, enabled, restricted, hotkey=badge,
                        value=value, label_color=label_color, tooltip=tooltip)
        self.buttons.append(button)
        # B99 S2: every button is keyboard-focusable. Surfaces that want
        # multiple sections (inventory/skills) pass explicit section names;
        # everything else lands in one section in draw order.
        self.focus.add(focus_section or "main", button)

    # B40 S4: the B37 'Upgradable' overlay chip is retired — it collided with
    # the rows' right-aligned value slot. The flag now lives as a tooltip line
    # (item_text/store_row_extras) and the reforge stations list the items.

    def _row_style(self) -> ui.RowStyle:
        """B40 S2: the overworld's RowStyle — the old button palette expressed
        through the shared renderer, so every screen draws rows ONE way."""
        if self._row_style_cache is None:
            self._row_style_cache = ui.RowStyle(
                font=self.font, bg=BTN, hover=BTN_HOVER, disabled=BTN_DISABLED,
                edge=BTN_EDGE, text=TEXT, text_dim=TEXT_DIM, value=ACCENT, pad=12)
        return self._row_style_cache

    def _draw_buttons(self) -> None:
        # B40 S2: every button renders via the shared draw_menu_row (unified
        # chrome, spec point 6). Buttons carrying a tooltip register their rect
        # with the hover tracker here — the >1 s dwell popup draws in draw().
        mouse = to_canvas(pygame.mouse.get_pos(), self._transform)
        style = self._row_style()
        focused_button = self.focus.focused()   # B99: reuses the hover look
        for b in self.buttons:
            row = ui.MenuRow(label=b.label, value=b.value, enabled=b.enabled,
                             restricted=b.restricted, tooltip=b.tooltip,
                             label_color=b.label_color, badge=b.hotkey)
            ui.draw_menu_row(self.screen, b.rect, row, style,
                             mouse=mouse, hover=self.hover, fit=self._fit_text,
                             focused=b is focused_button)



    # -- B38: skill-tome shop (mage tower) ----------------------------------





    # -- B70: settings overlay --------------------------------------------------


    # -- B71: death screen -----------------------------------------------------


    # -- B68: apothecary brewing ----------------------------------------------




    # -- B37 Slice 2: upgrade station ---------------------------------------













    def _lines(self, panel, lines, color=TEXT, start=64, step=24) -> int:
        for i, line in enumerate(lines):
            self.screen.blit(self.font.render(line, True, color), (panel.x + 20, panel.y + start + i * step))
        return panel.y + start + len(lines) * step

    def _content_rect(self, panel: pygame.Rect) -> pygame.Rect:
        return pygame.Rect(panel.x + 20, panel.y + 56, panel.width - 40, panel.height - 126)

    def _fit_text(self, text: str, max_width: int, font: pygame.font.Font | None = None) -> str:
        # B57: delegates to THE shared ellipsis-fit in ui.
        return ui.fit(text, font or self.font, max_width)

    def _wrapped_lines_pixels(self, text: str, max_width: int, font: pygame.font.Font | None = None) -> list[str]:
        # B57: delegates to THE shared wrap in ui.
        return ui.wrap(text, font or self.font, max_width)



    # Short stat names for the compare-vs-equipped delta on equipment options.
    _DELTA_LABELS = {"damage": "dmg", "armor": "armor", "max_hp": "hp",
                     "max_mana": "mana", "speed": "speed", "crit_chance": "crit",
                     "wisdom": "wisdom"}








    # B40 S3: _blit_item_stats is gone — store rows moved their stat text into
    # the shared hover tooltips (StoreEntry.description stays in core for the
    # terminal presentation).

    def _log_visible_now(self) -> int:
        """Visible chatbox lines for the current mode: the player-set size in free
        walk, a compact read-only strip under menus/overlays (so it shows the latest
        lines without burying menu content)."""
        if self._log_interactive():
            return self.log_visible
        return min(self.log_visible, LOG_VISIBLE_MIN)

    def _log_rect(self) -> pygame.Rect:
        """Geometry of the chatbox panel (bottom-left). Height tracks the visible
        line count (compact under menus); width scales gently with the window."""
        line_h = self.font_sm.get_height() + 3
        pad = 8
        panel_w = min(max(360, self.screen.get_width() // 3), self.screen.get_width() - 16)
        panel_h = pad * 2 + line_h * self._log_visible_now()
        return pygame.Rect(8, self.screen.get_height() - panel_h - 8, panel_w, panel_h)

    def _visual_log_lines(self) -> list[tuple[str, tuple, bool]]:
        """The shared event log flattened into word-wrapped (text, color, newest)
        visual lines (delegates to the shared chatlog component)."""
        width = self._log_rect().width - 8 * 2  # both-side padding
        return chatlog.visual_lines(self.event_log, width, self.font_sm)

    def _log_channel(self) -> str | None:
        """B16.1/B100: the active tab's channel filter (None = the ALL tab)."""
        if self.log_tab == "combat":
            return chatlog.CHANNEL_COMBAT
        if self.log_tab == "loot":
            return chatlog.CHANNEL_LOOT
        return None

    def _set_log_tab(self, tab: str) -> None:
        self.log_tab = tab
        self.log_scroll = 0   # a new filter = a new bottom; snap to newest

    def _draw_log(self) -> None:
        """The single on-screen chatbox (shared with battle): semi-transparent
        panel, bottom-left, showing the visible lines ending at the scroll
        position. B16.1/B82: the [All][Combat] tab chips live INSIDE the panel
        as a header strip — the vitals above are never occluded (one visible
        row is spent on the strip instead)."""
        rect = self._log_rect()
        chip_h = self.font_sm.get_height() + 6
        text_rect = pygame.Rect(rect.x, rect.y + chip_h, rect.width, rect.height - chip_h)
        self.log_scroll = chatlog.draw(
            self.screen, text_rect, self.event_log, self.font_sm,
            visible=max(1, self._log_visible_now() - 1), scroll=self.log_scroll,
            interactive=self._log_interactive(), edge=PANEL_EDGE, accent=ACCENT,
            channel=self._log_channel())
        strip = pygame.Surface((rect.width, chip_h), pygame.SRCALPHA)
        strip.fill((10, 12, 18, 200))
        self.screen.blit(strip, (rect.x, rect.y))
        chip_x = rect.x
        for tab_id, tab_label in (("all", "All"), ("combat", "Combat"), ("loot", "Loot")):
            width = self.font_sm.size(tab_label)[0] + 16
            chip = pygame.Rect(chip_x, rect.y, width, chip_h)
            active = self.log_tab == tab_id
            pygame.draw.rect(self.screen, (36, 42, 58) if active else (22, 26, 36),
                             chip, border_top_left_radius=4, border_top_right_radius=4)
            pygame.draw.rect(self.screen, PANEL_EDGE, chip, width=1,
                             border_top_left_radius=4, border_top_right_radius=4)
            self.screen.blit(self.font_sm.render(
                tab_label, True, TEXT if active else TEXT_DIM), (chip.x + 8, chip.y + 3))
            if self._log_interactive():   # read-only under menus/overlays (like scroll)
                self._add_button(chip, "", (lambda t=tab_id: self._set_log_tab(t)), True)
            chip_x += width + 3

    # -- main loop ----------------------------------------------------------

    def run(self) -> str:
        while self.running:
            self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)
            # B71: accumulate play time (whole seconds land on the player).
            self._playtime_accum += self.clock.get_time() / 1000.0
            if self._playtime_accum >= 1.0:
                whole = int(self._playtime_accum)
                self.engine.player.playtime_seconds += whole
                self._playtime_accum -= whole
        if self.exit_reason == "exit":
            pygame.quit()
        return self.exit_reason or "menu"


def _first_free_slot() -> str:
    """B71: a fresh game claims the first empty manual slot (slot 1 when full)."""
    for path in saveslots.SLOT_PATHS:
        if not os.path.exists(path):
            return path
    return saveslots.SLOT_PATHS[0]






def start_menu_slot_options() -> list[tuple[str, str]]:
    """B71: the live menu — New game + one Load row per existing slot/autosave.
    (The legacy start_menu_options stays for explicit-path callers/tests.)"""
    saveslots.migrate_legacy(SAVE_PATH)          # old root savegame.json -> slot 1
    options = [("new", T.START_NEW_GAME)]
    for i, summary in enumerate(saveslots.all_summaries()):
        if summary is None:
            continue
        options.append((f"load:{summary.path}",
                        f"Slot {i + 1} — {summary.name} · {summary.player_class} · "
                        f"Lv {summary.level} · {summary.playtime_label()}"))
    auto = saveslots.slot_summary(saveslots.AUTOSAVE_PATH)
    if auto is not None:
        options.append((f"load:{auto.path}",
                        f"Autosave — {auto.name} · Lv {auto.level} · {auto.playtime_label()}"))
    options.append(("settings", "Settings"))     # B70
    options.append(("quit", T.START_QUIT))
    return options


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
        # B40 S5: creation returns (name, class, starter_talent). Older/two-value
        # creation fns (tests, scripted starts) still work — starter is optional
        # and an empty pick falls back to the class default inside core.
        name, class_id, *starter = creation_fn(engine)
        engine.start_new_game(name, class_id,
                              starter_talent_id=starter[0] if starter else "")
        return engine
    if choice == "load":
        result = engine.load(save_path)
        if not result.success:
            raise ValueError(result.message)
        return engine
    if choice.startswith("load:"):               # B71: a specific slot/autosave
        path = choice.split(":", 1)[1]
        result = engine.load(path)
        if not result.success:
            raise ValueError(result.message)
        # An autosave load keeps saving to slot 1 semantics via _first_free_slot;
        # a slot load keeps saving to ITS slot.
        if path in saveslots.SLOT_PATHS:
            engine._save_slot_path = path
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

    focus_idx = 0   # B99 S2: keyboard focus over the start-menu rows
    while True:
        if screen.get_size() != display.get_size():
            screen = pygame.Surface(display.get_size())  # follow resize / fullscreen
        options = start_menu_slot_options()
        buttons, title_pos, msg_pos = start_menu_layout(display.get_size(), options)
        focus_idx = max(0, min(focus_idx, len(buttons) - 1))

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
                if event.key in (pygame.K_DOWN, pygame.K_TAB):
                    focus_idx = min(focus_idx + 1, len(buttons) - 1)
                    continue
                if event.key == pygame.K_UP:
                    focus_idx = max(focus_idx - 1, 0)
                    continue
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and buttons:
                    return buttons[focus_idx].on_click
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
        for i, button in enumerate(buttons):
            focused = i == focus_idx
            color = BTN_HOVER if (button.rect.collidepoint(mouse) or focused) else BTN
            pygame.draw.rect(screen, color, button.rect, border_radius=8)
            pygame.draw.rect(screen, ACCENT if focused else BTN_EDGE, button.rect,
                             width=2 if focused else 1, border_radius=8)
            label = font.render(button.label, True, TEXT)
            screen.blit(label, label.get_rect(center=button.rect.center))

        offset = present(display, screen, BG)
        clock.tick(FPS)


def settings_menu() -> None:
    """B70: the start-menu settings screen — rows cycle their value on click and
    persist immediately (fullscreen takes effect when the game starts; in-game
    the same settings live in the Esc menu and apply on the spot)."""
    values = user_settings.load()
    display = acquire_display((WIDTH, HEIGHT))
    screen = pygame.Surface(display.get_size())
    offset = (0, 0, 1.0)
    font = pygame.font.SysFont("menlo,consolas,monospace", 20)
    font_lg = pygame.font.SysFont("menlo,consolas,monospace", 34, bold=True)
    clock = pygame.time.Clock()
    options_by_key = {option["key"]: option for option in user_settings.OPTIONS}

    def _activate(key: str, direction: int = 1) -> bool:
        """Cycle/adjust a row; True means 'leave the screen' (back)."""
        if key == "back":
            return True
        option = options_by_key[key]
        if option["kind"] == "slider" and direction < 0:
            # B99 S2: left on the slider steps down 5 points (click/enter cycle
            # only steps up); shares the persisted value with the in-game rows.
            try:
                current = float(values.get(option["key"], 1.0))
            except (TypeError, ValueError):
                current = 1.0
            values[option["key"]] = max(0.0, round(current * 100 - 5) / 100.0)
        else:
            values[option["key"]] = user_settings.cycle_value(option, values.get(option["key"]))
        user_settings.save(values)
        return False

    focus_idx = 0   # B99 S2: keyboard focus over the settings rows
    while True:
        if screen.get_size() != display.get_size():
            screen = pygame.Surface(display.get_size())
        # B92: rows render from THE shared definition; every kind (toggle,
        # steps, slider) cycles its value on click out here.
        rows = [
            (option["key"], user_settings.option_label(option, values.get(option["key"])))
            for option in user_settings.OPTIONS
        ] + [("back", T.BACK)]
        buttons, title_pos, _ = start_menu_layout(display.get_size(), rows)
        focus_idx = max(0, min(focus_idx, len(buttons) - 1))
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
            if event.type == pygame.VIDEORESIZE:
                display = set_display_mode((event.w, event.h))
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return
                if event.key in (pygame.K_DOWN, pygame.K_TAB):
                    focus_idx = min(focus_idx + 1, len(buttons) - 1)
                elif event.key == pygame.K_UP:
                    focus_idx = max(focus_idx - 1, 0)
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and buttons:
                    if _activate(buttons[focus_idx].on_click):
                        return
                elif event.key in (pygame.K_LEFT, pygame.K_RIGHT) and buttons:
                    key = buttons[focus_idx].on_click
                    if key != "back" and options_by_key[key]["kind"] == "slider":
                        _activate(key, 1 if event.key == pygame.K_RIGHT else -1)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                click = to_canvas(event.pos, offset)
                for button in buttons:
                    if not button.rect.collidepoint(click):
                        continue
                    if _activate(button.on_click):
                        return
        screen.fill(BG)
        title = font_lg.render("Settings", True, ACCENT)
        screen.blit(title, title.get_rect(center=title_pos))
        mouse = to_canvas(pygame.mouse.get_pos(), offset)
        for i, button in enumerate(buttons):
            focused = i == focus_idx
            color = BTN_HOVER if (button.rect.collidepoint(mouse) or focused) else BTN
            pygame.draw.rect(screen, color, button.rect, border_radius=8)
            pygame.draw.rect(screen, ACCENT if focused else BTN_EDGE, button.rect,
                             width=2 if focused else 1, border_radius=8)
            label = font.render(button.label, True, TEXT)
            screen.blit(label, label.get_rect(center=button.rect.center))
        offset = present(display, screen, BG)
        clock.tick(FPS)


def engine_from_start_menu(save_path: str = SAVE_PATH) -> GameEngine | None:
    message = ""
    while True:
        choice = start_menu(save_path, message)
        if choice == "settings":                 # B70: edit prefs, back to the menu
            settings_menu()
            continue
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
