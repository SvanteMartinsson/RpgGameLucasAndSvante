# Svantrenish RPG — Backlog

Fångade förbättringar/buggar att åtgärda. ID:n (B1–B18) är stabila referenser i
build-prompts. Varje punkt: **Vad** / **Avsikt** / **Not** (storlek, beroende,
mät-först) / **Acceptans** (definition av "klart" — maskinellt kontrollerbart där
det går; styr autonomt batch-arbete, se `CLAUDE.md` → Autonomt Batch-Arbete).

> **STEG 0-princip:** punkter som beskriver nuvarande beteende vi inte säkert känner
> inleds med en STEG 0 som **mäter koden** innan ändring.

> **Avgränsning:** overworldens *försköning* spåras i `OVERWORLD_BEAUTIFY_PLAN.md`,
> dubbleras inte här. B2/B17 korsar den (se noter).

> **Acceptans markerad "(utkast — rätta)"** är arkitektens förslag på mål; Lucas
> sätter de slutliga siffrorna. Balans verifieras via `rpg_game/core/simulation.py`.

---

## Översikt

**✅ Klart:** B5 · B6 · B7 · B9 · B14 · B15 (detaljer i arkivet). **B4** datadel klar
(`e4f6c08`); kvarvarande UI lever i `CHARACTER_SCREEN.md`.
**▶ Pågår:** Overworld-försköning (Slice 1a, se beautify-planen); B8 nästa kart-slice.
**Härnäst:** karta klar (försköning + B8) → progression (⭐B3.1 → B3 + B7.1) →
town-UI (B10) → utforskande (B11+B12) → UI/skärmar (B16/B16.1, B18; equip-skärm =
`CHARACTER_SCREEN.md`) → tournaments (B13). _(Item-/ekonomi-passet B4·B6·B5·B15 klart.)_

---

## Aktiva punkter

### Rörelse & kamera

#### B1 — Spelarhastighet + utzoomning
- **Vad:** Sänk hastigheten något. Zooma ut ca 2 tiles.
- **Avsikt:** Bättre känsla/överblick på den större kartan.
- **Not:** Liten tuning, låg risk. `ZOOM_TARGET_TILES_W` (idag ~10 → ~12); hastighet
  är en rörelse-konstant.
- **Acceptans (utkast — rätta):** ~12 tiles synliga i bredd; hastigheten sänkt
  ~20–30%; tester gröna; arkitekten verifierar känslan i render/playtest.

### Overworld & karta

#### B2 — Broarna ser fel ut
- **Vad:** Broarna läser som räcken på mark, inte bro över vatten.
- **Avsikt:** En bro ska tydligt spänna över floden.
- **Not:** Grafik/placerings-bugg (9c686e0). Korsar beautify-planens vatten-städning
  och B17. STEG 0: vilka tiles i `water_bridge_32x32_crisp.png` är däck vs
  räcke/stolpe, och hur ligger de mot vattnet under?
- **Acceptans:** en bro renderar som däck med synligt vatten under; reachability +
  bro-kollision (gångbar) oförändrade; arkitekt-render från klon bekräftar.

#### B8 — Städerna behöver läsas in
- **Vad:** Designade stadskluster (packade 1–3-byggnaders-kluster) placeras/renderas.
- **Avsikt:** Städer = byggnads-kluster, inte markör-rutor.
- **Not:** Edge-fasens stads-slice. Modell låst (packade kluster, ~3 tiles/hus,
  samlad kollisions-footprint, Model A nu). Hänger ihop med B10, B4.
- **Acceptans:** varje stad renderar som packat kluster (terracotta-tak, ljus sten);
  samlad kollisions-footprint; reachability grön; arkitekt-render bekräftar modellen.

#### B17 — Diagonal flod utan kantighet  · *ny*
- **Vad:** Flod som kan gå diagonalt utan att se trappstegig ut. Möjlig lösning:
  halva tiles (trianglar) med korrekt kollision. Öppen för andra förslag.
