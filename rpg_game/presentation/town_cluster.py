"""Town building-cluster template (B8).

A town renders as a packed hub around a plaza: building sprites with their entrance
facing IN toward a cobble wayfinding net. The template is ANCHORED to the town's
tile (offsets are relative) so the whole hub moves with the town — Slice 1 refines
the start town (burg_5, a hub); Slice 2 reuses the model on the others.

Each entry is (building_id, dx, dy, fw, fh, facing, flip):
- footprint = an fw x fh tile collision rectangle, top-left at (anchor + (dx,dy)).
- facing = which 3/4 view to draw so the door points inward:
    "front" door faces south (house NORTH of plaza),
    "back"  door faces north (house SOUTH of plaza; cobble leads round),
    "q1"    door/sign faces WEST  (house EAST of plaza),
    "q2"    door/sign faces EAST  (house WEST of plaza).
- flip = mirror the sprite horizontally at render so the drawn door/sign points the
  way `facing` says (the q-view art reads east by default; the E column flips it to
  face west, in toward the courtyard).
The anchor tile itself is the walkable PLAZA (menu trigger) and is never built on.

Pure data + tile math (no pygame) so collision/cobble/anchor rules are unit-tested.
"""

# burg_5 hub: an L around the courtyard at the anchor (the core river is just SW,
# so the L grows N + E and the open courtyard sits in the SW inner corner). The
# precise rule: no building's scaled sprite may overlap ANOTHER building's entrance
# tile. That means nothing stands SOUTH of a front house (its door faces south into
# the open courtyard) and nothing stands WEST of a q1 house (its door faces west
# into the courtyard) — so the N row is all fronts and the E column is all q1, with
# the courtyard left clear between them. church=respawn, inn=Rest, shop=basics/junk,
# blacksmith=weapons, barracks=armour, town_hall=board.
CLUSTER_TEMPLATE = [
    ("church",    -2, -5, 2, 2, "front", False),  # N row — door south into the courtyard
    ("town_hall",  1, -5, 3, 2, "front", False),  # N row
    ("inn",        7, -3, 3, 2, "q1", True),       # E column — door west (sprite mirrored)
    ("blacksmith", 7, -1, 3, 2, "q1", True),       # E column
    ("barracks",   7,  1, 3, 2, "q1", True),       # E column
    ("shop",       7,  3, 3, 2, "q1", True),       # E column
]


def building_footprint(anchor, dx, dy, fw, fh):
    ax, ay = anchor
    return {(ax + dx + x, ay + dy + y) for x in range(fw) for y in range(fh)}


def cluster_footprints(anchor):
    """All solid collision tiles for the hub. The plaza (anchor) is never included."""
    cells = set()
    for _bid, dx, dy, fw, fh, _facing, _flip in CLUSTER_TEMPLATE:
        cells |= building_footprint(anchor, dx, dy, fw, fh)
    return cells


def cluster_buildings(anchor):
    """Render placements: (building_id, fx, fy, fw, fh, facing, flip). (fx,fy) =
    footprint top-left; the sprite is drawn bottom-aligned to row (fy + fh), and
    mirrored horizontally when flip is set."""
    ax, ay = anchor
    return [(bid, ax + dx, ay + dy, fw, fh, facing, flip)
            for bid, dx, dy, fw, fh, facing, flip in CLUSTER_TEMPLATE]


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


def cluster_entrances(anchor):
    return {b[0]: entrance_tile(anchor, b[1] - anchor[0], b[2] - anchor[1], b[3], b[4], b[5])
            for b in cluster_buildings(anchor)}


def cobble_network(anchor, blocked=frozenset(), water=frozenset()):
    """A COMB of cobble, not a paved square: a courtyard at the anchor, a trunk to
    the N row and one to the E column, and a single spur to each door with grass
    between the teeth. It only grows toward the houses (N + E) and never lays a tile
    that sits on, or even borders, water — so no cobble points SW into the river.
    Returns the set of cobble cells."""
    ax, ay = anchor
    foot = cluster_footprints(anchor)
    waterset, blockset = set(water), set(blocked)

    def ok(c):
        if c in foot or c in blockset or c in waterset:
            return False
        x, y = c                      # never border water (no cobble toward the river)
        return not any((x + a, y + b) in waterset for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))

    def line(x0, y0, x1, y1, net):    # straight H/V run, only walkable cells
        if x0 == x1:
            for y in range(min(y0, y1), max(y0, y1) + 1):
                if ok((x0, y)):
                    net.add((x0, y))
        else:
            for x in range(min(x0, x1), max(x0, x1) + 1):
                if ok((x, y0)):
                    net.add((x, y0))

    ents = cluster_entrances(anchor)
    builds = cluster_buildings(anchor)
    front = [ents[b[0]] for b in builds if b[5] == "front"]
    east = [ents[b[0]] for b in builds if b[5] == "q1"]

    net = set()
    for c in ((ax, ay), (ax + 1, ay), (ax, ay - 1), (ax + 1, ay - 1)):  # small NE courtyard
        if ok(c):
            net.add(c)
    if front:                         # vertical trunk up to the N row, a spur per door
        line(ax, min(e[1] for e in front), ax, ay, net)
        for ex, ey in front:
            line(ax, ey, ex, ey, net)
            if ok((ex, ey)):
                net.add((ex, ey))
    if east:                          # trunk east + a vertical spine, a spur per door
        sx = min(e[0] for e in east) - 1
        line(ax, ay, sx, ay, net)
        line(sx, min(e[1] for e in east), sx, max(e[1] for e in east), net)
        for ex, ey in east:
            if ok((ex, ey)) and (sx, ey) in net:
                net.add((ex, ey))
    return net
