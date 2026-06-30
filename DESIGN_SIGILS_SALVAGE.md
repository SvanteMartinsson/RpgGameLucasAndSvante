# DESIGN — Sigils & Salvage
*Arkitektens nattskift. Utkast för Lucas att vakna till. Allt nedan är grundat i
spelets FAKTISKA data (enemies.json-resistanser, items/gear/weapons, loot-tables).
Inget byggt — detta är ett designförslag du kan riva, ändra eller committa.*

---

## 0. Kärninsikten (varför det här)

Två saker ligger redan i spelet och används inte:

1. **Resistans-matrisen finns redan.** Varje fiende har en `resistances`-dict
   `{physical, fire, frost, holy, poison}` med multiplikatorer. Den är *djupt
   tematisk* och redan ifylld: **undead** tar holy ×1.5 men är **poison-immuna
   (×0.0)**; **treant** tar fire ×2.0 men resistar frost ×0.5; **bog_wraith** tar
   frost ×2.0; cave_bear/tar-beast tar fire; mudcrab *resistar* fire ×0.5.
   → Det finns en hel strategisk dimension inbyggd. **Men spelaren kan nästan
   inte röra den** — vapen har en fast `damage_type`, och nästan alla är
   `physical`. Du kan bara exploatera matrisen om du *råkar* hitta ett elementärt
   vapen (rimebrand/emberwand). Strategin är låst bakom slump.

2. **Junken gör ingenting.** `bone_dust`, `tattered_cloth`, `rat_pelt` är
   `kind:"junk"`, har bara ett pris, droppar konstant (din mage-logg: bone_dust om
   och om igen) och säljs för småmynt. Dött innehåll. Och varje dubblett-gear
   (tionde `guard_cap`) är samma sak — en icke-händelse.

**Sigils & Salvage knyter ihop dem till en loop:** fienderna du dödar ger dig
materialet att specialisera dig *mot just dem*. Den dolda matrisen blir ett spel
man faktiskt spelar — och junken blir nyckeln till den.

> **Loopen:** döda fiende → **salvage** junk/oönskad gear → **essens** → smid en
> **sigil** hos en enchanter → **slotta** den i vapnet → exploatera fiendens
> svaghet → döda effektivare → mer salvage. Self-reinforcing och tematiskt tät:
> bendammet från de odöda blir det heliga som bränner dem.

---

## 1. Trait-system & fast resistansmatris (LÅST med Lucas)

Resistanser är **trait-härledda**, inte handsatta per fiende — så "beasts är svaga mot
fire" blir en *regel man lär sig*. En fiende har **max 2 traits**. Fast stege:
`Immun 0.0 · Resist 0.65 · Normal 1.0 · Effective 1.25 · Super 1.5 · Bane 2.0`.

**Trait-profiler** (i steg: resist −1, normal 0, eff +1, super +2, bane +3):

| Trait | Profil |
|---|---|
| **beast** *(varg, vildsvin, björn — stora vilda djur, EJ råtta)* | fire +3 · poison +1 · frost −1 |
| **plant** *(treant)* | fire +3 · frost −1 |
| **swamp** *(tar-beast, ooze/bog)* | frost +3 · fire −1 · poison −1 |
| **undead** | holy +3 · poison IMMUN · frost −1 |
| **spirit** | holy +2 · physical −1 |
| **cursed** *(förbannad/pestad)* | holy +2 · physical −1 |

**Kombinationsregel (LÅST):** steg-additivt — summera trait-stegen per skadetyp,
klampa till [−1, +3], mappa till stegen. Immun är absolut (vinner alltid). Lightning
rör ingen trait → neutral överallt (Stormetcheds "safe default"-roll bevarad).

**Emergent egenskap:** *rena* traits ger skarpa svagheter (Bane 2.0), *hybrider*
rundas av (resist + bane på samma typ möts på Super 1.5). Rena fiender belönar exakt
rätt sigil; hybrider är flexiblare.

**Härledd matris** (nuvarande fiender — se `sigil_matrix_v2.png`):

| Fiende | Traits | ≠1× |
|---|---|---|
| Giant Rat | — | *neutral* |
| Wolf / Boar / Bear | beast | fire 2.0, poison 1.25, frost 0.65 |
| Treant | plant | fire 2.0, frost 0.65 |
| Tar-beast | swamp | **frost 2.0**, fire 0.65, poison 0.65 |
| Mutated Mudcrab | beast+swamp | fire 1.5, frost 1.5, poison 1.0 |
| Hollow Worg | beast+cursed | fire 2.0, poison 1.25, frost 0.65, holy 1.5, physical 0.65 |
| Undead / Priest | undead | holy 2.0, poison IMMUN, frost 0.65 |
| Bog Wraith | undead+swamp | holy 2.0, poison IMMUN, frost 1.5, fire 0.65 |
| Plague Acolyte | cursed | holy 1.5, physical 0.65 |

Element-nischer: **fire→beast/plant** · **holy→undead/cursed/spirit** ·
**frost→swamp** · **poison→levande djur** (dött mot undead/swamp) · **lightning→neutral default**.



