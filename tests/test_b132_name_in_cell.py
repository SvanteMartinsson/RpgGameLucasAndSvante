"""B132: text-in-cell consistency.

(a) A battle skill whose name does not fit its square cell gets a hover/focus
    tooltip with the FULL name (+ cost) instead of relying on a bare "...".
(b) A character equip slot shows its slot-TYPE glyph (Head/Chest/Ring) the same
    whether empty or filled — never a clipped item name; the worn item's name
    lives in the slot's hover tooltip.

Skips without pygame.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame

    from rpg_game.core.game import GameEngine
    from rpg_game.core.view import build_snapshot
    from rpg_game.presentation import ui
    from rpg_game.presentation import pygame_battle as pb
    from rpg_game.presentation.overworld_overlays import character_slot_glyph
    from rpg_game.presentation.pygame_overworld import OverworldApp

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class SkillCellTooltipTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _battle(self, skills):
        engine = GameEngine()
        engine.start_new_game("Hero", "rogue")
        engine.player.learned_skill_ids = ("evasion", "riposte")
        engine.player.equipped_skill_ids = skills
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        battle = pb.BattleApp(engine=engine, enemy=enemy, standalone=False)
        battle.open_submenu("skill")
        battle.draw()
        return battle

    def test_long_skill_name_registers_full_name_tooltip(self):
        battle = self._battle(("deadly_precision", "rupture", "evasion", "riposte"))
        full = next(s.name for s in build_snapshot(battle.engine).skills
                    if s.id == "deadly_precision")
        # the cell's name is clipped in-square, so a tooltip carries the full name
        cell = next(b for b in battle.buttons if b.custom and b.label == full)
        tip = battle._skill_cell_tooltip(cell)
        self.assertIsNotNone(tip, "clipped skill name registered no tooltip")
        self.assertEqual(tip.title, full)
        # and it is registered as a live hover zone on the cell rect
        titles = [p.title for _r, p in battle.hover._zones if isinstance(p, ui.Tooltip)]
        self.assertIn(full, titles)

    def test_esc_cell_has_no_tooltip(self):
        battle = self._battle(("deadly_precision", "rupture", "evasion", "riposte"))
        back = next(b for b in battle.buttons if b.custom and b.label == "Back")
        self.assertIsNone(battle._skill_cell_tooltip(back))

    def test_focused_clipped_cell_tooltip_available_without_mouse(self):
        # The focus fallback in draw() uses the same helper; focusing the clipped
        # cell yields a tooltip even though no mouse dwelt on it.
        battle = self._battle(("deadly_precision", "rupture", "evasion", "riposte"))
        full = next(s.name for s in build_snapshot(battle.engine).skills
                    if s.id == "deadly_precision")
        focused = next(b for b in battle.buttons if b.custom and b.label == full)
        for si, (_name, items) in enumerate(battle.focus._sections):
            if focused in items:
                battle.focus.section, battle.focus.index = si, items.index(focused)
        self.assertIsNotNone(battle._skill_cell_tooltip(battle.focus.focused()))


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class CharacterSlotGlyphTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        self.app = OverworldApp(engine=engine)
        self.app.display = pygame.Surface((980, 660))
        self.app.screen = pygame.Surface((980, 660))
        self.eng = self.app.engine
        self.app.overlay = "character"

    def _chest_slot(self):
        return next(s for s in build_snapshot(self.eng).equipment_slots
                    if s.id == "chest")

    def test_filled_slot_glyph_is_the_type_not_the_item_name(self):
        self.eng.player.owned_gear_ids = ("padded_vest",)
        self.eng.equip_gear("padded_vest", "chest")
        slot = self._chest_slot()
        self.assertTrue(slot.equipped_item_id)              # it IS filled
        self.assertEqual(character_slot_glyph(slot), "Chest")
        self.assertNotIn("Vest", character_slot_glyph(slot))

    def test_glyph_identical_empty_and_filled(self):
        empty = self._chest_slot()
        self.eng.player.owned_gear_ids = ("padded_vest",)
        self.eng.equip_gear("padded_vest", "chest")
        filled = self._chest_slot()
        self.assertEqual(character_slot_glyph(empty), character_slot_glyph(filled))

    def test_filled_slot_still_registers_item_name_tooltip(self):
        self.eng.player.owned_gear_ids = ("padded_vest",)
        self.eng.equip_gear("padded_vest", "chest")
        self.app.draw()
        titles = [p.title for _r, p in self.app.hover._zones
                  if isinstance(p, ui.Tooltip)]
        self.assertIn("Padded Vest", titles)


if __name__ == "__main__":
    unittest.main()
