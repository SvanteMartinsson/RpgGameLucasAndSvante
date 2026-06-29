# Svantrenish RPG — Backlog

Fångade förbättringar/buggar att åtgärda. ID:n (B1–B24) är stabila referenser i
build-prompts. Varje punkt: **Vad** / **Avsikt** / **Not** (storlek, beroende,
mät-först) / **Acceptans** (definition av "klart"; styr autonomt batch-arbete, se
`CLAUDE.md` → Autonomt Batch-Arbete).

> **STEG 0-princip:** punkter som beskriver nuvarande beteende vi inte säkert känner
> inleds med en STEG 0 som **mäter koden** innan ändring.

> **Acceptans markerad "(utkast — rätta)"** är arkitektens förslag på mål; Lucas
> sätter de slutliga siffrorna. Balans verifieras via `rpg_game/core/simulation.py`.

> **⭐ = designbärande** — kräver en designrunda + slice, inte en autonom commit.

---

## Översikt

**✅ Klart:** B1 · B5 · B6 · B7 · B9 · B14 · B15 · B19* · B7.1 · B20 (detaljer i arkivet).
Karta: organisk havskust, seamless vatten/bro-skin, död kod borttagen. Byggnads-assets
(13 × 128px) incheckade (`a8b262e`).
*B19 (vatten-kollision per-tile) är ett delsteg — **ersätts för vattnet av B21** (sub-tile).

**▶ Pågår:** B8 — Slice 1 byggd (`bebd2b7`); refining (facings/cobble-nät/y-sort/0.6,
burg_5 → hub). Designbeslut låsta, se `TOWN_DESIGN.md`. Väntar på resten av facing-arken.

**Härnäst (förslag):** B21 (sub-tile-kollision + fences — fixar vattnet på riktigt) ·
B12 (encounter-skalning — playtest visade hård tidig vägg) · B8 Slice 2 · sedan
content/system: B22 (enchants) · B23 (quests) · CHARACTER_SCREEN+B10 (shop+preview).

---

## Playtest-fynd (2026-06-28, fighter L1→7)

Källa: full battle-logg + Lucas findings. Fångade nedan som B21–B24 + uppdateringar.
- Tidig svårighet spikar: 3 dödsfall på ~2 min som L1–3 mot cave_bear L5–L10 → **B12**.
- Holy-vapen trivialiserar: `gravewarden_blade` 140–376 mot odöda, ~70 annars; pool
  ~⅓ odöda → **B24**.
- `undead_priest` healar ~128 HP (kan bli mjuk vägg) → **B24**.
- Equip-toggling ~20× för att jämföra stats (ingen preview) → **B10 / CHARACTER_SCREEN**.
- Vatten-kollision känns fel i spel (gå ut i vattnet vid edges, blockad vid hörn) →
  **B21**.

---

## Aktiva punkter

### Overworld, kollision & karta

#### B21 — Sub-tile-kollision + fences & gates  ⭐ designbärande  · *nytt, ersätter B19:s vattendel*
- **Vad:** Byt kollisions-primitiv från "blockerade tiles" till **sub-tile/kant-baserad
  kollision** (barriärer tunnare än 1 tile, blockerar bara precis där spelaren nuddar
  dem). Tre användningar av samma system:
  1. **Vatten:** osynliga kollisions-segment längs den faktiska strandlinjen → spelaren
     går ända fram till vattenbrynet men inte förbi, oavsett diagonal. Fixar det B19:s
     per-tile-tröskel inte kan (edge-tiles ~58% vatten → binärt per-tile blir alltid
     fel: gångbar = gå ut i vattnet, blockerad = står en bit från kanten).
  2. **Fences:** tunna staket som blockerar längs en linje; tvingar omvägar → världen
     känns större utan att växa.
  3. **Gates:** ett passerbart segment i ett fence som kostar guld att passera
     (friktion/progression; kan låsas upp permanent för känslan av att bygga upp).
- **Avsikt:** Korrekt strandlinje + ett världsbyggande verktyg (fences/gates) i en och
  samma primitiv.
