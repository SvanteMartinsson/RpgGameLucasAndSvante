"""B39: the battle chatbox shows ONE set of battle-end lines. The core still
returns its narration ("X was defeated." / "Gained N XP and M gold." /
"X dropped: ...") for tests, but the log surfaces only the short presentation
lines ("Victory!" / "+N XP" / "+N gold" / "Loot: item") with no dups. Rarity is
now shown by the loot line's COLOUR, not a "[rarity]" suffix.
"""

import collections
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

try:
    import pygame
    from rpg_game.core import combat
    from rpg_game.core.entities import LootDrop
    from rpg_game.core.game import GameEngine
    from rpg_game.presentation.pygame_battle import BattleApp
    from rpg_game.presentation import chatlog

    DEPS_OK = True
except Exception:  # pragma: no cover - import guard
    DEPS_OK = False


@unittest.skipUnless(DEPS_OK, "pygame/pytmx not installed")
class ChatboxDedupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _victory_battle(self):
        engine = GameEngine()
        engine.start_new_game("Hero", "fighter")
        enemy = engine.content.enemies["giant_rat"].create_enemy()
        log = collections.deque()
        battle = BattleApp(engine=engine, enemy=enemy, standalone=False, event_log=log)
        log.clear()  # drop the "a Giant Rat appears" line
        return battle, enemy, log

    def _victory_result(self, enemy, drop=None):
        # The exact tail core appends in game._handle_victory, plus a bit of
        # combat narration that must survive the filter.
        events = [
            f"{enemy.name} takes 6 physical damage.",
            f"{enemy.name} was defeated.",
            "Gained 5 XP and 7 gold.",
        ]
        if drop is not None:
            events.append(f"{enemy.name} dropped: {drop.name} [{drop.rarity}] (tier {drop.tier})!")
        return combat.CombatTurnResult(
            outcome="victory", events=events, xp_gained=5, gold_gained=7, loot_drop=drop,
        )

    def test_drop_logs_one_loot_line_and_no_dropped_line(self):
        battle, enemy, log = self._victory_battle()
        drop = LootDrop(item_id="hp_potion", name="Healing Potion", kind="consumable",
                        tier=1, rarity="common")
        battle._consume_result(self._victory_result(enemy, drop))
        texts = [t for t, _c in log]

        loot = [(t, c) for t, c in log if t.startswith("Loot:")]
        self.assertEqual(len(loot), 1, texts)                       # exactly one Loot line
        loot_text, loot_color = loot[0]
        self.assertNotIn("[", loot_text)                            # no "[common]" text
        self.assertEqual(loot_color, chatlog.rarity_color("common"))  # rarity shown by colour
        self.assertFalse([t for t in texts if "dropped:" in t], texts)  # verbose line gone

    def test_battle_end_is_not_doubled(self):
        battle, enemy, log = self._victory_battle()
        battle._consume_result(self._victory_result(enemy, drop=None))
        texts = [t for t, _c in log]

        self.assertEqual(texts.count("Victory!"), 1, texts)
        self.assertEqual(texts.count("+5 XP"), 1, texts)
        self.assertEqual(texts.count("+7 gold"), 1, texts)
        # Core narration is suppressed in the log (still returned by the engine).
        self.assertNotIn(f"{enemy.name} was defeated.", texts)
        self.assertNotIn("Gained 5 XP and 7 gold.", texts)
        # ...but ordinary combat narration is preserved.
        self.assertTrue(any("physical damage" in t for t in texts), texts)


if __name__ == "__main__":
    unittest.main()
