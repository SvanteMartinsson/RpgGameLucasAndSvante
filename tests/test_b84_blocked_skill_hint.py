"""B84: a tome-learned skill that is dimmed in battle must show WHY, compactly.

Repro from Lucas's playtest: a fighter learns holy_strike from a tome and
equips it; in battle the row is dimmed. Root cause is the (intended)
requires_weapon_category gating — the bug was that the verbose core sentence
overflowed the compact button, so the row read as "dimmed for no reason".
Locks: the row is disabled with a short readable hint, mana/cooldown hints are
compact too, and button labels never render wider than their rect.
Skips without pygame/pytmx.
"""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.core.game import GameEngine
    from rpg_game.core.view import build_snapshot
    from rpg_game.presentation import pygame_battle as pb

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class BlockedSkillHintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _fighter_with_holy_strike(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        engine.player.learned_skill_ids = (*engine.player.learned_skill_ids, "holy_strike")
        engine.equip_skill("holy_strike")
        enemy = engine.content.enemies["cave_bear"].create_enemy()
        return engine, pb.BattleApp(engine=engine, enemy=enemy, standalone=False)

    def _skill_opts(self, battle):
        battle.open_submenu("skill")
        snapshot = build_snapshot(battle.engine)
        return {opt[1]: opt for opt in battle._submenu_options(snapshot)}

    def test_tome_skill_with_wrong_weapon_is_dimmed_with_readable_hint(self):
        engine, battle = self._fighter_with_holy_strike()
        opts = self._skill_opts(battle)
        label, _skill_id, enabled, sub = opts["holy_strike"]
        self.assertFalse(enabled)
        self.assertEqual(sub, "needs magic weapon")

    def test_mana_hint_shows_current_vs_cost(self):
        engine, battle = self._fighter_with_holy_strike()
        engine.player.mana = 2
        opts = self._skill_opts(battle)
        _label, _skill_id, enabled, sub = opts["holy_strike"]
        self.assertFalse(enabled)
        self.assertEqual(sub, "Mana 2/7")

    def test_mana_hint_is_its_own_untruncated_button_line(self):
        engine, battle = self._fighter_with_holy_strike()
        engine.player.mana = 2
        battle.open_submenu("skill")
        battle.draw()
        button = next(b for b in battle.buttons if b.label == "Holy Strike")
        self.assertEqual(button.sublabel, "Mana 2/7")
        from rpg_game.presentation import ui
        self.assertEqual(
            ui.fit(button.sublabel, battle.font_sm, button.rect.width - 12),
            button.sublabel,
        )

    def test_cooldown_hint_shows_rounds_remaining(self):
        engine, battle = self._fighter_with_holy_strike()
        # give the fighter a matching weapon so only the cooldown blocks
        engine.player.equipped_weapon_id = next(
            w.id for w in engine.content.weapons.values() if w.category == "magic"
        )
        engine.player.cooldowns["holy_strike"] = 2
        opts = self._skill_opts(battle)
        _label, _skill_id, enabled, sub = opts["holy_strike"]
        self.assertFalse(enabled)
        self.assertEqual(sub, "cooldown 2")

    def test_button_labels_are_fitted_inside_their_rects(self):
        engine, battle = self._fighter_with_holy_strike()
        battle.open_submenu("skill")
        battle.draw()
        for button in battle.buttons:
            from rpg_game.presentation import ui

            fitted = ui.fit(button.label, battle.font_sm, button.rect.width - 12)
            self.assertLessEqual(
                battle.font_sm.size(fitted)[0], button.rect.width - 12
            )


if __name__ == "__main__":
    unittest.main()