- **Not:** **Motor-ändring** i presentation/kollision. STEG 0: hur fungerar `blocked`
  + `is_blocked(rect)` + `try_move` idag (per-tile-occupancy, från B19); hur ritas
  spelaren/kameran. Designfork att lösa FÖRST: vilken granularitet — rena tile-KANTER
  (räcker för fences, hjälper vattnet en bit) eller ett finare sub-tile-rutnät
  (t.ex. ½- eller ¼-tile, behövs för diagonal strandlinje inuti en tile)? Prototyp/
  mockup innan bygge. Slice-först (se nedan). Fence-grafik: tunna sprites på kant-
  positioner; gate = öppning + interaktion (guld-kostnad, lyder ekonomi à la B20).
- **Slices (förslag):**
  - **Slice 1:** kollisions-primitiven (kant/sub-tile) + applicera på VATTNET (osynliga
    segment längs strandlinjen). Bevisa i spel att man går ända fram men ej ut i vattnet.
  - **Slice 2:** synliga fences (tunna sprites + kollision på linjen).
  - **Slice 3:** gates (passerbart segment, guld-kostnad, ev. permanent upplåsning).
- **Acceptans (Slice 1):** spelaren går ända fram till vattenbrynet utan att kunna gå
  ut i vattnet, längs både raka kanter och hörn; reachability grön; broar funkar;
  determinism oförändrad; tester låser primitivens beteende.

#### B12 — Encounter-skalning: faror mot avstånd + nivåtak nära start  · *höjd prioritet (playtest)*
- **Vad:** Stad + närmsta rutor säkra; encounter-rate stiger med avstånd; path-tiles
  sänker raten. **Tillägg från playtest:** ett *tak* på fiendenivå nära startområdet —
  inte bara lägre rate, utan svagare fiender nära start.
- **Avsikt:** Vildmarken farligare längre ut; resor meningsfulla. Och: en färsk L1–3
  ska inte mötas av cave_bear L7/L10 direkt utanför start (3 dödsfall på ~2 min i
  playtest = vägg före spelet börjar).
- **Not:** STEG 0: mät `encounter_rate` / `wild_region` + hur fiende-NIVÅ väljs per
  region (loggen visar fast band L1–L10 oberoende av spelarnivå nära start). Delar
  besökt-data med B11. Sim-verifierbar.
- **Acceptans (utkast — rätta):** rate ~0 på stad + angränsande tiles; stiger med
  avstånd; path-tiles −30–50%; fiendenivå nära start tak:at (t.ex. ≤ spelarnivå+2);
  sim visar rate- och nivå-kurvan mot mål; test för rate-/nivåfunktionen.

#### B8 — Städerna som funktionsdrivna kluster  ⭐ designbärande  · *burg_5 KLAR (f41b13b); Slice 2 (alla 17 + triggrar) = guidad session*
- **Vad:** Packade kluster runt ett **torg**, **tiered storlek** (liten/medium/hub),
  hus nedskalade (~0.6, justerbar load-tid), **cobble-wayfinding-nät** till varje
  ingång, **y-sort**, mallbaserad komposition anchored relativt stadens tile.
  Se **`TOWN_DESIGN.md`** för funktionstaxonomi + splitt-regeln.
- **Designbeslut (låsta denna session):**
  - **Facings (väg B):** 4 vyer/byggnad (front c1 / baksida c3 / ¾ c2,c4). Rena
    splittade via connected-component (ej grid-slice). **Skylt-sidan = ingångs-
    ledtråd** → c2/c4 = sidobyggnader med ingång öst/väst → fyrsidig inåtvänd plats.
  - **Skala ~0.6** (load-tid, tunbar konstant — ej inbränt i PNG).
  - **Y-sort:** byggnader + spelare i en bas-y-sorterad passage (lätt, ej foliage).
  - **Cobble:** autotilat (kanter/hörn ur cainos_stone) bara på **rutter**, ej
    under hus. Nätet = wayfinding även när dörren är dold (norr-vänt hus).
  - **Tiered storlek:** 3 mallar; **`size`-fält per stad i core_zone.json** (tunbar).
    Mätt kapacitet (avstånd+kant): **3 stor / 7 medium / 7 liten** (se TOWN_DESIGN §5).
    Inte varje hus behöver funktion — bostäder (cottage/hus) + tower (landmärke) = fyllnad.
