# SPEC: RpgGameLucasAndSvante

Detta dokument beskriver spelet som det ser ut i koden idag. Det är inte en design för en framtida port, utan en nulägeskarta över Java-versionens faktiska beteende.

## Projektöversikt

- Språk: Java.
- Projektformat: Eclipse Java-projekt.
- Källkod: `src/`.
- Kompilerade klassfiler: `bin/`.
- Paket: inga Java-paket används; alla klasser ligger i default package.
- Extern dependency: inga externa bibliotek. Endast Java standardbibliotek (`Scanner`, `Random`, `LinkedList`).
- Startklass: `Main`.
- Entry point: `public static void main(String[] args)` i `src/Main.java`.

Körning utifrån befintlig struktur:

```sh
java -cp bin Main
```

Om koden behöver kompileras om:

```sh
javac -d bin src/*.java
java -cp bin Main
```

## Mappstruktur

```text
.
├── README.md
├── SPEC.md
├── .classpath
├── .project
├── .gitignore
├── src/
│   ├── Main.java
│   ├── GameObject.java
│   ├── Player.java
│   ├── Fight.java
│   ├── Input.java
│   ├── Store.java
│   ├── GiantRat.java
│   ├── CaveBear.java
│   └── Undead.java
└── bin/
    ├── Main.class
    ├── GameObject.class
    ├── Player.class
    ├── Fight.class
    ├── Input.class
    ├── Store.class
    ├── GiantRat.class
    ├── CaveBear.class
    └── Undead.class
```

`.gitignore` ignorerar `/bin/`, men `bin/` finns ändå i arbetskatalogen med kompilerade klassfiler.

## Klasser och ansvar

### `Main`

Ansvarar för programstart, initiering och huvudloop.

Viktiga fält:

- `LinkedList<GameObject> enemies`: lista med fiender.
- `Scanner scanner`: läser namn och klass från terminalen.
- `boolean isRunning = true`: styr huvudloopen. Sätts aldrig till `false` i nuvarande kod.
- `String name`: spelarens namn.
- `String klass`: spelarens klass.
- `Player player`: spelarobjektet.
- `Fight fight = new Fight()`: stridssystemet.
- `Store store`: butik.
- `boolean loop = true`: används vid klassval.
- `Random r`: slumpgenerator för fiendeval.
- `int ranE`: valt fiendeindex.
- `Input input = new Input()`: menyinput.

### `GameObject`

Abstrakt basklass för spelare och fiender.

Attribut:

- `int hp`
- `int dmg`
- `String name`
- `int maxHp`
- `int lvl`
- `int xp`
- `int gold`

Det finns inga metoder i basklassen.

### `Player`

Ärver från `GameObject`. Representerar hjälten.

Extra attribut:

- `String klass`
- `int armor = 0`
- `int invSpot`
- `int lastSpot = 0`
- `int xpReq = 100`
- `int xpLeft`
- `int weaponId`
- `String[] weaponArray = new String[5]`
- `int inputVar`
- `boolean loop = true`
- `Scanner scanner`

Metoder:

- `initWeaponArray()`: fyller vapennamn/itemnamn.
- `incStats()`: spelaren väljer stat vid level up.
- `levelUp()`: kontrollerar XP och höjer level.
- `update()`: kör `levelUp()`.
- `newWeapon(int id)`: sätter aktivt vapen-ID.
- `displayInv()`: skriver ut guld och aktivt vapen.
- `displayStats()`: skriver ut damage, HP, armor och XP.

### `Fight`

Ansvarar för strid mellan spelare och en fiende.

Viktiga fält:

- `boolean loop`
- `int loot`
- `int eChoise = 0`
- `Scanner scanner`
- `Random r`
- `int input`

Metoder:

- `playerAttack(GameObject player, GameObject enemy)`
- `enemyAttack(GameObject player, GameObject enemy)`
- `fight(GameObject player, GameObject enemy)`

### `Input`

Skriver ut huvudmenyn och läser menyval.

Attribut:

- `Scanner scanner`
- `int choise = 0`

Metod:

- `normalInput()`

### `Store`

Butikssystem.

Attribut:

- `String[] itemList = new String[4]`
- `Scanner scanner`
- `int itemId = 0`
- `int buy`
- `Player player`

Metoder:

- `initItems()`
- `buyItems()`

