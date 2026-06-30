import os
os.environ.setdefault("SDL_VIDEODRIVER","dummy"); os.environ.setdefault("SDL_AUDIODRIVER","dummy")
import pygame
pygame.init(); pygame.display.set_mode((1,1))
font=pygame.font.SysFont("menlo,monospace",13)
sheet=pygame.image.load("rpg_game/assets/tiles/generated/water_bridge_32x32_crisp.png").convert_alpha()
cols,rows=sheet.get_width()//32,sheet.get_height()//32
cell=32*4+18
surf=pygame.Surface((cols*cell,rows*cell)); surf.fill((30,30,40))
for r in range(rows):
    for c in range(cols):
        idx=r*cols+c
        surf.blit(pygame.transform.scale(sheet.subsurface(pygame.Rect(c*32,r*32,32,32)),(128,128)),(c*cell+4,r*cell+4))
        surf.blit(font.render(str(idx),True,(255,255,0)),(c*cell+4,r*cell+136))
pygame.image.save(surf,"scratchpad/bridge_montage.png"); print("wrote",cols,"x",rows)