- **Not:** Face-forward-assets klara (`a8b262e`); facing-PNG checkas in när hela
  uppsättningen croppats (halva genererad hittills). Hänger ihop med B5 (sortiment),
  B10 (shop-UI), B20 (inn), B22 (enchanter), B23 (board), B21 (gatehouse).
- **Slices:**
  - **Slice 1 (byggd, bebd2b7):** startstaden som kluster. *Refining kvar:* facings +
    cobble-nät + y-sort + 0.6-skala → burg_5 som **hub** (6–8 hus, funktionssvit).
  - **Slice 2:** alla 17 + **per-stad klareringskoll (STEG 0)** mot vatten/grindar/
    grannar (kapa mall om terräng kräver) + funktions-triggrar (blacksmith→vapen,
    barracks→rustning, apothecary→potions, shop→basics, inn→Rest, church→respawn,
    town_hall→board, shrine→enchanter, stable→snabbresa).
- **Acceptans (refining):** burg_5 renderar som hub med facings + autotilat cobble-nät +
  y-sort (spelaren går bakom hus norrut); skala justerbar; meny från torget; reachability
  grön; inget vatten/grannstads-överlapp; idempotent; tester.

#### B11 — Karta + fog of war
- **Vad:** Karta + fog of war för obesökta platser. **Avsikt:** orientering; utforskande
  belönas. **Not:** besökt-tracking (sparas) delas med B12. **Acceptans:** besökt-data
  persisterar; kart-vy; obesökt döljs, återbesök avtäcker; test.

#### B2 — Broarna (verifiera)
- Sannolikt löst av plank-skin + hav. Verifiera in-game, arkivera. Möjlig polish:
  gräs-ändkapslar vid broänden.

### Strid, progression & ekonomi

#### B24 — Balans-pass från playtest (fiende-abilities, skadetyp, drop-rate)  · *nytt*
- **Vad:** Tre balans-grejer som playtest blottade:
  1. **`undead_priest` heal** för stark (~128 HP i ett svep, nog att negera ett fullt
     träff) → kan bli mjuk vägg för en spelare som inte kan bursta igenom. Se över
     heal-mängd / cooldown.
  2. **Holy-vs-odöd-svingen** för extrem: `gravewarden_blade` 140–376 mot odöda vs ~70
     annars, och poolen är ~⅓ odöda → ett holy-drop trivialiserar stora delar.
  3. **Tidiga rare-drops:** tier-5 rares (`pyre_scepter`, `gravewarden_blade`) droppade
     från vanliga wild-fiender redan L3–5 → trivialiserar progressionen. Kopplar till
     **B6** (droptables) + **B12** (för stark fiende nära start gav för bra loot).
- **Avsikt:** Bevara meningsfull progression; inget enskilt drop ska göra spelet trivialt.
- **Not:** STEG 0 + sim: mät (a) `priest_heal`-värde/frekvens; (b) skadetyps-
  multiplikatorn holy→odöd; (c) pool-sammansättning per region (andel odöda — se nedan);
  (d) rare-drop-rate per fiende-tier/region. **Varning:** en session är för litet
  underlag för att döma drop-*rate* — verifiera via sim (N≥200), inte ögonmått.
- **Acceptans (utkast — rätta):** priest-heal kan bemötas (ej oändlig stall);
  holy-vs-odöd stark men inte one-shot-allt givet poolandelen; tier-5 rares sällsynta
  från låg-tier wild-fiender; sim-matris visar effekten mot mål.

