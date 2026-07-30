"""Render B135's quest surfaces into docs/nightly:
  b135b_notice_board.png       - the board with offers + a selected notice
  b135b_notice_board_active.png - a quest accepted and in progress, ready to hand in
  b135c_quest_log.png          - the quest log screen (Q)
  b135c_quest_tab.png          - the overworld chatbox with the Quest tab active
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from rpg_game.core import quests as core_quests  # noqa: E402
from rpg_game.core.game import GameEngine  # noqa: E402
from rpg_game.presentation.pygame_overworld import OverworldApp  # noqa: E402

SIZE = (980, 660)


def _app(engine):
    app = OverworldApp(engine=engine)
    app.display = pygame.Surface(SIZE)
    app.screen = pygame.Surface(SIZE)
    return app


def _engine():
    engine = GameEngine()
    engine.start_new_game("Hero", "fighter")
    return engine


def _save(app, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(app.screen, path)


def render_board(out: Path) -> None:
    engine = _engine()
    app = _app(engine)
    app.open_overlay("notice_board")
    app.board_selection = "spine_mork_skog"     # a mid-list notice, so both zones show
    app.draw()
    _save(app, out)


def render_board_active(out: Path) -> None:
    """A board with work in progress: one quest handed-in-ready, one part-way."""
    engine = _engine()
    engine.accept_quest("spine_cainos")
    for _ in range(6):
        core_quests.note_kill(engine.player, engine.content, engine.content.quests,
                              "giant_rat", "cainos")
    engine.accept_quest("side_rat_pelts")
    engine.player.inventory.add_consumable("rat_pelt", 2)
    app = _app(engine)
    app.open_overlay("notice_board")
    app.board_selection = "spine_cainos"
    app.draw()
    _save(app, out)


def _progressed_engine():
    """A save mid-way through several quests, for the log + tab shots."""
    engine = _engine()
    engine.accept_quest("spine_cainos")
    for _ in range(4):
        core_quests.note_kill(engine.player, engine.content, engine.content.quests,
                              "giant_rat", "cainos")
    engine.accept_quest("side_rat_pelts")
    engine.player.inventory.add_consumable("rat_pelt", 3)
    engine.accept_quest("side_chests")
    core_quests.note_chest_opened(engine.player, engine.content, engine.content.quests)
    engine.accept_quest("spine_mork_skog")
    for _ in range(8):
        core_quests.note_kill(engine.player, engine.content, engine.content.quests,
                              "dire_wolf", "mork_skog")
    return engine


def render_quest_log(out: Path) -> None:
    engine = _progressed_engine()
    app = _app(engine)
    app.open_overlay("quest_log")
    app.draw()
    _save(app, out)


def render_quest_tab(out: Path) -> None:
    engine = _progressed_engine()
    app = _app(engine)
    app._drain_quest_events()      # the accept/progress/ready lines land on the tab
    app.log_tab = "quest"
    app.draw()
    _save(app, out)


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    root = Path(__file__).resolve().parents[2] / "docs" / "nightly"
    render_board(root / "b135b_notice_board.png")
    render_board_active(root / "b135b_notice_board_active.png")
    render_quest_log(root / "b135c_quest_log.png")
    render_quest_tab(root / "b135c_quest_tab.png")
    pygame.quit()
    print("wrote b135b_notice_board{,_active}.png + b135c_quest_{log,tab}.png")


if __name__ == "__main__":
    main()
