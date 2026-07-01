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
from rpg_game.presentation.talent_text import (
    talent_action_label,
    talent_can_allocate,
    talent_detail,
    talent_rank_label,
    talent_status,
)
from rpg_game.presentation import town_cluster
from rpg_game.presentation import fog

MAPS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "maps")
DEFAULT_MAP = os.path.join(MAPS_DIR, "testmap.tmx")
BUILDINGS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "buildings")
# Town gangways use the SAME cobblestone road tiles as the inter-city paths drawn
# by regenerate_overworld.py — the cainos_grass sheet's cobble half (indices 32-63)
# — so a town's paths read as the same road texture, not a flat grey slab.
GRASS_SHEET = os.path.join(os.path.dirname(__file__), "..", "assets", "tiles", "cainos",
                           "TX Tileset Grass.png")
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
# B-doors: each building's door opens ONE town service. Overlays (character /
# inventory / skills / system) are global hotkeys, not place services, so they map
# to no building. A door whose service is unavailable here (no store / no
# tournaments) reads as locked. PROPOSED mapping — flagged for Lucas:
#   - three trade buildings share the single town store (redundant by design)
#   - church = "set respawn point" (the relocate_respawn service)
BUILDING_FUNCTION = {
    "inn": "rest",
    "cottage": "rest",          # B8 Slice 2a: the village bed
    "shop": "store",
    "blacksmith": "store",
    "barracks": "store",
    "church": "relocate_respawn",
    "town_hall": "tournaments",
}
# Each trade building opens its own slice of the town store (a category filter on
# the shared inventory, see store.STORE_CATEGORIES). Applies to every hub that has
# these building types, so the split generalises to future cities for free.
STORE_CATEGORY = {
    "blacksmith": "weapons",
    "barracks": "armor",
    "shop": "general",
}
# B30: a door opens a TITLED menu (the building's name) — no service runs until the
# player picks. These are the menu titles; the choice label/action is derived from
# BUILDING_FUNCTION (rest/store/relocate_respawn/tournaments).
BUILDING_TITLES = {
    "inn": "Inn",
    "cottage": "Cottage",
    "shop": "General Store",
    "blacksmith": "Blacksmith",
    "barracks": "Barracks",
    "church": "Church",
    "town_hall": "Town Hall",
    "tower": "Mage Tower",
}
# Building sprites are NATIVE-sized (vary per type); scale them at load time so the
# whole town shrinks together. Tunable — bump to enlarge every building uniformly.
BUILDING_SCALE = 0.55
# Per-building scale overrides. The mage tower's native art is huge (505x1049 vs
# ~120-240px for the rest), so it gets its own scale to loom as a landmark without
# swallowing the screen. Bottom-anchored draw is unchanged, so it still rises from
# its door at the base. Others fall back to BUILDING_SCALE.
BUILDING_SCALE_OVERRIDE = {"tower": 0.30}
# cainos's 4x4 autotile blob (cols 0-3, rows 0-3): tile index by which side grass
# borders the cobble cell. Corridors (grass on opposite sides) fall back to centre.
# cainos_grass shares cainos_stone's layout but puts the cobble-on-grass blob in the
# sheet's bottom (cobble) half, so the same blob indices shifted by +32 give the
# road cobble used between towns. COBBLE_BLOB is the grass-sheet (road) version.
_AUTOTILE_BLOB = {"center": 9, "N": 1, "S": 25, "W": 8, "E": 11,
                  "NW": 0, "NE": 3, "SW": 24, "SE": 27}
COBBLE_BLOB = {name: idx + 32 for name, idx in _AUTOTILE_BLOB.items()}
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
COLLISION_LAYER = "walls"
WATER_TILESET = "water_autotile"
# A water autotile cell blocks only if >= this fraction of it is water. Measured
# fractions: outer corner ~0.22, edge ~0.58, channel ~0.76, inner corner ~0.89,
# full 1.0 -> 0.6 makes shore (edge + outer) walkable while deep water still blocks.
WATER_BLOCK_THRESHOLD = 0.6
# Player-centered zoom: the world view is scaled so ~this many tiles are visible
# across the window (Platinum-style). Integer zoom only -> crisp pixel art. Integer
# steps mean the actual tiles-in-width jumps in steps (12 here -> ~12-13 wide).
ZOOM_TARGET_TILES_W = 12
# Encounter heatmap (B12): wilderness gets safer near towns and along roads. The
# per-step rate is the zone base scaled by distance to the nearest town — zero on
# a town and its immediate ring, ramping to full a few tiles out — and reduced on
# cobble path tiles (roads are travelled, less ambush). All tunable.
ENCOUNTER_SAFE_RADIUS = 1     # town + adjacent tiles: no encounters
ENCOUNTER_RAMP_TILES = 3      # tiles over which the rate ramps from 0 to full
ENCOUNTER_PATH_FACTOR = 0.6   # -40% on a road/path tile
# B32: a hub is a whole CLUSTER, not one tile. Encounters are zero on every cluster
# tile (footprints, plaza, doors, cobble) plus this many tiles of margin around it,
# so you can never be ambushed on a town's own streets or its doorstep.
SAFE_TILE_MARGIN = 2

# Action log / chatbox (B16 + B29): the bottom-left panel is the SINGLE place all
# on-screen text goes (no floating toasts). It keeps deep scrollback, shows a
# resizable number of lines (player grows/shrinks it, clamped), and can be scrolled
# up to read older lines.
LOG_HISTORY_MAX = 200       # how many lines are retained for scrollback
LOG_VISIBLE_DEFAULT = 10    # visible lines by default (bigger than the old 7)
LOG_VISIBLE_MIN = 5
LOG_VISIBLE_MAX = 18
LOG_SCROLL_STEP = 2         # lines per mouse-wheel notch

# Location indicator (top-right): within this many tiles of a hub's plaza the label
# reads relative ("south of Hordanita") instead of the generic wilds text.
NEAR_RADIUS = 8

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
HP_COL = (96, 200, 120)   # vitals bars (B31), matching the battle HUD
MANA_COL = (90, 140, 230)
BAR_TRACK = (24, 26, 34)
PLAYER_COLOR = (235, 200, 90)
PLAYER_EDGE = (40, 36, 16)
TOWN_COLOR = (90, 150, 230)
TOWN_HUB = (120, 220, 140)

