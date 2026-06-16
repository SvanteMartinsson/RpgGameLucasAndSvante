# COMBAT_DESIGN: Strid, klasser, progression och ekonomi

Detta dokument beskriver målbeteendet för spelets utbyggda stridssystem,
klasser, skill trees, ekonomi och friktion. Det är en ritning för en
*motoruppgradering* ovanpå den spelbara textversionen som `DESIGN.md`
beskriver — inte en omskrivning av den.

Relation till övriga dokument:

- `SPEC.md` — Java-versionens nuläge (avsikt, inte exakt beteende).
- `DESIGN.md` — Python-portens grundregler (entiteter, strid, progression,
  värld). Allt här bygger ovanpå den och får inte bryta dess
  arkitekturprinciper.
- `COMBAT_DESIGN.md` (detta dokument) — strids- och progressionsdjupet:
  klasser, skills, mana, skadetyper, fiendedjup, loot och friktion.

Alla balanssiffror nedan är startvärden avsedda att tunas i JSON, inte
huggna i sten. Strukturen är poängen; talen justeras.

## Bärande princip: en handling, en resolver

Den enskilt viktigaste regeln, och det som gör att "6 klasser × 2 träd" blir
*data* istället för kod:

**Varje stridshandling är data som beskriver vilka effekter den producerar.
En enda resolver i spelkärnan applicerar effekter och tickar statusar varje
runda.**

En basattack, en klass-skill, en använd potion och ett vapenbyte går alla
genom samma pipeline:

```text
handling (data) -> lista av effekter -> resolver applicerar -> strukturerat resultat
```

Konsekvenser:

- Att lägga till en skill är att lägga till data (effektbeskrivning), inte
  skriva ny stridskod.
- Fiender använder exakt samma pipeline. Fiende-"AI" är bara "välj en handling
  ur min egen handlingslista".
- Motorn byggs en gång och valideras med *en* klass och *en* fiendesvaghet.
  Klasser, träd och loot hälls sedan på som innehåll.

Detta får inte bryta `DESIGN.md`: kärnan använder inte `print()`/`input()`,
returnerar strukturerade resultat, och känner inte till terminal eller Pygame.

## Stats

Nuvarande stats i `DESIGN.md`: HP/Max HP, base_damage, armor. Utbyggnaden
lägger till resurs, turordning och crit. Varje stat ska göra ett distinkt
jobb och helst bära en klassidentitet.

| Stat | Status | Vad den gör | Klass-identitet |
|---|---|---|---|
| HP / Max HP | finns | Överlevnad | Tank |
| Mana / Max Mana | **ny** | Resurs som spenderas på skills | Mage / Cleric |
| Power | **döp om `base_damage`** | Enda offensiva skalningsstat; alla attacker och skills skalar från den | Fighter |
| Armor | finns, förtydligas | Platt avdrag mot **fysisk** skada (min 1 går alltid igenom) | Tank |
| Speed | **ny** | Turordning + flee-chans | Rogue |
| Crit-chans | **ny (valbar i v1)** | % chans till fast crit-multiplier | Rogue |

### Viktigt designbeslut: en offensiv stat

Det finns **ingen STR/INT-split**. En Mage är inte "hög magisk stat" — den
utrustar en stav vars `damage_type` är fire och vars skills skalar från
samma `Power`. Skadetypen lever på vapnet/skillen, inte på en separat stat.

Effekt: samma sex tal beskriver *alla* builds, stat-listan hålls kort, och
balansering sker på ett ställe.

`Armor` är nu uttryckligen fysisk mitigering. Elementär/holy/poison-skada
hanteras av **resistenser** (se Skadetyper), inte av armor.

### Speed och turordning

Speed avgör vem som agerar först i en runda. Det gör caster-pusslet skarpt:
är du snabbare hinner du agera före en telegraferad fiende-nuke. Speed
påverkar även flee-chans.

