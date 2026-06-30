import os
os.environ.setdefault("SDL_VIDEODRIVER","dummy"); os.environ.setdefault("SDL_AUDIODRIVER","dummy")
import pygame, pytmx
pygame.init(); pygame.display.set_mode((1,1))
tmx=pytmx.load_pygame("rpg_game/data/maps/overworld.tmx")
print("len(tmx.images):", len(tmx.images))
print("last grave_heath_props gid 4738 image:", None if tmx.images[4738] is None else "loaded")
# Place a water gid into a throwaway copy of the ground layer data and re-fetch via a fresh load with a referenced gid.
# Simpler: directly load the water tileset image file to confirm it's valid + locate the full-water tile.
img=pygame.image.load("rpg_game/assets/tiles/generated/water_autotile_32x32.png").convert_alpha()
print("water png:", img.get_size())
print("  full-water tile (0,0) center px:", img.get_at((16,16)))
# Confirm pytmx CAN map the water tileset: find the tileset object and load_image path
for t in tmx.tilesets:
    if t.name=="water_autotile":
        print("  tileset firstgid", t.firstgid, "source", t.source, "cols", t.columns, "count", t.tilecount)