#### Odöd-pool-densitet  · *mätuppgift (bekräftad i playtest)*
- Loggen bekräftar den gamla öppna frågan: ~⅓ av encounters var undead/undead_priest i
  burg_54/146/320. Om avsiktligt tematiskt = okej, men det är det som gör holy-vapnet
  (B24) trivialiserande. **Mät** pool per region (sim/räkning); justera densitet om för
  hög. Liten, sim-verifierbar, autonom-vänlig.

#### B3.1 — Dual-class (main + secondary)  ⭐ designbärande
- Kombinera main+secondary klass; talents återanvänds. Egen design-doc. Påverkar B3,
  abilities, vapenkrav. **HALT efter — review innan B3/B7.1.**

#### B3 — Talent tree är för tunt
- Bara 8 talents/klass. Beror på B3.1 (bygg dual-class FÖRST). STEG 0: mappa talent-data.

### Items, ekonomi & crafting

#### B22 — Enchantment-vendors (stads-specifika)  ⭐ designbärande  · *nytt*
- **Vad:** Vissa städer erbjuder **enchantments** — köp som förbättrar items med stats.
  Per stad varierar: item-typ(er) som kan enchantas, vilka stats, vilka tiers, kostnad.
  Exempel (låg-zon-stad): enchanta **uncommon feet & legs**, med **2 enchantments** i
  **3 storlekar** (minor / enchantment / greater), på **2 stat-val** (t.ex. armour ELLER
  speed; eller HP & mana). Olika städer = olika item-typ × stat × tier-kombinationer →
  massor av varianter. **Kostnad:** guld, eller guld + items (junk/crafting-items).
- **Avsikt:** Crafting/ekonomi-djup; ger städer (även icke-shop) en egen identitet och
  anledning att besökas; meningsfull guld- och junk-sink.
- **Not:** Större system. STEG 0: hur är items/stats/gear-data strukturerat (kan en
  enchant additivt lägga stats på en item-instans? finns item-instanser eller bara
  id→count?); finns junk/crafting-items redan (loggen visar `bone_dust`, `rat_pelt` —
  kandidater). Bygger på shop/town-infra (B10) + inventory (B20-consumables). Hänger
  ihop med CHARACTER_SCREEN (förstå vad enchant ger via preview).
- **Acceptans (utkast):** en enchant-vendor i en stad erbjuder en kurerad uppsättning
  (item-typ × stat × tier); köp drar guld (+ ev. items) och applicerar stat-bonus på
  vald item; olika städer olika utbud; preview visar resultatet före köp; persisterar;
  tester för utbud-data, kostnad, applicering, persistens.

#### B4 — Vapentyp + item-preview → CHARACTER_SCREEN
- Datadelen klar (`e4f6c08`). UI:t i CHARACTER_SCREEN-bygget. Se **B10** (preview).

### Städer & UI

#### B10 — Stads-/vendor-skärm + SHOP i character-interface med stat-preview  · *utökad (#6 + playtest)*
- **Vad:** Skärm med vendors per husfunktion. **Utökning:** själva **shoppen ska ligga
  i character-interfacet** (samma yta som equip), så man **förstår vad man köper** —
  hover/preview som visar itemets stats och stat-deltat mot det man har på, precis som
  vid equip.
- **Avsikt:** Köp- och utrustnings-beslut ska vara informerade. Playtest-belägg:
  spelaren togglade samma ring ~20× på en halv minut för att jämföra stats — det finns
  ingen preview idag.
- **Not:** Town-UI + character-UI, medel–stor. Byggnad→funktion låst (shop→Store,
  inn→Rest, church→respawn, tower→Mage Tower; ev. enchanter→B22, board→B23). Efter B8.
  Rest-vendorn lyder B20. Lever ihop med CHARACTER_SCREEN.md.
- **Acceptans:** stads-meny → rätt vendor per hus; shop öppnas i character-ytan; hover
  på item (shop + inventory) visar stats + delta mot equippat; klick köper/equippar;
  test för funktion→vendor-mappning + preview-delta.