Vald enkel lösning för v1: i en 1v1-strid jämförs spelarens och fiendens
speed vid rundans start; högre speed agerar först. Ingen separat
initiativ-ordning behövs förrän fler stridsdeltagare införs.

Vald enkel lösning för Crit: om det känns för tungt i v1, droppa Crit som
universell stat och låt crit bo i Rogue-talanger och gear istället.

## Resurs: mana

Mana, inte focus. Skillnaden är medveten och viktig för friktionen:

- Focus byggs upp inne i striden från noll.
- **Mana är en pool spelaren bär med sig mellan strider och måste fylla på.**

Det gör mana till en av friktionsspakarna automatiskt: tidigt är mana knapp,
skills kan inte spammas, och spelaren lutar sig mot basattacken och sparar
mana till rätt tillfälle (t.ex. en holy-nuke mot Undead).

Regler:

- Basattack kostar ingen mana.
- Skills kostar mana (och/eller har cooldown i rundor).
- Ingen mana-regen i strid tidigt i spelet. Mana fylls på genom vila i stad,
  potions/supplies, eller senare unlocks (tempel, passiv regen).
- Mana är en del av spelarens serialiserbara state (för framtida save/load).

## Klasser

Sex klasser, var och en med en tydlig mekanisk identitet.

| Klass | Identitet |
|---|---|
| Fighter | Rå skada, aggressiva skills |
| Tank | Mitigering, block, counter, taunt |
| Rogue | Crit/speed, bleed, execute, evasion |
| Mage | Elementär magi (fire/frost), DoT och burst |
| Cleric | Heal/sustain, holy (stark mot Undead) |
| Hunter | Exploaterar fiendesvagheter, traps, precision |

### Main + secondary

En karaktär väljer en **main-klass** och en **secondary-klass**. Detta är
källan till många olika runs.

- **Main** ger fulla basstats och hela sitt skill-träd.
- **Secondary** ger endast en *delmängd*: tier-1-grenen och en passiv, plus
  en mindre statmodifierare.

Vald enkel lösning, och en uttrycklig balansspärr: **secondary hålls grunt.**
Att tillåta två kompletta träd får balansen att explodera kombinatoriskt
(6×6 fulla kombinationer att balansera). Med grund secondary får man fram
arketyperna utan den kostnaden:

- Fighter / Rogue — blödande bruiser
- Tank / Cleric — närmast odödlig paladin
- Mage / Cleric — battlemage

## Skill trees

Mönster: varje klass har **två grenar**, varje gren **3–4 noder** (mix av
passiva och aktiva skills). En nod låses upp per level eller per talang-poäng
(se Öppna frågor).

Två klasser fullt utskrivna som mall för formen:

### Fighter

- **Berserker** — stackande rage, lifesteal, ökad skada vid låg HP, "reckless"
  (mer skada men tar mer skada).
- **Weaponmaster** — skalar starkt med vapnets skadebonus, garanterad crit på
  villkor, armor penetration, combo-attack.

### Tank

- **Guardian** — block/parry, thorns (reflekterar skada), taunt (sänker
  fiendens träffchans).
- **Sentinel** — armor-skalning, HP-regen per runda, counterattack, immunitet
  mot flee-tvång och vissa debuffs.

### Övriga klasser (samma form, definieras i data)

- **Rogue** — *Assassin* (crit/execute) vs *Duelist* (riposte/evasion).
- **Mage** — *Pyromancer* (burn-DoT/burst) vs *Cryomancer* (freeze = fienden
  tappar sin runda).
- **Cleric** — *Holy* (smite + heal) vs *Plague* (poison/curse/drain).
- **Hunter** — definieras vid implementation; tema: traps, mark-target,
  precision mot specifika fiendetyper.

## Stridssystem

Turbaserat, bygger på `DESIGN.md`:s rundordning men med utökade val.

### Stridsmenyn (fem val)

