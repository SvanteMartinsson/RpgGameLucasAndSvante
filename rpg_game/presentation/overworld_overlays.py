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

from rpg_game.core.view import build_snapshot
from rpg_game.presentation import chatlog
from rpg_game.presentation import settings as user_settings
from rpg_game.presentation import ui
from rpg_game.presentation import ui_text as T
from rpg_game.presentation.overworld_render import (
    ACCENT, BAD, GOOD, PANEL_EDGE, TEXT, TEXT_DIM, WARN)
from rpg_game.presentation.talent_text import (
    branch_label,
    grouped_class_talents,
    skill_effect_lines,
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


# --- B121: character-screen figure + anatomical equip slots ------------------
# Lucas-locked look (batch 2026-07-13): the hero is a hooded, faceless wanderer —
# a FULLY dark cloak (no lining) with two glowing CYAN eyes. This is a placeholder
# silhouette drawn from primitives; the real hood-open illustration drops in later
# (the hero-idle pattern), so all of it is deliberately simple and swappable.
CHAR_EYE = (72, 226, 236)            # cyan eyes — the only accent on the figure
CHAR_CLOAK = (16, 18, 26)            # cloak body: near-black, reads as a void
CHAR_CLOAK_HI = (34, 38, 54)         # faint rim so the silhouette reads on PANEL
CHAR_FACE_VOID = (6, 7, 11)          # the darker hollow inside the hood
CHAR_SLOT_FILLED_EDGE = WARN         # gold border on an occupied slot
CHAR_SLOT_EMPTY_EDGE = (72, 78, 98)  # dim border on an empty slot
CHAR_SLOT_BG = (26, 30, 42)
CHAR_SLOT_PX = 46                    # slot icon-box size (square)

# Anatomical slot anchors as (x, y) FRACTIONS of the figure box (0..1). Kept in one
# table so Lucas can fine-tune placement without touching draw code (batch:
# "slot-placeringen JUSTERBAR i konstant/data-tabell"). Screen-left is the figure's
# right hand: head over the hood, amulet at the neck, chest/legs on the torso, feet
# at the hem, weapon in one hand, the other hand + three rings clustered by it.
CHARACTER_SLOT_ANATOMY: dict[str, tuple[float, float]] = {
    "head":   (0.50, 0.05),
    "amulet": (0.50, 0.25),
    "chest":  (0.50, 0.41),
    "legs":   (0.50, 0.61),
    "feet":   (0.50, 0.93),
    "weapon": (0.12, 0.52),
    "hands":  (0.88, 0.50),
    "ring_1": (0.87, 0.68),
    "ring_2": (0.95, 0.82),
    "ring_3": (0.79, 0.82),
}

# Short glyph shown in an EMPTY slot (the equipped item's name shows when filled).
CHARACTER_SLOT_ABBR = {
    "weapon": "Wpn", "head": "Head", "chest": "Chest", "hands": "Hnds",
    "legs": "Legs", "feet": "Feet", "amulet": "Amul",
    "ring_1": "R1", "ring_2": "R2", "ring_3": "R3",
}


def character_slot_glyph(slot) -> str:
    """B132: the glyph a character slot shows — its TYPE abbreviation, identical
    filled or empty, so a worn slot never displays a clipped item name. The worn
    item's name lives in the slot's hover tooltip instead."""
    return CHARACTER_SLOT_ABBR.get(slot.id, slot.name[:4])


class OverlaysMixin:
    """Fullscreen overlays + modal screens for OverworldApp."""

    def _draw_overlay_screen(self) -> None:
        panel = self._overlay_panel(T.SCREEN_TITLES.get(self.overlay, self.overlay.capitalize()))
        renderer = getattr(self, f"_overlay_{self.overlay}")
        renderer(panel)
        # B106: wide enough for "Back" + the Esc badge chip (no "..." cut).
        back = pygame.Rect(panel.right - 170, panel.bottom - 54, 150, 40)
        self._add_button(back, T.BACK, self.close_overlay, badge=T.BACK_KEY)
        self._draw_buttons()

    # B40 S4: the header block is 3 lines x 22 px; the column regions start
    # below it with room for their own -22 px section labels, so the header can
    # no longer collide with the stats label (the playtest bug).
    _CHAR_HEADER_H = 3 * 22

    def _character_regions(self, panel: pygame.Rect) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
        """B121: three fluid zones — stats (left), the figure + anatomical slots
        (centre), the full scrollable inventory (right). All start below the
        3-line header so their -22 px section labels never collide with it."""
        content = self._content_rect(panel)
        gap = 16
        top = content.y + self._CHAR_HEADER_H + 26
        height = content.bottom - top
        stats_w = max(168, min(240, int(content.width * 0.25)))
        inv_w = max(176, min(280, int(content.width * 0.30)))
        figure_w = max(150, content.width - stats_w - inv_w - 2 * gap)
        stats = pygame.Rect(content.x, top, stats_w, height)
        figure = pygame.Rect(stats.right + gap, top, figure_w, height)
        items = pygame.Rect(figure.right + gap, top, content.right - (figure.right + gap), height)
        return stats, figure, items

    def _delta_text(self, candidate: dict, equipped: dict) -> str:
        """Compare-vs-equipped: ' (+3 dmg, -1 armor)' for the net change if this
        item replaced the one in the slot. Empty (' (=)') when nothing changes."""
        parts = []
        for stat in self._DELTA_LABELS:
            diff = candidate.get(stat, 0) - equipped.get(stat, 0)
            if diff:
                parts.append(f"{diff:+} {self._DELTA_LABELS[stat]}")
        return f"  ({', '.join(parts)})" if parts else "  (=)"

    def _delta_value(self, candidate: dict, equipped: dict) -> str:
        """B40 S4: the compare-vs-equipped figure for a row's value slot —
        '+3 dmg' / '+4 hp, -1 armor' / 'same'. No parentheses (spec point 3)."""
        delta = self._delta_text(candidate, equipped).strip().strip("()")
        return "same" if delta == "=" else delta

    def _overlay_character(self, panel) -> None:
        """B121: the character screen (see CHARACTER_SCREEN.md). A 3-line header,
        then three fluid zones: the stats summary (left, total + gear delta), the
        hooded figure with the ten equip slots placed anatomically (centre), and
        the full inventory (right, scrollable, rarity-coloured). Equip/unequip
        happens by clicking a slot or an inventory item; the snapshot is rebuilt
        each frame so the stat delta updates live. No game rules here — the split
        stats come straight off the B121a snapshot."""
        snap = build_snapshot(self.engine)
        p = snap.player
        content = self._content_rect(panel)
        header_lines = [
            f"{p.name} — {p.class_name} · Lv {p.level}",
            f"HP {p.hp}/{p.max_hp} · Mana {p.mana}/{p.max_mana} · XP {p.xp}/{p.xp_required}",
            f"Gold {p.gold} · Talent points {p.talent_points}",
        ]
        for i, line in enumerate(header_lines):
            self.screen.blit(self.font.render(self._fit_text(line, content.width, self.font), True, TEXT),
                             (content.x, content.y + i * 22))

        stats_rect, figure_rect, items_rect = self._character_regions(panel)
        self._draw_character_stats(stats_rect, snap)
        self._draw_character_figure_slots(figure_rect, snap)
        self._draw_character_inventory(items_rect, snap)

    def _draw_character_stats(self, rect, snap) -> None:
        """Left zone: each stat as 'total (+from_gear)' — the gear delta green
        when it helps, dimmed at zero (B121a data) — then the equipped weapon's
        type (category · damage_type · tier). Rows explain themselves on hover."""
        self.screen.blit(self.font_sm.render("Stats", True, TEXT_DIM), (rect.x, rect.y - 22))
        value_x = min(rect.width - 70, 104)
        for i, row in enumerate(snap.player.stats):
            y = rect.y + i * 24
            self.screen.blit(self.font_sm.render(row.label, True, TEXT_DIM), (rect.x, y + 1))
            total_s = self.font.render(str(row.total), True, TEXT)
            self.screen.blit(total_s, (rect.x + value_x, y - 1))
            if row.from_gear > 0:
                delta_s = self.font_sm.render(f"(+{row.from_gear})", True, GOOD)
            elif row.from_gear < 0:
                delta_s = self.font_sm.render(f"({row.from_gear})", True, BAD)
            else:
                delta_s = self.font_sm.render("(+0)", True, (86, 92, 108))
            self.screen.blit(delta_s, (rect.x + value_x + total_s.get_width() + 8, y + 1))
            row_rect = pygame.Rect(rect.x, y, rect.width, 22)
            self.hover.add(row_rect, ui.Tooltip(title=row.label, body=T.stat_help(row.stat)))

        weapon = next((w for w in snap.weapons if w.equipped), None)
        if weapon is not None:
            wy = rect.y + len(snap.player.stats) * 24 + 14
            self.screen.blit(self.font_sm.render("Weapon", True, TEXT_DIM), (rect.x, wy))
            type_line = f"{weapon.category.title()} · {weapon.damage_type} · tier {weapon.tier}"
            self.screen.blit(self.font_sm.render(self._fit_text(type_line, rect.width, self.font_sm), True, ACCENT),
                             (rect.x, wy + 20))

    def _draw_character_figure_slots(self, rect, snap) -> None:
        """Centre zone: the placeholder hooded figure with the ten real slots
        (equipment_slots.json) placed anatomically via CHARACTER_SLOT_ANATOMY."""
        self.screen.blit(self.font_sm.render("Equipment", True, TEXT_DIM), (rect.x, rect.y - 22))
        # Inset the figure box so edge slots (hands/rings/weapon) still sit inside
        # the zone rather than spilling into the neighbouring columns.
        box = rect.inflate(-CHAR_SLOT_PX, -CHAR_SLOT_PX // 2)
        self._draw_character_figure(box)
        slots = {slot.id: slot for slot in snap.equipment_slots}
        for slot_id, (fx, fy) in CHARACTER_SLOT_ANATOMY.items():
            slot = slots.get(slot_id)
            if slot is None:
                continue
            srect = pygame.Rect(0, 0, CHAR_SLOT_PX, CHAR_SLOT_PX)
            srect.center = (box.x + int(fx * box.width), box.y + int(fy * box.height))
            self._draw_equip_slot(srect, slot)

    def _draw_character_figure(self, box) -> None:
        """The placeholder wanderer: a fully dark, hood-open cloak with two cyan
        eyes. Primitives only — a stand-in for the real illustration (batch)."""
        w, h = box.width, box.height
        cx = box.centerx
        shoulder_y = box.y + int(0.26 * h)
        hem_y = box.y + int(0.97 * h)
        shoulder_x = max(6, int(0.20 * w))
        hem_x = max(8, int(0.30 * w))
        # Arms held out holding the cloak open (drawn first, behind the body).
        for sign in (-1, 1):
            arm = [
                (cx + sign * (shoulder_x - 2), shoulder_y + 4),
                (cx + sign * (hem_x + int(0.07 * w)), box.y + int(0.60 * h)),
                (cx + sign * (hem_x - 2), box.y + int(0.64 * h)),
                (cx + sign * int(0.06 * w), shoulder_y + int(0.10 * h)),
            ]
            pygame.draw.polygon(self.screen, CHAR_CLOAK, arm)
        # Bell-shaped cloak body.
        body = [(cx - shoulder_x, shoulder_y), (cx + shoulder_x, shoulder_y),
                (cx + hem_x, hem_y), (cx - hem_x, hem_y)]
        pygame.draw.polygon(self.screen, CHAR_CLOAK, body)
        pygame.draw.polygon(self.screen, CHAR_CLOAK_HI, body, width=2)
        # Hood: a rounded cowl over the shoulders.
        hood_w = max(6, int(0.16 * w))
        hood = pygame.Rect(cx - hood_w, box.y + int(0.02 * h), hood_w * 2, int(0.30 * h))
        pygame.draw.ellipse(self.screen, CHAR_CLOAK, hood)
        pygame.draw.ellipse(self.screen, CHAR_CLOAK_HI, hood, width=2)
        # Face hollow + the two glowing cyan eyes.
        face = pygame.Rect(0, 0, int(hood_w * 1.3), int(0.16 * h))
        face.center = (cx, box.y + int(0.15 * h))
        pygame.draw.ellipse(self.screen, CHAR_FACE_VOID, face)
        eye_dx = max(4, hood_w // 2)
        eye_r = max(2, hood_w // 7)
        for sign in (-1, 1):
            pygame.draw.circle(self.screen, CHAR_EYE, (cx + sign * eye_dx, face.centery), eye_r)

    def _draw_equip_slot(self, srect, slot) -> None:
        """One anatomical icon slot: gold-edged when worn, dimmed when empty.
        Clicking a worn gear slot unequips it; the weapon slot is always worn.
        Registered as a `custom` button so it stays clickable + keyboard-focusable
        while keeping its own icon look (B121)."""
        filled = bool(slot.equipped_item_id)
        pygame.draw.rect(self.screen, CHAR_SLOT_BG, srect, border_radius=6)
        edge = CHAR_SLOT_FILLED_EDGE if filled else CHAR_SLOT_EMPTY_EDGE
        pygame.draw.rect(self.screen, edge, srect, width=2, border_radius=6)
        # B132: the slot always shows WHAT it is (its type abbreviation), the same
        # glyph empty and filled — never a clipped item name. Filled reads as worn
        # via the gold edge + a bright (rarity-coloured) glyph; the worn item's
        # name lives in the hover tooltip.
        glyph = character_slot_glyph(slot)
        if filled:
            color, tip = self.store_row_extras(slot.equipped_item_id, selling=True)
            text_color = color or TEXT
        else:
            text_color, tip = TEXT_DIM, None
        gs = self.font_sm.render(glyph, True, text_color)
        self.screen.blit(gs, gs.get_rect(center=srect.center))
        if slot.id == "weapon":
            on_click = (lambda: None)          # the weapon is always worn; no unequip
        elif filled:
            on_click = (lambda sid=slot.id: self.unequip_gear_from_slot(sid))
        else:
            on_click = (lambda: None)          # empty slot: equip happens from inventory
        # The slot id rides as the (unrendered) label so a custom button stays
        # identifiable — the _draw_buttons custom branch never paints it.
        self._add_button(srect, slot.id, on_click, enabled=True, tooltip=tip,
                         focus_section="slots", custom=True)

    def _character_inventory_rows(self, snap):
        """The full owned inventory for the right zone: (item_id, name, color,
        tooltip, on_click, restricted, value). Weapons/gear are click-to-equip;
        consumables/misc are shown (rarity-coloured, with tooltip) but inert here
        — equipping is what this screen is for."""
        rows = []
        for w in snap.weapons:
            value, color, tip = self.inventory_row_extras(w.id)
            rows.append((w.id, w.name, color, tip,
                         (lambda wid=w.id: self.equip_weapon(wid)), not w.equippable, value))
        for g in snap.gear:
            value, color, tip = self.inventory_row_extras(g.id)
            rows.append((g.id, g.name, color, tip,
                         (lambda gid=g.id: self.equip_gear_from_inventory(gid)),
                         not g.equippable, value))
        items = self.engine.content.items
        for item_id, count in sorted(self.engine.player.inventory.consumables.items()):
            if count <= 0:
                continue
            value, color, tip = self.inventory_row_extras(item_id)
            rows.append((item_id, items[item_id].name, color, tip, None, False, value))
        return rows

    def _draw_character_inventory(self, rect, snap) -> None:
        """Right zone: every owned item, rarity-coloured, in a scrollable list
        (the B113 scroll helper). Rows within the viewport become menu buttons."""
        self.screen.blit(self.font_sm.render("Inventory", True, TEXT_DIM), (rect.x, rect.y - 22))
        rows = self._character_inventory_rows(snap)
        if not rows:
            self.screen.blit(self.font.render(T.INV_NONE, True, TEXT_DIM), (rect.x, rect.y + 6))
            return
        row_h = 30
        scroll = self._menu_scrolls["character_inv"]
        scroll.configure(len(rows) * row_h, rect.height)
        y0 = scroll.y(rect.y)
        for i, (item_id, name, color, tip, on_click, restricted, value) in enumerate(rows):
            r = pygame.Rect(rect.x, y0 + i * row_h, rect.width, row_h - 2)
            if not rect.contains(r):
                continue
            self._add_button(r, name, on_click, enabled=on_click is not None,
                             restricted=restricted, value=value, label_color=color,
                             tooltip=tip, focus_section="inventory")
        ui.draw_scroll_indicators(self.screen, self.font_sm, rect, scroll, row_h, TEXT_DIM)

    def _overlay_inventory(self, panel) -> None:
        """B40 S2: the menu spec applied. Left a bare category list (no "(N)"
        counters, empty ones dimmed-but-selectable), right the items as uniform
        rows — name in rarity colour, action-relevant figure (count/damage/
        'equipped') right-aligned, stats and prices on a >1 s hover. The old
        header strip is gone, which also removes the playtest text collision."""
        content = self._content_rect(panel)
        counts = self.inventory_counts()
        if self.inventory_category not in counts:
            self.inventory_category = "consumables"

        gap = 20
        overview_w = min(240, content.width // 2)
        overview = pygame.Rect(content.x, content.y, overview_w, content.height)
        items_rect = pygame.Rect(overview.right + gap, content.y,
                                 content.right - overview.right - gap, overview.height)

        row_h = max(22, min(30, overview.height // max(1, len(T.INV_CATEGORY_LABELS))))
        for i, (key, label) in enumerate(T.INV_CATEGORY_LABELS.items()):
            rect = pygame.Rect(overview.x, overview.y + i * row_h, overview.width, row_h - 2)
            marker = "> " if key == self.inventory_category else "  "
            self._add_button(rect, f"{marker}{label}",
                             (lambda k=key: self.open_inventory_category(k)), True,
                             restricted=not counts.get(key, 0),
                             focus_section="categories")

        rows = self.inventory_category_items(self.inventory_category)
        if not rows:
            self.screen.blit(self.font.render(T.INV_NONE, True, TEXT_DIM),
                             (items_rect.x, items_rect.y + 6))
            return
        max_rows = max(1, items_rect.height // 34)
        for i, (item_id, name, on_click, enabled) in enumerate(rows[:max_rows]):
            rect = pygame.Rect(items_rect.x, items_rect.y + i * 34, items_rect.width, 30)
            value, color, tip = self.inventory_row_extras(item_id)
            # Inert rows (miscellaneous) stay dimmed and unclickable but keep
            # their tooltip, so junk still explains itself on hover.
            self._add_button(rect, name, on_click, enabled and on_click is not None,
                             value=value, label_color=color, tooltip=tip,
                             focus_section="items")
        if len(rows) > max_rows:
            self.screen.blit(self.font_sm.render(f"v {len(rows) - max_rows} more v", True, TEXT_DIM),
                             (items_rect.x + 8, items_rect.bottom - 18))

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
            # B89: hovering a skill row explains what the skill does.
            tip = ui.Tooltip(title=skill.name, lines=skill_effect_lines(skill))
            self._add_button(rect, label, (lambda sid=skill.id, eq=is_eq: self.toggle_skill(sid, eq)), enabled,
                             tooltip=tip, focus_section="skills")

        self.screen.blit(self.font_sm.render(
            self._fit_text(T.talents_hint(eng.player.talent_points), middle.width, self.font_sm),
            True, WARN), (middle.x, middle.y))
        selected = self.selected_talent_node()
        # B105: sections per branch with a header row; cross-passives render
        # under their parent branch with a "requires" marker. The grouping is
        # the shared talent_text rule — tree data untouched.
        rows: list = []
        for branch, nodes in grouped_class_talents(eng.content, eng.player.player_class):
            rows.append(("header", branch, None))
            rows.extend(("node", branch, node) for node in nodes)
        max_rows = max(1, (middle.height - 32) // 32)
        y = middle.y + 30
        for kind, branch, node in rows[:max_rows]:
            if kind == "header":
                self.screen.blit(self.font_sm.render(
                    self._fit_text(branch_label(branch), middle.width, self.font_sm),
                    True, ACCENT), (middle.x, y + 6))
                y += 32
                continue
            # B106: compact status markers instead of [LEARNED]/[LOCKED]/
            # [CAN LEARN] prefixes — glyph + colour carry the same information
            # in a fraction of the width, so the NAME fits.
            glyph, role = ui.status_marker(talent_status(eng, node))
            color = {"good": GOOD, "accent": ACCENT, "dim": TEXT_DIM}.get(role)
            rank = talent_rank_label(eng, node)
            rect = pygame.Rect(middle.x, y, middle.width, 26)
            marker = "> " if selected is not None and node.id == selected.id else "  "
            rank_suffix = f" {rank}" if rank else ""
            if node.branch != branch and node.requires in eng.content.talents:
                cross = f" ↳ requires {eng.content.talents[node.requires].name}"
            else:
                cross = ""
            label = f"{marker}{glyph} {node.name}{rank_suffix}{cross}"
            self._add_button(rect, label, (lambda nid=node.id: self.select_talent(nid)), True,
                             label_color=color, focus_section="talents")
            y += 32

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
        self._add_button(learn_rect, f"{verb} selected", self.learn_selected_talent, can_allocate,
                         value="1 point",
                         focus_section="detail")

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
            # B106: the rank is a right-aligned value, not "(rank 1/3)" in the label.
            self._add_button(rect, f"{verb}: {node.name}",
                             (lambda nid=node.id: self.learn_talent(nid)), points > 0,
                             value=rank)

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
        viewport = pygame.Rect(panel.x + 12, panel.y + 88,
                               panel.width - 24, panel.height - 154)
        row_h = 46
        controls_rows = (len(T.CONTROLS) + 1) // 2
        content_height = len(user_settings.OPTIONS) * row_h + 26 + controls_rows * 26
        scroll = self._menu_scrolls["settings"]
        scroll.configure(content_height, viewport.height)
        y = scroll.y(viewport.y)
        self._music_slider_rect = None
        old_clip = self.screen.get_clip()
        self.screen.set_clip(viewport)
        # B92: rows come from THE shared definition (user_settings.OPTIONS) so
        # this overlay and the start menu can never diverge; only the live
        # apply-side effects are surface-specific.
        for option in user_settings.OPTIONS:
            key = option["key"]
            label = user_settings.option_label(option, self._setting_value(key))
            # B106: no "(F11)" suffixes — the Controls table below owns the keys.
            if option["kind"] == "slider":
                if viewport.contains(pygame.Rect(panel.x + 20, y, panel.width - 40, 38)):
                    self._draw_music_slider(panel, y)   # B69: 0-100, click or drag, live
                y += 54
                continue
            if option["kind"] == "steps":
                left = pygame.Rect(panel.x + 20, y, 180, 38)
                right = pygame.Rect(panel.x + 210, y, 180, 38)
                if viewport.contains(left) and viewport.contains(right):
                    self._add_button(left, f"{label} -", (lambda k=key: self._cycle_setting(k, -1)))
                    self._add_button(right, f"{label} +", (lambda k=key: self._cycle_setting(k, 1)))
            else:
                rect = pygame.Rect(panel.x + 20, y, panel.width - 40, 38)
                if viewport.contains(rect):
                    self._add_button(rect, label, (lambda k=key: self._cycle_setting(k, 1)))
            y += 46
        self.screen.blit(self.font_sm.render("Controls", True, ACCENT), (panel.x + 20, y))
        y += 26
        # B106: the Controls table — action dimmed left, key as a badge chip,
        # two columns (the shared ui helper; the mockup's layout).
        # Width reserves the bottom-right Back corner; row height keeps the
        # table inside the panel — text never spills outside its surface.
        ui.draw_controls_table(self.screen, self.font_sm, T.CONTROLS,
                               x=panel.x + 20, y=y, width=panel.width - 240,
                               action_color=TEXT_DIM, row_h=26)
        self.screen.set_clip(old_clip)
        ui.draw_scroll_indicators(self.screen, self.font_sm, viewport, scroll, row_h, TEXT_DIM)

    def _setting_value(self, key: str):
        """Current value for a shared-definition settings row (B92) — live
        runtime state where one exists, else the persisted value."""
        if key == "fullscreen":
            return self.fullscreen
        if key == "log_visible":
            return self.log_visible
        if key == "minimap":
            return self.show_minimap
        return self._settings.get(key, user_settings.DEFAULTS.get(key))

    def _cycle_setting(self, key: str, direction: int) -> None:
        """Apply a click on a shared-definition row with the surface-specific
        live effect (display toggle, log resize, persisted flag flips)."""
        if key == "fullscreen":
            self.toggle_fullscreen()
        elif key == "log_visible":
            self.resize_log(direction)
        elif key == "minimap":
            self.show_minimap = not self.show_minimap
            self._persist_settings()
        else:
            self._settings[key] = not bool(self._settings.get(key, user_settings.DEFAULTS.get(key)))
            user_settings.save(self._settings)

    def _draw_music_slider(self, panel: pygame.Rect, y: int) -> None:
        """B69: the music-volume slider row — a 0-100 bar the player clicks or
        drags (pygame_overworld.handle_events owns the mouse). The trough/fill
        redraws from the live setting, so the knob follows the drag; the rect
        is re-registered every frame for the hit test."""
        try:
            volume = max(0.0, min(1.0, float(self._settings.get("sound_music", 1.0))))
        except (TypeError, ValueError):
            volume = 1.0
        percent = int(round(volume * 100))
        label = self.font.render(f"Music volume: {percent}", True, TEXT)
        self.screen.blit(label, (panel.x + 20, y + 8))
        bar = pygame.Rect(panel.x + 260, y + 10, min(420, panel.width - 320), 20)
        self._music_slider_rect = bar
        # B99 S2: the slider row is keyboard-focusable; left/right adjust ±5.
        slider = ui.FocusSlider(rect=bar, adjust=self.adjust_music_volume)
        self.focus.add("main", slider)
        if self.focus.focused() is slider:
            pygame.draw.rect(self.screen, ACCENT, bar.inflate(8, 8), width=2, border_radius=12)
        pygame.draw.rect(self.screen, (30, 34, 46), bar, border_radius=10)
        fill_w = int(bar.width * volume)
        if fill_w > 0:
            pygame.draw.rect(self.screen, ACCENT,
                             pygame.Rect(bar.x, bar.y, fill_w, bar.height), border_radius=10)
        pygame.draw.rect(self.screen, PANEL_EDGE, bar, width=1, border_radius=10)
        knob_x = bar.x + max(0, min(bar.width, fill_w))
        pygame.draw.circle(self.screen, TEXT, (knob_x, bar.centery), 12)
        pygame.draw.circle(self.screen, PANEL_EDGE, (knob_x, bar.centery), 12, width=1)

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
        back = pygame.Rect(panel.right - 170, panel.bottom - 54, 150, 40)
        self._add_button(back, T.BACK, lambda: setattr(self, "mode", "walk"), badge=T.BACK_KEY)
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
        self._add_button(pygame.Rect(panel.right - 170, panel.bottom - 54, 150, 40),
                         T.BACK, lambda: setattr(self, "mode", "tournaments"), badge=T.BACK_KEY)
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

    def _draw_travel_event(self) -> None:
        """B67: a travel event — title, flavour text and one button per choice.
        The core resolves the choice; the shell applies the returned result."""
        event = self.active_event
        if event is None:
            self.mode = "walk"
            return
        panel = self._overlay_panel(event.title)
        y = panel.y + 60
        for line in self._wrapped_lines_pixels(event.text, panel.width - 40, self.font_sm):
            self.screen.blit(self.font_sm.render(line, True, TEXT), (panel.x + 20, y))
            y += 22
        y += 12
        for choice in event.choices:
            affordable = choice.cost_gold <= self.engine.player.gold
            # B106: the cost is a right-aligned value, never "(20g)" in the label.
            self._add_button(pygame.Rect(panel.x + 20, y, panel.width - 40, 44), choice.label,
                             (lambda c=choice.id: self._resolve_travel_event(c)), affordable,
                             value=f"{choice.cost_gold}g" if choice.cost_gold else "")
            y += 52
        self._draw_buttons()

    def _resolve_travel_event(self, choice_id: str) -> None:
        from rpg_game.core import events as core_events
        event = self.active_event
        self.active_event = None
        self.mode = "walk"
        result = core_events.resolve_choice(self.engine.player, event, choice_id, self.engine.rng)
        if result.text:
            if result.gold_delta > 0:   # B100: an event payout lands on the Loot tab
                self.push_log(result.text, chatlog.loot_source_color("event"),
                              channel=chatlog.CHANNEL_LOOT)
            else:
                self.push_log(result.text, WARN if result.start_encounter else GOOD)
        if result.start_encounter:
            enemy = self.engine.create_encounter()
            if enemy is not None:
                self.start_battle(enemy)

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
