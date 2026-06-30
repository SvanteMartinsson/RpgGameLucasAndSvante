import os
os.environ["SDL_VIDEODRIVER"]="dummy"; os.environ["SDL_AUDIODRIVER"]="dummy"
import pygame
from rpg_game.core.game import GameEngine
from rpg_game.presentation.pygame_battle import BattleApp
from rpg_game.presentation.pygame_canvas import set_display_mode
pygame.init(); pygame.display.set_mode((1,1))
eng=GameEngine(); eng.start_new_game("Hero","fighter")
for pid,pl in eng.content.places.items():
    if pl.encounters: eng.player.current_place_id=pid; break
b=BattleApp(engine=eng, enemy=eng.create_encounter(), standalone=False)
b.display = set_display_mode((2560,1440))
b.draw()
pygame.image.save(b.display, "scratchpad/battle_fill.png")
print("battle transform:", b._transform, "display:", b.display.get_size(), "canvas:", b.screen.get_size())
