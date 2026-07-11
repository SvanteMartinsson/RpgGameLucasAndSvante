"""B56: the overworld's map/terrain render layer.

Everything that PAINTS the world lives here — the zoomed viewport
(_draw_map + towns/graves/cobble/chests/lairs/bridges), the fullscreen
M-map with fog, and the minimap — plus the visual constants they own
(the shared palette included; the shell re-exports them). Split out of
pygame_overworld as a behaviour-preserving mixin: methods share state
with OverworldApp via self exactly as before.
"""

from __future__ import annotations

import os

import pygame

from rpg_game.presentation import fog
from rpg_game.presentation import town_cluster

BUILDINGS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "buildings")

# Town gangways use the SAME cobblestone road tiles as the inter-city paths drawn
# by regenerate_overworld.py — the cainos_grass sheet's cobble half (indices 32-63)
# — so a town's paths read as the same road texture, not a flat grey slab.
TILES_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "tiles")

GRASS_SHEET = os.path.join(TILES_DIR, "cainos", "TX Tileset Grass.png")

def _grass_sheet_path(theme: str) -> str:
    """The grass sheet whose cobble half a town's gangways use — the SAME sheet the
    inter-city roads use for that zone, so a heath town cobbles over heath grass,
    not cainos green."""
    if theme == "cainos":
        return GRASS_SHEET
    return os.path.join(TILES_DIR, "generated", f"01-TX-Tileset-Grass__{theme}.png")

# Building sprites are NATIVE-sized (vary per type); scale them at load time so the
# whole town shrinks together. Tunable — bump to enlarge every building uniformly.
BUILDING_SCALE = 0.55

# Per-building scale overrides. The mage tower's native art is huge (505x1049 vs
# ~120-240px for the rest), so it gets its own scale to loom as a landmark without
# swallowing the screen. Bottom-anchored draw is unchanged, so it still rises from
# its door at the base. Others fall back to BUILDING_SCALE.
BUILDING_SCALE_OVERRIDE = {"tower": 0.18}

# cainos's 4x4 autotile blob (cols 0-3, rows 0-3): tile index by which side grass
# borders the cobble cell. Corridors (grass on opposite sides) fall back to centre.
# cainos_grass shares cainos_stone's layout but puts the cobble-on-grass blob in the
# sheet's bottom (cobble) half, so the same blob indices shifted by +32 give the
# road cobble used between towns. COBBLE_BLOB is the grass-sheet (road) version.
_AUTOTILE_BLOB = {"center": 9, "N": 1, "S": 25, "W": 8, "E": 11,
                  "NW": 0, "NE": 3, "SW": 24, "SE": 27}

COBBLE_BLOB = {name: idx + 32 for name, idx in _AUTOTILE_BLOB.items()}

COLLISION_LAYER = "walls"

WATER_TILESET = "water_autotile"

# Graves render as FULL multi-tile stones — the sheet tile(s) above the placed
# body (idx-16, the crown/cross/arch) stacked on it — drawn y-sorted so the player
# passes BEHIND the upper tiles, while the collision cell keeps blocking (it stays
# on the walls layer, unchanged). In grave_heath the obstacle ring uses ONLY these
# gravestone bodies, so any grave_heath_props tile on walls is a grave. Indices
# mirror regenerate_overworld.GRAVES.
GRAVE_TILESET = "grave_heath_props"

GRAVE_SHEET_INDICES = (89, 103, 135, 137)

# Tiles tall per stone. Most are 2 (crown idx-16 + body idx); the cross tomb (89)
# is 3 — its base/plinth continues one tile below the body (105). Measured from the
# sheet: 89's bottom edge and 105's top edge are both fully opaque (they join),
# while the other bodies end cleanly (0% bottom edge). The composited sprite's
# BOTTOM tile always sits on the collision cell, so a taller stone just grows up.
GRAVE_TILES_TALL = {89: 3}

# Player-centered zoom: the world view is scaled so ~this many tiles are visible
# across the window (Platinum-style). Integer zoom only -> crisp pixel art. Integer
# steps mean the actual tiles-in-width jumps in steps (12 here -> ~12-13 wide).
ZOOM_TARGET_TILES_W = 12

