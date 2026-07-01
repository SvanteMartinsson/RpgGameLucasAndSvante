"""Shared menu-UI primitives for the pygame screens (overworld + battle).

SLICE 1 of the menu program: the foundation the 7-point menu spec builds on. It
supplies ONE Button (a superset of the old per-screen dataclasses), a hover
timer + tooltip renderer, and a reusable menu-row renderer. Pure pygame
rendering + geometry — NO game rules here. Screens keep owning their own event
loops and button lists; this module only provides the widgets they share.

This slice introduces the primitives WITHOUT changing menu content — the
inventory/shop/character/creation apply-slices adopt them later.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame


# --- unified Button --------------------------------------------------------
@dataclass
class Button:
    """The single button both screens use — the superset of the two old ones:

    - ``restricted``: overworld's "clickable but sperred-looking" state (a
      level-locked row still fires so the player gets a "needs level N" reason).
    - ``hotkey`` / ``sublabel``: battle's keyboard trigger + optional secondary
      label.

    ``on_click`` is usually a zero-arg callable, but the start menu stores a
    plain string result there, so it is typed permissively (``object``).
    """

    rect: "pygame.Rect"
    label: str
    on_click: object
    enabled: bool = True
    restricted: bool = False
    hotkey: str = ""
    sublabel: str = ""