#### B23 — Notice boards / quests (nytt missions-panel)  ⭐ designbärande  · *nytt*
- **Vad:** **Notice boards** i städer med uppdrag, rewards och info. Kräver ett **nytt
  meny-val** (C/K/I → Missions). Spektrum:
  - **Enklast:** "Travel to X" → XP & guld-reward.
  - **Svårare:** t.ex. "Identify AND slay an elusive Hollow Worg and report its traits"
    (hitta + döda en specifik fiende + rapportera).
  - **Item-rewards** också, som quests.
- **Avsikt:** Ger städer UTAN shop ett syfte; riktning åt utforskandet; belöningsloop
  utöver grind.
- **Not:** Nytt system: quest-data (mål, villkor, reward), quest-state (aktiv/klar,
  sparas), trigger-detektering (anlände till X? dödade Y?), och ett missions-UI
  (nytt panel-val). STEG 0: hur är panelerna (C/I/K) uppbyggda; var fångas
  "arrived at place" / "killed enemy"-events (loggen visar att events finns). Slice-
  först: börja med "travel to X" (enklaste quest-typen, ingen ny combat-logik).
- **Acceptans (Slice 1, utkast):** ett notice board i en stad listar minst en
  "travel to X"-quest; acceptera → aktiv; anländ till X → klar → XP+guld utbetalas;
  quest-state persisterar; nytt Missions-panelval öppnar listan; tester för
  accept/complete/persist.

#### B16 — Overworld-logg (RuneScape-lik)  · *redo (STEG 0 klar); batch-kandidat*
- Halvtransparent action-logg **nere till vänster**. Loggar: **combat** (skada/utfall),
  **drops** (vad man får), **level-ups**, **heals**, och world-events (toast).
- STEG 0 klar (Code): `_draw_hud`-mönstret (SRCALPHA-panel, oskalad skärmrymd efter den
  zoomade världen) → ett `_draw_log` matat av en **deque** som ackumulerar events.
  Liten, ren feature ovanpå befintlig HUD-stil. Enkel batch.

#### B16.1 — Combat-logg i overworld-loggen + flikar (ALL/Combat)  · *del av B16*
- Combat-rader överlever battle→overworld; flikar filtrerar. **Playtest-notis:** städa
  heal-loggningen — `priest_heal` loggar spelarens HP som "target", förvirrande; visa
  vem som healas och hur mycket.

#### B18 — Klassvals-skärmen omarbetad (fluid-layout)
- Inzoomad/dålig text. Gör ihop med fluid-migration (character_creation). STEG 0: varför
  inzoomad; var renderas texten.

### Innehåll & värld (kreativ expansion)

#### B27 — Innehålls-variation: nya skills, vapen, stats  · *nytt (batch-kandidat, kreativ frihet)*
- **Vad:** Code har **stor frihet** att skapa nytt innehåll för variation — nya skills
  (t.ex. elementala: thunder strike / zap / incineration / holy strike / plague ooze, m.fl.),
  nya vapen, ev. nya stats/skadetyper. Lucas uppmuntrar uppfinningsrikedom.
- **Räcken (icke förhandlingsbara):** allt **data-drivet** i befintliga format
  (`actions.json`, items, classes), respektera befintligt system (skadetyper, resistans,
  cooldown, mana). **Sim-balanserat** — inget nytt får göra en klass trivialt OP (sim-
  kontroll). Tester + compile gröna. Konsekvent namngivning/skadetyps-taxonomi.
- **HALT:** kraftspikar / medvetet starka signatur-items → flagga för Lucas, committa ej.
- **Återanvändning:** skapade skills/vapen ska vara återanvändbara — kan senare bli
  **köpbara i mage towers / butiker** (kopplar B22) eller turnerings-belöningar (B26).
- **Acceptans:** N nya skills/vapen, data-drivna, sim-balanserade, test-täckta; en kort
  lista över vad som lagts till + var det kan återanvändas.

