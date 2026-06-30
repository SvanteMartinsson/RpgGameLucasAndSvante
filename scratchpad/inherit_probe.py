import os
os.environ["RPG_DISPLAY_DEBUG"]="1"; os.environ["RPG_DISPLAY_DEBUG_LOG"]="/tmp/rpg_inherit.log"
import pygame
from rpg_game.presentation.pygame_canvas import set_display_mode
from rpg_game.presentation.pygame_overworld import OverworldApp
# Simulate the previous screen (menu/creation) leaving a larger window:
pygame.init()
set_display_mode((1391, 903))
print("prior window:", pygame.display.get_surface().get_size())
app = OverworldApp()
print("overworld windowed_size:", app.windowed_size, "display:", app.display.get_size())
# a couple frames
for _ in range(3):
    app.handle_events(); app.update(); app.draw(); app.clock.tick(60)
print("after frames display:", app.display.get_size())
pygame.quit()
