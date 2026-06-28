# TOWN_DESIGN — städer som funktionsdrivna kluster

Designunderlag för B8 (städer som byggnads-kluster) och de stadsbundna
innehållssystemen (B5, B10, B20, B22, B23). Beskriver **vad städer erbjuder**,
hur **storlek hänger ihop med funktionsrikedom**, och regeln för **var
specialisering får skapa friktion**. Allt här är data/tunbart — ingen ny motor
krävs för splittarna, bara mer sortiments-data per hus.

Förutsättning: nytt stadstänk = packade kluster runt ett **torg**, hus
nedskalade (~0.6, justerbar load-tid), **cobble-nät som wayfinding** till varje
ingång, **y-sort**, och **skylt-sidan som ingångsledtråd** (so ¾-vyer kan vara
sidobyggnader med ingång i öster/väster → fyrsidig inåtvänd plats möjlig).

---

## 1. Princip: inte varje hus behöver en funktion

Det vanligaste huset i en riktig stad har ingen tjänst — någon **bor** där.
Bostäder och landmärken ger staden täthet, liv och siluett utan att kräva en
mekanik. Dörren är bara låst.

Det löser räkneproblemet "hur fyller vi 8 hus med 8 funktioner?": en hub på 8
hus = **4–5 funktionella + 3–4 icke-funktionella** (bostäder/landmärken).

Icke-funktionella hus (idag):

- **cottage / hus** — bostad. Fyllnad och liv.
- **tower (vakttornet)** — landmärke/siluett. Ingen funktion i dagsläget.
  Reserverad för framtida bruk (kandidater: utkik som avtäcker fog → kopplar
  **B11**; eller mage-tower för skills/talents). Tills dess: dekor.

---

## 2. Funktionstaxonomi (byggnad → funktion)

| Hus | Funktion | System / backlog |
|-----|----------|------------------|
| shop (handelsbod) | basics + sälj junk/crafting-items | B5, B10 |
| blacksmith | **vapen** | B5, B10 |
| barracks (rustnings-variant) | **rustning** | B5, B10 |
| apothecary | potions / mana-pots | B5, B10, B15 |
| inn | vila (betald, voucher) | B20 |
| church | respawn-punkt | (respawn-systemet) |
| town_hall | notice board / quests + köp av respawn-relokering | B23, B10 |
| shrine | **enchanter** (stadsspecifik) | B22 |
| stable | snabbresa mellan städer | (framtida) |
| warehouse | förråd / stash (bank) | (framtida) |
| gatehouse | grind — betald passage (friktion/progression) | B21 |
| cottage / hus | bostad — ingen funktion | — |
| tower | landmärke — ingen funktion (reserverad) | (ev. B11) |

> Konst finns för church, cottage, gatehouse, inn samt shop/apothecary,
> town_hall, hus (de facing-rader som genererats). Övriga typer (barracks,
> shrine, stable, warehouse, blacksmith, tower) får facings/placeras efter hand;
> en stad behöver bara de typer dess storlek motiverar.

---

## 3. Splitt-regeln: basics överallt, specialisering = belöning

Att dela upp köpmannen i flera hus gör städer intressantare och fyller kluster —
**men bara på rätt nivå.**

**Inom en stad — splitta gärna.** Husen står vägg-i-vägg runt torget, så att gå
mellan vapensmed och rustningssmed kostar *några steg*. Nästan ingen friktion,
mycket smak. Dela t.ex. handeln i **vapensmed / rustningssmed / apotek /
handelsbod**. Detta är bara en utbyggnad av **B5** (kurerat sortiment per
butik) — ingen ny motor.

**Mellan städer — splitta INTE för baskram.** Att tvinga en resa till stad A för
rustning och stad B för vapen är för mycket friktion för basutrustning. Den
sortens specialisering ska vara **belöning, inte krav**, och reserveras för
specialvaror:

- **enchants** (B22) — redan stadsspecifika med flit.
- **rare/unika vendors**, quest-låsta varor.

**Princip:** *basutrustning når man i de flesta städer* (en handelsbod räcker);
specialisering ger **djup** för den som söker det — inte en mur för den som bara
vill köpa ett svärd. Resan ska vara värd det, inte ett ärende.

---

## 4. Storlek → funktionsrikedom

Storleken styr hur många tjänster en stad rymmer. Tre kluster-mallar:

- **liten (1–2 hus):** *en* funktion som blir stadens identitet — en shrine, en
  ensam handelsbod, eller bara en notice board. Det är detta som ger
  icke-shop-städer ett syfte (kopplar B23).
