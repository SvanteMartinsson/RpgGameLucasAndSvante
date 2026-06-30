import os
os.environ.setdefault("SDL_VIDEODRIVER","dummy"); os.environ.setdefault("SDL_AUDIODRIVER","dummy")
import pygame
pygame.init(); pygame.display.set_mode((1,1))
font=pygame.font.SysFont("menlo,monospace",12)
def montage(path,out,scale=3):
    sheet=pygame.image.load(path).convert_alpha()
    cols=sheet.get_width()//32; rows=sheet.get_height()//32
    cell=32*scale+18
    surf=pygame.Surface((cols*cell, rows*cell)); surf.fill((30,30,30))
    for r in range(rows):
        for c in range(cols):
            idx=r*cols+c
            tile=pygame.transform.scale(sheet.subsurface(pygame.Rect(c*32,r*32,32,32)),(32*scale,32*scale))
            x,y=c*cell+4,r*cell+4
            surf.blit(tile,(x,y))
            surf.blit(font.render(str(idx),True,(255,255,0)),(x,y+32*scale))
    pygame.image.save(surf,out); print("wrote",out,surf.get_size())
montage("rpg_game/assets/tiles/cainos/TX Tileset Grass.png","scratchpad/grass_montage.png")
montage("rpg_game/assets/tiles/cainos/TX Tileset Stone Ground.png","scratchpad/stone_montage.png")
