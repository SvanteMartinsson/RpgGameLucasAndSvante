# DESIGN: Python-versionen

Detta dokument beskriver målbeteendet för Python-versionen av spelet. `SPEC.md` beskriver Java-versionens nuläge; den används här som källa till spelets avsikt, men dokumenterade buggar och inkonsekvenser ska rättas.

## Mål

Första målet är en spelbar textversion i Python med ren spelkärna. Kärnan ska senare kunna användas av ett Pygame-gränssnitt utan att spelregler behöver skrivas om.

Spelet är ett textbaserat RPG där spelaren:

- skapar en hjälte
- väljer klass
- reser mellan platser på en världskarta
- möter fiender från platsens encounter-pool
- slåss med tydliga attackregler
- får XP och guld
- levlar upp
- köper vapen och potions
- använder inventory

Det behövs inget hårt slut ännu, men värld, progression och state ska designas så att quests, bossar eller vinstvillkor kan läggas till senare.

## Arkitekturprincip

Spelprojektet delas i två tydliga lager:

1. Spelkärna: entiteter, strid, progression, inventory, butik och värld. Den känner inte till terminal, Pygame, rendering eller input-metod.
2. Presentation: textgränssnittet i terminalen. Det översätter användarens val till anrop mot spelkärnan och visar resultat.

Pygame ska senare kunna bli ett alternativt presentationslager ovanpå samma kärna.

## Datadrivet innehåll

Innehåll ska ligga samlat i datafiler, inte utspritt i logiken.

Föreslagen lösning för steg 1:

- JSON för spelinnehåll som ofta ändras:
  - spelarklasser
  - vapen
  - förbrukningsitems
  - fiender
  - platser
  - butiksutbud
- Python `dataclasses` för runtime-objekt:
  - player
  - enemy instance
  - inventory
  - world state
  - combat result

JSON väljs för innehåll eftersom det är lätt att ändra utan att röra Python-kod.

## Föreslagen mappstruktur

Detta är strukturen som bör skapas för Python-porten:

```text
.
├── README.md
├── SPEC.md
├── DESIGN.md
├── CLAUDE.md
├── pyproject.toml
├── rpg_game/
│   ├── __init__.py
│   ├── __main__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── combat.py
│   │   ├── data_loader.py
│   │   ├── entities.py
│   │   ├── game.py
│   │   ├── inventory.py
│   │   ├── progression.py
│   │   ├── store.py
│   │   └── world.py
│   ├── data/
│   │   ├── classes.json
│   │   ├── enemies.json
│   │   ├── items.json
│   │   ├── world.json
│   │   └── weapons.json
│   └── presentation/
│       ├── __init__.py
│       └── terminal.py
└── tests/
    ├── test_combat.py
    ├── test_inventory.py
    └── test_progression.py
```

Första implementationen behöver inte ha många tester, men strukturen gör det lätt att testa spelregler utan att köra terminal-UI.

## Körning

Målet är att textversionen ska kunna köras med:

```sh
python -m rpg_game
```

Inga externa dependencies krävs i första steget.

Pygame installeras inte ännu.

## Spelflöde

### Start

1. Textgränssnittet startar.
2. Spelaren anger namn.
3. Spelaren väljer klass.
4. Ett nytt `GameState` skapas.
5. Spelaren placeras på `meta.start_place_id` från `world.json`.
6. Huvudmenyn visas.

All input ska vara case-insensitive. Ogiltig input ska ge ett tydligt felmeddelande och fråga igen.

### Huvudmeny

I textversionen ska huvudmenyn visa:

- visa stats
- visa inventory
- resa
- utforska / leta strid på nuvarande plats
- butik, om platsen har butik
- använd item
- avsluta

Till skillnad från Java-versionen ska alla tillgängliga val visas. Butiken ska synas när den kan användas.

### Värld och platser

Spelet struktureras runt en världskarta med platser/städer.

Världen laddas från `rpg_game/data/world.json`.

Top-level-format:

```json
{
  "meta": {
    "start_place_id": "some_place_id"
  },
  "places": []
}
```

Varje plats ska stödja och bevara dessa fält:

- `id`
- `name`
- `type`
- `description`
- `has_store`
- `mana_site`
- `port`
- `position` med `x` och `y`
- `danger_tier`
- `encounters`
- `respawn`
- `locked`
- `connections`

Varje connection ska stödja:

- `to`
- `travel`
- `distance_px`
- `distance_km_approx`

Regler:

- `meta.start_place_id` bestämmer var spelaren börjar.
- Resa använder alltid plats-id från `connections[].to`, aldrig platsnamn som intern referens.
- `locked = true` gör platsen onåbar tills den låsts upp.
- Upplåsningsmekanik är en TODO-stub i första versionen.
- `respawn = true` markerar respawn-platser.
- `has_store` styr om butiken visas.
- `mana_site`, `port`, `danger_tier`, `distance_px` och `distance_km_approx` laddas men har ingen spelmekanisk effekt ännu.

