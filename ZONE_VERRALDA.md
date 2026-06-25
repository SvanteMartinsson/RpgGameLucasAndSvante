# VERRALDA: den omstridda bygden i Nieia (level 3–7)

Spelets andra expansion, och dess första **bryggzon**. Designprincipen jämnar ut
en klippa playtestet blottade: kärnan är level 1–5, men i samma steg du går väster
möter du level 5–10 och dör (en level-3-spelare dog 8 gånger på 4 minuter).
Verralda sitter mellan dem — level 3–7 — en mjuk första utgång ur den trygga
kärnan innan vildmarken i väster.

**Status:** under byggnad. **Skelettet är gångbart** (commit 5540337): ett
grave_heath-hedfält söder om kärnan, nått via den öppnade sydsömmen, med Alherralba
som respawn-hub. Inga fiender/props/träd än. Grundat i `world.json` (världen
**Nieia**, `region_state_id 5`) och `enemies.json`. Verralda är ingen ny geografi —
det är det redan existerande tier-1-**hjärtlandet** i Nieia, namngivet. Alla
stadsnamn är kanon ur world.json; "Verralda" är regionens flavor-namn (som
`ZONE2.md` myntade "Förfallets gräns"), i samma iberiska klang som Nieias städer.
Vi öppnar och fyller; vi uppfinner inte.

**Låsta beslut:** tile-tema = `grave_heath`, recolor-harmoniserat (commit 69604d9,
bas-gräs-luma 74→87, i familjen). Kart-topologi = **utbyggnad av en enda
`overworld.tmx`** (48×20 → 48×32), INTE länkad TMX — Code:s STEG 0 visade att
temat är bakat (noll runtime-renderingskod), att väst redan ligger på samma karta
(bryggan västerut blir gratis och kontinuerlig), och att en länkad TMX hade krävt
ett helt kart-övergångssystem som inte finns. Lägsta-ny-kod-vägen.

## Topologi (ur world.json:s connections-graf)

Geografin vilar på den faktiska adjacens-grafen, inte koordinat-gissningar:

```
Hordanita (burg_5, hub) ──road── Gaste → Jinosa → Condillosca → Rotequero → Estables   [VÄST, tier 2, lvl 5–10]
        │
        └─road── Yeblegali ──→ Guaredama → Alherralba(butik) ──┐
                     │              │                          │   VERRALDA (tier-1-hjärtlandet)
                     │              ├── Salles ──trail── Fongorinos  ←─ brygga till VÄST
                     │              ├── Cantida → Urrequena (vägkors) → Herrallo / Jadra / Chuequeroma → Barroncami
                     └── poi_42 Mage Tower (återvändsgränd)
```

Tre saker faller ut, alla graf-verkliga:

- Verralda nås från Hordanita **via Yeblegali** (väg) — det är porten in från kärnan.
- Verralda **bryggar in i väst via Salles → Fongorinos** (trail, 16px). Så
  gradienten kärna (1–5) → Verralda (3–7) → väst (5–10) finns på riktigt i
  grafen — den är inte påhittad.
- `poi_42` Mage Tower är en återvändsgränd som bara kopplar till Yeblegali — ett
  avskilt torn, perfekt för en magiker-fraktions fäste.

## Plats i världen och svårighet

Verralda är gradientens mellansteg, mellan den trygga kärnan och den farliga väst.
Den västra *Förfallets gräns* (de döda och bestarna, se `ZONE2.md`) lämnas
reserverad för sin level 5–10, och den eventuella zon 3 (10–15) bortom
`gate_deep_west` ligger längre fram. Verralda fyller hålet vid 3–7.

## Lore: tvedräkt vid förfallets rand

> **Verralda** var Nieias bördiga hjärta — åkrar, en befäst marknadsstad, ett
> gammalt magikertorn på höjden. Men när förfallet kröp närmare västerifrån
> slutade den gamla ordningen att hålla. Skördarna räcker inte för alla, och tre
> läger har dragit sina gränser i myllan. Bönderna håller fast vid sin jord.
> Klanen från kullarna tar vad den behöver, och löper med tämjda bestar. Och i
> tornet ser magikerklaven på det hela uppifrån — somliga säger att de studerar
> förfallet, andra att de väntar ut de andra två. Marken är klyvd, och den som
> vandrar igenom väljer sida vare sig hen vill eller inte.

Tvedräkten *orsakas* av förfallet i väster — det binder ihop Verralda narrativt
med resten av Nieia och ger grund för quests: ta parti, medla, spela ut lägren
mot varandra, eller bara plundra deras krig.

## Känsla och miljö

Öppen, omstridd bygd — åker och hagar som glider över i kulliga skogsbryn, med ett
magikertorn som landmärke. Tonen är *spänd vardag*, inte skräck: människor som
krigar om krympande mark, inte ett hemsökt land. Medveten kontrast mot den dystra,
undead-tunga väst.

