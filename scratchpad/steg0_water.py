import os
os.environ.setdefault("SDL_VIDEODRIVER","dummy"); os.environ.setdefault("SDL_AUDIODRIVER","dummy")
import pygame
pygame.init(); pygame.display.set_mode((1,1))
CRISP="rpg_game/assets/tiles/generated/water_bridge_32x32_crisp.png"
img=pygame.image.load(CRISP).convert_alpha()
W,H=img.get_size(); TW=TH=32
cols,rows=W//TW,H//TH
print(f"sheet {W}x{H} = {cols}x{rows} tiles")

def tile_stats(cx,cy):
    opaque=[]; alphas=set()
    for y in range(cy*TH,cy*TH+TH):
        for x in range(cx*TW,cx*TW+TW):
            r,g,b,a=img.get_at((x,y)); alphas.add(a)
            if a>0: opaque.append((r,g,b))
    pct=100*len(opaque)/(TW*TH)
    if opaque:
        n=len(opaque)
        ar=sum(c[0] for c in opaque)/n; ag=sum(c[1] for c in opaque)/n; ab=sum(c[2] for c in opaque)/n
        luma=0.2126*ar+0.7152*ag+0.0722*ab
    else:
        ar=ag=ab=luma=0
    return pct,(round(ar,1),round(ag,1),round(ab,1)),round(luma,1),sorted(alphas)

# deep water tile (0,0)
pct,rgb,luma,alphas=tile_stats(0,0)
print(f"\nTILE(0,0) deep water: opaque {pct:.1f}%  meanRGB {rgb}  luma {luma}  alpha-values {alphas}")

# exact corner pixels of tile (0,0) to confirm uniform fill / self-tile
def edge(cx,cy,which):
    ox,oy=cx*TW,cy*TH
    if which=="N": return [img.get_at((ox+i,oy))[:3] for i in range(TW)]
    if which=="S": return [img.get_at((ox+i,oy+TH-1))[:3] for i in range(TW)]
    if which=="W": return [img.get_at((ox,oy+i))[:3] for i in range(TH)]
    if which=="E": return [img.get_at((ox+TW-1,oy+i))[:3] for i in range(TH)]

import statistics
for w in ("N","S","E","W"):
    e=edge(0,0,w)
    rs=[c[0] for c in e]; gs=[c[1] for c in e]; bs=[c[2] for c in e]
    print(f"  edge {w}: R {min(rs)}-{max(rs)} G {min(gs)}-{max(gs)} B {min(bs)}-{max(bs)}")
# opposite-edge match (seam test for self-tiling)
dN=edge(0,0,"N"); dS=edge(0,0,"S"); dE=edge(0,0,"E"); dW=edge(0,0,"W")
def maxdelta(a,b): return max(abs(a[i][j]-b[i][j]) for i in range(len(a)) for j in range(3))
print(f"  N vs S max delta: {maxdelta(dN,dS)}   E vs W max delta: {maxdelta(dE,dW)}  (low => self-tiles)")

# whole-sheet alpha histogram (confirm {0,255} crisp)
hist={}
for y in range(H):
    for x in range(W):
        a=img.get_at((x,y))[3]; hist[a]=hist.get(a,0)+1
print(f"\nwhole-sheet alpha histogram: {dict(sorted(hist.items()))}")

# classify every tile (opaque %)
print("\nper-tile opaque %:")
for cy in range(rows):
    row=[]
    for cx in range(cols):
        p,_,_,_=tile_stats(cx,cy); row.append(f"{p:5.1f}")
    print(f" row{cy}: "+" ".join(row))