### Fiendeklasser

Alla fiender ärver från `GameObject`.

- `GiantRat`
- `CaveBear`
- `Undead`

Varje fiendeklass har en oanvänd `Random r`.

## Game loop och spelflöde

### Start

1. `main()` skapar `new Main()`.
2. `Main()` kör `init()`.
3. `Main()` kör `gameLoop()`.

### Initiering

`init()` gör följande:

1. Skriver ut `Welcome to svantrenish rpg!`.
2. Frågar efter spelarens namn.
3. Frågar om spelaren vill vara `fighter` eller `tank`.
4. Om spelaren skriver `fighter` skapas:
   - `Player(100, 15, name, "fighter")`
   - `maxHp = 100`
   - `hp = 100`
   - `dmg = 15`
5. Om spelaren skriver `tank` skapas:
   - `Player(120, 10, name, "tank")`
   - `maxHp = 120`
   - `hp = 120`
   - `dmg = 10`
6. Alla andra klassval ger `invalid input!` och frågan upprepas.
7. Skriver ut vald klass.
8. Sätter `player.weaponId = 0`.
9. Kör `player.initWeaponArray()`.
10. Sätter `player.xp = 99`.
11. Skapar `Store(player)`.
12. Kör `store.initItems()`.

### Huvudloop

`gameLoop()` kör:

```java
while(isRunning){
    update();
}
```

`isRunning` sätts aldrig till `false`, så spelet har inget normalt avslut.

Varje `update()` gör följande:

1. Lägger till nya fiender i `enemies`:
   - `new GiantRat()`
   - `new CaveBear()`
   - `new Undead()`
2. Kör `player.update()`, vilket bara kontrollerar level up.
3. Kör `input.normalInput()`.
4. Hanterar menyval:
   - `1`: visa stats.
   - `2`: slåss mot slumpad fiende.
   - `3`: visa inventory.
   - `4`: öppna butik.
   - annat: `Invalid command!`
5. Försöker rensa `enemies`.

### Huvudmeny

`Input.normalInput()` visar bara:

```text
What do you want to do?

Display stats and xp: 1
Fight a random enemy: 2
Display inventory: 3
```

`Main.update()` stödjer även `case 4` för butik, men menytexten visar inte detta val.

### Fiendeval

Vid menyval `2` används:

```java
ranE = r.nextInt(2) + 1;
fight.fight(player, enemies.get(ranE));
```

Det ger bara index `1` eller `2`.

Vid första loopen, när listan är `[GiantRat, CaveBear, Undead]`, kan spelaren därför bara möta:

- `CaveBear`
- `Undead`

`GiantRat` väljs inte i första rundan.

Eftersom rensningen av `enemies` tar bort element samtidigt som index räknas upp lämnas vissa fiender kvar mellan uppdateringar. Det betyder att fiendelistan kan innehålla gamla fiender plus nya fiender i senare loopar.

## Entiteter

### Hjälte: fighter

Skapas vid klassval `fighter`.

| Attribut | Värde |
|---|---:|
| `name` | spelarens input |
| `klass` | `fighter` |
| `hp` | 100 |
| `maxHp` | 100 |
| `dmg` | 15 |
| `armor` | 0 |
| `gold` | 0 |
| `xp` | sätts först till 0 i constructor, sedan till 99 i `Main.init()` |
| `xpReq` | 100 |
| `lvl` | 0, eftersom det aldrig sätts i constructor |
| `weaponId` | 0 |
| startvapen | `Knife` |

### Hjälte: tank

Skapas vid klassval `tank`.

| Attribut | Värde |
|---|---:|
| `name` | spelarens input |
| `klass` | `tank` |
| `hp` | 120 |
| `maxHp` | 120 |
| `dmg` | 10 |
| `armor` | 0 |
| `gold` | 0 |
| `xp` | sätts först till 0 i constructor, sedan till 99 i `Main.init()` |
| `xpReq` | 100 |
| `lvl` | 0, eftersom det aldrig sätts i constructor |
| `weaponId` | 0 |
| startvapen | `Knife` |

### Giant Rat

| Attribut | Värde |
|---|---:|
| `name` | `Giant Rat` |
| `hp` | 20 |
| `maxHp` | 0, eftersom det aldrig sätts |
| `dmg` | 6 |
| `lvl` | 1 |
| `xp` | 0 |
| `gold` | 0 |