## 1b. System — Salvage (gör junk till valuta)

En **salvage-bänk** (egen byggnad, eller en åtgärd i smithen/inventory — se slice).
Två utflöden:

- **Junk → essens** (tematiskt bundet):
  - `bone_dust` → **`gravesalt`** (heligt-alignad: bendamm → bane mot de odöda)
  - `tattered_cloth` → **`mournthread`** (ande/kult: gift-/förbannelse-alignad)
  - `rat_pelt` → **`beasthide`** (best: fysisk/utility-alignad)
- **Oönskad gear → `etching_flux`** (generisk smid-valuta), skalad efter tier/rarity.
  Detta är poängen: den **tionde `guard_cap` blir flux i stället för besvikelse.**
  Salvage *minskar* drop-friktionen (färre värdelösa drops) och *lägger till*
  strategisk friktion (vad smider jag, mot vad?). Det är exakt rätt byte.

Regionala essenser (för de element vars källa inte är junk) kommer från salvage av
regionens tematiska gear/junk när zon 3+ landar — t.ex. `cinderash` (ash_waste →
fire), `rimebloom` (frostfell → frost). Tills dess bär enchantern receptet och flux
+ gravesalt/mournthread räcker för start-sigillerna.

---

## 2. System 2 — Sigils (välj din skadetyp = exploatera matrisen)

En **sigil** smids hos en enchanter (flux + essens + guld) och **slottas i ett
vapen-socket**. En vapen-sigil **konverterar vapnets skadetyp**.

**Skadetyps-sigiller (vapen-socket):**

| Sigil | Skadetyp | Lyser mot (grön i matrisen) | Fälla (röd) |
|---|---|---|---|
| **Hallowed Sigil** | holy | undead, undead_priest, bog_wraith-familjen (×1.5) | — |
| **Emberwrought Sigil** | fire | treant (×2.0!), tar-beast (×1.5), cave_bear (×1.25) | mudcrab (×0.5) |
| **Rimeward Sigil** | frost | bog_wraith (×2.0!) | treant (×0.5) |
| **Venomedge Sigil** | poison | neutrala mål | **undead = IMMUN (×0.0)**, cultist/bear resistar |
| **Stormetched Sigil** | lightning* | ingen super-effekt … | …men **ingen resistar** (B27-poolens oresisterade typ) |

\*Stormetched är den medvetna **"säkra default"**: aldrig super-effektiv, aldrig
resistad. Det gör elementär specialisering till ett *äkta val* — pålitlig vs
situationsbättre. Och det ger B27-poolens lightning-typ en tydlig roll.

**Rangmodell (3 steg, modest — samma form som talent-rangerna B36, en mental
modell för "uppgradera i 3 steg"):**
- *Lesser*: konverterar ~60 % av vapenskadan till den nya typen (resten native), ingen bonus.
- *Standard*: 100 % konvertering.
- *Greater*: 100 % + liten flat bonus (eller +0.1 på effektiva multiplikatorn mot svaga mål).

Granulärt och billigt att balansera — och det ger B37 exakt de **"små intressanta
uppgraderingar"** du efterlyste, ovanpå vapenkurvan i stället för att blåsa upp den.

---

## 3. System 3 — Wards (försvarsmotspel)

En **ward-sigil** slottas i gear (t.ex. amulett) och ger **resistans mot en
skadetyp** (Emberward, Rimeward Aegis, Hallowward …). Spelar roll när fiender
börjar slå elementärt (undead_priest holy, emberwand-cultister, framtida casters).
Det här förklarar dessutom retroaktivt de redan namngivna föremålen —
`censer_pendant`, `plaguebearer_mask`, `wraithlight_band`, `grave_band` — namnen
pekade redan hit; de blir naturliga ward-/sigil-bärare.

---

## 4. Friktionen (hjärtat — och varför det inte trivialiserar)

- **Ett vapen-socket.** Du kan vara holy *eller* fire — inte allt på en gång. Du
  **specialiserar dig per region/fiende.** Inget universellt optimum.
- **Konvertering ERSÄTTER native-typen.** En physical greatsword + Hallowed = holy
  greatsword. Du byter din neutrala pålitlighet mot situationsstyrka. Mot en
  poison-immun undead är din Venomedge **dött vikt** — du *känner* matrisen.
- **Byte kostar.** Omsocketning förbrukar lite flux (eller förstör den gamla
  sigillen). Du *committar* till en loadout. Att bära ett par sigiller och byta i
  stad/läger = det strategiska lagret. → **Öppet beslut:** förstör-vid-byte vs
  flux-för-extraktion.
- **De RÖDA cellerna är innehåll.** En Venom-build går in i grav-heden och slår i
  väggen (immun). En Rime-build mot treant gör halv skada. Att läsa regionen och
  förbereda *är* spelet. Friktion som belönar eftertanke, precis vår ådra.

---

## 5. Vad det löser och kopplar (ett system, många trådar)