1. **Attack** — basattack. Gratis. Skalar från Power + vapnets skadebonus.
2. **Skill** — välj bland dina **utrustade skills (max 4)**. Kostar mana
   och/eller cooldown.
3. **Item** — använd en consumable mitt i striden. Tar din runda.
4. **Swap weapon** — byt aktivt vapen. Tar din runda. Detta är "switch":
   byter du till en holy-vapen mot Undead utnyttjar du svagheten.
5. **Flee** — chans baserad på speed-/level-skillnad. Misslyckas = fienden
   får en gratisträff.

### Max 4 utrustade skills

Bron mellan Pokémon och RuneScape: du kan *kunna* många skills från träden,
men slottar **4** för en given run. Det skapar buildcraft (vilka fyra?) utan
att menyn svämmar över.

### Rundordning

Bygger på `DESIGN.md`, men turordning avgörs nu av Speed:

1. Snabbare part agerar först (jfr Speed).
2. Handlingen löses genom resolvern (effekter appliceras).
3. Om motparten dog avslutas striden direkt.
4. Annars agerar den andra parten.
5. Statuseffekter tickar vid rätt tidpunkt (se nedan).
6. Striden fortsätter.

Fienden agerar alltså aldrig om den redan dödats samma runda (regel från
`DESIGN.md` bevaras).

### Level up mitt i seger (arkitektur)

Bevaras från `DESIGN.md`: en seger som ger XP nog för en eller flera level
ups får **inte** anropa `input()` i kärnan. Kärnan returnerar ett tillstånd
"väntar på statval (ev. flera)", och presentationen matar tillbaka valen.

## Statuseffekter

Den enda biten som riskerar att svälla. Håll effektmodellen minimal och
generell:

```text
effect = { type, magnitude, duration, tick_timing }
```

- `type` — t.ex. burn, poison, bleed, freeze, regen, taunt, buff, debuff.
- `magnitude` — storlek (skada/heal/statändring).
- `duration` — antal rundor.
- `tick_timing` — när effekten verkar (rundans start/slut).

En enda loop i resolvern tickar alla aktiva effekter varje runda. Nya
effekter är data, inte ny kod. `freeze` är specialfallet "målet tappar sin
nästa handling" — modelleras som en flagga effekten sätter.

## Skadetyper och resistenser

Håll antalet skadetyper litet: **physical, fire, frost, holy, poison.**

- Vapen och skills har en `damage_type`.
- Fiender (och i princip vem som helst) har en resistenstabell:
  `resistances: { type: multiplier }`, default `1.0`.
- Slutskada multipliceras med målets resistens för den skadetypen.
- `Armor` reducerar endast **physical** skada (platt avdrag, min 1).
- Elementär/holy/poison mitigeras enbart via resistenser.

Detta gör "vapen bra mot olika fiender" till äkta mekanik och är helt
datadrivet. Startsvagheter på befintliga fiender:

| Fiende | Svaghet | Tålig mot | Roll |
|---|---|---|---|
| Giant Rat | allt (svag överlag) | — | introfiende |
| Undead | holy (×2.0) | poison (immun/hög resist) | holy-checkfiende |
| Cave Bear | poison, fire | physical (lätt resist) | uthållighetstest |

## Fiendedjup

Det som gör att spelarens djup faktiskt har något att bita i. Fiender går
genom samma motor som spelaren men får egna skills, svagheter och
**arketyper** som tvingar fram olika svar:

| Arketyp | Beteende | Tvingar spelaren att |
|---|---|---|
| Healer | Fyller på egen HP (t.ex. Undead-präst) | Bursta ner innan den hinner heala |
| Bruiser | Hög skada, låg speed | Mitigera/tanka eller dö |
| Swarm | Flera svaga | Testa AoE/uthållighet (när multi-target införs) |
| Caster | Telegraferar en stor nuke en runda i förväg | Välja: tanka, fly, eller avbryta (interrupt) |

Caster-arketypen är skälet till att Speed och telegrafering finns: en
synlig "laddar X nästa runda" gör striden till ett beslut, inte en kalkyl.