### CaveBear

| Attribut | Värde |
|---|---:|
| `name` | `CaveBear` |
| `hp` | 55 |
| `maxHp` | 0, eftersom det aldrig sätts |
| `dmg` | 8 |
| `lvl` | 3 |
| `xp` | 0 |
| `gold` | 0 |

### Undead

| Attribut | Värde |
|---|---:|
| `name` | `Undead` |
| `hp` | 45 |
| `maxHp` | 0, eftersom det aldrig sätts |
| `dmg` | 4 |
| `lvl` | 2 |
| `xp` | 0 |
| `gold` | 0 |

### NPC:er

Det finns ingen separat NPC-klass. Butiken representeras av `Store`, men ingen butiks-NPC eller dialogentitet finns.

## Stridssystem

Strid startar med:

```java
fight.fight(player, enemy);
```

Vid start skrivs:

```text
You encounter a [enemy.name]
```

Varje stridsrunda:

1. `loot = 0` sätts i början av rundan.
2. Spelarens HP skrivs ut.
3. Fiendens HP skrivs ut.
4. Spelaren väljer attack:
   - `1`: Power attack.
   - `2`: Normal attack.
   - `3`: Quick attack.
5. Spelaren attackerar.
6. Fienden attackerar alltid efteråt.
7. Efter båda attackerna kontrolleras död/vinst.

Det betyder att fienden fortfarande attackerar samma runda även om spelarens attack sänker fiendens HP till 0 eller mindre.

### Spelarens attacker

Attackval lagras i `Fight.input`.

| Val | Namn i UI | Träffvillkor i kod | Ungefärlig chans | Skada |
|---:|---|---|---:|---:|
| 1 | Power attack | `r.nextInt(101) >= 70` | 31/101, ca 30.69% | `player.dmg * 2` |
| 2 | Normal attack | `r.nextInt(101) >= 45` | 56/101, ca 55.45% | `player.dmg * 1.5` |
| 3 | Quick attack | `r.nextInt(101) >= 25` | 76/101, ca 75.25% | `player.dmg` |

UI visar avrundat:

```text
Power attack(30%): 1
Normal attack(55%): 2
Quick attack(75%): 3
```

Om spelaren skriver något annat än `1`, `2` eller `3` gör spelaren ingen attack, men fienden attackerar ändå.

### Fiendens attacker

Fienden väljer attack slumpmässigt:

```java
eChoise = r.nextInt(3) + 1;
```

Det ger attack `1`, `2` eller `3`.

| Val | Typ | Träffvillkor i kod | Ungefärlig chans | Skada |
|---:|---|---|---:|---:|
| 1 | Power-liknande | `r.nextInt(101) >= 70` | 31/101, ca 30.69% | `enemy.dmg * 2` |
| 2 | Normal-liknande | `r.nextInt(101) >= 45` | 56/101, ca 55.45% | `enemy.dmg * 1.5` |
| 3 | Quick-liknande | `r.nextInt(101) >= 25` | 76/101, ca 75.25% | `enemy.dmg` |

### HP och decimal skada

`hp` är `int`, men normal attack använder `* 1.5`, vilket ger ett `double`-värde.

Java tillåter detta genom compound assignment:

```java
enemy.hp -= player.dmg * 1.5;
player.hp -= enemy.dmg * 1.5;
```

Det motsvarar att resultatet castas tillbaka till `int`. Texten som skrivs ut kan därför visa decimal skada, medan faktisk HP blir heltal.

Exempel:

- Fighter med `dmg = 15` gör normal attack: utskriven skada är `22.5`.
- Om fienden har `45 hp` blir nytt HP `(int)(45 - 22.5) = 22`.

### Armor

`Player.armor` finns och visas i stats, men används inte i stridsberäkningar.

### Dödsregler

Efter spelar- och fiendeattack kontrolleras:

1. Om `player.hp <= 0`:
   - skriver `You died!`
   - sätter `player.hp = player.maxHp`
   - sätter `enemy.hp = enemy.maxHp`
   - avslutar striden
2. Annars om `enemy.hp <= 0`:
   - skriver `You killed the enemy!`
   - sätter `enemy.hp = enemy.maxHp`
   - ger XP
   - ger guld beroende på fiendens level
   - avslutar striden

