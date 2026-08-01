"""B139c: render the dialogue screen for review.

Writes docs/nightly/b139_dialogue_<state>_<moment>.png for Mirr in BOTH states
(warm and cold), at both moments that matter:

  typing  — a line being revealed. The portrait runs the TALK sheet here, and the
            placeholder's mouth line moves, so the animation seam is visibly wired
            even with no art.
  choices — the node's lines exhausted and the choice grid up, including a
            DIMMED choice with its reason (B112), so the gated state is reviewable
            and not just tested.

Mirr's four sheets landed 2026-08-01, so these render her REAL portrait: the
6-frame talk strip while a line types out, the 4-frame idle strip when it stands
still. The placeholder path is still there for any character whose art has not
arrived; it just no longer applies to her.
"""

from __future__ import annotations

import os
import random
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
from PIL import Image  # noqa: E402

from rpg_game.core import characters  # noqa: E402
from rpg_game.core.data_loader import load_content  # noqa: E402
from rpg_game.core.game import GameEngine  # noqa: E402
from rpg_game.presentation import pygame_dialogue as dialogue_screen  # noqa: E402

STATES = (
    ("warm", set()),
    ("cold", {"mirr_bereaved"}),
)


def _shot(app) -> Image.Image:
    app.draw()
    raw = pygame.image.tostring(app.screen, "RGB")
    return Image.frombytes("RGB", app.screen.get_size(), raw)


def render(out_dir: Path) -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    out_dir.mkdir(parents=True, exist_ok=True)
    content = load_content()
    written = []

    for state_id, flags in STATES:
        engine = GameEngine(content=content, rng=random.Random(0))
        engine.start_new_game("Hero", "fighter")
        engine.player.quest_flags |= flags
        mirr = engine.character_at("burg_5", "inn")
        app = dialogue_screen.DialogueApp(engine, mirr)
        assert app.state.id == state_id, (app.state.id, state_id)

        # 1) mid-line: the talk sheet / moving placeholder mouth.
        for _ in range(28):
            app.update()
        assert app.is_typing, "expected to still be typing"
        path = out_dir / f"b139_dialogue_{state_id}_typing.png"
        _shot(app).save(path)
        sheet, count = app.current_portrait()
        frames = dialogue_screen.portrait_frames(sheet, count)
        written.append((path, f"talk sheet {sheet} x{count} -> "
                              f"{'real art' if frames else 'PLACEHOLDER'}, "
                              f"frame {app.portrait_frame_index()}"))

        # 2) the choice grid, with the history filled in above it.
        guard = 0
        while not app.conversation.awaiting_choice() and app.running and guard < 40:
            app.skip_typing()
            app.advance()
            guard += 1
        assert app.conversation.awaiting_choice(), "never reached the choices"
        for _ in range(4):
            app.update()
        path = out_dir / f"b139_dialogue_{state_id}_choices.png"
        image = _shot(app)
        image.save(path)
        blocked = [(b.label, b.sublabel) for b in app.buttons if b.restricted]
        written.append((path, f"choices: {len(app.buttons)} cells, "
                              f"dimmed: {blocked or 'none'}"))

    missing = characters.missing_portrait_sheets(content.characters,
                                                dialogue_screen.PORTRAIT_DIR)
    problems = characters.portrait_sheet_problems(content.characters,
                                                 dialogue_screen.PORTRAIT_DIR)
    print(f"sheets missing: {missing or 'none'} · frame-count problems: "
          f"{problems or 'none'}")
    for path, note in written:
        print(f"wrote {path}  [{note}]")
    pygame.quit()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    render(root / "docs" / "nightly")
