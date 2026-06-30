import os,sys
os.environ.setdefault("SDL_VIDEODRIVER","dummy"); os.environ.setdefault("SDL_AUDIODRIVER","dummy")
import pygame, pytmx
pygame.init(); pygame.display.set_mode((1,1))
tmx=pytmx.load_pygame("rpg_game/data/maps/overworld.tmx"); TW=32
x0,y0,x1,y1=6,30,20,43   # west seam bridge crossing core->heath
surf=pygame.Surface(((x1-x0)*TW,(y1-y0)*TW))
for layer in tmx.visible_layers:
    if hasattr(layer,"tiles"):
        for x,y,img in layer.tiles():
            if img and x0<=x<x1 and y0<=y<y1: surf.blit(img,((x-x0)*TW,(y-y0)*TW))
pygame.image.save(pygame.transform.scale(surf,((x1-x0)*TW*3,(y1-y0)*TW*3)),"scratchpad/zoom_bridge.png")
print("wrote zoom_bridge")