Fiendernas `maxHp` sätts aldrig, så `enemy.maxHp` är `0`. Reset av fiende-HP sätter därför fiendens HP till `0`.

Eftersom fiender skapas på nytt i `Main.update()` påverkar detta oftast inte nästa nyskapade fiende, men gamla kvarlämnade fiendeobjekt i listan kan ha `hp = 0`.

### XP-belöning

Vid dödad fiende:

```java
player.xp += enemy.lvl * 5;
```

| Fiende | Level | XP |
|---|---:|---:|
| Giant Rat | 1 | 5 |
| Undead | 2 | 10 |
| CaveBear | 3 | 15 |

### Gold loot

Guld ges baserat på fiendens level.

| Fiendelevel | Kod | Möjligt utfall |
|---:|---|---:|
| 1 | `r.nextInt(6) + 3` | 3-8 guld |
| 2 | `r.nextInt(18) + 14` | 14-31 guld |
| 3 | `r.nextInt(22) + 18` | 18-39 guld |

Mappning till nuvarande fiender:

| Fiende | Level | Gold range |
|---|---:|---:|
| Giant Rat | 1 | 3-8 |
| Undead | 2 | 14-31 |
| CaveBear | 3 | 18-39 |

## Level och progression

`Player.update()` kör `levelUp()` varje huvudloop före menyvalet.

Level up sker om:

```java
if(xp >= xpReq)
```

Vid level up:

1. `hp = maxHp`
2. `xp = 0`
3. `xpReq *= xpReq * 1.00000000000`
4. `incStats()`
5. `lvl++`

Startvärden:

- `xp = 99` efter `Main.init()`.
- `xpReq = 100`.
- `lvl = 0`.

Det betyder att spelaren normalt levlar efter första dödade fienden, men level up sker först i nästa `update()` eftersom XP-kontrollen ligger före menyval/strid.

### Nytt XP-krav

Koden:

```java
xpReq *= xpReq * 1.00000000000;
```

Eftersom `xpReq` är `int` och compound assignment castar tillbaka till `int` blir första ändringen:

- från `100`
- till `10000`

Nästa level skulle därefter kräva extremt mycket mer XP.

### Statval vid level up

`incStats()` frågar:

```text
You just increased lvl! Type '1' for increased dmg and '2' for increased hp!
```

Val:

- `1`: `dmg += 5`
- `2`: `hp += 10`

Observera:

- Val `2` ökar bara aktuell `hp`, inte `maxHp`.
- `incStats()` använder fältet `loop`, som sätts till `false` efter första giltiga statvalet och återställs inte till `true`. Vid senare level up kan därför statvalet hoppas över.

## Vapen, items och skills

### Weapon array

`Player.initWeaponArray()` sätter:

| ID | Namn |
|---:|---|
| 0 | `Knife` |
| 1 | `Sword` |
| 2 | `Axe` |
| 3 | `Longsword` |
| 4 | `Hp potion` |

Aktivt vapen visas i inventory:

```java
weaponArray[weaponId]
```

Vapen påverkar inte skada i nuvarande kod. `newWeapon(int id)` ändrar bara `weaponId`.

### Store item list

`Store.initItems()` sätter:

| Butiksval | Item |
|---:|---|
| 1 | `Hp potion` |
| 2 | `Sword` |
| 3 | `Axe` |
| 4 | `Longsword` |

Butiken skriver ut itemnamn men inga priser.

### Butiksregler

`Store.buyItems()`:

| Val | Krav | Kostnad i kod | Effekt |
|---:|---:|---:|---|
| 1 | `player.gold >= 65` | 65 | `player.hp = player.maxHp` |
| 2 | `player.gold >= 100` | 50 | `player.newWeapon(1)` |
| 3 | `player.gold >= 175` | 175 | `player.newWeapon(2)` |
| 4 | `player.gold >= 350` | 350 | `player.newWeapon(3)` |

Sword har inkonsekvent krav och kostnad:

- Kräver minst 100 guld.
- Drar bara 50 guld.

Om spelaren saknar guld eller skriver ett annat val händer ingenting och inget felmeddelande visas.

Butiken kan nås via menyval `4`, men huvudmenyn visar inte att valet finns.

### Skills

Det finns inget separat skill-system. De enda stridsvalen fungerar som attacktyper:

- Power attack
- Normal attack
- Quick attack