**Tile-tema (öppet beslut):** Verralda ska se visuellt distinkt ut från
cainos-kärnan och de mörka västtemana — egna marktiles, träd och props (skilj
zoner genom *innehåll*, inte en färglinje). Oanvända teman finns redan som ark:
`grave_heath` (varm hed) ligger nära åker-/hag-känslan. **Beroende-not:** vilket
tema vi än väljer måste köras genom `recolor_themes.py` så det sitter i den
harmoniserade ljus-/mättnadsfamiljen — annars återinför vi klippan vi just tog
bort.

## Städer (verkliga world.json-platser, graf-grupperade)

| id | Namn | Typ | Roll i Verralda |
|---|---|---|---|
| `burg_117` | Yeblegali | village (tier0) | **porten in** från kärnan (Hordanita→Yeblegali, väg) |
| `burg_121` | Alherralba | town (**butik**) | **zon-hub + respawn** (realiserar den idag tile-lösa butiksstaden) |
| `burg_54` | Guaredama | village | bondebygd vid Alherralba |
| `burg_149` | Salles | village | bondeby — och **bryggan västerut** (→ Fongorinos) |
| `burg_385` | Cantida | village | bondebygd |
| `burg_293` | Urrequena | village | centralt vägkors, omstritt |
| `burg_163` | Herrallo | village | omstridd by |
| `burg_292` | Jadra | village | väg-approach (via Esple) |
| `burg_193` | Esple | village | väg-approach från Yeblegali |
| `burg_105` | Chuequeroma | village | raider-pressad utkant |
| `burg_53` | Barroncami | village | sydlig återvändsgränd (raider-territorium) |
| `poi_42` | Mage Tower | mage_tower | **magikerklavens fäste** |

Alla bär `giant_rat` + `undead` i sina pooler idag. **Vi tema-byter dem:** undead
hör hemma i väst, så de ersätts med fraktionerna + bestar (nedan).

## Åtkomst och resa

Fri gång (Modell B) — ingen nyckel, ingen achievement-låsning. Verralda realiseras
som **ny tilemap-region kopplad till kärnan**; grafens ankare är Yeblegali. **Vilken
fysisk tilemap-grind** (`gate_north`/`gate_south`) som realiserar länken är ett
**författningsbeslut vid bygget** — jag lutar åt söder (nära hubben, spawn-tryggt),
men det avgörs när vi författar kartan, inte här. En mjuk text-signal vid gränsen,
inte en vägg. Verraldas bortre kant bryggar mot väst via Salles → Fongorinos.

(Öppen arkitekturfråga: egen länkad TMX vs utbyggnad av `overworld.tmx`. För en
region som senare ska koppla mot väst lutar jag åt egen länkad TMX — beslut vid
bygg-steget.)

## Spawn och respawn

Alherralba (`burg_121`) får **`respawn: true`** och har redan butik → respawn-flytt
(700 G-mekaniken vi byggde) fungerar där. Död i Verralda skickar dig till
Alherralba, inte hela vägen till Hordanita — samma lärdom `ZONE2.md` drog för väst,
och den första nåbara service-staden i en mellanzon.

## Fraktioner och fiender

Tre humanoida fraktioner, mappade på `ENEMIES.md`:s arketyper och på faktiska
graf-delar — **utan undead**, med skadebredd (physical + fire/frost) som testar
spelaren annorlunda än den holy-tunga väst. Återbrukar mönstret från
arena-människorna som redan finns i `enemies.json` (taggar `human`/`mage`/`knight`
osv).

### Bondemilisen — *underdogs, svagast, rustnings-källan* (level 3–5)
Graf-del: marknadsklustret runt **Alherralba** (Alherralba/Salles/Cantida/Guaredama).
Bofasta bönder i desperation — inga krigare, och det ska synas. **Mekanisk roll:
zonens lågtröskel + spelets första rustnings-drops** (LOOT.md noterar att
rustnings-loot är en expansion — här introduceras den).

| id (förslag) | Roll | Lvl | Taggar | Notis |
|---|---|---:|---|---|
| `levy_militiaman` | grunt | 3 | human, militia | improviserat vapen, låg på allt — underdogen |
| `levy_hedgewarden` | **healer** | 4 | human, militia | örtkunnig läkekvinna; `instant_heal` (örter, INTE holy) — burst-pusslet utan undead |
| `levy_reeve` | grunt+ | 5 | human, militia, veteran | byäldsten; deras "starka", men modest |

Loot: tier 1–2 **rustning** (huvud/bröst/händer), gårds-junk som blir material.

### Magikerklaven — *casters, eld/frost* (level 4–6)
Graf-del: **`poi_42` Mage Tower** + dess approach (Yeblegali/Esple). Bräckliga men
telegraferar stora nukes — ger zonens icke-fysiska skadebredd helt utan undead/holy.

| id (förslag) | Roll | Lvl | Taggar | Notis |
|---|---|---:|---|---|
| `clave_apprentice` | caster-lite | 4 | human, mage | svag bolt + enstaka telegraf |
| `clave_pyromancer` | **caster** | 6 | human, mage | telegraferad eld-nuke; bräcklig, hög speed |
| `clave_frostbinder` | **caster** | 6 | human, mage | frost-nuke + slow/kontroll-känsla |
| `clave_warden` | bruiser-lite | 5 | human, mage, guard | frontlinje som skyddar casterna |

