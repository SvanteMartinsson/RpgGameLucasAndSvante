#!/usr/bin/env python3
"""
beautify_overworld.py — Skriv om overworld-kartans GRUND- och VÄGG-lager:
  GRUND: tema-medvetet basgräs + variation + gles detalj + kullerstensvägar
         som binder ihop städer + grindar.
  VÄGG (kollision): border + grindar BEVARAS exakt (kantceller rörs aldrig).
         Interiörens platshållar-block ersätts med tematiska prop-HINDER
         (buskar, stenar, gravstenar) — utspridda, men aldrig på vägar,
         städer (+halo), startruta eller grind-närhet.
  Reachability-koll: flood-fill från start kräver att ALLA städer + grindar
         går att nå; annars kastas fel (då sänk DENSITY eller byt frö).
Walls-edge bevaras byte-identiskt; prop-tiles renderas OCH blockerar (kollision
= "finns en tile i walls"). Idempotent: kantceller läses men ändras aldrig.
"""
import json, random, re, collections

random.seed(7)
TMX = "rpg_game/data/maps/overworld.tmx"
ZONE = "rpg_game/data/maps/core_zone.json"
W, H = 48, 20
DENSITY = 0.06  # andel interiör-ground-celler som får ett hinder

GRASS_FIRSTGID = {"cainos": 3, "mork_skog": 1923, "cursed_mire": 771}
# prop-tilesets vi registrerar (firstgid, namn, source). 256 tiles, 16 kол.
PROP_TILESETS = [
    (2691, "cainos_plant",      "../../assets/props/cainos/TX Plant with Shadow.png"),
    (2947, "cainos_props",      "../../assets/props/cainos/TX Props with Shadow.png"),
    (3203, "mork_skog_plant",   "../../assets/props/generated/01-TX-Plant-with-Shadow__mork_skog.png"),
    (3459, "mork_skog_props",   "../../assets/props/generated/03-TX-Props-with-Shadow__mork_skog.png"),
    (3715, "cursed_mire_plant", "../../assets/props/generated/01-TX-Plant-with-Shadow__cursed_mire.png"),
    (3971, "cursed_mire_props", "../../assets/props/generated/03-TX-Props-with-Shadow__cursed_mire.png"),
]
PLANT_FIRSTGID = {"cainos": 2691, "mork_skog": 3203, "cursed_mire": 3715}
PROPS_FIRSTGID = {"cainos": 2947, "mork_skog": 3459, "cursed_mire": 3971}

# en-ruta prop-tile-index
BUSHES = [97, 98, 99, 101, 103, 105, 107]          # Plant-arket
ROCKS  = [240, 241, 242, 243, 244, 245, 247, 248, 249]  # Props-arket
GRAVES = [87, 103, 135, 137, 167]                  # Props-arket (gravstenar/kors)

# ---- TRÄD (multi-tile, Plant-arket) ----
# Varje träd: en stam-tile (-> walls, kolliderar + ritas) + krontiles (-> decor_over,
# ritas ÖVER gräs via transparens, INGEN kollision, under spelaren). Koordinater är
# (dx, dy) relativt stam-basen (0,0); dy negativt = uppåt. Verifierat mot alfa-täckning.
TREES = [
    {"trunk": 66, "canopy": [(-1,-4,1),(0,-4,2),
                             (-1,-3,17),(0,-3,18),(1,-3,19),
                             (-1,-2,33),(0,-2,34),(1,-2,35),
                             (-1,-1,49),(0,-1,50),(1,-1,51)]},
    {"trunk": 70, "canopy": [(0,-4,6),
                             (-1,-3,21),(0,-3,22),(1,-3,23),
                             (-1,-2,37),(0,-2,38),(1,-2,39),
                             (-1,-1,53),(0,-1,54),(1,-1,55)]},
    {"trunk": 74, "canopy": [(-1,-3,25),(0,-3,26),(1,-3,27),
                             (-1,-2,41),(0,-2,42),(1,-2,43),
                             (0,-1,58),(1,-1,59)]},
]
# antal träd att försöka placera per zon (glesare i de förvanskade zonerna)
TREES_PER_ZONE = {"cainos": 9, "mork_skog": 4, "cursed_mire": 2}
TREE_TOP_MARGIN = 5   # stam-y måste vara >= detta så kronan håller sig innanför kanten

def theme_at(x):
    return "cainos" if x <= 27 else ("mork_skog" if x <= 40 else "cursed_mire")

# tema -> viktad lista av (sheet, idx)
def obstacle_pool(zone):
    pool = []
    if zone == "cainos":
        pool += [("plant", i) for i in BUSHES] * 3
        pool += [("props", i) for i in ROCKS] * 2
    elif zone == "mork_skog":
        pool += [("plant", i) for i in BUSHES] * 2
        pool += [("props", i) for i in ROCKS] * 2
        pool += [("props", i) for i in GRAVES] * 2
    else:  # cursed_mire
        pool += [("plant", i) for i in BUSHES] * 1
        pool += [("props", i) for i in ROCKS] * 3
        pool += [("props", i) for i in GRAVES] * 2
    return pool

