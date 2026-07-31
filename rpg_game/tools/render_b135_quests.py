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
    """A save mid-way through several quests, for the log + tab shots. Returns
    (engine, quest_lines) — the lines the hooks produced, so the Quest-tab shot
    shows the real variety (accepted / progress milestone / ready to hand in)."""
    engine = _engine()
    lines: list[str] = []

    def kill(enemy_id, zone, times=1):
        for _ in range(times):
            lines.extend(core_quests.note_kill(engine.player, engine.content,
                                               engine.content.quests, enemy_id, zone))

    engine.accept_quest("spine_cainos")
    kill("giant_rat", "cainos", 4)
    engine.accept_quest("side_rat_pelts")
    engine.player.inventory.add_consumable("rat_pelt", 3)
    engine.accept_quest("side_chests")
    lines.extend(core_quests.note_chest_opened(engine.player, engine.content,
                                              engine.content.quests))
    engine.accept_quest("spine_mork_skog")
    kill("dire_wolf", "mork_skog", 8)
    return engine, lines


def render_quest_log(out: Path) -> None:
    engine, _lines = _progressed_engine()
    app = _app(engine)
    app.open_overlay("quest_log")
    app.draw()
    _save(app, out)


def render_quest_tab(out: Path) -> None:
    from rpg_game.presentation import chatlog

    engine, lines = _progressed_engine()
    app = _app(engine)
    app._drain_quest_events()      # the accepted lines the engine queued
    for line in lines:             # ... plus the hooks' progress/ready lines
        app.push_log(line, chatlog.QUEST, channel=chatlog.CHANNEL_QUEST)
    app.log_tab = "quest"
    app.draw()
    _save(app, out)


def render_bounty_board(out: Path) -> None:
    """B135e: the bounty section, with one bounty already under way."""
    engine = _engine()
    bounty = engine.bounty_quests()[1]
    engine.accept_quest(bounty.id)
    for _ in range(max(1, bounty.objective.count // 2)):
        core_quests.note_kill(engine.player, engine.content, engine.all_quests(),
                              bounty.objective.target, bounty.zone)
    app = _app(engine)
    app.open_overlay("notice_board")
    app.board_selection = engine.bounty_quests()[0].id
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
    render_bounty_board(root / "b135e_bounty_board.png")
    pygame.quit()
    print("wrote b135b_notice_board{,_active}.png + b135c_quest_{log,tab}.png "
          "+ b135e_bounty_board.png")


if __name__ == "__main__":
    main()
