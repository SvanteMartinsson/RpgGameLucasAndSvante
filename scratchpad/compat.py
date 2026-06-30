import os
os.environ.setdefault("SDL_VIDEODRIVER","dummy"); os.environ.setdefault("SDL_AUDIODRIVER","dummy")
import pygame
pygame.init(); pygame.display.set_mode((1,1))
TS=32
sheet=pygame.image.load("rpg_game/assets/tiles/generated/water_autotile_32x32.png").convert_alpha()
ATLAS={"full":(0,0),"edge_N":(1,0),"edge_E":(2,0),"edge_S":(3,0),"edge_W":(0,1),
"out_NW":(1,1),"out_NE":(2,1),"out_SE":(3,1),"out_SW":(0,2),"in_NW":(1,2),
"in_NE":(2,2),"in_SE":(3,2),"in_SW":(0,3),"chan_H":(1,3),"chan_V":(2,3)}
def t(n):
    cx,cy=ATLAS[n]; return sheet.subsurface(pygame.Rect(cx*TS,cy*TS,TS,TS))
def prof(n,side):
    s=t(n)
    if side=="N": return tuple(1 if s.get_at((i,0))[3] else 0 for i in range(TS))
    if side=="S": return tuple(1 if s.get_at((i,TS-1))[3] else 0 for i in range(TS))
    if side=="W": return tuple(1 if s.get_at((0,i))[3] else 0 for i in range(TS))
    if side=="E": return tuple(1 if s.get_at((TS-1,i))[3] else 0 for i in range(TS))
names=list(ATLAS)
# distinct border profiles that occur
from collections import Counter
prof_set=Counter()
for n in names:
    for s in "NSEW": prof_set[prof(n,s)]+=1
print("distinct border profiles (water mask along a 32px edge):")
def fmt(p): return "".join("#" if v else "." for v in p)
for p,c in prof_set.items(): print(f"  {fmt(p)}  x{c}")
print()
# E-W compatibility: A right border == B left border
print("LEGAL horizontal neighbours (A | B): A.E == B.W")
for a in names:
    ok=[b for b in names if prof(a,"E")==prof(b,"W")]
    print(f"  {a:7} -> {ok}")
print()
print("LEGAL vertical neighbours (A above B): A.S == B.N")
for a in names:
    ok=[b for b in names if prof(a,"S")==prof(b,"N")]
    print(f"  {a:7} -> {ok}")