Vald enkel lösning: Swarm och multi-target skjuts till efter v1 (kräver att
striden hanterar fler än en motståndare). De övriga tre fungerar i 1v1.

## Ekonomi: guld vs loot

Den centrala regeln, som river sönder "grinda råttor → köp BIS → spelet är
slut"-loopen:

**Guld köper bredd. Loot ger höjd.**

### Guld köper bredd (horisontellt)

Guld täcker hål och bekvämlighet, aldrig slutspelsstyrka:

- Basvapen i varje skadetyp (en billig holy mace så man *kan* möta Undead,
  en enkel fire-stav).
- Enkel armor i låg-till-mellantier.
- Potions och supplies.
- Stadsuppgraderingar (se Friktion).

### Loot ger höjd (vertikalt)

De faktiska makt-uppgraderingarna droppar bara — och **det bästa lootet
sitter bakom de svåraste fienderna, inte de säkraste.** Det är spärren mot
grind: att döda råttor i evighet ger guld till en potion och en bredd-pjäs,
men aldrig grottbjörns-svärdet som gör Berserker-bygget.

Exempel på axeln: en köpt holy mace låter dig *delta* mot Undead; en droppad
Consecrated Maul gör dig *stark* mot dem.

### Två spärrar (byggs in från start)

1. **Tak på köpbar tier.** Gear har tier 1–6. Butiken toppar på **tier 2**.
   Tier 3+ är loot-only. Guld-grinden finns kvar som ett *golv* (täck alltid
   ett hål) men taket är hårt.
2. **Frikoppla guld-källa från loot-kvalitet.** Farligare fiender ska löna
   sig på *båda* axlarna: mer guld *och* reell chans på bra loot. Annars blir
   den säkra grinden optimal igen.

## Loot-system (slump + sällsynthetstier)

Vald modell: RuneScape-likt — slumpdrop från viktade tabeller med
sällsynthetstier.

### Sällsynthetstier

Gear klassas i tier 1–6 (motsvarar ungefär rarity). Butik: tier 1–2.
Loot-only: tier 3–6.

### Drop-struktur

Varje fiende har en `loot_table`:

```text
loot_table = [
  { item_id | pool_ref, weight, rarity_tier },
  ...
]
drop_chance = sannolikheten att något alls droppar
```

Roll-ordning vid seger:

1. Rulla `drop_chance` — droppar något?
2. Om ja: viktad slumpdragning ur fiendens `loot_table`.
3. Junk-loot (säljbart skräp) ligger i tabellen med hög vikt och utgör en
   guld-källa utan att ge makt.

### Delad rare/epic-tabell

En **gemensam rare drop table** (tier 4–6) som endast fiender över en viss
nivå kan nå (en `rare_table_access`-flagga/tröskel per fiende). Det är
mekaniken som gör att verkligt bra loot kräver att man går uppåt i
svårighet, inte bara grindar säkert och länge.

### Tier-gate per fiende

En fiende kan bara rulla sällsynthetstier upp till sitt eget band. En råtta
når aldrig tier 4+, oavsett hur många man dödar.

## Friktion

Designmål: **hög friktion tidigt; unlocks på vägen som lättar.** Men en
ärlig avgränsning först:

**Bra friktion = meningsfulla beslut under knapphet. Dålig friktion = väntan
och orättvis RNG.** Unlocks ska ta bort *tråk* (omständlighet), inte göra
spelet lätt. Den bästa unlocken är när något som var ett pyssel blir
automatiskt.

Tre ekonomier, var och en som tidig friktion → unlock som lättar:

### Heal & mana

- **Tidigt:** enda pålitliga heal/mana-påfyllningen är att vila i staden —
  vilket tvingar en resa hem och bränner turen. Potions dyra mot tidig guld.
  Ingen mana-regen i strid.
