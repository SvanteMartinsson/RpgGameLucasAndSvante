import os
os.environ["SDL_VIDEODRIVER"]="dummy"; os.environ["SDL_AUDIODRIVER"]="dummy"
import pygame
pygame.init(); pygame.display.set_mode((1,1))
font=pygame.font.SysFont("menlo,monospace",11)
sheet=pygame.image.load("rpg_game/assets/props/cainos/TX Plant with Shadow.png").convert_alpha()
cols=16; rows=8  # show first 8 rows (idx 0-127)
cell=32*3+16
surf=pygame.Surface((cols*cell, rows*cell)); surf.fill((40,40,50))
for r in range(rows):
    for c in range(cols):
        idx=r*16+c
        op=sum(1 for yy in range(r*32,r*32+32) for xx in range(c*32,c*32+32) if sheet.get_at((xx,yy))[3]>0)
        surf.blit(pygame.transform.scale(sheet.subsurface(pygame.Rect(c*32,r*32,32,32)),(96,96)),(c*cell+4,r*cell+4))
        col=(120,255,120) if op>=256 else ((255,255,120) if op>0 else (90,90,90))
        surf.blit(font.render(f"{idx}",True,col),(c*cell+4,r*cell+100))
pygame.image.save(surf,"scratchpad/plant_montage.png"); print("wrote", cols,"x",rows)