- **medium (3–5 hus):** 2–3 tjänster (t.ex. handelsbod + inn + board) + ett par
  bostäder.
- **hub (6–8 hus):** full svit — vapensmed, rustningssmed, apotek, inn, church,
  town_hall — + bostäder. (T.ex. burg_5, se §6.)

Storleken sätts som ett **`size`-fält per stad i `core_zone.json`** (tunbart).
Code väljer största mall som **får plats** (se §5).

---

## 5. Mätt kapacitet (avstånd, inte hus-storlek, är gränsen)

Begränsningen för stadsstorlek är **avståndet mellan städerna**, inte
byggnadernas storlek (0.6-skalan + cobble gör att fler hus får plats per radie).
Mätt på `core_zone.json` (17 städer, Chebyshev-avstånd till närmsta granne +
kant), max-radie ≈ `(min(grannavstånd, kant) // 2) − 1` (1-tile glapp):

| Tier | Radie | Hus | Antal | Städer |
|------|-------|-----|-------|--------|
| STOR | ≥5 | 6–8 | 3 | burg_293, **burg_5**, burg_160 |
| MEDIUM | 3–4 | 3–5 | 7 | burg_117, 67, 320, 105, 235, 54, 149 |
| liten | ≤2 | 1–2 | 7 | burg_53, 379, 219, 146, 200, 121, 385 |

Slutsats: **enhetligt 3–8 överallt går inte** — 7 städer (grannavstånd 7–8) ryms
bara som 1–2 hus utan att krocka. **Tiered är både möjligt och bättre** —
variation (hub vs by vs utpost), och små städer får mening via *innehåll* (en
board, en shrine) i stället för storlek.

> **Brasklapp:** siffrorna är **bara avstånd + kant** — de räknar inte med
> floder/vatten/grindar/terräng. En stad nära vatten har mindre brukbar mark än
> radien antyder. Tiern ovan är en **första sortering**; vid Slice 2 mäter Code
> exakt klarering mot vatten/grindar **per stad (STEG 0)** och kapar mallen om
> terrängen kräver. (burg_5: floden i SV, men 12 till granne och 18 till kant →
> radie 5 åt N/Ö räcker gott, redan verifierat i mock.)

---

## 6. burg_5 — exempel-hub (startstaden)

Stor tier (radie 5, 6–8 hus). Ankaret (26,18) = torg + meny-trigger; floden i
SV → kluster åt N/Ö. Förslag på svit (spikas i refining-prompten när alla
facings är inne):

- **church** (respawn) — N, front (dörr in i torget).
- **inn** (vila) — sido, skylt mot torget.
- **shop / handelsbod** (basics + junk-sälj) — sido, skylt mot torget.
- **blacksmith** (vapen) + **barracks/rustning** — splittad handel, inom-stad.
- **town_hall** (board/quests) — front eller sido.
- **+ 1–2 bostäder (cottage/hus)** för täthet.

Doörriktning löses per position: front=syd (N-hus), skylt-sida=öst/väst
(sido-hus), baksida=nord (syd-hus, cobble-ledd ingång). Cobble-nätet leder till
varje ingång.

---

## 7. Implementationsnoter

- **3 kluster-mallar** (liten/medium/hub) i samma stil som nuvarande
  `town_cluster.py` (ankrad mall: `(building, dx, dy, fw, fh)` + facing).
- **`size`-fält per stad** i `core_zone.json` (tunbart); default efter §5.
- **Per-stad klareringskoll (STEG 0)** vid Slice 2: mät fri mark mot
  vatten/grindar/grannar, kapa mallen om den inte får plats; reachability grön;
  inga överlapp. Sortimentet (vilka varor per hus) = **data**, byggt på B5.
- Skala (~0.6) = justerbar load-tid-konstant; y-sort; cobble autotilat bara på
  rutter (ej under hus).

---

## 8. Backlog-koppling

- **B8** — uppdateras till tiered, funktionsdrivet upplägg (3 mallar + `size`-fält
  + per-stad klareringskoll). Slice 1 = burg_5 (hub). Slice 2 = alla 17 +
  funktions-triggrar.
- **B5** — kurerat sortiment per butik; bär splitten (vapen/rustning/potions/basics).
- **B10** — shop-UI i character-interface med stat-preview; funktion→vendor-mappning.
- **B20** — inn = vila.
- **B22** — shrine = stadsspecifik enchanter (specialisering = belöning).
- **B23** — town_hall = notice board/quests; ger små städer syfte.
- **B21** — gatehouse = betald grind.
- **B11** — möjlig framtida tower-funktion (utkik/fog).
