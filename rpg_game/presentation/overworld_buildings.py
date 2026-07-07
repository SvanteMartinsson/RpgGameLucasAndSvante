"""B56: the overworld's building-service menus.

Every screen a town door opens lives here — the door menu itself, the
store (buy/sell), the mage-tower tome shop, the apothecary brewing menu
(B68 interim home) and the upgrade station — plus the building->service
tables. Split out of pygame_overworld as a behaviour-preserving mixin:
methods share state with OverworldApp via self exactly as before.
"""

from __future__ import annotations

import pygame

from rpg_game.core import progression
from rpg_game.core.view import build_snapshot
from rpg_game.presentation import chatlog
from rpg_game.presentation import ui_text as T
from rpg_game.presentation.overworld_render import ACCENT, BAD, GOOD, TEXT, TEXT_DIM, WARN

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


class BuildingMenusMixin:
    """Building-service menus for OverworldApp (see module docstring)."""

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
            y += 52
        # B38: a mage tower also teaches skills via tomes.
        if self.engine.tomes_for_sale(building_id):
            self._add_button(pygame.Rect(panel.x + 20, y, panel.width - 40, 44), "Study skill tomes",
                             (lambda b=building_id: self._open_tome_shop(b)), True)
            y += 52
        # B68: brewing. INTERIM home: the general shop's counter — moves to the
        # apothecary building's own door when B8 2b gives it one.
        if building_id == "shop" and self.engine.brew_recipes():
            self._add_button(pygame.Rect(panel.x + 20, y, panel.width - 40, 44), "Brew potions",
                             (lambda: self._open_apothecary()), True)
        back = pygame.Rect(panel.right - 150, panel.bottom - 54, 130, 40)
        self._add_button(back, T.BACK, self._close_building_menu)
        self._draw_buttons()

    def _open_tome_shop(self, building_id: str) -> None:
        self.building_menu = None
        self.tome_building = building_id
        self.mode = "tome_shop"

    def _close_tome_shop(self) -> None:
        self.tome_building = None
        self.mode = "walk"

    def _buy_tome(self, item_id: str) -> None:
        result = self.engine.buy_tome(self.tome_building, item_id)
        self.push_log(result.message, GOOD if result.success else BAD)

    def _draw_tome_shop(self) -> None:
        """B38: a mage-tower shop listing skill tomes. Buying puts a tome in the
        inventory; studying it there (I) learns the skill (level-gated). Known
        skills + unaffordable/owned tomes are shown but disabled."""
        from rpg_game.core import talents
        panel = self._overlay_panel("Mage Tower — Skill Tomes")
        gold = self.engine.player.gold
        known = set(talents.unlocked_skill_ids(self.engine.player, self.engine.content))
        y = panel.y + 66
        self.screen.blit(self.font_sm.render(
            f"Gold: {gold}    ·    study a bought tome from your inventory (I) to learn it",
            True, TEXT_DIM), (panel.x + 20, y))
        y += 30
        for tome in self.engine.tomes_for_sale(self.tome_building):
            skill = self.engine.content.actions[tome.teaches].name
            already = tome.teaches in known
            owned = self.engine.player.inventory.count(tome.id) > 0
            suffix = "  (known)" if already else ("  (owned)" if owned else "")
            label = f"{tome.name}  —  {skill}  ·  Lv {tome.level_req}  ·  {tome.price}g{suffix}"
            enabled = (not already) and gold >= tome.price
            self._add_button(pygame.Rect(panel.x + 20, y, panel.width - 40, 40), label,
                             (lambda t=tome.id: self._buy_tome(t)), enabled)
            y += 46
        back = pygame.Rect(panel.right - 150, panel.bottom - 54, 130, 40)
        self._add_button(back, T.BACK, self._close_tome_shop)
        self._draw_buttons()

    def _open_apothecary(self) -> None:
        self.building_menu = None
        self.mode = "apothecary"

    def _brew(self, recipe_id: str) -> None:
        result = self.engine.brew(recipe_id)
        self.push_log(result.message, GOOD if result.success else BAD)

    def _draw_apothecary(self) -> None:
        """B68: the brewing screen — one row per recipe showing output, the
        materials you have vs need, and the gold cost; dimmed until affordable."""
        from rpg_game.core import alchemy
        panel = self._overlay_panel("Apothecary — Brewing")
        player = self.engine.player
        self.screen.blit(self.font_sm.render(
            f"Gold: {player.gold}    ·    materials come from drops and chests",
            True, TEXT_DIM), (panel.x + 20, panel.y + 60))
        y = panel.y + 92
        for recipe in self.engine.brew_recipes():
            output = self.engine.content.items[recipe.output].name
            parts = []
            for material_id, count in recipe.materials:
                have = player.inventory.count(material_id)
                name = self.engine.content.items[material_id].name
                parts.append(f"{name} {have}/{count}")
            label = f"{output}   —   {' + '.join(parts)}   ·   {recipe.gold}g"
            can = alchemy.brew_blocker(player, recipe) is None
            self._add_button(pygame.Rect(panel.x + 20, y, panel.width - 40, 40), label,
                             (lambda rid=recipe.id: self._brew(rid)), can)
            y += 46
        back = pygame.Rect(panel.right - 150, panel.bottom - 54, 130, 40)
        self._add_button(back, T.BACK, lambda: setattr(self, "mode", "walk"))
        self._draw_buttons()

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

        back = pygame.Rect(panel.right - 150, panel.bottom - 54, 130, 40)
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

    def _draw_store_screen(self) -> None:
        title = T.STORE_TITLES.get(self.store_category, T.SCREEN_TITLES["store"])
        panel = self._overlay_panel(title)
        self._screen_store(panel)
        back = pygame.Rect(panel.right - 150, panel.bottom - 54, 130, 40)
        self._add_button(back, T.BACK, lambda: setattr(self, "mode", "walk"))
        self._draw_buttons()

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

    def buy(self, item_id: str) -> None:
        result = self.engine.buy_item(item_id)
        self.set_toast(result.message, GOOD if result.success else BAD)

    def sell(self, item_id: str) -> None:
        result = self.engine.sell_item(item_id)
        # A successful sale reads in the item's rarity colour (unified with drops);
        # a failure stays in the failure colour.
        color = chatlog.rarity_color(self._item_rarity(item_id)) if result.success else BAD
        self.set_toast(result.message, color)

    def _item_rarity(self, item_id: str) -> str:
        if item_id in self.engine.content.weapons:
            return self.engine.content.weapons[item_id].rarity
        if item_id in self.engine.content.gear_items:
            return self.engine.content.gear_items[item_id].rarity
        return "common"