# B11 fullscreen map: unrevealed fog + per-terrain-family land colours (from the
# ground tileset name) so zones + the southern heath read as landmarks; water is
# detected from the walls water_autotile tileset.
MAP_FOG = (22, 22, 30)
MAP_BG = (10, 12, 18)
MAP_WATER = (58, 92, 150)
MAP_LAND_DEFAULT = (74, 96, 72)
MAP_FAMILY_COLORS = {
    "cainos": (96, 132, 78),        # core green
    "mork_skog": (52, 80, 58),      # dark forest
    "cursed_mire": (104, 110, 66),  # sickly fen
    "grave_heath": (104, 96, 118),  # heath (south)
    "frostfell": (176, 196, 214),   # pale ice
    "ash_waste": (120, 116, 112),   # grey ash
    "karr": (150, 132, 96),         # tan
}
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
        return blocked

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
class Button:
    rect: pygame.Rect
    label: str
    on_click: object
    enabled: bool = True
    # Visually sperred but still clickable: a level-locked item reads as restricted
    # yet a click still fires (so the player gets a "needs level N" explanation).
    restricted: bool = False


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
        # B8 Slice 1: the start town renders as a building cluster. The cluster is
        # anchored to its tile (template offsets), its footprints become solid
        # collision, and the anchor tile stays the walkable plaza/menu trigger.
        self._cobble_tiles = self._load_cobble_tiles()
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
        # Sub-pixel movement remainder (float) per axis; the int part moves the rect
        # each frame, the fraction carries over -> a non-integer PLAYER_SPEED. Zeroed
        # on any teleport so no drift accumulates across a reposition.
        self._move_accum_x = 0.0
        self._move_accum_y = 0.0
        self.font = pygame.font.SysFont("menlo,consolas,monospace", 16)
        self.font_sm = pygame.font.SysFont("menlo,consolas,monospace", 13)
        self.font_lg = pygame.font.SysFont("menlo,consolas,monospace", 22, bold=True)
        self.font_italic = pygame.font.SysFont("menlo,consolas,monospace", 13, italic=True)
        self.mode = "walk"  # walk | store | tournaments | tournament_confirm | tournament_intermission
        self.overlay = ""  # character | inventory | skills_talents | system
        self.inventory_category = "consumables"  # selected category in the inventory overlay
        self.overlay_return_mode = ""
        self.selected_equipment_slot = "weapon"
        self.selected_talent_id = ""
        self.selected_tournament_id = ""
        self.tournament_run: TournamentRun | None = None
        self.store_category: str | None = None  # which trade building's store slice is open
        self.building_menu: tuple[str, str] | None = None  # (place_id, building_id) of the open door menu
        self.upgrade_building: str | None = None     # B37 Slice 2: open station building id
        self.selected_upgrade_item: str | None = None  # item being inspected at the station
        self._pending_tags: list = []                # queued 'Upgradable' row tags
        # B11 fullscreen map caches: terrain texture (built once) + fog composite
        # (rebuilt only when the revealed-tile count changes).
        self._map_terrain = None
        self._map_composite = None
        self._map_composite_count = -1
        self.buttons: list[Button] = []
        # B16 + B29: the chatbox is the ONLY on-screen text. Combat lines flow in via
        # the shared deque passed to BattleApp; world events flow in through set_toast
        # -> push_log. Deep scrollback (LOG_HISTORY_MAX), a player-resizable visible
        # height (log_visible), and a scroll offset for reading older lines.
        self.event_log: "collections.deque" = collections.deque(maxlen=LOG_HISTORY_MAX)
        self.log_visible = LOG_VISIBLE_DEFAULT
        self.log_scroll = 0      # lines scrolled up from the bottom (0 = newest visible)
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

    def set_toast(self, message: str, color=TEXT, log: bool = True) -> None:
        # B29: no floating toasts — every on-screen message goes to the chatbox log.
        # log=False keeps the B29.3 contract: a message the battle shell already
        # logged into the shared event_log is dropped here so it appears only once.
        if log:
            self.push_log(message, color)

    def push_log(self, message: str, color=TEXT) -> None:
        """Append a line to the chatbox log (deduping immediate repeats). Stays
        pinned to the newest line unless the player has scrolled up to read history."""
        if self.event_log and self.event_log[-1][0] == message:
            return
        self.event_log.append((message, color))
        if self.log_scroll:        # reading history: hold position relative to newest
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
        if self.engine.rng.random() < self.encounter_rate_at(self.world.current_tile):
            return self.engine.create_encounter()
        return None

    def _nearest_town_dist(self, tile) -> int:
        tx, ty = tile
        return min((max(abs(tx - x), abs(ty - y)) for (x, y) in self.world.town_tiles),
                   default=99)

    def _on_path(self, tile) -> bool:
        x, y = tile
        try:
            ground = self.world.tmx.get_layer_by_name("ground")
        except (ValueError, KeyError):
            return False
        gid = ground.data[y][x]
        return any(fg <= gid < fg + 64 and (gid - fg) >= 32 for fg in (3, 387))

    def encounter_rate_at(self, tile) -> float:
        """Per-step encounter chance at a tile: 0 anywhere on a town cluster + its
        margin (B32) or next to any town anchor, ramping to the zone base a few
        tiles out, reduced on roads. (B12 heatmap.)"""
        if tile in self._safe_tiles:
            return 0.0
        dist = self._nearest_town_dist(tile)
        if dist <= ENCOUNTER_SAFE_RADIUS:
            return 0.0
        ramp = min(1.0, (dist - ENCOUNTER_SAFE_RADIUS) / ENCOUNTER_RAMP_TILES)
        rate = self.encounter_rate * ramp
        if self._on_path(tile):
            rate *= ENCOUNTER_PATH_FACTOR
        return rate

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
        if outcome == "defeat":
            # Engine already respawned the player; move the sprite to match.
            respawn_place = self.engine.player.current_place_id
            tile = self.town_tile_by_place.get(respawn_place)
            if tile is not None:
                self.world.set_tile(*tile)
            self._move_accum_x = self._move_accum_y = 0.0  # teleport -> no carried drift
            self.sync_location()
            self.set_toast(T.defeat_respawn(self.engine.current_place().name), BAD)
        else:
            # Victory or flee: stay where we are; location is still the wilds. The
            # battle shell already logged the outcome into the shared event_log, so
            # these are toast-only (log=False) to avoid a duplicate log line.
            self.sync_location()
            if outcome == "fled":
                self.set_toast(T.fled_from(enemy.name), WARN, log=False)
            else:
                self.set_toast(T.victory_over(enemy.name), GOOD, log=False)
        self._last_tile = self.world.current_tile

    # -- town actions (all go through the engine) ---------------------------

    def _interact_door(self, place_id: str, building_id: str) -> None:
        """B30: open a TITLED menu for a hub building's door — NO service runs until
        the player picks. Sync the engine to the hub first (a door tile is not the
        place tile). A building whose service isn't offered here (unmapped, no store,
        no tournaments) logs as locked instead of opening a menu."""
        self.engine.enter_place(place_id)
        func = BUILDING_FUNCTION.get(building_id)
        if func == "store" and not self.engine.current_place().has_store:
            func = None
        elif func == "tournaments" and not self.engine.available_tournaments():
            func = None
        # A door opens a menu if it offers a service OR an upgrade station (the mage
        # tower has no store/rest service — only armour upgrades).
        is_station = self.engine.station_category(building_id) is not None
        if func is None and not is_station:
            self.push_log(T.BUILDING_LOCKED, TEXT_DIM)
            return
        self.building_menu = (place_id, building_id)
        self.mode = "building"

    def _choose_building_action(self, func: str, category: str | None = None) -> None:
        """Run the chosen building service. Closes the menu first; store/tournaments
        re-open their own screen, rest/respawn just log their result."""
        self.store_category = category
        self.building_menu = None
        self.mode = "walk"
        self.do_action(func)

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
            "consumables": sum(c for i, c in bag.items() if c > 0 and items[i].kind == "consumable"),
            "miscellaneous": sum(c for i, c in bag.items() if c > 0 and items[i].kind != "consumable"),
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
        miscellaneous is inert."""
        snap = build_snapshot(self.engine)
        items = self.engine.content.items
        bag = self.engine.player.inventory.consumables
        rows = []
        if category in ("consumables", "miscellaneous"):
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
        lines = [
            detail.name,
            detail.status,
            f"Rank: {detail.rank}/{detail.max_rank}",
            f"Effect: {detail.effect}",
        ]
        if detail.next_rank not in ("at max rank", ""):
            lines.append(f"Next: {detail.next_rank}")
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
                if self._log_interactive():   # scroll only in walk; read-only under menus
                    self.scroll_log(event.y * LOG_SCROLL_STEP)   # wheel up = older lines
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
            elif self.mode == "building":
                self._close_building_menu()
            elif self.mode == "upgrade_station":
                self._close_upgrade_station()
            elif self.mode == "store":
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

    def update(self) -> None:
        if self.overlay or self.mode != "walk":
            return
        keys = pygame.key.get_pressed()
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        if dx or dy:
            # Accumulate sub-pixel movement; move the integer part, carry the rest.
            # int() truncates toward zero so the fraction keeps its sign both ways.
            self._move_accum_x += dx * PLAYER_SPEED
            self._move_accum_y += dy * PLAYER_SPEED
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
        if self.mode == "walk" and not self.overlay:
            self._draw_vitals()
        if self.mode == "building":
            self._draw_building_menu()
        elif self.mode == "upgrade_station":
            self._draw_upgrade_station()
        elif self.mode == "store":
            self._draw_store_screen()
        elif self.mode == "tournaments":
            self._draw_tournament_list_screen()
        elif self.mode == "tournament_confirm":
            self._draw_tournament_confirm_screen()
        elif self.mode == "tournament_intermission":
            self._draw_tournament_intermission_screen()
        if self.overlay == "map":
            self._draw_map_overlay()      # fullscreen, not the standard panel
        elif self.overlay:
            self._draw_overlay_screen()
        # Chatbox LAST so it stays visible (read-only) over overlays and menus, not
        # only in walk — the player always sees why an action was blocked.
        self._draw_log()
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

    # -- B11 fullscreen map + fog of war ------------------------------------

    def _map_family(self, tileset_name: str | None) -> str | None:
        if not tileset_name:
            return None
        for family in MAP_FAMILY_COLORS:
            if tileset_name.startswith(family):
                return family
        return None

    def _build_map_terrain(self) -> "pygame.Surface":
        """A 1px-per-tile terrain texture, coloured by ground family (zones + the
        heath) with water from the walls water_autotile tileset. Built once."""
        tmx = self.world.tmx
        surf = pygame.Surface((tmx.width, tmx.height))
        surf.fill(MAP_LAND_DEFAULT)
        ground = next((l for l in tmx.layers if getattr(l, "name", None) == "ground"), None)
        walls = next((l for l in tmx.layers if getattr(l, "name", None) == "walls"), None)
        get_ts = tmx.get_tileset_from_gid
        land_of: dict[int, tuple] = {0: MAP_LAND_DEFAULT}   # memoize gid -> colour
        water_of: dict[int, bool] = {0: False}
        for y in range(tmx.height):
            grow = ground.data[y] if ground else None
            wrow = walls.data[y] if walls else None
            for x in range(tmx.width):
                color = MAP_LAND_DEFAULT
                if grow is not None:
                    gid = grow[x]
                    if gid not in land_of:
                        ts = get_ts(gid)
                        fam = self._map_family(ts.name if ts else None)
                        land_of[gid] = MAP_FAMILY_COLORS.get(fam, MAP_LAND_DEFAULT)
                    color = land_of[gid]
                if wrow is not None:
                    wg = wrow[x]
                    if wg not in water_of:
                        ts = get_ts(wg)
                        water_of[wg] = bool(ts and ts.name == "water_autotile")
                    if water_of[wg]:
                        color = MAP_WATER
                surf.set_at((x, y), color)
        return surf

    def _map_composite_surface(self) -> "pygame.Surface":
        """Terrain with unrevealed tiles painted as fog. Cached; rebuilt only when
        the revealed count changes (movement is blocked while the map is open, so
        this is at most once per open)."""
        bits = self.engine.player.revealed_tiles
        count = fog.count_revealed(bits)
        if self._map_terrain is None:
            self._map_terrain = self._build_map_terrain()
        if self._map_composite is None or self._map_composite_count != count:
            tmx = self.world.tmx
            comp = self._map_terrain.copy()
            for y in range(tmx.height):
                for x in range(tmx.width):
                    if not fog.is_revealed(bits, tmx.width, x, y):
                        comp.set_at((x, y), MAP_FOG)
            self._map_composite = comp
            self._map_composite_count = count
        return self._map_composite

    def _map_screen_rect(self) -> "pygame.Rect":
        w, h = self.screen.get_size()
        tmx = self.world.tmx
        margin = 64
        scale = min((w - 2 * margin) / tmx.width, (h - 2 * margin) / tmx.height)
        mw, mh = int(tmx.width * scale), int(tmx.height * scale)
        return pygame.Rect((w - mw) // 2, (h - mh) // 2, mw, mh)

    def _draw_map_overlay(self) -> None:
        """B11: the fullscreen orientation map. Fog-masked terrain + discovered
        town/gate/mage-tower pins + a 'you are here' marker. NO fast-travel — the
        only interaction is closing it (M/Esc)."""
        self.screen.fill(MAP_BG)
        tmx = self.world.tmx
        W, H = tmx.width, tmx.height
        comp = self._map_composite_surface()
        rect = self._map_screen_rect()
        self.screen.blit(pygame.transform.scale(comp, (rect.width, rect.height)), rect.topleft)
        pygame.draw.rect(self.screen, PANEL_EDGE, rect, width=2)
        sx, sy = rect.width / W, rect.height / H
        bits = self.engine.player.revealed_tiles

        def to_screen(tx, ty):
            return (int(rect.x + (tx + 0.5) * sx), int(rect.y + (ty + 0.5) * sy))

        # discovered gates
        for (gx, gy) in self.world.gate_messages:
            if fog.is_revealed(bits, W, gx, gy):
                px, py = to_screen(gx, gy)
                pygame.draw.rect(self.screen, WARN, (px - 3, py - 3, 6, 6))
                pygame.draw.rect(self.screen, MAP_BG, (px - 3, py - 3, 6, 6), 1)

        # discovered towns (mage-tower towns get an accent diamond + label tag)
        meta = self.zone.town_meta or {}
        for (tx, ty), pid in self.zone.towns.items():
            if not fog.is_revealed(bits, W, tx, ty):
                continue
            px, py = to_screen(tx, ty)
            is_tower = (meta.get(pid) or {}).get("prop") == "tower"
            if is_tower:
                pygame.draw.polygon(self.screen, ACCENT,
                                    [(px, py - 5), (px + 5, py), (px, py + 5), (px - 5, py)])
                pygame.draw.polygon(self.screen, MAP_BG,
                                    [(px, py - 5), (px + 5, py), (px, py + 5), (px - 5, py)], 1)
            else:
                color = TOWN_HUB if pid == self.zone.respawn_place_id else TOWN_COLOR
                pygame.draw.circle(self.screen, color, (px, py), 4)
                pygame.draw.circle(self.screen, MAP_BG, (px, py), 4, 1)
            label = self.zone.town_labels.get((tx, ty), pid)
            if is_tower:
                label += " (Mage Tower)"
            self.screen.blit(self.font_sm.render(label, True, TEXT), (px + 7, py - 7))

        # "you are here"
        ppx, ppy = to_screen(*self.world.current_tile)
        pygame.draw.circle(self.screen, GOOD, (ppx, ppy), 5)
        pygame.draw.circle(self.screen, MAP_BG, (ppx, ppy), 5, 2)

        self.screen.blit(self.font_lg.render("World Map", True, ACCENT), (rect.x, rect.y - 42))
        self.screen.blit(self.font_sm.render(
            "M / Esc: close   ·   fog lifts as you explore   ·   orientation only",
            True, TEXT_DIM), (rect.x, rect.bottom + 10))

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

    def _load_building_sprites(self) -> dict:
        """Load every (building, facing) view that appears across the resolved
        templates, scaled once by BUILDING_SCALE. Keyed by (bid, facing): a building
        can face differently per tier (inn is q1 in a capital, front in a town)."""
        sprites = {}
        pairs = {(b[0], b[5]) for tmpl in self.cluster_templates.values() for b in tmpl}
        for bid, facing in pairs:
            path = os.path.join(BUILDINGS_DIR, f"{bid}_{facing}.png")
            try:
                raw = pygame.image.load(path).convert_alpha()
                w, h = raw.get_size()
                scale = BUILDING_SCALE_OVERRIDE.get(bid, BUILDING_SCALE)
                sprites[(bid, facing)] = pygame.transform.smoothscale(
                    raw, (max(1, round(w * scale)), max(1, round(h * scale))))
            except (pygame.error, FileNotFoundError):
                sprites[(bid, facing)] = None  # missing art -> cobble still renders, no crash
        return sprites

    def _water_tiles(self) -> set:
        """All water-autotile cells (blocked deep water AND walkable shore), so the
        cobble net can route clear of every one of them."""
        tmx = self.world.tmx
        try:
            walls = tmx.get_layer_by_name(COLLISION_LAYER)
        except (ValueError, KeyError):
            return set()
        cells = set()
        for x, y, _img in walls.tiles():
            gid = walls.data[y][x]
            ts = tmx.get_tileset_from_gid(gid) if gid else None
            if ts is not None and ts.name == WATER_TILESET:
                cells.add((x, y))
        return cells

    def _load_cobble_tiles(self) -> dict:
        """Slice the cainos_grass cobble autotile blob (the road cobble) into 32px
        tiles by name, so town gangways use the same cobblestone as the roads."""
        tiles = {}
        try:
            sheet = pygame.image.load(GRASS_SHEET).convert_alpha()
        except (pygame.error, FileNotFoundError):
            return tiles
        cols = sheet.get_width() // 32
        for name, idx in COBBLE_BLOB.items():
            tiles[name] = sheet.subsurface(((idx % cols) * 32, (idx // cols) * 32, 32, 32))
        return tiles

    def _cobble_tile_for(self, x: int, y: int) -> "pygame.Surface":
        """Marching-tile pick: which framed cobble tile a net cell uses, from which
        orthogonal neighbours are also cobble (grass borders get an edge/corner)."""
        net = self._cobble_net
        top, bot = (x, y - 1) not in net, (x, y + 1) not in net
        left, right = (x - 1, y) not in net, (x + 1, y) not in net
        if (top and bot) or (left and right):
            key = "center"                       # corridor -> flat fill
        elif top and left:
            key = "NW"
        elif top and right:
            key = "NE"
        elif bot and left:
            key = "SW"
        elif bot and right:
            key = "SE"
        elif top:
            key = "N"
        elif bot:
            key = "S"
        elif left:
            key = "W"
        elif right:
            key = "E"
        else:
            key = "center"
        return self._cobble_tiles.get(key)

    def _draw_town(self, world: "pygame.Surface", ox: int, oy: int,
                   player_rect: "pygame.Rect") -> None:
        """Draw the start-town cobble net (autotiled, on routes only) then the
        buildings and the player in ONE base-y-sorted pass, so the player is hidden
        behind houses to the north and drawn in front of houses to the south."""
        tw, th = self.world.tw, self.world.th
        for (cx, cy) in self._cobble_net:        # cobble under everything
            tile = self._cobble_tile_for(cx, cy)
            if tile is not None:
                world.blit(tile, (cx * tw - ox, cy * th - oy))
        # drawables: (base_y, kind, payload) sorted so nearer (larger y) draw last.
        # Every hub's buildings join ONE y-sorted pass so clusters and the player
        # occlude correctly regardless of which town the player is near.
        drawables = []
        for pid, anchor in self.cluster_anchors.items():
            for bid, fx, fy, fw, fh, facing, flip in town_cluster.cluster_buildings(anchor, self.cluster_templates[pid]):
                sprite = self._building_sprites.get((bid, facing))
                if sprite is None:
                    continue
                if flip:               # mirror so the door/sign faces in toward the courtyard
                    sprite = pygame.transform.flip(sprite, True, False)
                base_y = (fy + fh) * th            # footprint bottom edge (world y)
                cx = fx * tw + (fw * tw) // 2
                sw, sh = sprite.get_size()
                drawables.append((base_y, "b", (sprite, cx - sw // 2 - ox, base_y - sh - oy)))
        drawables.append((player_rect.bottom + oy, "p", player_rect))
        for _base_y, kind, payload in sorted(drawables, key=lambda d: d[0]):
            if kind == "b":
                sprite, sx, sy = payload
                world.blit(sprite, (sx, sy))
            else:
                pygame.draw.rect(world, PLAYER_COLOR, payload, border_radius=4)
                pygame.draw.rect(world, PLAYER_EDGE, payload, width=2, border_radius=4)

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
        # B11: reveal the on-screen tiles into the fog bitset as the player walks.
        fog.reveal_rect(self.engine.player.revealed_tiles, tmx.width, tmx.height,
                        left, right, top, bottom)
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
            label_xy = (self.zone.town_labels.get((tx, ty), place_id),
                        tx * tw - ox + tw // 2, ty * th - oy - 8)
            if place_id in self.cluster_anchors:
                continue   # hub: no floating name (the buildings ARE the marker);
                           # the top-right indicator names the city instead
            rect = pygame.Rect(tx * tw - ox + 4, ty * th - oy + 4, tw - 8, th - 8)
            color = TOWN_HUB if place_id == self.zone.respawn_place_id else TOWN_COLOR
            pygame.draw.rect(world, color, rect, border_radius=4)
            pygame.draw.rect(world, BG, rect, width=2, border_radius=4)
            labels.append(label_xy)
        for (tx, ty), _msg in self.world.gate_messages.items():
            rect = pygame.Rect(tx * tw - ox + 2, ty * th - oy + 2, tw - 4, th - 4)
            pygame.draw.rect(world, GATE_COLOR, rect, border_radius=3)
            for gx in range(rect.left + 5, rect.right, 8):
                pygame.draw.line(world, BG, (gx, rect.top), (gx, rect.bottom), 2)
        # B8: cobble net + buildings + player, base-y-sorted (player hides behind
        # houses north of it, draws in front of houses south of it).
        self._draw_town(world, ox, oy, self.world.player.move(-ox, -oy))
        # Zoom the whole world surface up by an integer factor (crisp), then blit.
        self.screen.blit(pygame.transform.scale(world, (view_w * zoom, view_h * zoom)), (0, 0))
        # Town labels in unscaled screen space at the zoomed positions (readable).
        for text, wx, wy in labels:
            surf = self.font_sm.render(text, True, TEXT)
            self.screen.blit(surf, surf.get_rect(center=(wx * zoom, wy * zoom)))

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

    def _add_button(self, rect, label, cb, enabled=True, restricted=False) -> None:
        self.buttons.append(Button(rect, label, cb, enabled, restricted))

    def _blit_upgradable_tag(self, rect: pygame.Rect, item_id: str) -> None:
        """B37 Slice 2: an italic 'Upgradable'/'Upgraded' tag on a rare+ item row.
        Just the flag — the actual reforge options live at the blacksmith/mage
        tower, not here."""
        if not self.engine.is_upgradable(item_id):
            return
        # Queue it; drawn AFTER the buttons (which paint over their whole rect) so
        # the tag stays visible on top of the row.
        self._pending_tags.append((pygame.Rect(rect), item_id))

    def _draw_buttons(self) -> None:
        mouse = to_canvas(pygame.mouse.get_pos(), self._transform)
        for b in self.buttons:
            dim = (not b.enabled) or b.restricted   # restricted = clickable but sperred-looking
            if dim:
                color = BTN_DISABLED
            elif b.rect.collidepoint(mouse):
                color = BTN_HOVER
            else:
                color = BTN
            pygame.draw.rect(self.screen, color, b.rect, border_radius=6)
            pygame.draw.rect(self.screen, BTN_EDGE, b.rect, width=1, border_radius=6)
            fitted = self._fit_text(b.label, b.rect.width - 24, self.font)
            label = self.font.render(fitted, True, TEXT_DIM if dim else TEXT)
            self.screen.blit(label, label.get_rect(midleft=(b.rect.x + 12, b.rect.centery)))
        # B37 Slice 2: 'Upgradable'/'Upgraded' italic tags ride on top of the rows,
        # on a small chip so they stay legible over the label tail.
        for rect, item_id in self._pending_tags:
            tag = "Upgraded" if self.engine.is_item_upgraded(item_id) else "Upgradable"
            surf = self.font_italic.render(tag, True, ACCENT)
            chip = pygame.Rect(0, 0, surf.get_width() + 10, surf.get_height() + 4)
            chip.midright = (rect.right - 6, rect.centery)
            pygame.draw.rect(self.screen, BTN, chip, border_radius=4)
            pygame.draw.rect(self.screen, PANEL_EDGE, chip, width=1, border_radius=4)
            self.screen.blit(surf, surf.get_rect(center=chip.center))
        self._pending_tags = []

    def _close_building_menu(self) -> None:
        self.building_menu = None
        self.mode = "walk"

    def _draw_building_menu(self) -> None:
        """B30: a titled menu (the building's name) with the service as a choice.
        Mirrors the tournament screen (title panel + choice buttons + Back)."""
        place_id, building_id = self.building_menu
        title = BUILDING_TITLES.get(building_id, building_id.replace("_", " ").title())
        panel = self._overlay_panel(title)
        func = BUILDING_FUNCTION.get(building_id)
        category = STORE_CATEGORY.get(building_id)
        info = None
        if func == "rest":
            cost = progression.rest_cost(self.zone.zone_for_tile(self.world.current_tile))
            label = f"Rest ({cost} gold)" if cost else "Rest (free)"
        elif func == "store":
            label = {"weapons": "Browse weapons", "armor": "Browse armour"}.get(category, "Browse goods")
        elif func == "relocate_respawn":
            label = "Set respawn point here"
            current = self.engine.content.places.get(self.engine.player.respawn_place_id)
            info = f"Current respawn: {current.name if current else 'none'}"
        elif func == "tournaments":
            label = "Tournaments"
        else:
            label = None   # station-only building (mage tower): no store/rest service
        y = panel.y + 80
        if info:
            self.screen.blit(self.font_sm.render(info, True, TEXT_DIM), (panel.x + 20, y))
            y += 30
        if func is not None and label is not None:
            self._add_button(pygame.Rect(panel.x + 20, y, panel.width - 40, 44), label,
                             (lambda f=func, c=category: self._choose_building_action(f, c)), True)
            y += 52
        # B37: a station building (blacksmith weapons / mage tower armour) offers an
        # upgrade choice. The blacksmith also has its weapon store above; the mage
        # tower has ONLY this.
        if self.engine.station_category(building_id) is not None:
            station_cat = self.engine.station_category(building_id)
            up_label = "Upgrade weapon" if station_cat == "weapon" else "Upgrade armour"
            self._add_button(pygame.Rect(panel.x + 20, y, panel.width - 40, 44), up_label,
                             (lambda b=building_id: self._open_upgrade_station(b)), True)
        back = pygame.Rect(panel.right - 130, panel.bottom - 54, 110, 40)
        self._add_button(back, T.BACK, self._close_building_menu)
        self._draw_buttons()

    # -- B37 Slice 2: upgrade station ---------------------------------------

    def _open_upgrade_station(self, building_id: str) -> None:
        self.building_menu = None
        self.upgrade_building = building_id
        items = self.engine.station_upgradable_items(building_id)
        self.selected_upgrade_item = items[0] if items else None
        self.mode = "upgrade_station"

    def select_upgrade_item(self, item_id: str) -> None:
        self.selected_upgrade_item = item_id

    def apply_upgrade(self, item_id: str, variant_id: str) -> None:
        result = self.engine.apply_item_upgrade(item_id, variant_id)
        self.push_log(result.message, GOOD if result.success else BAD)

    def _item_display_name(self, item_id: str) -> str:
        if item_id in self.engine.content.weapons:
            return self.engine.content.weapons[item_id].name
        if item_id in self.engine.content.gear_items:
            return self.engine.content.gear_items[item_id].name
        return item_id

    def _upgrade_mod_text(self, mod) -> str:
        if mod.type == "element":
            return f"+{mod.value} {mod.damage_type} damage (on hit)"
        return f"{mod.stat} {mod.value:+}"

    def _draw_upgrade_station(self) -> None:
        building = self.upgrade_building
        category = self.engine.station_category(building)
        title = f"{BUILDING_TITLES.get(building, building.title())} — {'Weapon' if category == 'weapon' else 'Armour'} Upgrades"
        panel = self._overlay_panel(title)
        items = self.engine.station_upgradable_items(building)
        gold = self.engine.player.gold
        self.screen.blit(self.font_sm.render(
            f"Pick an item to reforge (one permanent upgrade each).  Gold {gold}", True, TEXT_DIM),
            (panel.x + 20, panel.y + 56))

        left = pygame.Rect(panel.x + 20, panel.y + 86, 220, panel.bottom - panel.y - 140)
        right = pygame.Rect(left.right + 16, panel.y + 86, panel.right - left.right - 36, left.height)
        if not items:
            self.screen.blit(self.font.render("You own nothing to upgrade here.", True, TEXT_DIM),
                             (left.x, left.y))
        if self.selected_upgrade_item not in items:
            self.selected_upgrade_item = items[0] if items else None
        for i, item_id in enumerate(items):
            rect = pygame.Rect(left.x, left.y + i * 34, left.width, 30)
            marker = "> " if item_id == self.selected_upgrade_item else "  "
            done = " [upgraded]" if self.engine.is_item_upgraded(item_id) else ""
            self._add_button(rect, f"{marker}{self._item_display_name(item_id)}{done}",
                             (lambda iid=item_id: self.select_upgrade_item(iid)), True)

        if self.selected_upgrade_item is not None:
            self._draw_upgrade_variants(right, self.selected_upgrade_item)

        back = pygame.Rect(panel.right - 130, panel.bottom - 54, 110, 40)
        self._add_button(back, T.BACK, self._close_upgrade_station)
        self._draw_buttons()

    def _draw_upgrade_variants(self, rect: pygame.Rect, item_id: str) -> None:
        recipe = self.engine.upgrade_recipe(item_id)
        already = self.engine.is_item_upgraded(item_id)
        name = self._item_display_name(item_id)
        y = rect.y
        self.screen.blit(self.font.render(name, True, TEXT), (rect.x, y)); y += 26
        if already:
            variant = self.engine.upgrade_variant(item_id, self.engine.player.item_upgrades[item_id])
            self.screen.blit(self.font_sm.render(
                f"Already upgraded: {variant.name if variant else '?'} — cannot upgrade again.",
                True, BAD), (rect.x, y))
            return
        if recipe is None:
            self.screen.blit(self.font_sm.render("No reforge known for this item yet.", True, TEXT_DIM), (rect.x, y))
            return
        col_w = (rect.width - 16) // 2
        for v_index, variant in enumerate(recipe.variants):
            vx = rect.x + v_index * (col_w + 16)
            vy = y
            self.screen.blit(self.font.render(self._fit_text(variant.name, col_w, self.font), True, ACCENT), (vx, vy))
            vy += 22
            for mod in variant.mods:
                self.screen.blit(self.font_sm.render(self._fit_text(self._upgrade_mod_text(mod), col_w, self.font_sm), True, TEXT), (vx, vy))
                vy += 18
            vy += 4
            # gold (red if short) + each material with have/need
            gold_ok = self.engine.player.gold >= variant.gold
            self.screen.blit(self.font_sm.render(f"Gold: {variant.gold}", True, TEXT if gold_ok else BAD), (vx, vy)); vy += 18
            short = False
            for material_id, need in variant.materials:
                have = self.engine.player.inventory.count(material_id)
                ok = have >= need
                short = short or not ok
                mat_name = self.engine.content.items[material_id].name if material_id in self.engine.content.items else material_id
                self.screen.blit(self.font_sm.render(self._fit_text(f"{mat_name} {have}/{need}", col_w, self.font_sm),
                                                     True, TEXT if ok else BAD), (vx, vy)); vy += 18
            affordable = gold_ok and not short
            btn = pygame.Rect(vx, rect.bottom - 40, col_w, 32)
            # Clickable-but-restricted when unaffordable: the click logs why.
            self._add_button(btn, "Reforge" if affordable else "Reforge (need more)",
                             (lambda iid=item_id, vid=variant.id: self.apply_upgrade(iid, vid)),
                             enabled=True, restricted=not affordable)

    def _close_upgrade_station(self) -> None:
        self.upgrade_building = None
        self.mode = "walk"

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
        self._add_button(back, T.BACK, lambda: setattr(self, "mode", "walk"))
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
        title = T.STORE_TITLES.get(self.store_category, T.SCREEN_TITLES["store"])
        panel = self._overlay_panel(title)
        self._screen_store(panel)
        back = pygame.Rect(panel.right - 130, panel.bottom - 54, 110, 40)
        self._add_button(back, T.BACK, lambda: setattr(self, "mode", "walk"))
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

    # Short stat names for the compare-vs-equipped delta on equipment options.
    _DELTA_LABELS = {"damage": "dmg", "armor": "armor", "max_hp": "hp",
                     "max_mana": "mana", "speed": "speed", "crit_chance": "crit"}

    def _delta_text(self, candidate: dict, equipped: dict) -> str:
        """Compare-vs-equipped: ' (+3 dmg, -1 armor)' for the net change if this
        item replaced the one in the slot. Empty (' (=)') when nothing changes."""
        parts = []
        for stat in self._DELTA_LABELS:
            diff = candidate.get(stat, 0) - equipped.get(stat, 0)
            if diff:
                parts.append(f"{diff:+} {self._DELTA_LABELS[stat]}")
        return f"  ({', '.join(parts)})" if parts else "  (=)"

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
            # Mana is derived from Wisdom (shown in the header); the stats grid shows
            # Wisdom itself (base -> +gear -> total).
            ("wisdom", "Wisdom", self.engine.player.wisdom),
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
            equipped_bonus = equipped_w.damage_bonus if equipped_w is not None else 0
            max_weapons = max(1, (items_rect.bottom - options_y) // 34)
            for i, w in enumerate(snap.weapons[:max_weapons]):
                rect = pygame.Rect(items_rect.x, options_y + i * 34, items_rect.width, 28)
                if w.equipped:
                    status = " [equipped]"
                elif not w.equippable:
                    status = f"  needs Lv {w.required_level}"
                else:  # compare-vs-equipped: weapons only move the damage stat
                    status = self._delta_text({"damage": w.damage_bonus}, {"damage": equipped_bonus})
                # Status/delta right after the name so it survives width-truncation.
                label = f"{w.name}{status}  +{w.damage_bonus} {w.damage_type}"
                # Always clickable: a level-locked weapon is restricted (dimmed) but a
                # click still explains why it can't be equipped. The equipped one is a
                # no-op ("already equipped").
                self._add_button(rect, label, (lambda wid=w.id: self.equip_weapon(wid)),
                                 enabled=True, restricted=not w.equippable)
                self._blit_upgradable_tag(rect, w.id)
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
        # Stats of the gear currently in this slot, for the compare-vs-equipped delta.
        equipped_gear = next((g for g in snap.gear if g.id == selected_slot.equipped_item_id), None)
        equipped_mods = dict(equipped_gear.stat_modifiers) if equipped_gear is not None else {}
        choices = [
            gear for gear in snap.gear
            if gear.slot_type == selected_slot.slot_type and not gear.equipped_slot_id
        ]
        max_choices = max(1, (items_rect.bottom - start_y) // 34)
        for i, gear in enumerate(choices[:max_choices]):
            rect = pygame.Rect(items_rect.x, start_y + i * 34, items_rect.width, 28)
            mods = ", ".join(f"{stat} {value:+}" for stat, value in gear.stat_modifiers)
            if gear.equippable:
                suffix = self._delta_text(dict(gear.stat_modifiers), equipped_mods)
            else:
                suffix = f"  needs Lv {gear.required_level}"
            # Delta right after the name so it survives width-truncation; raw mods last.
            label = f"{gear.name}{suffix} [{gear.rarity}] {mods}"
            self._add_button(rect, label,
                             (lambda gid=gear.id, sid=selected_slot.id: self.equip_gear_to_slot(gid, sid)),
                             enabled=True, restricted=not gear.equippable)
            self._blit_upgradable_tag(rect, gear.id)

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
                self._blit_upgradable_tag(rect, _item_id)

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
            rank = talent_rank_label(eng, node)
            rect = pygame.Rect(middle.x, middle.y + 30 + i * 32, middle.width, 26)
            marker = "> " if selected is not None and node.id == selected.id else "  "
            rank_suffix = f" {rank}" if rank else ""
            label = f"{marker}{status} {node.name}{rank_suffix} ({node.branch} t{node.order})"
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

        can_allocate = talent_can_allocate(self.engine, node)
        verb = talent_action_label(self.engine, node)
        learn_rect = pygame.Rect(rect.x + 10, rect.bottom - 42, rect.width - 20, 32)
        self._add_button(learn_rect, f"{verb} selected (1 point)", self.learn_selected_talent, can_allocate)

    def _screen_store(self, panel) -> None:
        eng = self.engine
        gold = build_snapshot(eng).player.gold
        self.screen.blit(self.font_sm.render(T.store_hint(gold), True, WARN),
                         (panel.x + 20, panel.y + 56))
        col_w = (panel.width - 60) // 2
        # Each row is a price button plus the item's stats (skada/tier/mods/nivå)
        # from StoreEntry/SellEntry.description, wrapped under it. Taller rows ->
        # fewer fit, fine since the differentiated stores carry only one category.
        top = panel.y + 106
        row_h = 56
        max_rows = max(1, (panel.bottom - top - 10) // row_h)
        # The BUY column (left) shares the bottom-left corner with the chatbox; stop
        # its rows above the log rect so no item hides under the chatbox.
        buy_bottom = min(panel.bottom, self._log_rect().top)
        buy_rows = max(1, (buy_bottom - top - 10) // row_h)
        self.screen.blit(self.font.render(T.STORE_BUY, True, TEXT), (panel.x + 20, panel.y + 80))
        for i, entry in enumerate(eng.store_entries(self.store_category)[:buy_rows]):
            y = top + i * row_h
            self._add_button(pygame.Rect(panel.x + 20, y, col_w, 28),
                             f"{entry.name}  {entry.price}g", (lambda iid=entry.id: self.buy(iid)), gold >= entry.price)
            self._blit_item_stats(entry.description, panel.x + 20, y + 30, col_w)
        self.screen.blit(self.font.render(T.STORE_SELL, True, TEXT), (panel.x + 40 + col_w, panel.y + 80))
        for i, entry in enumerate(eng.sellable_entries(self.store_category)[:max_rows]):
            y = top + i * row_h
            self._add_button(pygame.Rect(panel.x + 40 + col_w, y, col_w, 28),
                             f"{entry.name} x{entry.count}  {entry.value}g", (lambda iid=entry.id: self.sell(iid)))
            self._blit_item_stats(entry.description, panel.x + 40 + col_w, y + 30, col_w)

    def _blit_item_stats(self, description: str, x: int, y: int, width: int, max_lines: int = 2) -> None:
        """Render an item's stat line (skada/tier/mods/nivå) under a store row,
        wrapped to the column width. Stats only — no comparison."""
        if not description:
            return
        for line in self._wrapped_lines_pixels(description, width - 8, self.font_sm)[:max_lines]:
            self.screen.blit(self.font_sm.render(line, True, TEXT_DIM), (x + 4, y))
            y += self.font_sm.get_height() + 1

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
        # Both fresh nodes (Learn) and owned-but-not-maxed nodes (Upgrade).
        nodes = eng.available_talents() + eng.upgradable_talents()
        if not nodes:
            self._lines(panel, [T.NO_TALENTS], TEXT_DIM, start=88)
            return
        for i, node in enumerate(nodes[:8]):
            rect = pygame.Rect(panel.x + 20, panel.y + 84 + i * 40, panel.width - 40, 34)
            verb = talent_action_label(eng, node)
            rank = talent_rank_label(eng, node)
            suffix = f" ({rank})" if rank else ""
            self._add_button(rect, f"{verb}: {node.name}{suffix}",
                             (lambda nid=node.id: self.learn_talent(nid)), points > 0)

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
        """B39: the event log flattened into word-wrapped visual lines (no
        truncation). Each entry becomes >=1 line via _wrapped_lines_pixels; the
        bool flags lines from the newest entry so the renderer keeps them bright."""
        width = self._log_rect().width - 8 * 2  # both-side padding
        entries = list(self.event_log)
        out: list[tuple[str, tuple, bool]] = []
        for idx, (text, color) in enumerate(entries):
            newest = idx == len(entries) - 1
            for piece in self._wrapped_lines_pixels(text, width, self.font_sm):
                out.append((piece, color, newest))
        return out

    def _draw_log(self) -> None:
        """B29 chatbox: the single on-screen text surface. Semi-transparent panel,
        bottom-left, showing log_visible VISUAL lines ending at the scroll position;
        long lines word-wrap (never truncated). Oldest fade dimmer; a '... N more'
        hint appears when scrolled up."""
        line_h = self.font_sm.get_height() + 3
        pad = 8
        rect = self._log_rect()
        vis = self._log_visible_now()
        overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
        # More opaque under menus so it stays readable over the overlay dim.
        overlay.fill((10, 12, 18, 180 if self._log_interactive() else 220))
        self.screen.blit(overlay, rect.topleft)
        pygame.draw.rect(self.screen, PANEL_EDGE, rect, width=1, border_radius=4)
        lines = self._visual_log_lines()
        n = len(lines)
        if not lines:        # always show the panel (it's the primary HUD now)
            return
        # Window of visible visual lines, clamped, honoring the scroll offset.
        self.log_scroll = min(self.log_scroll, max(0, n - vis))
        end = n - self.log_scroll
        start = max(0, end - vis)
        for i, (text, color, newest) in enumerate(lines[start:end]):
            shade = color if newest else tuple((c + d) // 2 for c, d in zip(color, TEXT_DIM))
            surf = self.font_sm.render(text, True, shade)
            self.screen.blit(surf, (rect.x + pad, rect.y + pad + i * line_h))
        if self.log_scroll:        # show there is newer text below the view
            hint = self.font_sm.render(f"v {self.log_scroll} more v", True, ACCENT)
            self.screen.blit(hint, hint.get_rect(bottomright=(rect.right - pad, rect.bottom - 2)))

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