def prop_gid(zone, sheet, idx):
    base = PLANT_FIRSTGID[zone] if sheet == "plant" else PROPS_FIRSTGID[zone]
    return base + idx

def tree_footprint(stamp, tx, ty):
    """Alla celler trädet upptar (stam + krona), för krock-/kant-koll."""
    cells = {(tx, ty)}
    for dx, dy, _ in stamp["canopy"]:
        cells.add((tx + dx, ty + dy))
    return cells

def place_trees(protected, blocked_props):
    """Placera träd footprint-medvetet. Returnerar (trunks, canopy, footprint_all):
       trunks: {(x,y): gid}  -> läggs i walls (kollision + ritas)
       canopy: {(x,y): gid}  -> läggs i decor_over (ritas över gräs, ingen kollision)
       footprint_all: set     -> alla trädceller (så props undviker dem)."""
    trunks, canopy, footprint_all = {}, {}, set()
    for zone, n in TREES_PER_ZONE.items():
        xs = [x for x in range(2, W - 2) if theme_at(x) == zone]
        if not xs:
            continue
        placed = 0
        attempts = 0
        while placed < n and attempts < 400:
            attempts += 1
            tx = random.choice(xs)
            ty = random.randint(TREE_TOP_MARGIN, H - 2)
            stamp = random.choice(TREES)
            fp = tree_footprint(stamp, tx, ty)
            # hela footprinten måste vara innanför interiören, fri från skydd,
            # befintliga props, andra träd, och ha 1 cells luft runt om
            halo = {(x + dx, y + dy) for (x, y) in fp for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
            if any(not (1 <= x < W - 1 and 1 <= y < H - 1) for x, y in fp):
                continue
            if fp & protected or fp & blocked_props or halo & footprint_all:
                continue
            base = PLANT_FIRSTGID[zone]
            trunks[(tx, ty)] = base + stamp["trunk"]
            for dx, dy, idx in stamp["canopy"]:
                canopy[(tx + dx, ty + dy)] = base + idx
            footprint_all |= fp
            placed += 1
    return trunks, canopy, footprint_all

# ---- grund-lager (gräs + vägar) ----
GBASE, GVAR, GDET = 0, [1, 2, 3], [4, 5, 6, 7, 12, 13, 20, 21, 22, 28, 29]
COBBLE = [35, 43, 44, 45]
def ggid(x, idx):
    return GRASS_FIRSTGID[theme_at(x)] + idx

def l_path(a, b):
    (x1, y1), (x2, y2) = a, b
    c = set()
    for x in range(min(x1, x2), max(x1, x2) + 1): c.add((x, y1))
    for y in range(min(y1, y2), max(y1, y2) + 1): c.add((x2, y))
    return c

def read_layer_csv(src, name):
    m = re.search(r'<layer id="\d+" name="%s"[^>]*>\s*<data encoding="csv">\s*(.*?)\s*</data>' % name, src, re.S)
    rows = [r for r in m.group(1).strip().split("\n")]
    grid = [[int(v) for v in r.rstrip(",").split(",")] for r in rows]
    return grid

def main():
    zone = json.load(open(ZONE))
    towns = {t["place_id"]: tuple(t["tile"]) for t in zone["towns"]}
    town_tiles = set(towns.values())
    gates = [tuple(g["tile"]) for g in zone["gates"]]
    start = tuple(zone.get("start_tile", [14, 10]))
    P = towns; north, south, east = gates

    edges = [
        (P["burg_5"], P["burg_117"]), (P["burg_5"], P["burg_160"]),
        (P["burg_5"], north), (P["burg_5"], south), (P["burg_5"], P["burg_235"]),
        (P["burg_235"], P["burg_146"]), (P["burg_146"], P["burg_379"]),
        (P["burg_146"], P["burg_67"]), (P["burg_146"], P["burg_200"]),
        (P["burg_146"], east), (P["burg_200"], P["burg_219"]),
        (P["burg_219"], P["burg_320"]),
    ]
    path_cells = set()
    for a, b in edges: path_cells |= l_path(a, b)
    path_cells = {(x, y) for x, y in path_cells if 0 <= x < W and 0 <= y < H}

    # skyddade celler (inga hinder här)
    protected = set(path_cells) | set(town_tiles) | {start}
    for (tx, ty) in town_tiles | {start} | set(gates):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                protected.add((tx + dx, ty + dy))

    src = open(TMX, encoding="utf-8").read()
    walls_orig = read_layer_csv(src, "walls")

    # ---- GRUND ----
    ground = [[0]*W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if (x, y) in path_cells:
                ground[y][x] = ggid(x, random.choice(COBBLE))
            else:
                r = random.random()
                idx = random.choice(GDET) if r < 0.04 else (random.choice(GVAR) if r < 0.30 else GBASE)
                ground[y][x] = ggid(x, idx)

    # ---- VÄGG (border bevaras, interiör = fräscha hinder) ----
    walls = [[0]*W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if x in (0, W-1) or y in (0, H-1):
                walls[y][x] = walls_orig[y][x]          # kant: bevara exakt

    # ---- TRÄD först (footprint-medvetet) så props kan undvika dem ----
    trunks, canopy, tree_fp = place_trees(protected, set())
    for (x, y), gid in trunks.items():
        walls[y][x] = gid                                # stam -> kollision + ritas
    protected |= tree_fp                                 # props undviker hela trädet

    pools = {z: obstacle_pool(z) for z in ("cainos", "mork_skog", "cursed_mire")}
    for y in range(1, H-1):
        for x in range(1, W-1):
            if (x, y) in protected: continue
            if random.random() < DENSITY:
                z = theme_at(x)
                sheet, idx = random.choice(pools[z])
                walls[y][x] = prop_gid(z, sheet, idx)

    # ---- reachability: flood-fill från start över icke-blockerade ----
    blocked = {(x, y) for y in range(H) for x in range(W) if walls[y][x] != 0}
    seen = set(); dq = collections.deque([start]); seen.add(start)
    while dq:
        x, y = dq.popleft()
        for nx, ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
            if 0 <= nx < W and 0 <= ny < H and (nx,ny) not in blocked and (nx,ny) not in seen:
                seen.add((nx,ny)); dq.append((nx,ny))
    unreachable = [t for t in town_tiles if t not in seen]
    # grindar: grindrutan själv är öppen (0); nåbar om någon granne är nådd
    gate_bad = [g for g in gates if g not in seen]
    assert not unreachable, f"städer omurade: {unreachable}"
    assert not gate_bad, f"grindar onåbara: {gate_bad}"

    # ---- skriv tillbaka grund + vägg ----
    def csv(grid): return ",\n".join(",".join(str(grid[y][x]) for x in range(W)) for y in range(H))
    src = re.sub(r'(<layer id="1" name="ground"[^>]*>\s*<data encoding="csv">\s*).*?(\s*</data>)',
                 lambda m: m.group(1)+csv(ground)+"\n"+m.group(2), src, count=1, flags=re.S)
    src = re.sub(r'(<layer id="2" name="walls"[^>]*>\s*<data encoding="csv">\s*).*?(\s*</data>)',
                 lambda m: m.group(1)+csv(walls)+"\n"+m.group(2), src, count=1, flags=re.S)

    # ---- decor_over: kron-tiles, ritas ÖVER gräs, INGEN kollision (ej "walls") ----
    decor = [[0]*W for _ in range(H)]
    for (x, y), gid in canopy.items():
        if 0 <= x < W and 0 <= y < H:
            decor[y][x] = gid
    decor_layer = (f' <layer id="3" name="decor_over" width="{W}" height="{H}">\n'
                   f'  <data encoding="csv">\n{csv(decor)}\n  </data>\n </layer>\n')
    if 'name="decor_over"' in src:
        src = re.sub(r' <layer id="3" name="decor_over".*?</layer>\n', decor_layer, src, count=1, flags=re.S)
    else:
        # lägg direkt efter walls-lagret så det ritas ovanpå men under spelaren
        src = re.sub(r'(</layer>\s*)(?=</map>)', r'\1' + decor_layer, src, count=1, flags=re.S)
        src = src.replace('nextlayerid="3"', 'nextlayerid="4"', 1)

    # ---- registrera prop-tilesets (idempotent) ----
    if "cainos_plant" not in src:
        block = ""
        for fg, name, source in PROP_TILESETS:
            block += (f' <tileset firstgid="{fg}" name="{name}" tilewidth="32" tileheight="32" '
                      f'tilecount="256" columns="16">\n  <image source="{source}" '
                      f'width="512" height="512"/>\n </tileset>\n')
        src = src.replace('<layer id="1" name="ground"', block + '<layer id="1" name="ground"', 1)

    open(TMX, "w", encoding="utf-8").write(src)
    n_obs = sum(1 for y in range(H) for x in range(W) if walls[y][x] != 0 and not (x in (0,W-1) or y in (0,H-1)))
    n_trees = len(trunks)
    print(f"OK: {len(path_cells)} vägceller, {n_obs} hinder (varav {n_trees} träd-stammar), "
          f"{len(canopy)} kron-tiles i decor_over, alla städer+grindar nåbara")

if __name__ == "__main__":
    main()