- **Avsikt:** Floder läser organiskt, inte block-kantigt.
- **Not:** Grafik + ev. kollision. Billigast: mjukare meander i genereringen (ingen
  kollisionsändring). STEG 0: vilka diagonala vatten-tiles finns; binär kollision
  per tile eller subtile?
- **Acceptans (utkast — rätta):** en diagonal flod läser organiskt i render; vald
  lösning dokumenterad; vatten-konnektivitet (flood-fill) + reachability oförändrade;
  vid subtile-kollision: test som låser kollisionen.

#### B11 — Karta + fog of war
- **Vad:** Karta så man hittar tillbaka; fog of war för obesökta platser.
- **Avsikt:** Orientering; utforskande belönas.
- **Not:** Ny feature, medel. Besökt-tracking (sparas) + kart-vy + fog-rendering.
  Delar besökt-data med B12.
- **Acceptans:** besökt-data sparas/laddas över sessioner; kart-vy öppnas; obesökt
  döljs, återbesök avtäcker; test för besökt-tracking + persistens.

### Strid & progression

#### B3.1 — Dual-class (main + secondary)  ⭐ designbärande
- **Vad:** Spelaren kombinerar **main** + **secondary** klass.
- **Avsikt:** Roliga kombos; talents återanvänds över combos (löser delvis B3).
- **Not:** Större arkitektur-feature, egen design-doc. Hörnsten — design FÖRST.
  Påverkar B3, abilities, vapen-krav (B4).
- **Acceptans:** design-doc skriven; main+secondary kan väljas/kombineras;
  talents/abilities/vapenkrav respekterar kombon; tester låser combo-reglerna.
  **HALT efter denna — bygg inte B3/B7.1 i samma körning (review först).**

#### B3 — Talent tree är för tunt
- **Vad:** Bara 8 talents/klass — för få.
- **Avsikt:** Mer djup i progressionen.
- **Not:** Storlek beror på B3.1 (bygg dual-class FÖRST). STEG 0: mappa talent-data.
- **Acceptans (utkast — rätta):** meningsfullt fler valbara talents per klass-väg
  efter B3.1-återanvändning (mål: ≥2× dagens upplevda val); unlock/equip + max 4
  skills testade; ingen parallell talent-väg.

#### B7.1 — Starter-skill spökar i talent-/skills-UI:t  · *ny, uppföljning på B7*
- **Vad:** Frenzy (starter-skill) visas som "Can learn" trots att den är upplåst från
  start; man måste dessutom spendera en point för att fortsätta den redan upplåsta
  pathen.
- **Avsikt:** Starter-skillen ska räknas som inlärd — varken erbjudas igen eller
  dubbelkräva en point.
- **Not:** Trolig bugg i seamen B7↔B3-UI. **Hypotes (verifiera):** starter-skillen
  skrivs inte in i talent-state som learned/spent vid klassval. STEG 0: hur avgör
  UI:t "Can learn" vs "Learned"; registreras starter-skillen vid klassval?
- **Acceptans:** starter-skill visas som "Learned"; pathen fortsätter utan extra
  point-spend för den redan upplåsta noden; regressionstest låser beteendet.

### Items & ekonomi

##### B4 — Vapentyp + item-preview → se CHARACTER_SCREEN.md
- **Status:** datadelen klar (`e4f6c08`) — vapentyp/preview exponeras i snapshot +
  text-helpers, testad. UI:t ersätts inte i interim-skärmen utan byggs som en del av
  den nya equip-/character-skärmen (`CHARACTER_SCREEN.md`): hover på weapons/armour
  → stats, klick → equip, slot-ikoner på kåp-figuren.
- **Not:** B4 är inte längre en egen UI-punkt — den lever i CHARACTER_SCREEN-bygget.