- **Unlocks:** lägerplats i skogen (slipp hela vägen hem), lifesteal/regen
  via talanger (Berserker, Sentinel), billigare potions via recept, tempel i
  staden som ger mana. Sent: passiv out-of-combat-regen.

### Att ta sig framåt

- **Tidigt:** platser är gatade. Skogen nås från staden; grottan låst bakom
  nyckel/elite tills något klarats. Ingen fast travel — varje resa manuell.
  Det är här hemresa-för-heal gör som mest ont.
- **Unlocks:** nyckel/bro öppnar ny region; senare **fast travel**
  (waypoint/teleport-scroll) som tar bort fram-och-tillbaka-tråket helt.

### Guld & items

- **Tidigt:** guld knappt, bra gear oöverkomligt, drops snåla. Första svärdet
  (50 g) en riktig grind när råttor ger 3–8 g. Inget förvar.
- **Unlocks:** bank/stash (RuneScape-känslan), bättre drop-rate / luck-faktor,
  junk-loot att sälja, upgrade-bänk som förbättrar vapen, mer inventory-plats.

### Stadsspinen som ryggrad

De flesta lättnads-unlocks är **guld-köpta stadsuppgraderingar** (bättre inn,
tempel, bank, smedja). Det ger en naturlig guld-sink *och* en synlig "staden
växer med mig"-känsla. Mekaniskt är det flaggor och data, inte ny motor.

Vald lösning för unlock-källa: en **mix**, med stadsspinen som ryggrad —
guld-köpta stadsuppgraderingar för lättnad/bekvämlighet, plus quest-/elite-
belöningar för portar (klara grottbossen → grottnyckeln).

### Måttstock för rätt känsla (timme ett)

Fighter, knife, knappt någon mana. Två råttor dödade, 11 guld, 60 % HP,
nästan slut på mana. Beslut: pusha mot en tredje (guld till en potion, kan
döda dig) eller vända hem och fylla på (säkert men långsamt). Det är den
hårda, *bra* friktionen. Tjugo levlar senare: fast travel, tempel,
lifesteal-talang, bank full av loot — samma spel, noll tråk, allt
build-uttryck kvar.

## Öppna frågor

Beslut som inte behöver tas nu men som bör hållas synliga:

- **Bad-luck-skydd för loot.** Ren slump på rare-tabellen skapar sin egen
  grind ("döda bossen 80 gånger"). Två motgift: (a) deterministisk första
  gången — första gången en boss fälls droppar dess signature garanterat;
  (b) stigande drop-chans per miss. Vilket, eller båda?
- **Crit som universell stat eller inte.** Behåll Crit för alla, eller låt
  crit bo enbart i Rogue-talanger/gear i v1?
- **Skill-upplåsning:** en nod per level, eller separata talang-poäng som kan
  sparas/omfördelas?
- **Hunter-trädet:** två grenar behöver definieras.
- **Mana-regen sent:** hur mycket passiv regen, och var i progressionen?

## Byggordning

1. **Motoruppgraderingen först:** handling→effekt→resolver-pipelinen, mana,
   skill-slots (max 4), statuseffekt-modellen, skadetyper + resistenser,
   Speed/turordning.
2. **Validera** med *en* ny klass och *en* fiendesvaghet (t.ex. Cleric +
   holy mot Undead) innan mer hälls på.
3. **Häll på innehåll som data:** resterande klasser, skill trees, fiender,
   loot-tabeller, gear-tiers.
4. **Ekonomi och friktion:** tier-tak i butik, loot-tabeller med rare-table,
   stadsuppgraderingar, gating av platser.

## Medvetet utanför denna uppgradering

- Multi-target / Swarm-strid (kräver fler än en motståndare).
- Save/load (men allt nytt state ska vara serialiserbart).
- Pygame-rendering (kärnan ska inte blockera det).
- Roguelike run-struktur / meta-progression mellan runs (eget senare spår).
- Fullständig balansering — siffrorna här är startvärden att tuna i JSON.