#### B28 — Världsexpansion: fler städer (och ev. zoner)  · *nytt (batch-kandidat, delvis)*
- **Vad:** Fler städer i den befintliga världen, byggda på den **verifierade hub/tiered-
  kluster-modellen** + `core_zone.json`/regen-mönstret. Lucas vill expandera världen.
- **Autonom-vänligt NU** tack vare de automatiska kriterierna från burg_5: entré-test,
  ingen-cobble-i-vatten, `footprints ∩ water == ∅`, reachability. Code genererar +
  verifierar mot testerna; **rendrar för Lucas estetik-granskning** (korrekthet av tester,
  estetik av Lucas i efterhand).
- **Nya ZONER är tyngre** (terräng/tmx, gates, enemy-pool, tema, svårighet = designbärande)
  → om en ny zon kräver riktig terräng-design: **HALT + förslag**, bygg inte blint. Lättare
  zon-utökning som följer befintligt regen/json-mönster är ok.
- **Acceptans:** X nya städer som passerar alla stads-tester + reachability, renders
  bifogade; ev. zon-scaffold endast om det följer befintligt mönster, annars flaggat.


- **Vad:** En progressions-ladder av turneringar bortom start-zonens 4, knuten till
  städer i senare zoner — så arena-innehållet skalar med spelaren. Återanvänder det
  diversifierade buff-systemet (tanky/burst-split + finale-per-index-skalning).
- **Avsikt:** Mer PvE-arena-innehåll genom progressionen; ger fler städer ett syfte
  (kompletterar B23). Turneringar är meny-/zon-gated → fungerar även på flat-markör-
  städer, så **kräver inte Slice 2**.
- **Not:** Sim-verifierbar, autonom-vänlig — MEN **belönings-item per turnering är
  designbärande** → HALT, Code föreslår men Lucas väljer signatur-item. STEG 0:
  nuvarande turnerings-/enemy-/reward-struktur + vilka städer ligger i vilken zon.
- **Acceptans (utkast):** minst en ny turnerings-tier i en senare-zon-stad; opponents
  ur zonens pool; sim visar att den är klarbar runt zonens nivå-band (ej L1); belöning
  = skalad guld/XP + flaggat signatur-item; tester. Sim N≥200.

#### B25 — Klassbalans-granskning (skill-användande sim)  · *nytt*
- **Vad:** Mät klassbalansen med en **skill-användande** sim L1→7, jämför alla 6 klasser.
- **Avsikt:** Fighter framstår som outlier i attack-only-sim (L3 88% vs ~0% andra), men
  attack-only straffar casters som lever på skills → gapet är delvis artefakt. Avgör om
  fightern faktiskt är OP eller om det är sim-modellen.
- **Not:** Kräver att sim:en kan driva skill-rotationer (ej bara attack). Sim-verifierbar.
  **Nerfa inget** förrän skill-sim/playtest visar det verkliga gapet.
- **Acceptans:** sim-matris (6 klasser × nivå, skill-användande) som visar relativa
  win-rates; rekommendation om fightern behöver justeras eller ej.

#### B13 — Tournaments: svårighet (KLART, se arkiv)
- Löst: Frenzy-CD (root-fix) + diversifierade turneringsbuffar. Fortsättning = B26.

---

## Föreslagna kluster & ordning

1. **Autonom batch (nu):** **B16** (overworld-logg) · **B27** (nya skills/vapen — kreativ
   frihet m. räcken) · **B26** (turnerings-expansion) · **B28** (fler städer) · **B24-flaggan**
   (tier-cap låg-nivå wild). Sim-/test-verifierbart; HALT på designbärande (signatur-items,
   nya zoner som kräver terräng-design). Renders bifogas för estetik-granskning.
2. **Guidad session:** **B8 Slice 2** (alla 17 städer + funktions-triggrar) — visuellt,
   kräver din render-granskning per stad. Sedan vad städer *erbjuder*: **B10** (shop+
   preview) → **B22** ⭐ (enchants) → **B23** ⭐ (quests).