# Colors (shared palette with the battle shell)
BG = (18, 20, 28)

PANEL_EDGE = (60, 66, 86)

TEXT = (222, 226, 235)

TEXT_DIM = (140, 148, 166)

ACCENT = (120, 170, 255)

GOOD = (120, 220, 140)

WARN = (235, 180, 90)

BAD = (230, 110, 110)

PLAYER_COLOR = (235, 200, 90)

PLAYER_EDGE = (40, 36, 16)

TOWN_COLOR = (90, 150, 230)

TOWN_HUB = (120, 220, 140)

# B11 fullscreen map: unrevealed fog + per-terrain-family land colours (from the
# ground tileset name) so zones + the southern heath read as landmarks; water is
# detected from the walls water_autotile tileset.
MAP_FOG = (22, 22, 30)

# B11 Slice 2: always-on minimap. Shows ~3.5x the walk viewport (ZOOM_TARGET_TILES_W
# wide) around the player, reusing the fog-masked map composite (unexplored stays
# hidden). Top-left corner; toggled with N.
MINIMAP_TILES = (44, 33)      # window in tiles (~3.5x the 12-wide walk view)

MINIMAP_BOX = (176, 132)      # on-screen pixel size (nearest-neighbour scaled)

MINIMAP_MARGIN = 10

MAP_BG = (10, 12, 18)

MAP_WATER = (58, 92, 150)

MAP_LAND_DEFAULT = (74, 96, 72)

# Obstacles show as a dot per tile so a cluster reads as a blob on the map.
# B51: rock/grave props stay grey; bush thickets get their own leafy green so
# foliage reads apart from stone AND from the terrain field (tunable).
MAP_OBSTACLE = (178, 178, 184)   # rock / grave props

MAP_BUSH = (54, 132, 52)         # bush thickets (_plant) — leafy green, not grey

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

# B52: seam bridge decks are authored with vertical planks; rotate them 90° at
# render so the planks run across the walking direction (Lucas's fix).
BRIDGE_TILESETS = {"water_bridge", "bridge_halfdeck"}

# B101: the rotated halfdeck tile carries ONE dark stringer (rail) on its left
# edge — columns 0..3 of the 32px tile. On a multi-column crossing that painted
# a seam line between every column. Variants are derived at render time from
# the deck's neighbourhood (no map-format change): the left edge column keeps
# the rail, mid columns get the rail replaced by plank continuation (column x
# copies column x + RAIL_W), and the right edge column is the tile flipped
# horizontally so its single rail lands on the outer edge.
DECK_RAIL_W = 4   # stringer width in pixels, measured on bridge_halfdeck idx 0

# B63: world chests. Closed/open sprites live at fixed rects in the Cainos props
# sheet (same layout in every generated theme recolour). Chest tiles are SOLID;
# stand next to one and press E/Enter to open it.
PROPS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "props")

CHEST_CLOSED_RECT = (96, 30, 32, 31)
CHEST_SCALE = 0.85   # B81: Lucas playtest — chests were ~15% too large

CHEST_OPEN_RECT = (96, 76, 32, 49)

# B65: boss lairs draw the boss's battle sprite in the world (darkened once
# felled). Same generated-art directory the battle shell reads.
SPRITE_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "sprites", "generated")

# B47 (Lucas-GO on the PoC): zone-seam colour blend. Ground tiles within
# ZONE_BLEND_BAND of a seam get pre-blended images (own tile crossfaded toward
# the neighbour theme's corresponding tile), registered as synthetic gids ONCE
# at load — zero per-frame cost, no PNG retouching, no seeded streams touched.
# 0 turns the whole pass off. A deterministic per-tile jitter of ±1 alpha step
# breaks the column banding the PoC showed.
ZONE_BLEND_BAND = 4
ZONE_BLEND_STEPS = 8

