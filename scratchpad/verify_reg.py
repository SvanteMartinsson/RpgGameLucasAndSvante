import os
os.environ.setdefault("SDL_VIDEODRIVER","dummy"); os.environ.setdefault("SDL_AUDIODRIVER","dummy")
import pygame, pytmx
pygame.init(); pygame.display.set_mode((1,1))
tmx=pytmx.load_pygame("rpg_game/data/maps/overworld.tmx")
print("map:", tmx.width,"x",tmx.height, "layers:", [l.name for l in tmx.layers])
# new tileset present?
ts=[t for t in tmx.tilesets if t.name=="water_autotile"]
print("water_autotile registered:", bool(ts), "firstgid:", ts[0].firstgid if ts else None)
# firstgid 4739 should resolve to a 32x32 image (full water tile = opaque teal)
img=tmx.get_tile_image_by_gid(4739)
print("gid 4739 image:", None if img is None else img.get_size())
if img is not None:
    # sample center pixel -> teal water
    print("  center px:", img.get_at((16,16)))
# confirm NO layer references gids >= 4739 (nothing placed -> nothing visual changed)
maxgid=0; placed_new=0
for layer in tmx.layers:
    if hasattr(layer,"data"):
        for row in layer.data:
            for g in row:
                if g>maxgid: maxgid=g
                if g>=4739: placed_new+=1
print("max gid referenced by any layer:", maxgid, "| cells referencing water set:", placed_new)
