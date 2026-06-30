import os, time
os.environ["RPG_DISPLAY_DEBUG"]="1"
os.environ["RPG_DISPLAY_DEBUG_LOG"]="/tmp/rpg_probe.log"
import pygame
from rpg_game.presentation.pygame_overworld import OverworldApp
app=OverworldApp()
log=open("/tmp/rpg_probe.log","a")
for i in range(60):
    app.handle_events(); app.update()
    # log surface vs ACTUAL window each frame
    try: win=pygame.display.get_window_size()
    except Exception: win=None
    surf=app.display.get_size() if app.display else None
    scr=app.screen.get_size()
    log.write(f"frame {i}: screen={scr} display_surface={surf} window={win}\n")
    app.draw()
    app.clock.tick(60)
log.close(); pygame.quit()
print("done")
