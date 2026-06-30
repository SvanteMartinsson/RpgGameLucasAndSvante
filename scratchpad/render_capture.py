import os, sys
os.environ.setdefault("SDL_VIDEODRIVER","dummy"); os.environ.setdefault("SDL_AUDIODRIVER","dummy")
import pygame
from rpg_game.presentation.pygame_overworld import OverworldApp
pygame.init(); pygame.display.set_mode((1,1))
app = OverworldApp()
app.screen = pygame.Surface((960, 640))           # fixed view for determinism
out = sys.argv[1]
# render the map at several camera positions, stitch into one tall image for a thorough compare
positions = [(24,16),(2,2),(46,30),(10,25),(40,5)]
big = pygame.Surface((960, 640*len(positions)))
for i,(tx,ty) in enumerate(positions):
    app.world.set_tile(tx,ty)
    app.screen.fill((0,0,0))
    app._draw_map()
    big.blit(app.screen, (0, 640*i))
pygame.image.save(big, out)
import hashlib
print(out, "md5", hashlib.md5(pygame.image.tostring(big,"RGBA")).hexdigest())