# B83: the player's walk/idle animation (Lucas's hooded sprite, 8 directions).
# Row order in player_walk.png mirrors his review sheet: r0..r7 = N NE E SE S SW W NW;
# player_idle.png is the front/blink cycle. Cadence per his animation test:
# walk ~7.5 fps, idle 4 fps (in 60 fps render frames).
PLAYER_WALK_SHEET = os.path.join(SPRITE_DIR, "player_walk.png")
PLAYER_IDLE_SHEET = os.path.join(SPRITE_DIR, "player_idle.png")
PLAYER_SPRITE_TILES = 1.05     # sprite height in tiles (feet on the tile);
                               # 1.5 × 0.7 — Lucas: 30% mindre, husen såg små ut
WALK_FRAME_TICKS = 8           # 60 / 8  = 7.5 fps
IDLE_FRAME_TICKS = 15          # 60 / 15 = 4 fps
PLAYER_DIRECTIONS = {(0, -1): 0, (1, -1): 1, (1, 0): 2, (1, 1): 3,
                     (0, 1): 4, (-1, 1): 5, (-1, 0): 6, (-1, -1): 7}


def player_facing(dx: float, dy: float, fallback: int = 4) -> int:
    """8-way facing row from a movement vector (0 when standing still)."""
    key = ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))
    return PLAYER_DIRECTIONS.get(key, fallback)

# Theme bands (mirrors core_zone ground_themes; x<83 cainos, 83-158 mork_skog,
# >=159 cursed_mire, y>=100 grave_heath overrides).
def _blend_theme_at(x: int, y: int) -> str:
    if y >= 100:
        return "grave_heath"
    if x >= 159:
        return "cursed_mire"
    if x >= 83:
        return "mork_skog"
    return "cainos"


def _blend_seam_info(x: int, y: int):
    """(distance to nearest seam, theme on the OTHER side) or (None, None)."""
    candidates = []
    if y < 100:
        candidates.append((abs(x - 82.5), "mork_skog" if x <= 82 else "cainos"))
        candidates.append((abs(x - 158.5), "cursed_mire" if x <= 158 else "mork_skog"))
        candidates.append((abs(y - 99.5), "grave_heath"))
    else:
        candidates.append((abs(y - 99.5), _blend_theme_at(x, 99)))
    dist, other = min(candidates, key=lambda c: c[0])
    if dist > ZONE_BLEND_BAND:
        return None, None
    return dist, other