Dessa har fasta träffchanser och skademultipliers enligt stridsavsnittet.

## Save/load

Det finns inget save/load-system.

All progression finns bara i minnet under körningen:

- HP
- damage
- XP
- level
- gold
- aktivt vapen

När programmet avslutas försvinner allt.

## Färdigt i nuvarande kod

Följande finns implementerat i någon form:

- Terminalbaserad start med namn och klassval.
- Två spelarklasser: `fighter` och `tank`.
- Basklass för spelobjekt.
- Tre fiendetyper.
- Huvudmeny med stats, fight och inventory.
- Slumpad strid med tre attacktyper.
- HP, damage, XP, level och gold.
- Loot från fiender.
- Inventory-visning.
- Butikssystem med potion och vapen.
- Level up med val mellan damage och HP.

## Ofullständigt eller inkonsekvent

- Spelet har inget normalt avslut; `isRunning` sätts aldrig till `false`.
- Huvudmenyn visar inte butiksvalet `4`, trots att `Main.update()` stödjer det.
- Fiendevalet använder bara index `1` och `2`, så första `GiantRat` kan inte väljas.
- Fiendelistan rensas inte korrekt; gamla fiender kan ligga kvar.
- Fiendernas `maxHp` sätts aldrig, vilket gör reset till `0`.
- Fienden attackerar även om spelarens attack redan har dödat den.
- Armor visas men används inte.
- Vapen påverkar inte spelarens damage.
- Butikens vapen har inga stats.
- Sword kräver 100 guld men kostar 50 guld.
- Butiken visar inga priser och inga felmeddelanden vid otillräckligt guld.
- `Hp potion` finns både som butiksitem och i `weaponArray`, men `weaponArray[4]` används inte som potion.
- `Player.invSpot`, `Player.lastSpot`, `Store.itemId` och flera `Random r`-fält används inte.
- `Player.lvl` startar implicit på 0.
- Spelarens XP sätts till 99 i `Main.init()`, vilket gör att första dödade fienden nästan direkt triggar level up.
- `xpReq` hoppar från 100 till 10000 vid första level up.
- HP-val vid level up ökar aktuell HP men inte `maxHp`.
- `incStats()` kan bara fungera korrekt första gången eftersom dess loop-flagga inte återställs.
- Input hanteras med flera separata `Scanner`-instanser på `System.in`.
- Ogiltig input i strid ger ingen varning och låter fienden attackera.
- Det finns ingen save/load.
- Det finns ingen karta, quests, dialog, NPC-modell eller storyprogression utöver starttext.

## Otydligt eller saknas inför fortsatt design

Följande behöver beslutas eller fyllas i innan en Python/Pygame-port kan bli en tydlig spelritning:

- Ska spelet vara oändligt, eller ska det finnas ett mål/slut?
- Ska `GiantRat` vara en möjlig fiende från början?
- Hur ska fiender väljas: helt slumpat, per område, per level eller enligt encounter-tabell?
- Ska fiender ha `maxHp`, och ska de kunna återanvändas?
- Ska fienden få attackera efter att den dött samma runda?
- Ska spelaren dö permanent, respawna, förlora guld/XP eller bara healas?
- Vad ska armor göra?
- Vilka stats ska vapen ha?
- Ska weapon damage ersätta eller modifiera spelarens `dmg`?
- Ska potion vara ett inventory-item, ett direktköp i butik eller båda?
- Ska det finnas inventory med flera items, stackar och konsumtion?
- Vilka priser ska butiksitems faktiskt ha, särskilt Sword?
- Ska butiken vara synlig i huvudmenyn?
- Ska level börja på 1 istället för 0?
- Vad ska XP-kurvan vara efter level 1?
- Ska level up-valet öka `maxHp` eller bara nuvarande HP?
- Ska attackchanserna vara exakt 30/55/75 eller som kodens 31/101, 56/101 och 76/101?
- Ska decimal skada tillåtas, avrundas, golvas eller alltid vara heltal?
- Ska klassval vara case-insensitive, till exempel godkänna `Fighter`?
- Ska felaktig input reprompta istället för att låta spelet fortsätta?
- Ska spelet ha save/load?
- Ska det finnas karta, platser, quests, dialoger eller NPC:er?
- Ska Pygame-porten bevara buggar exakt eller använda detta dokument för att definiera korrigerat beteende?
