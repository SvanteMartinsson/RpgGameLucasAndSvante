# RpgGameLucasAndSvante

Ett textbaserat RPG som började som en Java-prototyp och nu portas till en
datadriven Python-version. Den spelbara versionen finns i `rpg_game/`; den
ursprungliga Java-koden ligger kvar i `src/` som historik och referens.

## Snabbstart

Kör spelet från projektroten:

```sh
python3 -m rpg_game
```

Kör testsviten:

```sh
python3 -m unittest discover -s tests
```

Kör en snabb import-/syntaxkontroll:

```sh
python3 -m compileall -q rpg_game tests
```

Projektet kräver Python 3.10+ och har inga externa runtime-beroenden.

## Projektstruktur

```text
rpg_game/
  core/              # spelkärnan: regler, state, combat, progression, world
  data/              # JSON-data för klasser, skills, fiender, loot och värld
  presentation/      # terminal-UI + Pygame-UI (battle + overworld)
  tools/             # utvecklarverktyg för tuning och diagnostik
tests/               # regressionstester för regler och speldata
src/                 # ursprunglig Java-prototyp
bin/                 # kompilerade Java-klasser, historik
*.md                 # design-, slice- och projektdokumentation
```

Viktig princip: `rpg_game/core/` får inte vara beroende av terminalen. Kärnan
returnerar strukturerade resultat; `rpg_game/presentation/terminal.py` skriver
text och läser input. Tack vare det använder Pygame-lagret samma spelregler
utan att duplicera dem.

## Dokumentation

- `README.md`: praktisk översikt för att köra och förstå projektet.
- `CLAUDE.md`: arbetsregler och arkitekturkontrakt för framtida kodarbete.
- `SPEC.md`: vad den ursprungliga Java-versionen faktiskt gjorde.
- `DESIGN.md`: målbilden för Python-porten.
- `COMBAT_DESIGN.md`: stridsmotor, stats, statusar och ekonomi på systemnivå.
- `CLASSES.md`: konkret klass- och talangdata.
- `WEAPONS.md`: vapenkategorier, skill-gating och vapenskalning.
- `PROGRESSION.md`: enemy levels, XP-skalning, equip-krav och Identify.
- `LOOT.md`: lootmodell, rare table, pickup och sälj.
- `ENEMIES.md`: fiendearketyper, AI och telegraph.
- `DAMAGE.md`: multikomponent-skada, attack-action och crit-range.
- `PRESENTATION_API.md`: kontraktet mellan core och terminal/Pygame-lager.
- `OVERWORLD.md`: Pygame-/tilemap-overworlden (kamera, gates, zoner).

## Spelöversikt

Spelaren väljer klass, startar i världen från `world.json`, reser mellan
platser, utforskar för encounters, slåss i turordning baserad på speed och får
XP, guld och eventuellt loot vid seger.

Nuvarande Python-version innehåller:

- sex spelarklasser: Cleric, Tank, Rogue, Fighter, Mage och Hunter
- talent trees med linjär upplåsning per gren
- max fyra utrustade skills
- action -> effects -> resolver-pipeline för strid
- statusar som poison, regen, buff, debuff, mitigation, reflect och skip_turn
- crit, evasion, armor penetration, multi-hit och conditional damage
- mana, cooldowns, speed-baserad turordning och enemy AI
- vapenägande, vapenbyte, vapenkategorier och level-krav för att equippa
- loot drops med rarity-labels, pickup och sälj i butik
- level-skalad XP och Identify i strid
- save/load
- immutable snapshots för presentationslager
- platsbundna turneringar med namngivna mänskliga motståndare

## Tuning

Kör attack-only-simuleringar för klass/fiende-matchups:

```sh
python3 -m rpg_game.tools.simulate_balance --trials 100
```

Verktyget skriver CSV med win rate, average turns, HP vid seger och timeouts.
Det är ett underlag för nummer-tuning, inte en ersättning för manuell playtest.

## Datadrivet innehåll

Nytt innehåll ska i första hand in i `rpg_game/data/`, inte hårdkodas i
spelkärnan.

- `classes.json`: klassernas startstats och startskills.
- `actions.json`: basattacker, skills, items och fiende-actions.
- `talents.json`: klassernas talent nodes och passiva effekter.
- `weapons.json`: vapen, tier, kategori, skadetyp, pris och bonus.
- `items.json`: consumables och junk.
- `enemies.json`: fiendestats, AI, loot pools och drop chance.
- `tournaments.json`: platsbundna turneringar, opponent-serier och rewards.
- `loot.json`: delad rare table.
- `world.json`: karta, platser, resvägar, encounters och butikslager.

### Lägga till en fiende

1. Lägg fienden i `rpg_game/data/enemies.json`.
2. Lägg fiendens `id` i `encounters` för en plats i `world.json`.
3. Kör `python3 -m unittest discover -s tests`.

### Lägga till ett vapen

1. Lägg vapnet i `rpg_game/data/weapons.json`.
2. Sätt `tier`, `category`, `damage_type`, `damage_bonus` och `price`.
3. Lägg vapnet i en butik eller loot table.
4. Kör testerna.

### Lägga till en skill

1. Lägg actionen i `actions.json`.
2. Koppla den till en aktiv talent node i `talents.json`.
3. Om skillen kräver vapentyp, sätt `requires_weapon_category`.
4. Lägg ett fokuserat test för regeln.

### Lägga till en turnering

1. Lägg namngivna motståndare i `enemies.json`.
2. Lägg turneringen i `tournaments.json` med `place_id`, `opponent_ids` och
   `reward`.
3. Håll individuella tournament-opponents på låg/ingen loot om slutrewarden ska
   vara den viktiga belöningen.
4. Kör testerna.

## Viktiga regler

- Använd `round_half_up()` för skada och XP-formler där halv-avrundning spelar
  roll. Använd inte Pythons `round()` för dessa spelregler.
- Armor reducerar bara physical damage. Övriga skadetyper går via resistances.
- Minst 1 skada går igenom efter mitigation när en träff gör skada.
- En fiende attackerar inte om spelaren redan dödat den samma runda.
- Level up får inte blockera i kärnan. Kärnan sätter pending stat choices och
  presentationen frågar spelaren.
- Loot-rarity visas för spelaren som klass (`common`, `rare` osv.), inte som
  exakt dropchance.

## Nuvarande begränsningar

Följande är medvetet inte färdigt ännu:

- bank/stash
- quests och dialogsystem
- permanent bestiary för Identify
- flera samtidiga fiender