class MapRenderMixin:
    """Map/terrain rendering for OverworldApp (see module docstring)."""

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
        decor = next((l for l in tmx.layers if getattr(l, "name", None) == "decor_over"), None)
        get_ts = tmx.get_tileset_from_gid
        land_of: dict[int, tuple] = {0: MAP_LAND_DEFAULT}   # memoize gid -> colour
        water_of: dict[int, bool] = {0: False}
        obstacle_of: dict[int, bool] = {0: False}           # gid -> rock/grave/bush prop
        for y in range(tmx.height):
            grow = ground.data[y] if ground else None
            wrow = walls.data[y] if walls else None
            drow = decor.data[y] if decor else None
            for x in range(tmx.width):
                color = MAP_LAND_DEFAULT
                if grow is not None:
                    gid = grow[x]
                    if gid not in land_of:
                        ts = get_ts(gid)
                        fam = self._map_family(ts.name if ts else None)
                        land_of[gid] = MAP_FAMILY_COLORS.get(fam, MAP_LAND_DEFAULT)
                    color = land_of[gid]
                is_water = False
                if wrow is not None:
                    wg = wrow[x]
                    if wg not in water_of:
                        ts = get_ts(wg)
                        water_of[wg] = bool(ts and ts.name == "water_autotile")
                    if water_of[wg]:
                        color = MAP_WATER
                        is_water = True
                # Obstacle dots: rock/grave props (walls) + bush thickets (decor_over).
                # Every obstacle tile paints one grey pixel, so a cluster shows as a
                # grey blob on the map. Obstacles never sit on water.
                if not is_water:
                    for row_data in (wrow, drow):
                        if row_data is None:
                            continue
                        og = row_data[x]
                        if og not in obstacle_of:
                            ts = get_ts(og)
                            # B51: 0 none · 1 prop (rock/grave, grey) · 2 plant (bush, green)
                            kind = 0
                            if ts and ts.name.endswith("_plant"):
                                kind = 2
                            elif ts and ts.name.endswith("_props"):
                                kind = 1
                            obstacle_of[og] = kind
                        if obstacle_of[og]:
                            color = MAP_BUSH if obstacle_of[og] == 2 else MAP_OBSTACLE
                            break
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

    def _draw_minimap(self) -> None:
        """B11 Slice 2: a small always-on minimap in the top-left, showing a window
        of ~MINIMAP_TILES around the player. Reuses the fog-masked map composite, so
        unexplored terrain stays hidden (identical fog to the M map). N toggles it."""
        tmx = self.world.tmx
        W, H = tmx.width, tmx.height
        win_w, win_h = min(MINIMAP_TILES[0], W), min(MINIMAP_TILES[1], H)
        comp = self._map_composite_surface()          # 1px/tile, unrevealed = MAP_FOG
        ptx, pty = self.world.current_tile
        left, top = fog.minimap_origin(ptx, pty, W, H, win_w, win_h)
        sub = comp.subsurface(pygame.Rect(left, top, win_w, win_h))
        box_w, box_h = MINIMAP_BOX
        scaled = pygame.transform.scale(sub, (box_w, box_h))
        x0 = y0 = MINIMAP_MARGIN
        panel = pygame.Surface((box_w + 4, box_h + 4), pygame.SRCALPHA)
        panel.fill((10, 12, 18, 185))
        self.screen.blit(panel, (x0 - 2, y0 - 2))
        self.screen.blit(scaled, (x0, y0))
        pygame.draw.rect(self.screen, PANEL_EDGE, (x0 - 2, y0 - 2, box_w + 4, box_h + 4), 1)
        # player marker at its position within the window
        mx = x0 + int((ptx - left + 0.5) * box_w / win_w)
        my = y0 + int((pty - top + 0.5) * box_h / win_h)
        pygame.draw.circle(self.screen, GOOD, (mx, my), 3)
        pygame.draw.circle(self.screen, MAP_BG, (mx, my), 3, 1)

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

    def _grave_sheet(self) -> tuple:
        """(sheet_surface, columns) for the grave props sheet, resolved from the
        tileset's own image source (no hard-coded path). (None, 0) if unavailable."""
        tmx = self.world.tmx
        ts = next((t for t in tmx.tilesets if t.name == GRAVE_TILESET), None)
        if ts is None or not getattr(ts, "source", None):
            return None, 0
        path = os.path.normpath(os.path.join(os.path.dirname(self.world.map_path), ts.source))
        try:
            return pygame.image.load(path).convert_alpha(), int(ts.columns)
        except (pygame.error, FileNotFoundError, TypeError, ValueError):
            return None, 0

    def _load_graves(self) -> tuple:
        """Grave cells (grave_heath_props tiles on the collision layer) + a full
        2-tile stone sprite per placed cell: the sheet tile above the placed bottom
        (idx-cols) stacked on the bottom, so the crown/cross/arch is no longer
        clipped. Drawn y-sorted in _draw_town so the player passes BEHIND the upper
        tile; the bottom cell still blocks (it stays on the walls layer). pytmx
        compacts gids, so each placed bottom is matched to its source stone by pixel
        bytes rather than gid arithmetic."""
        tmx = self.world.tmx
        walls = next((l for l in tmx.layers if getattr(l, "name", None) == COLLISION_LAYER), None)
        cells: dict = {}
        sprites: dict = {}
        if walls is None:
            return cells, sprites
        get_ts = tmx.get_tileset_from_gid
        tw, th = self.world.tw, self.world.th
        sheet, cols = self._grave_sheet()
        bottom_to_full: dict = {}
        if sheet is not None and cols:
            def cut(idx):
                r, c = divmod(idx, cols)
                return sheet.subsurface(pygame.Rect(c * tw, r * th, tw, th)).copy()
            for idx in GRAVE_SHEET_INDICES:
                h = GRAVE_TILES_TALL.get(idx, 2)
                full = pygame.Surface((tw, th * h), pygame.SRCALPHA)
                for k in range(h):               # crown (idx-cols) down to the base
                    full.blit(cut(idx - cols + cols * k), (0, th * k))
                # key by the PLACED body tile (idx) so the pixel-match still works,
                # even when the body isn't the sprite's bottom tile (cross tomb).
                bottom_to_full[pygame.image.tostring(cut(idx), "RGBA")] = full
        for y, row in enumerate(walls.data):
            for x, gid in enumerate(row):
                if not gid:
                    continue
                ts = get_ts(gid)
                if not (ts and ts.name == GRAVE_TILESET):
                    continue
                cells[(x, y)] = gid
                if gid not in sprites:
                    img = tmx.get_tile_image_by_gid(gid)
                    key = pygame.image.tostring(img, "RGBA") if img is not None else None
                    sprites[gid] = bottom_to_full.get(key)
        return cells, sprites

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

    def _load_cobble_tiles(self, sheet_path: str) -> dict:
        """Slice a grass sheet's cobble autotile blob (the road cobble) into 32px
        tiles by name, so town gangways use the same cobblestone as the roads —
        for whichever ZONE's sheet is passed."""
        tiles = {}
        try:
            sheet = pygame.image.load(sheet_path).convert_alpha()
        except (pygame.error, FileNotFoundError):
            return tiles
        cols = sheet.get_width() // 32
        for name, idx in COBBLE_BLOB.items():
            tiles[name] = sheet.subsurface(((idx % cols) * 32, (idx // cols) * 32, 32, 32))
        return tiles

    def _cluster_ground_theme(self, anchor: tuple[int, int]) -> str:
        """The grass theme a cluster sits on, from the ground tileset at its anchor
        (e.g. 'grave_heath_grass' -> 'grave_heath'). Falls back to cainos."""
        tmx = self.world.tmx
        try:
            ground = tmx.get_layer_by_name("ground")
            gid = ground.data[anchor[1]][anchor[0]]
            ts = tmx.get_tileset_from_gid(gid) if gid else None
        except (ValueError, KeyError, IndexError):
            ts = None
        name = ts.name if ts else ""
        return name[:-len("_grass")] if name.endswith("_grass") else "cainos"

    def _cobble_tiles_for(self, theme: str) -> dict:
        """Per-zone cobble tiles, loaded once and cached (cainos preloaded)."""
        if theme not in self._cobble_tiles_by_theme:
            self._cobble_tiles_by_theme[theme] = self._load_cobble_tiles(_grass_sheet_path(theme))
        return self._cobble_tiles_by_theme[theme] or self._cobble_tiles

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
        theme = self._cobble_cell_theme.get((x, y), "cainos")
        return self._cobble_tiles_for(theme).get(key)

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
        # Graves: full 2-tile stones anchored on the (blocking) bottom cell's bottom
        # edge, so the upper tile occupies the row above and the player — with a
        # smaller base_y when standing north of it — draws BEHIND it. Cull to the view.
        left, right, top, bot = getattr(self, "_vis_bounds",
                                        (0, self.world.tmx.width, 0, self.world.tmx.height))
        for (gx, gy), gid in self._grave_cells.items():
            if not (left <= gx < right and top <= gy < bot):
                continue
            sprite = self._grave_sprites.get(gid)
            if sprite is None:
                continue
            base_y = (gy + 1) * th
            drawables.append((base_y, "b", (sprite, gx * tw - ox, base_y - sprite.get_height() - oy)))
        drawables.append((player_rect.bottom + oy, "p", player_rect))
        for _base_y, kind, payload in sorted(drawables, key=lambda d: d[0]):
            if kind == "b":
                sprite, sx, sy = payload
                world.blit(sprite, (sx, sy))
            else:
                self._draw_player(world, payload)

    def _draw_player(self, world: "pygame.Surface", rect: "pygame.Rect") -> None:
        """B83: the animated hooded player — walk cycle in the movement's
        direction, front/blink cycle at rest. Falls back to the classic yellow
        square if the sheets are missing (feet stay on the tile either way)."""
        frames = getattr(self, "_player_frames", None)
        if frames is None:
            pygame.draw.rect(world, PLAYER_COLOR, rect, border_radius=4)
            pygame.draw.rect(world, PLAYER_EDGE, rect, width=2, border_radius=4)
            return
        if getattr(self, "_player_moving", False):
            sprite = frames["walk"][self._player_facing][self._player_frame % 4]
        else:
            sprite = frames["idle"][self._player_frame % 4]
        world.blit(sprite, (rect.centerx - sprite.get_width() // 2,
                            rect.bottom - sprite.get_height()))

    def _load_player_frames(self):
        """{'walk': [8][4], 'idle': [4]} scaled so the sprite stands
        PLAYER_SPRITE_TILES tall, or None when the sheets are absent."""
        try:
            walk = pygame.image.load(PLAYER_WALK_SHEET).convert_alpha()
            idle = pygame.image.load(PLAYER_IDLE_SHEET).convert_alpha()
        except (pygame.error, FileNotFoundError):
            return None
        cell_w, walk_cell_h = walk.get_width() // 4, walk.get_height() // 8
        target_h = max(1, round(self.world.th * PLAYER_SPRITE_TILES))
        target_w = max(1, round(cell_w * target_h / walk_cell_h))

        def cut(sheet, row, col, cell_h):
            cell = sheet.subsurface(pygame.Rect(col * cell_w, row * cell_h, cell_w, cell_h))
            return pygame.transform.scale(cell, (target_w, target_h))

        return {
            "walk": [[cut(walk, row, col, walk_cell_h) for col in range(4)]
                     for row in range(8)],
            "idle": [cut(idle, 0, col, idle.get_height()) for col in range(4)],
        }

    def _tick_player_anim(self) -> None:
        """Advance the player's animation clock (called once per render frame)."""
        self._player_anim_clock = getattr(self, "_player_anim_clock", 0) + 1
        ticks = WALK_FRAME_TICKS if getattr(self, "_player_moving", False) else IDLE_FRAME_TICKS
        if self._player_anim_clock >= ticks:
            self._player_anim_clock = 0
            self._player_frame = (getattr(self, "_player_frame", 0) + 1) % 4

    def _load_chest_sprites(self) -> dict:
        """B63: (theme, opened) -> chest sprite, cropped from the theme's props
        sheet (cainos original; generated recolours share the layout). A missing
        sheet degrades to None (chest still blocks + opens, just invisible)."""
        sprites: dict = {}
        themes = {chest.theme for chest in self.engine.content.chests.values()}
        for theme in themes:
            if theme == "cainos":
                path = os.path.join(PROPS_DIR, "cainos", "TX Props.png")
            else:
                path = os.path.join(PROPS_DIR, "generated", f"04-TX-Props__{theme}.png")
            try:
                sheet = pygame.image.load(path).convert_alpha()
                # B81: chests read a touch large in the world — render at 85%.
                for opened, crop in ((False, CHEST_CLOSED_RECT), (True, CHEST_OPEN_RECT)):
                    raw = sheet.subsurface(pygame.Rect(*crop))
                    sprites[(theme, opened)] = pygame.transform.scale(
                        raw, (max(1, round(raw.get_width() * CHEST_SCALE)),
                              max(1, round(raw.get_height() * CHEST_SCALE))))
            except (pygame.error, FileNotFoundError):
                sprites[(theme, False)] = sprites[(theme, True)] = None
        return sprites

    def _draw_chests(self, world: "pygame.Surface", ox: int, oy: int,
                     left: int, right: int, top: int, bottom: int) -> None:
        """Draw every chest in view, bottom-anchored on its tile; open state reads
        from the player's persisted opened_chest_ids."""
        tw, th = self.world.tw, self.world.th
        opened = set(self.engine.player.opened_chest_ids)
        for chest in self.engine.content.chests.values():
            cx, cy = chest.tile
            if not (left - 1 <= cx < right + 1 and top - 1 <= cy < bottom + 2):
                continue
            sprite = self._chest_sprites.get((chest.theme, chest.id in opened))
            if sprite is None:
                continue
            world.blit(sprite, (cx * tw - ox, (cy + 1) * th - oy - sprite.get_height()))

    def _lair_sprite(self, boss_id: str):
        """The living boss's overworld sprite — its battle art scaled to loom
        two tiles tall. A missing sprite degrades to None (the lair still
        blocks + challenges). B80: no felled variant — a beaten boss vanishes."""
        cached = self._lair_sprites.get(boss_id, False)
        if cached is not False:
            return cached
        boss = self.engine.content.bosses[boss_id]
        path = os.path.join(SPRITE_DIR, f"{boss.enemy_id}.png")
        sprite = None
        try:
            raw = pygame.image.load(path).convert_alpha()
            target_h = self.world.th * 2
            width = max(1, round(raw.get_width() * target_h / raw.get_height()))
            sprite = pygame.transform.scale(raw, (width, target_h))
        except (pygame.error, FileNotFoundError):
            sprite = None
        self._lair_sprites[boss_id] = sprite
        return sprite

    def _draw_lairs(self, world: "pygame.Surface", ox: int, oy: int,
                    left: int, right: int, top: int, bottom: int) -> None:
        """B65/B80: draw every LIVING lair boss in view, bottom-anchored on its
        tile; felled bosses are gone (lair_tiles only holds the living)."""
        tw, th = self.world.tw, self.world.th
        for tile, boss_id in self.lair_tiles.items():
            bx, by = tile
            if not (left - 2 <= bx < right + 2 and top - 2 <= by < bottom + 3):
                continue
            sprite = self._lair_sprite(boss_id)
            if sprite is None:
                continue
            x = bx * tw - ox + (tw - sprite.get_width()) // 2
            world.blit(sprite, (x, (by + 1) * th - oy - sprite.get_height()))

    def _apply_zone_blend(self) -> None:
        """B47: build the seam crossfade at load as DRAW-TIME overrides —
        (x, y) -> pre-blended image index. Layer data stays untouched, so the
        road scan, the M-map terrain and every gid-walking consumer keep seeing
        real gids. Deterministic: same map -> same overrides."""
        self._blend_overrides: dict = {}
        if ZONE_BLEND_BAND <= 0:
            return
        tmx = self.world.tmx
        ground = next((l for l in tmx.layers if getattr(l, "name", None) == "ground"), None)
        if ground is None:
            return
        firstgid_by_name = {ts.name: ts.firstgid for ts in tmx.tilesets}

        def tileset_of_original(og):
            for ts in tmx.tilesets:
                if ts.firstgid <= og < ts.firstgid + ts.tilecount:
                    return ts
            return None

        blended_cache: dict = {}
        for y in range(tmx.height):
            row = ground.data[y]
            for x in range(tmx.width):
                dist, other = _blend_seam_info(x, y)
                if dist is None:
                    continue
                mix = 0.5 * (1 - dist / ZONE_BLEND_BAND)      # 0.5 at the seam -> 0 at edge
                step = round(mix * ZONE_BLEND_STEPS)
                step += (1 if (x * 7 + y * 13) % 4 == 0 else 0) \
                     - (1 if (x * 5 + y * 11) % 4 == 0 else 0)   # mild deterministic jitter
                step = max(0, min(ZONE_BLEND_STEPS, step))
                if step <= 0:
                    continue
                internal = row[x]
                og = tmx.tiledgidmap.get(internal, 0)
                if not og:
                    continue
                ts = tileset_of_original(og)
                theme = _blend_theme_at(x, y)
                if ts is None or not ts.name.startswith(theme):
                    continue                                   # only this zone's own tiles
                key = (internal, other, step)
                if key not in blended_cache:
                    blended_cache[key] = self._build_blend_gid(
                        tmx, ts, og, internal, other, step, firstgid_by_name)
                synthetic = blended_cache[key]
                if synthetic is not None:
                    self._blend_overrides[(x, y)] = synthetic

    _BLEND_THEMES = ("grave_heath", "cursed_mire", "mork_skog", "cainos",
                     "frostfell", "ash_waste", "karr")

    def _build_blend_gid(self, tmx, ts, og, internal, other, step, firstgid_by_name):
        """One pre-blended tile image registered as a synthetic gid (or None if
        the neighbour theme lacks the corresponding tile). The theme tilesets
        are parallel recolours, so index arithmetic maps tiles 1:1."""
        theme = next((t for t in self._BLEND_THEMES if ts.name.startswith(t)), None)
        if theme is None:
            return None
        target_first = firstgid_by_name.get(other + ts.name[len(theme):])
        if target_first is None:
            return None
        mapped = tmx.map_gid(target_first + (og - ts.firstgid))
        if not mapped:
            return None
        own_img = tmx.images[internal]
        other_img = tmx.images[mapped[0][0]]
        if own_img is None or other_img is None:
            return None
        blend = own_img.convert_alpha()
        layer = other_img.convert_alpha().copy()
        layer.set_alpha(int(255 * step / ZONE_BLEND_STEPS))
        blend.blit(layer, (0, 0))
        tmx.images.append(blend)
        return len(tmx.images) - 1

    def _bridge_deck_image(self, gid, image, variant: str = "left"):
        """B52: rotate seam bridge-deck tiles 90° so their planks run across the
        walking direction. B101: `variant` picks the edge-aware deck look (see
        DECK_RAIL_W). Cached per (gid, variant); non-bridge tiles pass through."""
        cached = self._bridge_img_cache.get((gid, variant), False)
        if cached is False:
            ts = self.world.tmx.get_tileset_from_gid(gid)
            if ts and ts.name in BRIDGE_TILESETS:
                cached = self._deck_variant(pygame.transform.rotate(image, 90), variant)
            else:
                cached = None
            self._bridge_img_cache[(gid, variant)] = cached
        return cached or image

    @staticmethod
    def _deck_variant(rotated, variant: str):
        """B101 deck variants, derived deterministically from the rotated tile:
        'left'/'solo' keep it unchanged (rail on the outer left), 'right' flips
        it horizontally (rail on the outer right), 'mid' erases the rail by
        copying plank column x + DECK_RAIL_W over each rail column x."""
        if variant == "right":
            return pygame.transform.flip(rotated, True, False)
        if variant != "mid":
            return rotated
        img = rotated.copy()
        height = rotated.get_height()
        for x in range(DECK_RAIL_W):
            img.blit(rotated.subsurface((x + DECK_RAIL_W, 0, 1, height)), (x, 0))
        return img

    @staticmethod
    def _deck_variant_key(row, x, gid) -> str:
        """Which deck variant a bridge cell needs, from its same-row neighbours
        (same gid = same crossing): edge columns keep one rail, mid columns none."""
        left = x > 0 and row[x - 1] == gid
        right = x + 1 < len(row) and row[x + 1] == gid
        if left and right:
            return "mid"
        if left:
            return "right"
        if right:
            return "left"
        return "solo"

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
        self._vis_bounds = (left, right, top, bottom)   # for grave culling in _draw_town
        # B11: reveal the on-screen tiles into the fog bitset as the player walks.
        fog.reveal_rect(self.engine.player.revealed_tiles, tmx.width, tmx.height,
                        left, right, top, bottom)
        get_image = tmx.get_tile_image_by_gid
        blend_overrides = getattr(self, "_blend_overrides", {})
        for layer in tmx.visible_layers:
            data = getattr(layer, "data", None)
            if data is None:  # not a tile layer (object/image layer)
                continue
            is_walls = getattr(layer, "name", None) == COLLISION_LAYER
            is_ground = getattr(layer, "name", None) == "ground"
            for y in range(top, bottom):
                row = data[y]
                for x in range(left, right):
                    gid = row[x]
                    if not gid:  # empty cell
                        continue
                    if is_walls and (x, y) in self._grave_cells:
                        continue  # drawn as a full y-sorted stone in _draw_town
                    image = get_image(gid)
                    if is_ground and blend_overrides:
                        override = blend_overrides.get((x, y))
                        if override is not None:
                            image = tmx.images[override]   # B47 seam crossfade
                    dest = (x * tw - ox, y * th - oy)
                    if image is None:  # tile without graphic -> placeholder block, never crash
                        pygame.draw.rect(world, PANEL_EDGE, pygame.Rect(dest, (tw, th)))
                    else:
                        world.blit(self._bridge_deck_image(
                            gid, image, self._deck_variant_key(row, x, gid)), dest)
        self._draw_chests(world, ox, oy, left, right, top, bottom)   # B63
        self._draw_lairs(world, ox, oy, left, right, top, bottom)   # B65
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

