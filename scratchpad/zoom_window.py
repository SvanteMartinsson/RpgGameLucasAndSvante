import os, sys
os.environ.setdefault("SDL_VIDEODRIVER","dummy"); os.environ.setdefault("SDL_AUDIODRIVER","dummy")
import pygame, pytmx
pygame.init(); pygame.display.set_mode((1,1))
tmx=pytmx.load_pygame("rpg_game/data/maps/overworld.tmx")
TW=TH=32
x0,y0,x1,y1=19,11,32,21   # spawn window x=19-31, y=11-20 (~13x10 tiles)
surf=pygame.Surface(((x1-x0)*TW,(y1-y0)*TH))
for layer in tmx.visible_layers:
    if hasattr(layer,"tiles"):
        for x,y,img in layer.tiles():
            if img and x0<=x<x1 and y0<=y<y1: surf.blit(img,((x-x0)*TW,(y-y0)*TH))
# scale ~4x to mimic player zoom crispness
big=pygame.transform.scale(surf,((x1-x0)*TW*4,(y1-y0)*TH*4))
pygame.image.save(big,sys.argv[1]); print("wrote",sys.argv[1],big.get_size())
