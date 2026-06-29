"""Town building-cluster template (B8).

A town renders as a packed hub around a plaza: building sprites with their entrance
facing IN toward a cobble wayfinding net. The template is ANCHORED to the town's
tile (offsets are relative) so the whole hub moves with the town — Slice 1 refines
the start town (burg_5, a hub); Slice 2 reuses the model on the others.

Each entry is (building_id, dx, dy, fw, fh, facing):
- footprint = an fw x fh tile collision rectangle, top-left at (anchor + (dx,dy)).
- facing = which 3/4 view to draw so the door points inward:
    "front" door faces south (house NORTH of plaza),
    "back"  door faces north (house SOUTH of plaza; cobble leads round),
    "q1"    door/sign faces WEST  (house EAST of plaza),
    "q2"    door/sign faces EAST  (house WEST of plaza).
The anchor tile itself is the walkable PLAZA (menu trigger) and is never built on.

Pure data + tile math (no pygame) so collision/cobble/anchor rules are unit-tested.
"""

from collections import deque

# burg_5 hub: an L around the courtyard at the anchor (the core river is just SW,
# so the L grows N + E and the open courtyard sits in the SW inner corner). The
# precise rule: no building's scaled sprite may overlap ANOTHER building's entrance
# tile. That means nothing stands SOUTH of a front house (its door faces south into
# the open courtyard) and nothing stands WEST of a q1 house (its door faces west
# into the courtyard) — so the N row is all fronts and the E column is all q1, with
# the courtyard left clear between them. church=respawn, inn=Rest, shop=basics/junk,
# blacksmith=weapons, barracks=armour, town_hall=board.
CLUSTER_TEMPLATE = [
    ("church",    -2, -5, 2, 2, "front"),   # N row — door south into the courtyard
    ("town_hall",  1, -5, 3, 2, "front"),   # N row
    ("inn",        6, -3, 3, 2, "q1"),      # E column — door west into the courtyard
    ("blacksmith", 6, -1, 3, 2, "q1"),      # E column
    ("barracks",   6,  1, 3, 2, "q1"),      # E column
    ("shop",       6,  3, 3, 2, "q1"),      # E column
]


def building_footprint(anchor, dx, dy, fw, fh):
    ax, ay = anchor
    return {(ax + dx + x, ay + dy + y) for x in range(fw) for y in range(fh)}


def cluster_footprints(anchor):
    """All solid collision tiles for the hub. The plaza (anchor) is never included."""
    cells = set()
    for _bid, dx, dy, fw, fh, _facing in CLUSTER_TEMPLATE:
        cells |= building_footprint(anchor, dx, dy, fw, fh)
    return cells


def cluster_buildings(anchor):
    """Render placements: (building_id, fx, fy, fw, fh, facing). (fx,fy) = footprint
    top-left; the sprite is drawn bottom-aligned to row (fy + fh)."""
    ax, ay = anchor
    return [(bid, ax + dx, ay + dy, fw, fh, facing)
            for bid, dx, dy, fw, fh, facing in CLUSTER_TEMPLATE]


def entrance_tile(anchor, dx, dy, fw, fh, facing):
    """The walkable tile a building's door opens onto (cobble leads here)."""
    ax, ay = anchor
    fx, fy = ax + dx, ay + dy
    if facing == "front":            # door south
        return (fx + fw // 2, fy + fh)
    if facing == "back":             # door north
        return (fx + fw // 2, fy - 1)
    if facing == "q1":               # door west
        return (fx - 1, fy + fh // 2)
    return (fx + fw, fy + fh // 2)    # q2: door east


def _bfs(src, dst, blocked, bound):
    minx, maxx, miny, maxy = bound
    seen = {src: None}
    q = deque([src])
    while q:
        c = q.popleft()
        if c == dst:
            break
        for nx, ny in ((c[0] + 1, c[1]), (c[0] - 1, c[1]), (c[0], c[1] + 1), (c[0], c[1] - 1)):
            n = (nx, ny)
            if minx <= nx <= maxx and miny <= ny <= maxy and n not in seen and n not in blocked:
                seen[n] = c
                q.append(n)
    if dst not in seen:
        return []
    path, c = [], dst
    while c is not None:
        path.append(c)
        c = seen[c]
    return path


def cobble_network(anchor, avoid=frozenset()):
    """Walkable cobble cells: a 3x3 plaza around the anchor plus a routed spur from
    the plaza to each building's entrance. Never overlaps a footprint (cobble sits
    on the streets/plaza, not under houses) nor any cell in `avoid` (e.g. water /
    other blocked terrain the caller passes in)."""
    ax, ay = anchor
    foot = cluster_footprints(anchor)
    block = set(foot) | set(avoid)
    plaza = {(ax + dx, ay + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - block
    net = set(plaza)
    xs = [x for x, _y in foot] + [ax]
    ys = [y for _x, y in foot] + [ay]
    bound = (min(xs) - 2, max(xs) + 2, min(ys) - 2, max(ys) + 2)
    for _bid, dx, dy, fw, fh, facing in CLUSTER_TEMPLATE:
        ent = entrance_tile(anchor, dx, dy, fw, fh, facing)
        if ent in avoid:
            continue
        net |= set(_bfs(anchor, ent, block, bound))
        net.add(ent)
    return net
