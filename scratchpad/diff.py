import os
os.environ.setdefault("SDL_VIDEODRIVER","dummy"); os.environ.setdefault("SDL_AUDIODRIVER","dummy")
import pygame
pygame.init(); pygame.display.set_mode((1,1))
a=pygame.image.load("scratchpad/baseline_48x32.png")
b=pygame.image.load("scratchpad/culled_48x32.png")
print("sizes:", a.get_size(), b.get_size())
diff=0; first=None
for y in range(a.get_height()):
    for x in range(a.get_width()):
        if a.get_at((x,y))!=b.get_at((x,y)):
            diff+=1
            if first is None: first=(x,y,a.get_at((x,y)),b.get_at((x,y)))
print("differing pixels:", diff, "of", a.get_width()*a.get_height())
print("first diff:", first)