Loot: stavar/trollspön (eld/frost-vapen → element/socket-systemet i
`HORIZONTAL_PROGRESSION.md`), reagenser (material).

### Harrow-klanen — *bruisers, bestar, starkast i zonen* (level 5–7)
Graf-del: de vildare utkanterna (**Chuequeroma/Barroncami**) + Urrequena-vägkorset
som omstritt. Kullarnas raiders som löper med tämjda bestar — zonens toughaste.

| id (förslag) | Roll | Lvl | Taggar | Notis |
|---|---|---:|---|---|
| `harrow_raider` | grunt+ | 5 | human, raider | yx-bärare |
| `harrow_houndmaster` | grunt | 6 | human, raider | uppträder i pool med bestar |
| `harrow_berserker` | **bruiser** | 7 | human, raider | tung yxa, hög HP/power, låg speed — zonens hårdaste |

Loot: greataxes (→ material-stegen i `HORIZONTAL_PROGRESSION.md`, vars exempel
*bokstavligen* är "greataxe"), hide-rustning, best-troféer (material).

### Bestar i Verralda (återbrukade, inga nya art-assets)
Alla redan i `enemies.json`, alla `beast`, inga undead:

- `giant_rat` (lvl 1) — ohyra i åkermarken.
- `cave_bear` (lvl 3) — vild best i skogsbrynet.
- `wild_boar` (lvl 6) — vildsvin i hagar och bryn.
- `dire_wolf` (lvl 6) — Harrow-klanens hundar (uppträder med `harrow_houndmaster`).

## Difficulty-ramp inom zonen

Bondemilis (3–5, underdogs) < Magikerklaven (4–6) < Harrow + bestar (5–7). En
spelare börjar tryggt mot milisen, rustar upp på deras rustnings-drops, och tar
sig sedan an klaven och raiders — därefter väst. Exakta stat-/skadetal tunas i
`enemies.json` senare; detta dokument sätter roller och band, inte siffror.

## Fiende-struktur: var fienderna "bor" (tre lager)

1. **Zon-dokumentet (detta)** — *vilka* fraktionerna är, fantasi, roll, taggar, var
   de uppträder. Den narrativa sanningen.
2. **`ENEMIES.md`** — den kanoniska *rostern* (id · roll · level · speed ·
   resist/taggar · notis) tvärs alla zoner. Verraldas fiender läggs här när de byggs.
3. **`enemies.json`** — faktiska *stats* (hp, damage, ai-regler, loot_table). Code:s jobb.

### Rekommendation: synka ENEMIES.md mot verkligheten FÖRST
`ENEMIES.md` dokumenterar 5 fiender; `enemies.json` har 22. 17 är odokumenterade
(arena-duellanterna ×10, dire_wolf, wild_boar, treant, mutated_mudcrab, bog_wraith,
tar_beast, hollow_worg). Innan vi lägger till nya bör rostern spegla verkligheten.
Eftersom stats bor i `enemies.json` (gissa inte hp/damage) är detta en lämplig
Code-uppgift: läs `enemies.json`, regenerera `ENEMIES.md`:s roster mot faktisk data,
rapportera. Det är det naturliga första bygg-steget.

## Status per slice (uppdateras allt eftersom)

- [x] **ENEMIES.md-synk** (5c6189d) — rostern speglar enemies.json (22 fiender).
- [x] **Recolor grave_heath** (69604d9) — temat i den harmoniserade familjen.
- [x] **Gångbart hed-skelett** (5540337) — fält söder om kärnan, gate_south öppnad,
  frontier-grind flyttad till [13,31], Alherralba [14,26] som respawn-hub. Inga
  fiender/props/träd. Kärna + väst byte-identiska.
- [ ] **Props + träd i heden** — registrera grave_heaths prop-tilesets, måla liv
  i fältet (samma pipeline som kärnan). Ger värme/djup åt den nu bara/grå heden.
- [ ] **Fraktions-byar** — lägg Salles/Guaredama/Cantida m.fl. som town-tiles
  (graf-grupperade enligt topologin ovan).
- [ ] **Fiender + fraktioner + loot** — Bondemilis/Klaven/Harrow; kräver
  `zone_for_tile`→2D (uppskjuten runtime-bit) och nya enemies i enemies.json +
  ENEMIES.md.

## Öppna beslut som kvarstår

1. **Hedens ton** — den recolor-lyfta grave_heath läser grågrön/dämpad snarare än
   "varm hed". Funkar tonalt för gränsbygd; avgör om den ska värmas eller lämnas
   (kan vägas igen när props/träd lagts, som lyfter känslan).
2. **Fiende-id:n och exakta stats** — namnen i fraktions-tabellerna är förslag;
   band och roller är designen.
3. **Tilemap-grind västerut** — när och hur Salles→Fongorinos-bryggan realiseras
   som gångbara tiles (gradienten in i väst).

Inget av detta är en byggorder. Dokumentet är kompassen; bygg-prompts skrivs mot
det när formen är godkänd.