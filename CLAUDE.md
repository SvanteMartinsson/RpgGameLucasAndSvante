# CLAUDE.md

Det här dokumentet är en praktisk guide för framtida arbete i repo:t. Det
beskriver faktisk struktur och kontrakt som koden förväntas följa.

## Status

Projektet innehåller två generationer:

- `src/` och `bin/`: ursprunglig Java-prototyp, kvar som historik.
- `rpg_game/`: aktiv Python-port.

Python-porten är spelbar i terminalen och har tester för strid, klasser,
talanger, world loading, loot, vapenkrav, progression, enemy AI och Identify.

## Körning

Starta spelet:

```sh
python3 -m rpg_game
```

Kör hela testsviten:

```sh
python3 -m unittest discover -s tests
```

Snabb import-/syntaxkontroll:

```sh
python3 -m compileall -q rpg_game tests
```

Inga externa runtime-dependencies krävs.

## Arkitekturkontrakt

Spelkärnan ligger i `rpg_game/core/`. Den ska inte använda:

- `print()`
- `input()`
- terminalspecifik kod
- Pygame

Presentation ligger i `rpg_game/presentation/`. Just nu finns terminal-UI i
`rpg_game/presentation/terminal.py`. Ett framtida Pygame-lager ska prata med
samma `GameEngine` och samma strukturerade resultat.

Strid ska gå genom en enda pipeline:

```text
CombatAction -> EffectSpec-lista -> resolver -> ActionResolution/CombatTurnResult
```

Det gäller spelarattacker, skills, items, weapon swap och fienders handlingar.
Bygg inte en parallell damage- eller skill-väg.

## Viktiga moduler

- `rpg_game/__main__.py`: startpunkt för `python3 -m rpg_game`.
- `rpg_game/core/entities.py`: dataclasses för content, state och runtime-entiteter.
- `rpg_game/core/data_loader.py`: laddar JSON-data till dataclasses.
- `rpg_game/core/game.py`: `GameEngine`; orkestrerar world, combat, loot, store och progression.
- `rpg_game/core/combat.py`: action/effect-resolver, skada, statusar, AI och Identify-resultat.
- `rpg_game/core/progression.py`: `round_half_up`, XP-krav, level-skalad XP och statval.
- `rpg_game/core/talents.py`: talent unlock/equip, passiva effekter och max 4 skills.
- `rpg_game/core/store.py`: köp, sälj och weapon equip-regler i butik.
- `rpg_game/core/inventory.py`: användning av consumables.
- `rpg_game/core/world.py`: plats, resa och encounters.

## Datafiler

Allt nytt innehåll ska i första hand in i `rpg_game/data/`.

- `classes.json`: klassernas basstats, startvapen och startskills.
- `actions.json`: actions och skills, inklusive effekter, cooldowns, mana och gating.
- `talents.json`: talent trees och passiva effekter.
- `weapons.json`: vapen, tier, kategori, skadetyp, skadebonus och pris.
- `items.json`: consumables och junk.
- `enemies.json`: fiendemallar, AI-regler, tags, loot pools och drop chance.
- `loot.json`: delad rare table.
- `world.json`: karta, platser, connections, stores och encounter pools.

Undvik att hårdkoda nya fiender, vapen, platser eller skills i Python-koden om
det kan uttryckas i JSON.

## Regler Som Måste Bevaras

- Använd `round_half_up()` för skada och XP-formler där halv-avrundning spelar roll.
- Använd inte Pythons `round()` för spelbalansregler.
- Armor reducerar bara `physical`; övriga skadetyper använder `resistances`.
- Skada är en lista skadekomponenter: varje avräknas mot sin egen `resistance`,
  bara `physical` mot `armor`; summan minus `mitigation` golvas vid 1.
- Spelaren väljer en enda `Attack`-action; kärnan rollar quick/normal/power
  viktat och använder den rollade profilens hit chance och damage range.
  Skills har fast multiplikator. Crit är en additiv range-förlängare, inte
  fast ×2. Inga fasta basattack-skadetal — se `DAMAGE.md` för skademodellen.
- Fienden attackerar inte om den redan dött tidigare i rundan.
- Level up får inte anropa `input()` i kärnan. Returnera pending choices.
- Talangval och statval drivs av presentationen via `GameEngine`.
- Max 4 utrustade skills.
- Skills med `requires_weapon_category` är otillgängliga med fel vapenkategori.
- Gated damage skills skalar med `Power + equipped_weapon.damage_bonus`.
- Vapen kan ägas oavsett level, men equip/swap kräver `max(1, tier - 2)`.
- Loot-rarity visas som label, inte exakt dropchance.

## Klasser

Alla sex klass-träd är byggda och testade:

- Cleric
- Tank
- Rogue
- Fighter
- Mage
- Hunter

Klassdata ligger i `classes.json`, `actions.json` och `talents.json`.
Motorfunktioner som behövdes för klasserna ska hållas generiska och datadrivna:
crit, evasion, conditional modifiers, armor penetration, multi-hit, stacking
buffs, skip_turn, mitigation, reflect, vulnerability och status ticks.

## Enemy AI

Fiender använder samma action/effect-pipeline som spelaren. AI väljer action
via `enemy.ai`:

- första matchande och ready regel används
- fallback är uniformt slumpval bland ready icke-telegraph-actions
- telegraph-actions laddas en runda och släpps nästa om fienden överlever

## Loot

`enemy.drop_chance` avgör om något droppar. Om ja väljs ett item viktat ur
fiendens loot pool plus eventuell shared rare table.

Rarity-label räknas från faktisk dropchance i den aktuella poolen:

- `common`: 1/1-1/20
- `uncommon`: 1/21-1/50
- `rare`: 1/51-1/150
- `mega rare`: 1/151-1/300
- `legendary`: 1/301+

Spelaren ser bara labeln, inte exakta odds.

## Dokument

- Läs `README.md` för projektöversikt.
- Läs `SPEC.md` endast för Java-prototypens historik.
- Läs `DESIGN.md` för Python-versionens målbild.
- Läs slice-dokumenten (`CLASSES.md`, `WEAPONS.md`, `PROGRESSION.md`,
  `LOOT.md`, `ENEMIES.md`, `DAMAGE.md`) när du ändrar relaterade system.

## När Du Ändrar Kod

1. Läs relevant modul och relevant datafil först.
2. Håll ändringen liten och datadriven där det går.
3. Lägg eller uppdatera fokuserade tester för ny regel.
4. Kör:

```sh
python3 -m unittest discover -s tests
python3 -m compileall -q rpg_game tests
```

5. Kontrollera att `rpg_game/core/` fortfarande saknar `print()` och `input()`.

## Kända Begränsningar

Inte implementerat ännu:

- save/load
- bank/stash
- quests
- dialogsystem
- Pygame
- permanent bestiary för Identify
- flera samtidiga fiender
