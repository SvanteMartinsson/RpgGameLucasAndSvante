import os
os.environ.setdefault("SDL_VIDEODRIVER","dummy"); os.environ.setdefault("SDL_AUDIODRIVER","dummy")
import pygame, pytmx, json
pygame.init(); pygame.display.set_mode((1,1))
tmx=pytmx.load_pygame("rpg_game/data/maps/overworld.tmx")
TW=TH=32; W,H=tmx.width,tmx.height
surf=pygame.Surface((W*TW,H*TH))
surf.fill((20,24,20))
for layer in tmx.visible_layers:
    if hasattr(layer,"tiles"):
        for x,y,img in layer.tiles():
            if img: surf.blit(img,(x*TW,y*TH))
# mark towns + gates + start
zone=json.load(open("rpg_game/data/maps/core_zone.json"))
font=pygame.font.SysFont("menlo,monospace",20)
start=tuple(zone["start_tile"])
for t in zone["towns"]:
    x,y=t["tile"]; c=(255,140,26) if t["place_id"]=="burg_5" else (255,213,74)
    pygame.draw.rect(surf,c,(x*TW+3,y*TH+3,TW-6,TH-6),border_radius=5)
    pygame.draw.rect(surf,(20,24,20),(x*TW+3,y*TH+3,TW-6,TH-6),width=2,border_radius=5)
    surf.blit(font.render(t["label"],True,(255,255,255)),(x*TW-10,y*TH-20))
for g in zone["gates"]:
    x,y=g["tile"]; pygame.draw.rect(surf,(255,93,93),(x*TW+2,y*TH+2,TW-4,TH-4))
# seam line
pygame.draw.line(surf,(255,93,93),(0,36*TH),(W*TW,36*TH),3)
small=pygame.transform.smoothscale(surf,(W*12,H*12))
pygame.image.save(small,"scratchpad/new_map.png")
print("wrote scratchpad/new_map.png", small.get_size())
