"""Pygame overworld — free-walk world connected to the engine (Model B).

Presentation layer. Core (`rpg_game/core`) holds all rules; here we only render
state via `build_snapshot()` and mutate via existing `GameEngine` methods, same
contract as the battle and character-creation shells.

Model B = free walk (WASD) over a walkable world. Towns are tiles you step onto;
entering one sets the engine's current location (`engine.enter_place`). Pressing
Enter on a town opens the location menu (rest, store, talents, skills, inventory,
equip, stats, save). Wilderness has no town menu.

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
from dataclasses import dataclass, field

import pygame
from pytmx.util_pygame import load_pygame

from rpg_game.core import combat
from rpg_game.core.game import GameEngine
from rpg_game.core.view import build_snapshot

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
        gates = {tuple(g["tile"]): g["message"] for g in data.get("gates", [])}
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


# --- app -------------------------------------------------------------------


class OverworldApp:
    TOWN_ACTIONS = [
        ("stats", "Stats"),
        ("inventory", "Inventory"),
        ("equip", "Equip weapon"),
        ("skills", "Skills"),
        ("store", "Store"),
        ("talents", "Talents"),
        ("rest", "Rest"),
        ("save", "Save"),
    ]

    def __init__(self, engine: GameEngine | None = None, zone: ZoneConfig | None = None) -> None:
        pygame.init()
        pygame.display.set_caption("Svantrenish RPG — Overworld")
        pygame.display.set_mode((1, 1))  # video mode for tile .convert() during load
        self.zone = zone or ZoneConfig.load()
        self.engine = engine or self._new_engine()
        self.world = Overworld(self.zone.map_path, dict(self.zone.gates), dict(self.zone.towns))
        self.world.set_tile(*self.zone.start_tile)
        self.sync_location()
        view_w = min(self.world.map_px_w, 960)
        view_h = min(self.world.map_px_h, 640)
        self.screen = pygame.display.set_mode((view_w, view_h))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("menlo,consolas,monospace", 16)
        self.font_sm = pygame.font.SysFont("menlo,consolas,monospace", 13)
        self.font_lg = pygame.font.SysFont("menlo,consolas,monospace", 22, bold=True)
        self.mode = "walk"  # walk | townmenu | stats | inventory | equip | skills | store | talents
        self.buttons: list[Button] = []
        self.toast = ""
        self.toast_color = TEXT
        self.toast_timer = 0
        self.running = True

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

    # -- town actions (all go through the engine) ---------------------------

    def do_action(self, action: str) -> None:
        if action == "stats":
            self.mode = "stats"
        elif action == "inventory":
            self.mode = "inventory"
        elif action == "equip":
            self.mode = "equip"
        elif action == "skills":
            self.mode = "skills"
        elif action == "talents":
            self.mode = "talents"
        elif action == "store":
            if self.engine.current_place().has_store:
                self.mode = "store"
            else:
                self.set_toast("No store in this town.", TEXT_DIM)
        elif action == "rest":
            result = self.engine.rest()
            self.set_toast(result.message, GOOD if result.outcome == "rested" else TEXT_DIM)
        elif action == "save":
            result = self.engine.save(SAVE_PATH)
            self.set_toast(result.message, GOOD if result.success else BAD)

    def equip_weapon(self, weapon_id: str) -> None:
        player = self.engine.player
        if weapon_id == player.equipped_weapon_id:
            self.set_toast("Already equipped.", TEXT_DIM)
            return
        weapon = self.engine.content.weapons[weapon_id]
        action = combat.create_weapon_swap_action(weapon)
        result = combat.resolve_action(player, player, action, self.engine.rng, weapon=weapon)
        if result.blocked:
            self.set_toast(" ".join(result.events) or "Cannot equip that.", BAD)
        else:
            self.set_toast(f"Equipped {weapon.name}.", GOOD)

    def toggle_skill(self, action_id: str, equipped: bool) -> None:
        message = self.engine.unequip_skill(action_id) if equipped else self.engine.equip_skill(action_id)
        self.set_toast(message, GOOD)

    def buy(self, item_id: str) -> None:
        result = self.engine.buy_item(item_id)
        self.set_toast(result.message, GOOD if result.success else BAD)

    def sell(self, item_id: str) -> None:
        result = self.engine.sell_item(item_id)
        self.set_toast(result.message, GOOD if result.success else BAD)

    def learn_talent(self, node_id: str) -> None:
        message = self.engine.allocate_talent(node_id)
        self.set_toast(message, GOOD)

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
            if self.mode in ("stats", "inventory", "equip", "skills", "store", "talents"):
                self.mode = "townmenu"
            elif self.mode == "townmenu":
                self.mode = "walk"
            else:
                self.running = False
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
        if self.mode != "walk":
            return
        keys = pygame.key.get_pressed()
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        if dx or dy:
            message = self.world.try_move(dx * PLAYER_SPEED, dy * PLAYER_SPEED)
            if message:
                self.set_toast(message, WARN)
            self.sync_location()

    # -- rendering ----------------------------------------------------------

    def draw(self) -> None:
        self.buttons = []
        self.screen.fill(BG)
        self._draw_map()
        self._draw_hud()
        if self.mode == "townmenu":
            self._draw_town_menu()
        elif self.mode in ("stats", "inventory", "equip", "skills", "store", "talents"):
            self._draw_subscreen()
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
        where = place.name if in_town else f"Wilds near {place.name}"
        left = f"{snap.player.name}  Lv{snap.player.level}  HP {snap.player.hp}/{snap.player.max_hp}  Gold {snap.player.gold}"
        self.screen.blit(self.font_sm.render(left, True, TEXT), (8, 6))
        right = self.font_sm.render(where, True, ACCENT if in_town else TEXT_DIM)
        self.screen.blit(right, right.get_rect(topright=(self.screen.get_width() - 8, 6)))
        if self.mode == "walk":
            hint = "Enter: town menu" if in_town else "WASD/arrows to move"
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
        for i, (action, label) in enumerate(self.TOWN_ACTIONS):
            col, row = i % 2, i // 2
            rect = pygame.Rect(panel.x + 20 + col * (col_w + 20), panel.y + 70 + row * 56, col_w, 44)
            enabled = not (action == "store" and not has_store)
            self._add_button(rect, label, (lambda a=action: self.do_action(a)), enabled)
        self.screen.blit(self.font_sm.render("Esc / Enter: back to map", True, TEXT_DIM),
                         (panel.x + 20, panel.bottom - 30))
        self._draw_buttons()

    def _draw_subscreen(self) -> None:
        panel = self._overlay_panel(self.mode.capitalize())
        renderer = getattr(self, f"_screen_{self.mode}")
        renderer(panel)
        back = pygame.Rect(panel.right - 130, panel.bottom - 54, 110, 40)
        self._add_button(back, "Back (Esc)", lambda: setattr(self, "mode", "townmenu"))
        self._draw_buttons()

    def _lines(self, panel, lines, color=TEXT, start=64, step=24) -> int:
        for i, line in enumerate(lines):
            self.screen.blit(self.font.render(line, True, color), (panel.x + 20, panel.y + start + i * step))
        return panel.y + start + len(lines) * step

    def _screen_stats(self, panel) -> None:
        p = build_snapshot(self.engine).player
        self._lines(panel, [
            f"{p.name} — {p.class_name} (Lv {p.level})",
            f"HP {p.hp}/{p.max_hp}    Mana {p.mana}/{p.max_mana}",
            f"XP {p.xp}/{p.xp_required}    Talent points {p.talent_points}",
            f"Damage {p.total_damage} (base {p.base_damage} + weapon {p.weapon_damage_bonus})",
            f"Armor {p.armor}    Speed {p.speed}    Crit {p.crit_chance}%",
            f"Gold {p.gold}",
        ])

    def _screen_inventory(self, panel) -> None:
        eng = self.engine
        lines = ["Consumables:"]
        consumables = [(i, c) for i, c in sorted(eng.player.inventory.consumables.items()) if c > 0]
        lines += [f"  {eng.content.items[i].name} x{c}" for i, c in consumables] or ["  (none)"]
        lines.append("")
        lines.append("Weapons:")
        for w in build_snapshot(eng).weapons:
            mark = " (equipped)" if w.equipped else ""
            lines.append(f"  {w.name} +{w.damage_bonus} {w.damage_type}{mark}")
        self._lines(panel, lines, step=22)

    def _screen_equip(self, panel) -> None:
        self.screen.blit(self.font_sm.render("Click a weapon to equip (level permitting).", True, TEXT_DIM),
                         (panel.x + 20, panel.y + 56))
        for i, w in enumerate(build_snapshot(self.engine).weapons):
            rect = pygame.Rect(panel.x + 20, panel.y + 84 + i * 42, panel.width - 40, 36)
            suffix = " [equipped]" if w.equipped else ("" if w.equippable else f"  needs Lv {w.required_level}")
            self._add_button(rect, f"{w.name} (+{w.damage_bonus} {w.damage_type}, tier {w.tier}){suffix}",
                             (lambda wid=w.id: self.equip_weapon(wid)), w.equippable and not w.equipped)

    def _screen_skills(self, panel) -> None:
        eng = self.engine
        equipped_ids = set(eng.player.equipped_skill_ids)
        self.screen.blit(self.font_sm.render(f"Equipped {len(equipped_ids)}/4 — click to equip/unequip.", True, TEXT_DIM),
                         (panel.x + 20, panel.y + 56))
        skills = eng.equippable_skills()
        if not skills:
            self._lines(panel, ["No skills unlocked yet — learn talents first."], TEXT_DIM, start=88)
            return
        for i, skill in enumerate(skills):
            rect = pygame.Rect(panel.x + 20, panel.y + 84 + i * 40, panel.width - 40, 34)
            is_eq = skill.id in equipped_ids
            label = f"{'[E] ' if is_eq else ''}{skill.name}"
            enabled = is_eq or len(equipped_ids) < 4
            self._add_button(rect, label, (lambda sid=skill.id, eq=is_eq: self.toggle_skill(sid, eq)), enabled)

    def _screen_store(self, panel) -> None:
        eng = self.engine
        gold = build_snapshot(eng).player.gold
        self.screen.blit(self.font_sm.render(f"Gold: {gold}    (click to buy / sell one)", True, WARN),
                         (panel.x + 20, panel.y + 56))
        col_w = (panel.width - 60) // 2
        self.screen.blit(self.font.render("Buy", True, TEXT), (panel.x + 20, panel.y + 80))
        for i, entry in enumerate(eng.store_entries()[:6]):
            rect = pygame.Rect(panel.x + 20, panel.y + 106 + i * 38, col_w, 32)
            self._add_button(rect, f"{entry.name}  {entry.price}g", (lambda iid=entry.id: self.buy(iid)), gold >= entry.price)
        self.screen.blit(self.font.render("Sell", True, TEXT), (panel.x + 40 + col_w, panel.y + 80))
        for i, entry in enumerate(eng.sellable_entries()[:6]):
            rect = pygame.Rect(panel.x + 40 + col_w, panel.y + 106 + i * 38, col_w, 32)
            self._add_button(rect, f"{entry.name} x{entry.count}  {entry.value}g", (lambda iid=entry.id: self.sell(iid)))

    def _screen_talents(self, panel) -> None:
        eng = self.engine
        points = build_snapshot(eng).player.talent_points
        self.screen.blit(self.font_sm.render(f"Talent points: {points} — click to learn.", True, WARN),
                         (panel.x + 20, panel.y + 56))
        nodes = eng.available_talents()
        if not nodes:
            self._lines(panel, ["No talents available to learn right now."], TEXT_DIM, start=88)
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


def main(argv: list[str] | None = None) -> None:
    OverworldApp().run()


if __name__ == "__main__":
    main()
