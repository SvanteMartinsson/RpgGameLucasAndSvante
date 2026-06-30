import os
os.environ["SDL_VIDEODRIVER"]="dummy"; os.environ["SDL_AUDIODRIVER"]="dummy"
import pygame, pytmx
pygame.init(); pygame.display.set_mode((1,1))
tmx=pytmx.load_pygame("rpg_game/data/maps/overworld.tmx"); TW=32
def crop(x0,y0,x1,y1,scale,out):
    surf=pygame.Surface(((x1-x0)*TW,(y1-y0)*TW)); surf.fill((20,24,20))
    for layer in tmx.visible_layers:
        if hasattr(layer,"tiles"):
            for x,y,img in layer.tiles():
                if img and x0<=x<x1 and y0<=y<y1: surf.blit(img,((x-x0)*TW,(y-y0)*TW))
    pygame.image.save(pygame.transform.scale(surf,(int((x1-x0)*TW*scale),int((y1-y0)*TW*scale))),out); print("wrote",out)
crop(0,0,17,15, 2.4, "scratchpad/c_TL.png")
crop(63,0,80,15, 2.4, "scratchpad/c_TR.png")
crop(0,41,17,56, 2.4, "scratchpad/c_BL.png")
crop(63,41,80,56, 2.4, "scratchpad/c_BR.png")
crop(12,24,42,48, 1.7, "scratchpad/c_seam.png")
