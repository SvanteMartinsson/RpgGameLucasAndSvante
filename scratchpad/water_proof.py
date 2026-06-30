import os, math
os.environ.setdefault("SDL_VIDEODRIVER","dummy"); os.environ.setdefault("SDL_AUDIODRIVER","dummy")
import pygame, pytmx
pygame.init(); pygame.display.set_mode((1,1))
W,H,TW=80,56,32
WF=4739  # water_autotile firstgid
ATLAS={"full":0,"edge_N":1,"edge_E":2,"edge_S":3,"edge_W":4,"out_NW":5,"out_NE":6,
"out_SE":7,"out_SW":8,"in_NW":9,"in_NE":10,"in_SE":11,"in_SW":12,"chan_H":13,"chan_V":14}
CORNER_MAP={(1,1,1,1):"full",(0,0,1,1):"edge_N",(1,1,0,0):"edge_S",(1,0,0,1):"edge_E",
(0,1,1,0):"edge_W",(0,0,1,0):"out_NW",(0,0,0,1):"out_NE",(0,1,0,0):"out_SW",(1,0,0,0):"out_SE",
(0,1,1,1):"in_NW",(1,0,1,1):"in_NE",(1,1,1,0):"in_SW",(1,1,0,1):"in_SE"}

def seg_dist(px,py,ax,ay,bx,by):
    dx,dy=bx-ax,by-ay
    if dx==0 and dy==0: return math.hypot(px-ax,py-ay)
    t=max(0,min(1,((px-ax)*dx+(py-ay)*dy)/(dx*dx+dy*dy)))
    return math.hypot(px-(ax+t*dx),py-(ay+t*dy))

def poly_field(pts,hw):
    def f(gx,gy):
        return min(seg_dist(gx,gy,*pts[i],*pts[i+1]) for i in range(len(pts)-1))<=hw
    return f

def autotile(field):
    corner=[[field(gx,gy) for gx in range(W+1)] for gy in range(H+1)]
    placed,saddles={},[]
    for y in range(H):
        for x in range(W):
            pat=(int(corner[y][x]),int(corner[y][x+1]),int(corner[y+1][x+1]),int(corner[y+1][x]))
            if sum(pat)==0: continue
            n=CORNER_MAP.get(pat)
            if n is None: saddles.append((x,y))
            else: placed[(x,y)]=n
    return placed,saddles

# core inner river (proof): polyline to seam, 2-wide (half-width 1.0)
CORE_RIVER=[(20,2),(18,10),(23,19),(27,27),(24,34),(24,36)]
placed,saddles=autotile(poly_field(CORE_RIVER,1.0))
water=set(placed)
print("core river: water cells",len(water),"saddles",saddles[:5],"count",len(saddles))

# seam test: every adjacent placed pair shares border profile -> use the tileset image
sheet=pygame.image.load("rpg_game/assets/tiles/generated/water_autotile_32x32.png").convert_alpha()
def prof(name,side):
    c=ATLAS[name]%4; r=ATLAS[name]//4; t=sheet.subsurface(pygame.Rect(c*32,r*32,32,32))
    if side=="N": return tuple(1 if t.get_at((i,0))[3] else 0 for i in range(32))
    if side=="S": return tuple(1 if t.get_at((i,31))[3] else 0 for i in range(32))
    if side=="W": return tuple(1 if t.get_at((0,i))[3] else 0 for i in range(32))
    return tuple(1 if t.get_at((31,i))[3] else 0 for i in range(32))
fails=0
for (x,y),nm in placed.items():
    for dx,dy,a,b in [(1,0,"E","W"),(0,1,"S","N")]:
        nb=placed.get((x+dx,y+dy))
        if nb and prof(nm,a)!=prof(nb,b): fails+=1
print("seam mismatches:",fails)

# bridge at y=26-28, x=27-28 : find river cells there, determine band, assert straight 2-wide
brect=[(x,y) for x in (27,28) for y in (26,27,28)]
bwater=[c for c in brect if c in water]
# river flows ~N-S here (vertical), so cross-section is in X. check 2-wide in x at each y
rows={}
for (x,y) in water:
    if 25<=y<=29: rows.setdefault(y,[]).append(x)
straight=all(sorted(rows.get(y,[]))==list(range(min(rows[y]),min(rows[y])+len(rows[y]))) and len(rows[y])==2 for y in (26,27,28) if y in rows)
print("river x-span by row y25-29:",{y:sorted(v) for y,v in sorted(rows.items())})
print("bridge straight 2-wide (y26-28):",straight)

# render zoomed core river + bridge over the real map ground
tmx=pytmx.load_pygame("rpg_game/data/maps/overworld.tmx")
x0,y0,x1,y1=14,14,34,38
surf=pygame.Surface(((x1-x0)*TW,(y1-y0)*TW))
g=tmx.get_layer_by_name("ground")
for x,y,img in g.tiles():
    if img and x0<=x<x1 and y0<=y<y1: surf.blit(img,((x-x0)*TW,(y-y0)*TW))
for (x,y),nm in placed.items():
    if x0<=x<x1 and y0<=y<y1:
        c=ATLAS[nm]%4; r=ATLAS[nm]//4
        surf.blit(sheet.subsurface(pygame.Rect(c*32,r*32,32,32)),((x-x0)*TW,(y-y0)*TW))
# bridge: horizontal planks idx13 over the river crossing (make those cells "bridge")
bridge=pygame.image.load("rpg_game/assets/tiles/generated/water_bridge_32x32_crisp.png").convert_alpha()
plank_h=bridge.subsurface(pygame.Rect((13%8)*32,(13//8)*32,32,32))
bridge_cells=[(x,y) for (x,y) in water if 26<=y<=27 and x in (min(rows.get(y,[99]),default=99),)]  # placeholder
# proper: bridge spans the 2 river cells at y=26 and y=27 (cross E-W means cover both x at one y-pair)
bcells=[]
for y in (26,27):
    for x in sorted(rows.get(y,[])): bcells.append((x,y))
for (x,y) in bcells:
    if x0<=x<x1 and y0<=y<y1: surf.blit(plank_h,((x-x0)*TW,(y-y0)*TW))
big=pygame.transform.scale(surf,((x1-x0)*TW*2,(y1-y0)*TW*2))
pygame.image.save(big,"scratchpad/proof_river.png")
print("bridge cells:",bcells,"-> wrote scratchpad/proof_river.png")
