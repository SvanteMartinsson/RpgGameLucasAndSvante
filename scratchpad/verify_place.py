import os, re, shutil
os.environ.setdefault("SDL_VIDEODRIVER","dummy"); os.environ.setdefault("SDL_AUDIODRIVER","dummy")
import pygame, pytmx
pygame.init(); pygame.display.set_mode((1,1))
SRC="rpg_game/data/maps/overworld.tmx"; TMP="rpg_game/data/maps/_place_test.tmx"
shutil.copy(SRC, TMP)
try:
    txt=open(TMP).read()
    m=re.search(r'(<layer id="1" name="ground".*?<data encoding="csv">\s*)(\d+)', txt, re.S)
    txt=txt[:m.start(2)]+"4739"+txt[m.end(2):]   # raw gid 4739 = full-water
    open(TMP,"w").write(txt)
    tmx=pytmx.load_pygame(TMP)
    img=tmx.get_tile_image(0,0,0)
    print("placed full-water at ground(0,0)")
    print("image:", None if img is None else img.get_size(), "center px:", img.get_at((16,16)) if img else None)
    print("water_autotile loaded into images:", any(
        i is not None and i.get_size()==(32,32) for i in tmx.images[-16:]))
finally:
    os.remove(TMP)