> **B6 · B5 · B15 — klara.** Per-enemy unique/common-tables, store-diversifiering
> (gear köpbart) och den tierade mana/health-potion-ekonomin är byggda och testade.
> Se arkivet.

### Städer & UI

#### B10 — Vendor-skärm i stadsmenyer
- **Vad:** Skärm med olika vendors per hus/funktion man besöker.
- **Avsikt:** Ge städerna karaktär; koppla funktion till byggnad.
- **Not:** Town-UI, medel. Byggnad→funktion låst (shop→Store, inn→Rest,
  church→respawn, tower→Mage Tower). Steg mot Model B. Efter B8.
- **Acceptans:** stadsmenyn visar vendors mappade till husfunktioner; klick öppnar
  rätt vendor; test för funktion→vendor-mappning.

### Gränssnitt, loggar & skärmar

#### B16 — Overworld-logg (RuneScape-lik)  · *ny*
- **Vad:** Halvgenomskinlig action-logg nere till vänster i overworld.
- **Avsikt:** Se vad som hänt utan att tappa kartan.
- **Not:** Presentation (`pygame_overworld`), overlay i skärmrymd som HUD:en. STEG 0:
  hur ritas HUD-overlayen (font/panel/alpha)?
- **Acceptans:** läsbar halvtransparent panel nere till vänster som skriver
  world-actions; respekterar `present()`-transformen; arkitekt-render bekräftar.

#### B16.1 — Combat-logg i overworld-loggen + flikar  · *ny, del av B16*
- **Vad:** Combat-loggen in i overworld-loggen; flikar **ALL** + **Combat**.
- **Avsikt:** Beständig historik; combat-events försvinner inte efter strid.
- **Not:** Bygger på B16. STEG 0: var produceras combat-rader; kan de fångas i en
  delad buffer som överlever battle→overworld?
- **Acceptans:** combat-rader hamnar i overworld-loggen och överlever
  battle→overworld; flikarna ALL/Combat filtrerar rätt; test för buffer-persistens.

#### B18 — Klassvals-skärmen omarbetad  · *ny*
- **Vad:** Skärmen efter "New Game" är utdaterad — inzoomad, dålig textkvalité.
- **Avsikt:** Läsbar, snygg klassvalsskärm.
- **Not:** Presentation (`character_creation`). **Gör ihop med fluid-layout-
  migrationen** (character_creation är nästa skärm i ordningen efter start_menu).
  STEG 0: varför inzoomad (fast canvas-skala?); var renderas texten?
- **Acceptans:** skärmen fyller fönstret fluid (ej fast inzoomad); text skarp/läsbar
  på små + stora fönster; klassval funkar; klick mappar genom transformen;
  arkitekt-render bekräftar på två fönsterstorlekar.

### Encounters

#### B12 — Encounter-heatmap (avstånd från stad)
- **Vad:** Stad + närmsta tiles safe; rate ökar längre ut; path-tiles sänker raten.
- **Avsikt:** Gör vildmarken farligare längre ut; resor meningsfulla.
- **Not:** STEG 0 (vet inte hur logiken funkar): mät `encounter_rate`/`wild_region`.
  Delar besökt-data med B11. Påverkar inte respawn.
- **Acceptans (utkast — rätta):** rate ~0 på stad + angränsande tiles; stiger
  monotont med avstånd till nivå R i djupaste vildmark; path-tiles sänker raten
  ~30–50%; sim/körning visar rate-kurvan mot mål; test för rate-funktionen.

### Tournaments

#### B13 — Tournaments: svårighet, priser, fler platser
- **Vad:** Tournament-fienderna är för lätta; priser justeras; fler tournaments över
  världen.
- **Avsikt:** Göra tournaments till en anledning att utforska.
- **Not:** Balans + content. Verifiera via `simulation.py`. Greater pots som reward
  kopplar till B15. Fler platser knyter ihop med B11/B12.
