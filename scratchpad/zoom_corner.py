import os
os.environ["SDL_VIDEODRIVER"]="dummy"; os.environ["SDL_AUDIODRIVER"]="dummy"
import pygame, pytmx
pygame.init(); pygame.display.set_mode((1,1))
tmx=pytmx.load_pygame("rpg_game/data/maps/overworld.tmx"); TW=32
x0,y0,x1,y1=0,0,18,16
surf=pygame.Surface(((x1-x0)*TW,(y1-y0)*TW)); surf.fill((20,24,20))
for layer in tmx.visible_layers:
    if hasattr(layer,"tiles"):
        for x,y,img in layer.tiles():
            if img and x0<=x<x1 and y0<=y<y1: surf.blit(img,((x-x0)*TW,(y-y0)*TW))
pygame.image.save(pygame.transform.scale(surf,((x1-x0)*TW*3,(y1-y0)*TW*3)),"scratchpad/zoom_corner.png")
print("wrote zoom_corner")