3. **Kollision & värld:** ⭐**B21** (sub-tile-kollision — fixar vatten/fences/gates).
4. **Klassbalans:** **B25** (skill-användande sim) innan ev. fighter-justering.
5. **Progression:** ⭐**B3.1** FÖRST (HALT) → **B3**.
6. **Värld/utforskande:** **B11** (delar besökt-data med B12 + B23).
7. **UI/skärmar:** CHARACTER_SCREEN (absorberar B4); **B16** (overworld-logg) + flikar
   (B16.1-rest); **B18** (klassvals-skärm fluid).

> Mät-först-punkter (B21, B23, B26) inleds med STEG 0.
> ⭐-punkter (B8 Slice 2, B21, B22, B23, B3.1) får en designrunda/granskning — ej obevakat.

---

## ✅ Klart (arkiv)

- **B1** (`9568633`) — zoom 10→12, hastighet −20% via sub-pixel-accumulator. 521 tester.
- **B5** (`df0d394`) — store diversification (kurerat sortiment per store).
- **B6** (`391d5b0`) — droptables per enemy; unik-rate 4.7–5.4%. *(Se B24: rare-drop-rate
  från låg-tier wild-fiender kan behöva ner.)*
- **B7** (`68b7935`) — starter skills per klass. Se B7.1.
- **B7.1** (`51ef516`) — starter-skill registreras som learned vid klassval (ej "Can
  learn", ingen dubbel point).
- **B9** (`be34ce2`) — README uppdaterad.
- **B14** (`e53d9c2`) — full HP+mana efter tournament.
- **B15** (`ff543fe`) — mana pots (lesser/std/greater) + mana-stat-gear.
- **B19** (`1000b24`) — vatten-kollision majoritets-baserad (tröskel 0.6). *Delsteg;
  **ersätts för vattnet av B21** (sub-tile) eftersom per-tile inte kan följa en diagonal
  strandlinje. Behålls tills B21 Slice 1 landar.*
- **B20** (`2d43c65`) — betald vila (50/100 per zon) + gratis Rest Voucher vid nytt spel
  + respawn full HP+mana. 533 tester.
- **B2** (arkiverad) — broar verifierade (plank-skin `45401b0`, 38/38 celler gångbara
  + vattengränsande). Gräs-ändkapslar = valfri framtida polish.
- **B12-rate** (`dd66afc`) — encounter-rate-heatmap: 0 på stad+grannruta, ramp över 3
  tiles, ×0.6 path-tiles. *Nivåtak medvetet PARKERAT (Lucas): fasta regionala fara-band
  behålls, L5 nära start är meningen — ej world-scaling.*
- **B16.1-heal** (`aea376b`) — heal-loggning fixad: egen heal-rad (healer/amount/hp_after),
  loggar ej heal som attack. *(Flikar/overworld-persistens kräver B16 — ej byggt.)*
- **B24** (`59e2cfb`) — holy-vs-odöd 2.0→1.5; `rare_tier_cap(level)`; priest_heal CD 2→3.
  *Öppen flagga → batch: `consecrated_maul` (tier-4) droppar fortf. ~7% från L3-4 wild —
  capa tier vid L<5.*
- **Frenzy-CD** (`3e394db`) — `cooldown_rounds: 2` på frenzy (root-fix för fighter-spam:
  casts 3.0→1.9-2.0). Data-ändring; CD-infran enforcar.
- **B13** (buffar `ff1d03e`) — diversifierade turneringsbuffar: small/mid (≤4, incl.
  iron_ring) ×1.6 HP + varannan tanky(+armor+dmg)/burst(+crit+dmg); finale (≥10) per-index
  split. Fresh L1 <30%. *Expansion = B26; fighter-outlier = B25.*
- **B8 burg_5** (`f41b13b`) — startstadens hub: 52 facings, load-tid-skala 0.55, y-sort,
  Ö-kolumn spegelvänd (skylt inåt), kam-cobble (spur/dörr, ingen cobble mot vattnet),
  entré-kriterium. *Slice 2 (alla 17 + funktions-triggrar) kvarstår — guidad session.*