# CLAUDE.md

## Projektstatus

Det här repo:t innehåller den ursprungliga Java-prototypen och en ny Python-port.

Java-versionen ligger kvar i:

- `src/`
- `bin/`

Python-versionen ligger i:

- `rpg_game/`
- `tests/`

`SPEC.md` beskriver Java-versionens faktiska nuläge. `DESIGN.md` beskriver målbeteendet för Python-versionen.

## Kör Python-spelet

Från projektroten:

```sh
python3 -m rpg_game
```

På system där `python` pekar på Python 3.10+ fungerar även:

```sh
python -m rpg_game
```

Inga externa dependencies krävs.

## Kör tester

```sh
python3 -m unittest discover -s tests
```

Snabb syntax/import-kontroll:

```sh
python3 -m compileall rpg_game tests
```

## Arkitektur

Python-porten är uppdelad i spelkärna och presentation.

Spelkärnan ligger i `rpg_game/core/` och ska inte använda:

- `print()`
- `input()`
- Pygame
- terminalspecifik kod

Presentation ligger i `rpg_game/presentation/`. Just nu finns bara terminal-UI:

- `rpg_game/presentation/terminal.py`

Målet är att Pygame senare ska kunna läggas till som ett separat presentationslager ovanpå samma kärna.

## Viktiga moduler

- `rpg_game/__main__.py`: startpunkt för `python3 -m rpg_game`.
- `rpg_game/core/entities.py`: dataclasses för player, fiender, items, platser och game state.
- `rpg_game/core/data_loader.py`: laddar JSON-innehåll.
- `rpg_game/core/progression.py`: XP-kurva, `round_half_up()`, level up och statval.
- `rpg_game/core/combat.py`: action -> effects -> resolver-pipeline, status ticks, generic effect vocabulary, damage types, speed order och combat-resultat.
- `rpg_game/core/game.py`: `GameEngine`, orkestrerar state, world, combat, store och inventory.
- `rpg_game/core/talents.py`: class talent allocation, linear branch prerequisites, passive application och max 4 equipped skills.
- `rpg_game/core/world.py`: platser, resor och encounters.
- `rpg_game/core/store.py`: butik och köp.
- `rpg_game/core/inventory.py`: användning av consumables.
- `rpg_game/presentation/terminal.py`: terminalmenyer och användarinput.

## Datadrivet innehåll

Nytt spelinnehåll ska i första hand läggas i JSON-filerna i `rpg_game/data/`.

- `classes.json`: spelarklasser och startstats.
- `actions.json`: combat-handlingar som producerar effekter, till exempel base attacks och skills.
- `talents.json`: klassnoder, grenar, prerequisites via order och passiva effekter.
- `weapons.json`: vapen, pris och skadebonus.
- `items.json`: förbrukningsitems, till exempel potions.
- `enemies.json`: fiendemallar med HP, damage, armor, XP och gold.
- `world.json`: världens `meta.start_place_id`, platser, resvägar, encounter-listor och framtida kartfält.

Lägg inte nya fiender, vapen eller platser hårdkodat i combat- eller UI-koden.

Combat-handlingar ska gå genom samma pipeline:

```text
action -> effects -> resolver -> structured result
```

Det gäller base attacks, skills, items, weapon swap och fienders drag. Lägg
nya skills som data i `actions.json` när det räcker.

Talanger ska ligga i `talents.json`. Kärnan exponerar
`available_talents()` och `allocate_talent(node_id)` via `GameEngine`; UI:t
ska fråga spelaren och mata tillbaka valen, på samma sätt som statval efter
level-up.

## Regler som tester låser

Det finns tester för avrundningsregler och progression:

- Fighter `base_damage = 15` med normal attack `x1.5` mot 0 armor ska göra 23 skada.
- XP-trösklarna för level 1-5 ska vara `100`, `150`, `225`, `338`, `506`.

Skada och XP-krav ska avrundas med:

```python
round_half_up(x) = math.floor(x + 0.5)
```

Använd inte Pythons inbyggda `round()` för dessa regler.

## Level up-kontrakt

Kärnan får aldrig fråga spelaren med `input()`.

När combat ger XP som triggar level up:

- kärnan höjer level
- kärnan ökar `player.pending_stat_choices`
- combat-resultatet returnerar `pending_stat_choices`
- presentationen frågar spelaren om statval
- presentationen skickar tillbaka valet via `GameEngine.apply_stat_choice()`

Detta är viktigt för att framtida Pygame-UI ska kunna använda samma spelkärna.

## Lägg till nytt innehåll

Exempel: ny fiende

1. Lägg till fienden i `rpg_game/data/enemies.json`.
2. Lägg fiendens id i `encounters` för en plats i `rpg_game/data/world.json`.
3. Kör testerna.

Exempel: nytt vapen

1. Lägg till vapnet i `rpg_game/data/weapons.json`.
2. Lägg vapnets id i `store_inventory` för en butik i `rpg_game/data/world.json`.
3. Kör spelet och kontrollera butiken.

## Nuvarande begränsningar

Följande är medvetet inte implementerat ännu:

- Pygame
- save/load
- quests
- dialogsystem
- bossar
- flera ägda vapen
- inventory-vikt eller maxslots
- magi eller separat skill-system
