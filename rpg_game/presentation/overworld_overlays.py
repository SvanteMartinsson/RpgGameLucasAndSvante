"""B56: the overworld's fullscreen overlays and modal screens.

Character/inventory/skills+talents/system/settings/bestiary overlays, the
tournament list/confirm/intermission screens and the death/victory screens.
Split out of pygame_overworld as a behaviour-preserving mixin: methods share
state with OverworldApp via self exactly as before (shared chrome like
_overlay_panel/_add_button stays in the shell). B40 S2-S5 apply-slices edit
THESE screens — they now live in one place.
"""

from __future__ import annotations

import os

import pygame

from rpg_game.core import saveslots
from rpg_game.core.view import build_snapshot
from rpg_game.presentation import settings as user_settings
from rpg_game.presentation import ui_text as T
from rpg_game.presentation.overworld_render import (
    ACCENT, BAD, GOOD, PANEL_EDGE, TEXT, TEXT_DIM, WARN)
from rpg_game.presentation.talent_text import (
    talent_action_label,
    talent_can_allocate,
    talent_rank_label,
    talent_status,
)

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


class OverlaysMixin:
    """Fullscreen overlays + modal screens for OverworldApp."""

    def _draw_overlay_screen(self) -> None:
        panel = self._overlay_panel(T.SCREEN_TITLES.get(self.overlay, self.overlay.capitalize()))
        renderer = getattr(self, f"_overlay_{self.overlay}")
        renderer(panel)
        back = pygame.Rect(panel.right - 130, panel.bottom - 54, 110, 40)
        self._add_button(back, T.BACK, self.close_overlay)
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

        self.screen.blit(self.font_sm.render(
            self._fit_text(T.skills_hint(len(equipped_ids)), left.width, self.font_sm),
            True, TEXT_DIM), (left.x, left.y))
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

        self.screen.blit(self.font_sm.render(
            self._fit_text(T.talents_hint(eng.player.talent_points), middle.width, self.font_sm),
            True, WARN), (middle.x, middle.y))
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

    def _overlay_system(self, panel) -> None:
        self.screen.blit(self.font_sm.render(T.SYSTEM_HINT, True, TEXT_DIM),
                         (panel.x + 20, panel.y + 56))
        self._add_button(pygame.Rect(panel.x + 20, panel.y + 92, panel.width - 40, 42),
                         T.SYSTEM_SAVE, self.save_game)
        self._add_button(pygame.Rect(panel.x + 20, panel.y + 144, panel.width - 40, 42),
                         "Settings", (lambda: setattr(self, "overlay", "settings")))
        self._add_button(pygame.Rect(panel.x + 20, panel.y + 196, panel.width - 40, 42),
                         T.SYSTEM_QUIT, self.quit_game)

    def _overlay_settings(self, panel: pygame.Rect) -> None:
        """B70: display/HUD settings — every change applies immediately AND
        persists to settings.json. Volume rows arrive with B69."""
        self.screen.blit(self.font_sm.render(
            "Changes apply immediately and persist.", True, TEXT_DIM),
            (panel.x + 20, panel.y + 56))
        y = panel.y + 92
        self._add_button(pygame.Rect(panel.x + 20, y, panel.width - 40, 42),
                         f"Fullscreen: {'On' if self.fullscreen else 'Off'}   (F11)",
                         self.toggle_fullscreen)
        y += 50
        self._add_button(pygame.Rect(panel.x + 20, y, 180, 42),
                         f"Log rows: {self.log_visible} -", (lambda: self.resize_log(-1)))
        self._add_button(pygame.Rect(panel.x + 210, y, 180, 42),
                         f"Log rows: {self.log_visible} +", (lambda: self.resize_log(1)))
        y += 50
        self._add_button(pygame.Rect(panel.x + 20, y, panel.width - 40, 42),
                         f"Minimap: {'On' if self.show_minimap else 'Off'}   (N)",
                         (lambda: (setattr(self, 'show_minimap', not self.show_minimap),
                                   self._persist_settings())))
        y += 50
        fx_on = bool(self._settings.get("combat_fx", True))
        self._add_button(pygame.Rect(panel.x + 20, y, panel.width - 40, 42),
                         f"Combat FX: {'On' if fx_on else 'Off'}",
                         (lambda: (self._settings.update(combat_fx=not fx_on),
                                   user_settings.save(self._settings))))
        y += 58
        self.screen.blit(self.font_sm.render("Keys", True, ACCENT), (panel.x + 20, y))
        y += 26
        for line in ("WASD / arrows — move        E / Enter — interact (doors, chests)",
                     "M — world map        N — minimap        B — bestiary",
                     "C — character        I — inventory        K — skills & talents",
                     "+ / - — log size        PgUp / PgDn — scroll log        F11 — fullscreen",
                     "Esc — menu / back"):
            self.screen.blit(self.font_sm.render(line, True, TEXT_DIM), (panel.x + 20, y))
            y += 22

    def move_bestiary_selection(self, delta: int) -> None:
        from rpg_game.core import bestiary
        total = len(bestiary.codex_enemy_ids(self.engine.content))
        if total:
            self.bestiary_index = (self.bestiary_index + delta) % total

    def _bestiary_thumb(self, enemy_id: str):
        """(thumbnail, silhouette) for an enemy's battle sprite, cached. The
        silhouette (dark fill, alpha kept) is shown while only 'seen'."""
        if enemy_id in self._bestiary_sprite_cache:
            return self._bestiary_sprite_cache[enemy_id]
        path = os.path.join(os.path.dirname(__file__), "..", "assets", "sprites",
                            "generated", f"{enemy_id}.png")
        thumb = shadow = None
        try:
            raw = pygame.image.load(path).convert_alpha()
            w, h = raw.get_size()
            scale = min(150 / w, 150 / h)
            thumb = pygame.transform.smoothscale(raw, (max(1, int(w * scale)), max(1, int(h * scale))))
            shadow = thumb.copy()
            shadow.fill((28, 30, 40), special_flags=pygame.BLEND_RGB_MIN)
        except (pygame.error, FileNotFoundError):
            pass
        self._bestiary_sprite_cache[enemy_id] = (thumb, shadow)
        return thumb, shadow

    def _overlay_bestiary(self, panel: pygame.Rect) -> None:
        """B66: the codex — left a scrollable roster (unseen rows dimmed as ???),
        right the selected enemy: sprite or silhouette, level band, and its
        traits/weaknesses/skills once UNLOCKED (Identify once or 5 kills)."""
        from rpg_game.core import bestiary
        rows = bestiary.entries(self.engine.content, self.engine.player)
        if not rows:
            return
        self.bestiary_index %= len(rows)
        seen, unlocked, total = bestiary.progress(self.engine.content, self.engine.player)
        self.screen.blit(self.font_sm.render(
            f"Seen {seen}/{total}   ·   Known {unlocked}/{total}   ·   arrows/wheel browse",
            True, TEXT_DIM), (panel.x + 20, panel.y + 56))

        # Roster rows are Buttons (the shared row idiom): "> " marks the selection,
        # unseen creatures show as ??? in the restricted (dimmed) style. B79: the
        # window follows the selection (wheel/arrows) and shows how much lies
        # beyond each edge, so the full codex is reachable and its size readable.
        list_rect = pygame.Rect(panel.x + 20, panel.y + 84, 300, panel.height - 150)
        row_h = 30
        visible = max(1, list_rect.height // row_h)
        start = max(0, min(self.bestiary_index - visible // 2, len(rows) - visible))
        for i, entry in enumerate(rows[start:start + visible]):
            idx = start + i
            rect = pygame.Rect(list_rect.x, list_rect.y + i * row_h, list_rect.width, row_h - 4)
            marker = "> " if idx == self.bestiary_index else "  "
            name = entry.name if entry.seen else "???"
            band = f"  ·  Lv {entry.level_min}-{entry.level_max}" if entry.unlocked else ""
            self._add_button(rect, f"{marker}{name}{band}",
                             (lambda n=idx: setattr(self, "bestiary_index", n)),
                             True, restricted=not entry.seen)
        if start > 0:
            self.screen.blit(self.font_sm.render(f"^ {start} more ^", True, TEXT_DIM),
                             (list_rect.x + 8, list_rect.y - 18))
        below = len(rows) - (start + visible)
        if below > 0:
            self.screen.blit(self.font_sm.render(f"v {below} more v", True, TEXT_DIM),
                             (list_rect.x + 8, list_rect.bottom + 2))

        entry = rows[self.bestiary_index]
        dx = panel.x + 350
        detail = pygame.Rect(dx, panel.y + 84, panel.right - dx - 20, panel.height - 150)
        thumb, shadow = self._bestiary_thumb(entry.id)
        sprite = (thumb if entry.unlocked else shadow) if entry.seen else None
        if sprite is not None:
            self.screen.blit(sprite, (detail.x, detail.y))
        ty = detail.y
        tx = detail.x + 170
        title = entry.name if entry.seen else "Unknown creature"
        self.screen.blit(self.font_lg.render(title, True, ACCENT if entry.unlocked else TEXT_DIM), (tx, ty))
        ty += 34
        if not entry.seen:
            self.screen.blit(self.font_sm.render("You have not met this creature yet.", True, TEXT_DIM), (tx, ty))
            return
        if not entry.unlocked:
            need = bestiary.KILL_UNLOCK - entry.kills
            for line in (f"Defeated: {entry.kills}",
                         f"Identify it, or defeat {need} more,",
                         "to reveal its secrets."):
                self.screen.blit(self.font_sm.render(line, True, TEXT_DIM), (tx, ty))
                ty += 22
            return
        self.screen.blit(self.font_sm.render(
            f"Lv {entry.level_min}-{entry.level_max}   ·   defeated {entry.kills}", True, TEXT), (tx, ty))
        ty += 24
        if entry.traits:
            self.screen.blit(self.font_sm.render("Traits: " + ", ".join(entry.traits), True, TEXT), (tx, ty))
            ty += 24
        weak = [t for t, v in sorted(entry.resistances.items()) if v > 1.0]
        resist = [t for t, v in sorted(entry.resistances.items()) if 0 < v < 1.0]
        immune = [t for t, v in sorted(entry.resistances.items()) if v == 0]
        for label, values, colour in (("Weak to", weak, GOOD), ("Resists", resist, WARN),
                                      ("Immune", immune, BAD)):
            if values:
                self.screen.blit(self.font_sm.render(f"{label}: " + ", ".join(values), True, colour), (tx, ty))
                ty += 22
        if entry.skills:
            ty += 6
            self.screen.blit(self.font_sm.render("Abilities:", True, TEXT), (tx, ty))
            ty += 22
            for name in entry.skills[:6]:
                self.screen.blit(self.font_sm.render(f"· {name}", True, TEXT_DIM), (tx, ty))
                ty += 20

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

    def _draw_death_screen(self) -> None:
        """B71: "You fell." — rise at the respawn (penalty already applied by the
        core) or load the autosave / a manual slot instead."""
        panel = self._overlay_panel("You fell.")
        place = self.engine.current_place().name
        self.screen.blit(self.font_sm.render(
            f"You wake at {place}, lighter of purse.", True, TEXT_DIM),
            (panel.x + 20, panel.y + 60))
        y = panel.y + 96
        self._add_button(pygame.Rect(panel.x + 20, y, panel.width - 40, 44),
                         f"Rise at {place}", (lambda: setattr(self, "mode", "walk")), True)
        y += 52
        auto = saveslots.slot_summary(saveslots.AUTOSAVE_PATH)
        if auto is not None:
            label = f"Load autosave — {auto.name} · Lv {auto.level} · {auto.playtime_label()}"
            self._add_button(pygame.Rect(panel.x + 20, y, panel.width - 40, 44), label,
                             (lambda: self._load_save(saveslots.AUTOSAVE_PATH)), True)
            y += 52
        for i, summary in enumerate(saveslots.all_summaries()):
            if summary is None:
                continue
            label = (f"Load slot {i + 1} — {summary.name} · {summary.player_class} · "
                     f"Lv {summary.level} · {summary.playtime_label()}")
            self._add_button(pygame.Rect(panel.x + 20, y, panel.width - 40, 44), label,
                             (lambda p=summary.path: self._load_save(p)), True)
            y += 52
        self._draw_buttons()

    def _draw_victory_screen(self) -> None:
        """B65: the ending — shown once, when the final boss falls. The world
        stays open behind it; Continue (or Esc) returns to the map."""
        veil = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        veil.fill((8, 6, 16, 210))
        self.screen.blit(veil, (0, 0))
        panel = self._overlay_panel(T.VICTORY_TITLE)
        y = panel.y + 64
        for line in T.VICTORY_LINES:
            if line:
                self.screen.blit(self.font_sm.render(line, True, TEXT), (panel.x + 20, y))
            y += 22
        self._add_button(pygame.Rect(panel.x + 20, y + 10, panel.width - 40, 44),
                         T.VICTORY_CONTINUE, (lambda: setattr(self, "mode", "walk")), True)
        self._draw_buttons()

