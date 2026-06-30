import re
src=open("rpg_game/data/maps/overworld.tmx").read()
m=re.search(r'<layer id="2" name="walls"[^>]*>\s*<data encoding="csv">\s*(.*?)\s*</data>', src, re.S)
rows=[r.rstrip(",") for r in m.group(1).strip().split("\n")]
grid=[[int(v) for v in r.split(",")] for r in rows]
H=len(grid); W=len(grid[0])
print("walls dims", W, H)
from collections import Counter
top=Counter(grid[0]); bottom=Counter(grid[H-1])
left=Counter(grid[y][0] for y in range(H)); right=Counter(grid[y][W-1] for y in range(H))
print("top edge gids:", top)
print("bottom edge gids:", bottom)
print("left edge gids:", left)
print("right edge gids:", right)