Vald enkel lösning: spelaren kan resa direkt mellan anslutna platser utan kostnad, tidsförlust eller random encounter under resan.

### Encounters

När spelaren väljer att utforska nuvarande plats slumpas en fiende från platsens `encounters`.

Regler:

- Alla fiender i platsens `encounters` kan väljas.
- Tom `encounters`-lista betyder trygg plats och ingen strid.
- Fiender skapas som nya instanser från data varje encounter.
- En fiende har alltid `hp = max_hp` vid stridsstart.
- Fiender återanvänds inte mellan strider.

## Entiteter

### Player

Spelaren har:

- `name`
- `player_class`
- `level`
- `xp`
- `xp_required`
- `hp`
- `max_hp`
- `base_damage`
- `armor`
- `gold`
- `equipped_weapon_id`
- `inventory`
- `current_place_id`
- `respawn_place_id`

Startvärden:

| Klass | Level | XP | Max HP | Base damage | Armor | Guld | Startvapen |
|---|---:|---:|---:|---:|---:|---:|---|
| Fighter | 1 | 0 | 100 | 15 | 0 | 0 | Knife |
| Tank | 1 | 0 | 120 | 10 | 2 | 0 | Knife |

Vald enkel lösning: tank får `armor = 2` eftersom armor annars finns men saknar tydlig skillnad mellan klasserna. Fighter behåller högre damage.

### Enemy

En fiende har:

- `id`
- `name`
- `level`
- `max_hp`
- `hp`
- `damage`
- `armor`
- `xp_reward`
- `gold_min`
- `gold_max`

Första fiendedata:

| ID | Namn | Level | Max HP | Damage | Armor | XP | Gold |
|---|---|---:|---:|---:|---:|---:|---|
| `giant_rat` | Giant Rat | 1 | 20 | 6 | 0 | 5 | 3-8 |
| `undead` | Undead | 2 | 45 | 4 | 1 | 10 | 14-31 |
| `cave_bear` | Cave Bear | 3 | 55 | 8 | 0 | 15 | 18-39 |

XP och gold bygger på Java-versionens avsikt, men `max_hp` sätts korrekt.

## Stridssystem

Strid är turbaserad. En runda:

1. Spelaren väljer attack.
2. Spelarens attack löses.
3. Om fienden dog avslutas striden direkt.
4. Annars väljer fienden slumpmässig attack.
5. Fiendens attack löses.
6. Om spelaren dog avslutas striden med respawn.
7. Annars fortsätter striden.

Fienden attackerar alltså inte om spelaren redan dödat den samma runda.

### Attacktyper

Attacktyperna gäller både spelare och fiender:

| ID | Namn | Träffchans | Skademultiplier |
|---|---|---:|---:|
| `power` | Power attack | 30% | 2.0 |
| `normal` | Normal attack | 55% | 1.5 |
| `quick` | Quick attack | 75% | 1.0 |

Träffchans ska vara exakt 30%, 55% och 75%.

### Skadeformel

All avrundning för skada ska gå via en explicit helper:

```text
round_half_up(x) = math.floor(x + 0.5)
```

Detta används eftersom Pythons inbyggda `round()` använder banker's rounding, där `round(22.5)` blir `22`. Spelets regler ska i stället avrunda `22.5` till `23`.

Spelarens råskada:

```text
raw_damage = round_half_up((player.base_damage + equipped_weapon.damage_bonus) * attack.multiplier)
```

Fiendens råskada:

```text
raw_damage = round_half_up(enemy.damage * attack.multiplier)
```

Armor reducerar inkommande skada:

```text
final_damage = max(1, raw_damage - target.armor)
```

All faktisk skada är heltal.

Vald enkel lösning: armor gäller både spelare och fiender.

### Miss

Om attacken missar gör den 0 skada och rundan fortsätter.

Ogiltigt attackval ska inte räknas som en runda. UI:t ska fråga igen.

### Vinst

När fienden dör:

- spelaren får `xp_reward`
- spelaren får slumpat guld mellan `gold_min` och `gold_max`
- level up kontrolleras direkt efter XP-belöning
- striden avslutas

Kärnan får aldrig anropa `input()` för level up. Om XP-belöningen ger en eller flera levels ska kärnan uppdatera spelarens level och returnera hur många statval som väntar.

Combat/victory-resultatet ska uttrycka detta explicit, exempelvis:

```text
CombatTurnResult(
    outcome="victory",
    events=[...],
    xp_gained=15,
    gold_gained=24,
    levels_gained=1,
    pending_stat_choices=1
)
```