- **Acceptans (Lucas mål):**
  - Färsk **lvl 1 utan items** ska **förlora alla** turneringar (~0% vinst, sim
    N≥200 seeds/matchup).
  - **Tournament 2** (reward: *consecrated maul*) först klarbar **lvl 2 med flera
    items eller lvl 3**: lvl1 ~0%, lvl2-utan-items låg vinst, lvl2-med-items eller
    lvl3 rimlig vinst.
  - Fler turneringar placerade över världen (platsbundna).
  - Rapportera sim-matrisen (nivå × utrustning × turnering → vinst-rate) mot målen.

---

## Föreslagna kluster & ordning

1. **Karta klar först** (pågår): försköning (`OVERWORLD_BEAUTIFY_PLAN.md`) → **B8**.
   **B2** + **B17** städas in i samma fas.
2. **Item-/ekonomi-pass** (samlat): **B4 → B6 → B5 → B15** (delar itempoolen).
3. **Progression**: ⭐**B3.1** FÖRST (HALT efter) → **B3** + **B7.1**.
4. **Town-UI**: **B10** efter B8.
5. **Värld/utforskande**: **B11** + **B12** (delar besökt-data).
6. **UI/skärmar**: **B16 + B16.1**; **B18** ihop med fluid-migration av
   character_creation.
7. **Tournaments**: **B13** ihop med B15-rewards.
8. **Småfixar när som helst**: **B1**, **B2**.

> Mät-först-punkter (B12, B13, B16.1, B17, B7.1) inleds med STEG 0 som mäter
> nuvarande kod innan design.

---

## ✅ Klart (arkiv)

#### B7 — Starter skills för alla klasser
- **Klar** (`68b7935`). Varje klass startar med sin signatur-l1-skill. Data-only.
- **Uppföljning:** se **B7.1** (aktiv).

#### B9 — README uppdaterad
- **Klar** (`be34ce2`). README speglar Pygame-overworlden, beroenden, starter skills,
  respawn-regeln, full HP efter tournament.

#### B14 — Full HP efter tournament
- **Klar** (`e53d9c2`). `complete_tournament` återställer HP+mana till fullt.

#### B6 — Droptables per enemy
- **Klar** (`391d5b0`). STEG 0: loot var redan per-enemy (`loot_table`) + delad
  `rare_table`, men utan signatur. Nytt `unique_table`-fält per drop-fiende, mergat
  i samma viktade `loot_pool()` (ingen parallell väg). 12 tematiska signaturer
  (11 gear + vapnet Worgfang) viktade så varje landar ~3–8% (sim: 4.7–5.4%).

#### B5 — Store diversification
- **Klar** (`df0d394`). STEG 0: alla 4 stores föll till `DEFAULT_STORE_INVENTORY`
  (identiskt) och kunde inte sälja gear. Gear-köp tillagt i store; varje store fick
  eget kurerat sortiment (vapen + consumables + simpel/mid gear), tematiskt per stad.
  Inga två identiska, ingen tom. _Antaget: per-stad-sortiment — bekräfta._

#### B15 — Mana items/stats + mana pots
- **Klar** (`ff543fe`). lesser_hp/lesser_mana (25) + greater_mana (100) tillagda.
  Distributionsregel låst: lesser-pots i alla stores; greater-pots i ingen store,
  endast via drop (greater_mana seedad i caster-droptabeller). Mana-stat-gear fanns.
  _Antaget: tier 25/50/100, priser 30/50, greater_mana 280, drop-vikter 12/10 — bekräfta._

#### B4 — Vapentyp + item-preview (datadel)
- **Datadel klar** (`e4f6c08`). Vapentyp (category)+stats exponeras i
  `WeaponSnapshot` och surfas via `ui_text.weapon_label()`/`weapon_preview()` i
  inventory + Character-panelen. UI visuellt overifierad; full equip-skärm =
  `CHARACTER_SCREEN.md` (aktiv pekare ovan).