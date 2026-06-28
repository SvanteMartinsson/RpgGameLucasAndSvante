"""Town building-cluster template (B8).

A town renders as a packed cluster of building sprites on a plaza instead of a
flat marker. The template is ANCHORED to the town's tile (offsets are relative),
so the whole cluster moves with the town — Slice 1 instantiates it on the start
town (burg_5); Slice 2 will reuse it on the others.

Each entry is (building_id, dx, dy, fw, fh): the building's collision footprint is
an fw x fh tile rectangle whose top-left is (anchor_x + dx, anchor_y + dy). The
128px sprite is drawn anchored on the footprint's bottom edge (the roof overhangs
upward, like a tree crown; the player is drawn over it). The anchor tile itself is
the walkable PLAZA that triggers the town menu and is never covered by a building.

Pure data + tile math — no pygame — so collision/anchor rules are unit-testable.
"""

# Packed two-row cluster placed NORTH + EAST of the plaza (the start town's river
# runs to the south-west, so the cluster grows away from it). 1-tile streets sit
# between the footprints (columns/rows left out of the rectangles below).
CLUSTER_TEMPLATE = [
    ("church",     1, -4, 3, 2),   # respawn  (top-left)
    ("inn",        5, -4, 3, 2),   # Rest     (top-right)
    ("shop",       1, -1, 3, 2),   # Store    (bottom-left)
    ("town_hall",  5, -1, 3, 2),   # flavor   (bottom-right)
    ("cottage",    9, -3, 2, 2),   # flavor   (east)
]


def building_footprint(anchor, dx, dy, fw, fh):
    ax, ay = anchor
    return {(ax + dx + x, ay + dy + y) for x in range(fw) for y in range(fh)}


def cluster_footprints(anchor):
    """All solid collision tiles for the cluster anchored at `anchor` (a town tile).
    The anchor (plaza) tile is never included."""
    cells = set()
    for _bid, dx, dy, fw, fh in CLUSTER_TEMPLATE:
        cells |= building_footprint(anchor, dx, dy, fw, fh)
    return cells


def cluster_buildings(anchor):
    """Render placements: (building_id, fx, fy, fw, fh) where (fx, fy) is the
    footprint's top-left tile. The sprite is drawn bottom-aligned to (fy + fh)."""
    ax, ay = anchor
    return [(bid, ax + dx, ay + dy, fw, fh) for bid, dx, dy, fw, fh in CLUSTER_TEMPLATE]