Presentationlagret ansvarar därefter för att fråga spelaren om varje statbonus och anropa en kärnmetod som:

```text
apply_stat_choice(player, "damage")
apply_stat_choice(player, "hp")
```

Kärnan ska validera statvalet, applicera effekten och minska `pending_stat_choices`. Om flera level ups sker i samma seger returnerar kärnan ett högre `pending_stat_choices`-värde, och presentationen matar tillbaka valen ett i taget.

### Död och respawn

Permadeath används inte.

När spelaren dör:

- striden avslutas
- spelaren flyttas till sin respawn-plats, normalt startstaden
- spelaren behåller level, XP, guld, vapen och inventory
- spelaren återställs till full HP

Vald enkel lösning: spelaren förlorar inget vid död i första Python-versionen. Det kan ändras senare om spelet behöver högre risk.

## Progression

Spelaren börjar på:

- level 1
- XP 0

XP-krav:

```text
xp_required(level) = round_half_up(100 * 1.5 ** (level - 1))
```

Detta betyder:

| Level | XP till nästa |
|---:|---:|
| 1 | 100 |
| 2 | 150 |
| 3 | 225 |
| 4 | 338 |
| 5 | 506 |

Level up sker direkt när spelaren har tillräckligt mycket XP. Om spelaren har XP nog för flera levels ska flera level ups kunna ske.

Vid level up:

- `level += 1`
- spelaren får välja statbonus varje gång
- val `damage`: `base_damage += 5`
- val `hp`: `max_hp += 10` och `hp += 10`, max upp till nya `max_hp`
- nytt XP-krav beräknas med formeln ovan

Vald enkel lösning: XP som överstiger kravet sparas, istället för att nollställas.

## Inventory

Inventory är enkelt men riktigt:

- en utrustad vapenslot
- stackbara förbrukningsvaror
- inget vikt- eller slot-system i första versionen

Spelaren startar med:

- `Knife` utrustad
- inga potions

Förbrukningsvaror lagras som:

```text
item_id -> count
```

### Potion

Potion är inte ett vapen. Den ligger i inventory och används manuellt.

Första potion:

| ID | Namn | Effekt | Pris |
|---|---|---|---:|
| `hp_potion` | HP Potion | läker 50 HP, max till `max_hp` | 65 |

Vald enkel lösning: potion kan användas både utanför strid och i strid om terminal-UI:t stödjer det. För första terminalversionen räcker det att kunna använda den från huvudmenyn.

## Vapen

Vapen ger skadepåslag ovanpå spelarens basskada.

Första vapendata:

| ID | Namn | Damage bonus | Pris |
|---|---|---:|---:|
| `knife` | Knife | 0 | 0 |
| `sword` | Sword | 5 | 50 |
| `axe` | Axe | 9 | 175 |
| `longsword` | Longsword | 14 | 350 |

Sword kostar 50 och kräver 50 guld. Java-versionens inkonsekvens mellan krav 100 och kostnad 50 rättas.

Vald enkel lösning: när spelaren köper ett vapen utrustas det direkt. Det finns ingen vapensamling ännu.

## Butik

Butik finns på platser som har `has_store = true`.

Butiken ska:

- visas i huvudmenyn när den finns på nuvarande plats
- visa itemnamn, typ, pris och relevant stat
- kontrollera guld mot priset
- visa felmeddelande vid för lite guld
- dra rätt mängd guld vid köp
- lägga potions i inventory
- utrusta köpta vapen direkt

Första butikens utbud:

- HP Potion, 65 guld
- Sword, 50 guld
- Axe, 175 guld
- Longsword, 350 guld

## Save/load

Save/load implementeras inte i första porten, men state ska hållas i strukturer som går att serialisera senare.

Vald enkel lösning: ingen fil sparas i steg 1.

## Presentation: terminal

Terminal-UI:t ska vara tunt och bara ansvara för:

- skriva text
- läsa input
- reprompta vid ogiltigt val
- visa menyer
- anropa spelkärnan
- visa resultat från spelkärnan

Terminal-UI:t ska inte själv beräkna skada, XP, loot, inventory eller world state.

## Framtida Pygame-lager

Pygame-lagret ska senare kunna använda samma spelkärna.

För att möjliggöra det ska kärnan:

- returnera strukturerade resultat från actions
- inte använda `print()`
- inte använda `input()`
- inte importera terminal- eller Pygame-kod
- inte anta att en action alltid kommer från tangentbordstext

## Fortfarande utanför aktuell implementation

Följande är fortfarande framtida arbete:

- Pygame
- save/load
- quests
- bossar
- dialogsystem
- utrustningsslots utöver vapen
- inventory-vikt eller maxslots
- kartgrafik
- permanent bestiary
- flera samtidiga fiender

Strukturen ska däremot inte blockera att detta läggs till senare.
