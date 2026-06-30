import os
os.environ.setdefault("SDL_VIDEODRIVER","dummy"); os.environ.setdefault("SDL_AUDIODRIVER","dummy")
import pygame, pytmx
pygame.init(); pygame.display.set_mode((1,1))
tmx=pytmx.load_pygame("rpg_game/data/maps/overworld.tmx")
TW=TH=32
x0,y0,x1,y1=4,4,44,30   # core slice incl Hordanita(26,18),Yeblegali(10,8),Gaste(38,22)
surf=pygame.Surface(((x1-x0)*TW,(y1-y0)*TH)); surf.fill((20,24,20))
for layer in tmx.visible_layers:
    if hasattr(layer,"tiles"):
        for x,y,img in layer.tiles():
            if img and x0<=x<x1 and y0<=y<y1: surf.blit(img,((x-x0)*TW,(y-y0)*TH))
pygame.image.save(pygame.transform.scale(surf,((x1-x0)*TW*2//3,(y1-y0)*TH*2//3)),"scratchpad/closeup.png")
print("wrote closeup")
