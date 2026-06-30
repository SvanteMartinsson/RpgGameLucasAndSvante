import os,sys
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
    pygame.image.save(pygame.transform.scale(surf,(int((x1-x0)*TW*scale),int((y1-y0)*TW*scale))),out)
    print("wrote",out)
crop(14,22,30,36, 3.0, "scratchpad/s3_forest.png")     # (a) a forest mass (the 20,28 blob)
crop(8,24,40,48, 1.6, "scratchpad/s3_seam.png")        # (b) across the seam y36 (core->heath)