- **B22 (enchant-vendors)** får ett konkret innehåll: varje stads enchanter säljer
  en **sigil-familj** tematiskt knuten till regionen — grav-/helig-stad → Hallowed,
  frostfell → Rimeward, ask → Emberwrought, träsk/pest → Venomedge/Mournthread,
  start-hubben (burg_5) → Stormetched (pålitlig default) + salvage-bänk. Inga tvång
  att resa för baslinjen, men specialisering belönar utforskning — stads-ådran.
- **Crafting** (tom idag) får sin första riktiga loop: salvage + sigil-smide.
- **B37 (item-rebalans)** får **epic** en *mekanisk identitet*: epic = föremål med
  **inbyggt socket** (vapen) / extra ward-slot (gear), eller en bunden unik sigil.
  `consecrated_maul` = epic holy-klubba (bunden Hallowed) + ett socket. Epic betyder
  *build-flexibilitet*, inte bara större siffror. Legendary (pyre_scepter,
  gravewarden_blade, worldsplitter) sitter kvar ovanför som fasta unika builds.
- **B27/B38 (skill-pool & förvärv):** en frost-build (Rimeward + frost_shard) får
  tematisk synergi; vissa skill-tomes kan gateas bakom matchande essens (lär dig
  `holy_strike` hos Hallowed-enchantern mot gravesalt). Poolen får ett hem.
- **B36 (talent-ranger):** samma 3-rangs modesta modell → en mental modell för båda.

---

## 6. Skalbarhet (data-drivet, noll ny kod per innehåll)

- Ny fiende-familj → sätt bara dess `resistances`-dict (redan mönstret).
- Ny sigil → en data-post. Ny region → en ny enchanter-familj.
- Sigil-effekten åker genom EN combat-pipeline (skadetyps-konvertering vid
  träff-uträkning) — ingen forkning. Respekterar invarianterna.

---

## 7. Hur det slice:as (för Code, senare — inte i natt)

- **Slice 1 — Salvage:** junk/gear → `gravesalt`/`mournthread`/`beasthide`/`etching_flux`.
  Data + en salvage-meny (åtgärd i inventory eller en bänk). Sim/test: salvage-utbyte.
  STEG 0: var hanteras junk/inventory-kategorier idag; var en salvage-åtgärd kopplas in.
- **Slice 2 — Sigils + vapen-socket (den strategiska kärnan):** sigil-items, ett
  socket på vapen, skadetyps-konvertering i pipelinen, 3 ranger. Sim: skadeutfall
  mot 2-3 familjer med/utan rätt sigil (visa att matrisen aktiveras). STEG 0: var
  appliceras `damage_type` i pipelinen; hur bär ett vapen ett socket.
- **Slice 3 — Enchanters (B22) + wards + epic-socket (B37):** enchanter-vendors per
  stad med familj-sortiment; ward-sigiller i gear; epic = inbyggt socket. Renders.

---

## 8. Öppna beslut för dig (morgon)

1. **Socket-modell:** bara vapen (1 socket) till att börja med, eller direkt
   vapen + en ward-slot på amulett?
2. **Byteskostnad:** förstör-vid-byte (hårdare commit) vs flux-för-extraktion (mjukare)?
3. **Konvertering vs addering:** ska en sigil *ersätta* native-typen (mitt förslag,
   tydligast) eller *lägga till* en andel elementär skada (mjukare men suddigare)?
4. **Lightning som "safe default"** — gillar du rollen, eller ska poolens lightning
   förbli ren skill-grej och Stormetched strykas?
5. **Namn:** sitter Sigils & Salvage / Gravesalt / Hallowed / Emberwrought /
   Rimeward / Venomedge / Stormetched, eller vill du ha en annan ton?

## 9. Risker / var jag kan ha fel

- **Komplexitet tidigt:** en ny spelare ska inte mötas av matris-pussel på L1.
  Mildring: salvage + Stormetched räcker länge; skadetyps-tänket blir relevant
  först när elementära fiender (treant/bog_wraith/zon 2+) dyker upp. Introducera
  sigiller runt zon-gränsen, inte i burg_5.
- **Balans:** ×2.0-cellerna (treant fire, bog_wraith frost) är *starka* — med rätt
  Greater-sigil kan en familj bli för lätt. Det vill simulteras (den skill-aware
  harnessen från i natt hjälper). Kanske capa effektiv multiplikator vid t.ex. 1.6.
- **Konvertering kan göra native-physical-builds sämre** om man tvingas in i den.
  Därför: physical förblir fullt dugligt (Stormetched/ingen sigil), sigiller är
  opt-in uppsida, inte ett krav.

---

*Sammanfattning: spelet har redan en dold skadetyps-strategi och en död junk-ström.
Sigils & Salvage förenar dem till en tematiskt tät loop, ger B22/crafting/epic/B27
ett gemensamt hem, skapar friktion som belönar förberedelse, och skalar rent på
data. Riv det fritt — men jag tror kärnan (väck matrisen, gör junk till nyckeln) är
en riktig ådra för VÅRT spel.*
