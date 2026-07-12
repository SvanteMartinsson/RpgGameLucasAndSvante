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

**✅ Klart (2026-07-06): B65 zonbossar + huvudmål** — spelet har nu ett SLUT (5 bossar,
Pale Gate, victory-skärm). Dessförinnan våg 1+2 (2026-07-04→06): **B53** (CI) · **B54**
(content-validering) · **B55** (encounter-core) · **B57** (en wrap) · **B58** (effekt-
dispatch) · **B59** (save-schema) · **B60** (terminal-beslut) · **B61** (worldgen-flytt) ·
**B63** (lootkistor) · **B66** (bestiarium) · **B68** (alkemi) · **B70** (settings) ·
**B71** (save-slots+död) · **B72** (stridskänsla). Natt-batch 2026-07-01→02: **B42/B46/
B43/B38/B11 S2/B41/B25**. Föregående: **B35/B36/B37 S1+2**, **Wisdom A+B**, **#3**,
**B8 S2a**, **B11 S1**, **B40 S1**, unified chatbox, **B24-flaggan**.
Äldre: B1/B5/B6/B7/B7.1/B9/B14/B15/B19/B20/B39.

**✅ Klart (nattbatch 2026-07-06→07):** **B74** (load-buggen: exakt tile persisteras) ·
**B75** (rundsekvensering 0,5 s + skip-setting) · **B76** (battle-layout v2) · **B77**
(status-appliceringar med källa) · **B78** (läsbara skill-texter) · **B79** (bestiarium-
scroll) · **B80** (fälld boss försvinner) · **B81** (kistor −15 %) · **B82** (chips i
panelen) · **B47** (zonsöms-blend i produktion, draw-time-overrides) · **B83** (player
walk/idle-animationer, 8 riktningar). Sviten 953→980.

**✅ Även klart (dagbatch 2026-07-06):** **B44+B16.1** (chatt v4: segmentfärger, röd
vs-dig-skada, All/Combat-flikar) · **B56** (OverworldApp 3423→1969 rader, tre mixin-
moduler, render-identiskt) · **B62** (ekonomi-sim + N=300-rapport) · **B48-förarbete**
(zon-referenskarta `docs/ZONE_MAP.png`) · **B47-PoC** (blend-beslutsbilder `docs/b47_poc/`).

**✅ Klart (städat 2026-07-10):** **B48–B52** (alla fem ✅, se resp. post) · **B47-beslutet**
avgjort (blend GO → B47 ✅ KLAR i produktion) · **B48-designrundan** avslutad (Lucas-GO
2026-07-06) · **Playtest-fynd B74–B83** alla ✅. **B69 S1+S2** (ljud + musik, audio-HALT
godkänd) · **B70 S2** (musikvolym-reglaget).

**▶ Pågår / nästa:** **Nattbatch 2026-07-10→11: B84–B95 + kraftkurve-blocket (B93/B94/B95/
B27) + B67 S1 + ev. B73 S1** (se sektionen "Playtest-tasks 2026-07-10" nedan) · **B40
apply-slices S2–S5** (render-HALT/skärm; redigerar nu `overworld_overlays`; S2/S4 bär
playtest-kollisionerna) · **B8 Slice 2b-rest** (Lucas-tuning av roster/priser; shrine/board
väntar på B22/B23-rundor). **B64 dungeons = PARKERAD** (Lucas 2026-07-06: väntar på karta
som stödjer interiörer).

**Härnäst (öppet, ej byggt):** *Designbärande (⭐, designrunda först):* B21 (sub-tile-
kollision) · B22 (enchant-vendors) · B23 (quests) · B3.1→B3 (dual-class) · B10/B18 (UI).
*(#2 encounter-heatmap = LIVE, B12-rate.)*

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

### Playtest-tasks (2026-07-02, fighter playtest)

> STEG 0 gjord av Code mot koden där det gick; #2 bekräftad LIVE, ej ny punkt.

- **#2 — Encounter-heatmap (nära stad låg, längre bort mer, vägar sänker):** ✅ **LIVE**
  redan — `B12-rate` (`dd66afc`): `ENCOUNTER_SAFE_RADIUS=1` (stad+granne = 0), `ENCOUNTER_RAMP_TILES=3`
  (rampar 0→full över 3 tiles från stad), cobble/väg-tiles ×0.6. Öppna igen bara om kurvan ska tunas
  (t.ex. brantare ramp eller ramp mot avstånd-till-VÄG, inte bara stad).

#### B48 — Per-zon/per-område enemy-spawn-authoring  ⭐ designbärande (stor)  · ✅ **KLAR** (Lucas-GO 2026-07-06)
- **Geo-levelband GODKÄNDA rakt av (Lucas 2026-07-12):** first-pass-banden ur nattens
  BFS-gångavståndsförslag (docs/nightly/geo_proposal.md + geo_*.png) sätts i
  `spawn_areas`-datan (level_min/level_max), precedens AREA>region>mall (5cc6504).
- **KLAR:** union-modellen byggd — `core/spawns.py` (`SpawnArea`, `pool_at`: union av
  alla träffande områden, vikter summeras per fiende; tom → `spawn_fallbacks[region]`;
  `weighted_pick` = ett rng-drag). **22 Lucas-ritade områden** + 4 fallbacks authorade i
  `maps/core_zone.json` (inkl. skissfärger); pool-param trädd genom
  `engine.create_encounter(pool)` → `world.create_encounter` — **platslösa vägar
  (terminal/sims) oförändrade** (behåller place-pool + rare-slot; beslut: world.json
  rörs INTE). Skalet skickar tile-poolen i `maybe_encounter` (B55-mönstret: skalet äger
  tilen, core äger regeln). `_validate_spawns` fail-fast (okänd fiende, boss i pool,
  vikt ≤0, trasig rect, dubblett-id, tom fallback). **Rotfang → (14,88)** (snap-
  verifierad, stadsavstånd 35). **Holy-kompensationen:** gravewarden_blade på
  cursed_wights tabell + chest_heath_4. Rares som vikter: vine 8 i plant-områdena,
  hag 8 i sin ficka (~21 % i västra halvan, utspädd mot tar-landet), worg 6 vs shade 40
  (13 % i Pale Gate-hörnet, 3 % i väst-kolumnens blandzoner), wight 12 i elit-öst.
  Distributions-verifierat på 10 representativa tiles + 300 seedade motor-drag.
  `docs/ZONE_MAP.png` omrenderad med alla områden som facit. 16 nya tester;
  **953 gröna**. ENEMIES.md-sektionen omskriven.
- **Grave heath-skiss mottagen (Lucas 2026-07-06, avstämning pågår):** BLÅ nordväst
  x2-91/y101-162 = undead+priest+rotting_fiend (mjuk entré) · GRÖN väst-syd x0-72/
  y133-207 + syd-mitt x72-139/y187-207 = ghoul+grave_hound · VIT kolumn väst x42-91/
  y100-207 = shade+hollow_worg(LÅG vikt) — vaktar Barrow-lyan · RÖD öst-mitt x132-209/
  y100-199 = priest+skeleton_warrior+cursed_wight · LILA nordost x180-230/y100-142 =
  priest+rotting_fiend (⚠ saknades i legenden, läst ur bilden) · VIT öst-syd x170-235/
  y144-207 = shade+hollow_worg(LÅG vikt) — Pale Gate-hörnet. **Öppet:** (1) lila-rutan
  bekräftas? (2) fallback = ghoul+grave_hound? (3) cursed_wight låg-måttlig vikt i röd,
  rare-slot tom (Claude-rek)?
- **Bekräftat byggt (nattbatch 2026-07-09, STEG 0 mot `core_zone.json`):** alla tre öppna
  frågorna ovan är redan i data — `spawn_areas` har `heath_northeast_pocket` [180,100,230,142]
  (lila-rutan, undead_priest 30 + rotting_fiend 30), `spawn_fallbacks.burg_121` = ghoul 35 +
  grave_hound 35 (fallback bekräftad), och `heath_elite_east` har cursed_wight vikt 12 (låg-
  måttlig, ingen separat rare-slot). Alla 7 heath-rektanglarna + cainos/mork_skog/cursed_mire-
  skisserna nedan matchar exakt mot koordinaterna i denna text — **hela B48-zonauktoreringen
  är byggd**, "avstämning pågår" i rubriken ovan är inaktuell. Ingen kod ändrad, ren
  verifiering. (Se även Odöd-pool-densitet-mätningen som använder samma data.)
- **Cursed mire-skiss LÅST (Lucas 2026-07-06):** VIT topp x159-239/y0-18 + östkust
  x226-239/y0-96 = mudcrab · GUL HELA zonen = bog_leech (baslager = fallback) ·
  RÖD mitt-nord x172-222/y2-71 = bog_wraith+witchlight · GRÖN öst-syd x187-239/y40-97 =
  tar_beast **+ mire_lurker** (Claude-beslut på delegation: tunga fysiska träskbrutar
  ihop, sydost = "tunga träsket" mot Yagra) · BLÅ hag-ficka x178-204/y72-89 = bog_hag
  med MÅTTLIG vikt (Lucas-OK; sällsynthet via liten yta, zon-rare-slotten lämnas tom).
  **rotting_fiend flyttar till grave heath** (undead ≠ swamp; Lucas placerar i heath-
  skissen, annars heaths allmänna undead-lager).
- **Mörk skog-skiss LÅST (Lucas 2026-07-06):** VIT nord x84-147/
  y2-40 = boar+wolf+bear · BLÅ väst-mitt x83-133/y24-75 = goblin_raider+cave_bear ·
  GRÖN syd x83-157/y66-99 = thornling+goblin_shaman · GUL öst x122-158/y0-99 =
  treant+broodmother. Fallback = blå (samma mönster som Cainos); strangling_vine =
  låg vikt i grön+gul (istf zon-rare); grön överkant y66 bekräftad.
- **Hollow worg-BESLUT (Lucas 2026-07-06):** blir RARE i heath (låg vikt i B48-modellen;
  cursed_wight behåller rare_encounter-slotten) + BÅDA kompensationerna för holy-kedjan:
  gravewarden_blade läggs på cursed_wights tabell OCH i chest_heath_4 (tier-5-kistan).
  Motiv: melee-spelarens Barrow King-förberedelse får inte bli ~3× långsammare.
  Byggs i B48-batchen.
- **Cainos-skiss LÅST (Lucas 2026-07-06):** tre överlappande
  rekt-områden ritade på ZONE_MAP: GRÖN=stag (västremsa x0-30/y0-72 + hela sydbandet
  y73-99), GUL=undead (nordficka x31-52/y0-28 + östkolumn x52-82/y0-97), BLÅ=generalister
  dog/rat/spider/goblin (mittband x3-80/y30-72 runt START). **Modellbeslut ur skissen:
  överlapp = pool-UNION** (alla träffande områdens viktade pooler summeras — first-match-
  wins ersätts). Fallback utanför områden: blå-poolen (bekräftas). Vikter: Claude utkastar,
  uniform start. **Rotfang-lyan flyttas** till sydvästkanten ~(14,88) (snap-verifieras).
  Övriga zoner ritas av Lucas efter Cainos-låsning.
- **Referenskarta (2026-07-06):** `docs/ZONE_MAP.png` — M-map-schematiken med zon-band,
  alla 17 städer namngivna, pool-städerna markerade (guld), B65-lyorna och START.
  Regenerera: `.venv/bin/python -m rpg_game.tools.worldgen.render_zone_map`.
  **Kart-fynd att ta i designrundan:** pool-städerna ligger inte alltid i "sin" zon —
  burg_54 (Guaredama, cainos-poolens container) ligger fysiskt i grave heath; bindningen
  band→plats är mekaniskt korrekt men mentalt förvirrande. Design låst sedan tidigare:
  viktade heltalspooler + fler sub-regioner authorade inline i core_zone `wild_regions`;
  Claude utkastar rosters, Lucas tunar mot kartan.
- **Vad:** Kunna sätta VILKA fiender som spawnar VAR med finare kornighet än idag, så utbudet
  varierar inom och mellan zoner (inte samma pool överallt). **Not/STEG 0:** B42 la grunden — 4 zon-
  pooler via `wild_regions`→plats-`encounters` (cainos/mork_skog/cursed_mire/grave_heath skiljer sig
  redan). #1 = (a) verifiera in-game att zonerna faktiskt visar olika utbud, (b) finare per-område-
  kontroll (sub-regioner / fler `wild_regions`-band / vikter per fiende i en pool i stället för uniform
  `rng.choice`). **Stor puck** → egen designrunda: authoring-modell (viktade pooler? fler band? per-
  tile-taggar?). **Acceptans:** olika områden ger tydligt olika fiende-mix; authoring datadrivet.

#### B50 — Combat-loggen ska gå att scrolla (som overworld-loggen)  · ✅ **KLAR** (`scroll_log` + hjul/PageUp-Down i battle, clamp mot visuella rader; test)
- **Vad:** Combat-loggen ska ha samma scroll (hjul + PageUp/Down) som overworld-loggen. **Not:** den
  delade `chatlog`-komponenten har redan `_log_scroll`/`visual_lines`; overworld wirar scroll-events
  men battle-shellen gör det troligen inte. STEG 0: jämför scroll-wiring i `pygame_overworld` vs
  `pygame_battle`. **Acceptans:** combat-loggen scrollar bakåt/framåt; test för scroll-clamp.

#### B51 — Buskar egen färg på minimap/(M)-karta  · ✅ **KLAR** (`MAP_BUSH` grön för `_plant`, rock/grave kvar grå; render-verifierad; test)
- **Vad:** Buskar ska ritas i egen färg — skild från både bakgrund OCH sten. **STEG 0:** idag (`9182af0`)
  ritas busk- OCH sten-kluster som samma **grå** prickar på M-kartan (och därmed minimapen som återanvänder
  kompositen). Fix = egen busk-färg (t.ex. dämpad grön) ≠ sten-grå ≠ terräng-grön. **Acceptans:** buskar
  syns i egen färg på M-karta + minimap; test för färgvalet.

#### B52 — Broarna: flippa plank-riktningen  · ✅ **KLAR** (render-tids-rotation 90° av `water_bridge`/`bridge_halfdeck`; headless-verifierad horisontell; test)
- **Vad:** Seam-broarnas plankor går fel håll (uppifrån-ner). Ska flippas så plankorna löper vänster→
  höger (horisontellt) tvärs gångriktningen. **STEG 0:** nuvarande seam-däck = `idx0` "vertical-plank
  railless deck" (`c76ef2b`, Lucas pick B). Fix = välj/rotera plank-tilen till horisontell orientering
  (troligen ett annat deck-idx eller `pygame.transform.rotate`/flippad tile). **Acceptans:** broplankor
  löper horisontellt; broarna renderar snyggt över seam; reachability oförändrad; render-review.

#### B49 — Fiendens level bredvid namnet i combat-skärmen  · ✅ **KLAR** (`enemy_nameplate` = "Namn Lv N" i namnplåten; test)
- **Vad:** Visa motståndarens level intill namnet i combat-vyn (t.ex. "Cave Bear · Lv 5"). **Not:**
  `snapshot`/enemy bär redan `level`; ren presentation i `pygame_battle` (enemy-namn-rendering).
  **Acceptans:** combat-skärmen visar fiendens level vid namnet; render-review.

### Playtest-fynd (2026-07-06, våg 2 + bossar) — DISKUSSION, invänta GO per punkt

*Lucas playtest av våg 1+2+B65. Godkänt utan åtgärd: save-slots, settings-persistens,
chatt-färgerna, flikarna (funktion), alkemi-priser, dödsflödet, boss-balansen ("vann som
L3 efter flera försök + potions" = förberedelse-loopen fungerar — balans ligger kvar).
Nedan: fynd som ska åtgärdas/beslutas. Inget byggs före GO.*

#### B74 — Load-bug: fel stad efter vildmarks-save  · ✅ **KLAR** (nattbatch 2026-07-06: `overworld_tile` persisteras via B59-tabellen, sync_location håller det färskt; load återställer exakt tile med fallback till stads-tilen för legacy/blockerade tiles; 4 tester)
- **Symptom (Lucas):** startade om och spawnade i Guaredama — en stad han aldrig besökt —
  i stället för Hordanita.
- **Rotorsak (BEKRÄFTAD i kod):** i vildmarken sätter `sync_location`
  `current_place_id = wild_region_at(tile)` = zonens pool-container (cainos → `burg_54`
  Guaredama). Autosave efter vildmarksstrid sparar det; `_load_save`/start teleporterar
  till `town_tile_by_place[current_place_id]` — containerstadens FYSISKA tile, som för
  burg_54 ligger i grave heath (samma pool-stads-mismatch som ZONE_MAP avslöjade, se B48).
- **Lösningsförslag:** persistera spelarens **exakta tile** (`overworld_tile`, nytt fält i
  B59-tabellen + migration v2→v3); load återställer till tilen, fallback till town-tile
  för äldre saves. Respawn-vid-död ändras INTE (respawn_place_id-flödet är korrekt).
- **Acceptans:** save i vildmark → load → samma tile; gammal save laddar via fallback;
  död→respawn opåverkad; test för round-trip + migration.

#### B75 — Rundsekvensering i strid  · ✅ **KLAR** (nattbatch: rundan spelas upp per aktör à 0,5 s — `_sequence_steps` delar flata event-listan på resolutionsgränserna, B72-FX triggar per steg, första steget direkt; input+knappar låsta under uppspelning; victory/loot/mode i finalen; skip-klick = setting `combat_skip`, default AV, rad i Settings; 5 tester + flush_sequence för synkrona anropare)
- **Lucas:** aktörerna upplevs slå samtidigt; man kan spamma A genom striden. Önskat:
  se vem som agerar först/sist med delay mellan aktionerna, och ingen ny input förrän
  hela rundan spelats upp. Ger även kroken för framtida spell-animationer.
- **Lösningsförslag:** presentationen spelar upp `CombatTurnResult.action_resolutions`
  **stegvis** (kö, ~400–600 ms per aktion; logg-rader + B72-FX triggas per steg i stället
  för allt på en gång). Knapparna disabled tills kön är tom; klick/Space snabbspolar.
  Kärnan orörd — resolutionerna ligger redan per aktör i initiativordning.
- **BESLUT (Lucas 2026-07-06):** **0,5 s per aktion**; "klicka sig förbi" blir en
  **setting (B70-raden), default AV** — utan settingen är rundan olåst först när
  uppspelningen är klar.
- **Acceptans:** sekventiell uppspelning à 0,5 s; input blockerad under rundan;
  klick-skipp fungerar ENDAST med settingen på; FX/logg synkade per steg; tester för
  kö-tömning + input-lås + settingen.

#### B76 — Battle-layout v2  · ✅ **KLAR** (nattbatch: LOG=vänsterkolumn i full höjd (~2× rader), VITALS ovanför ACTIONS i högerkolumnen; layouttest omskrivet till nya invarianterna; headless-render för Lucas morgon-review)
- **Lucas (skärmdump):** flytta HP/Mana/XP + stats + vapen till HÖGER sida ovanför
  knapparna; combatloggen tar vänstra bredden och blir högre — mer lik overworld-chatten,
  får plats med mer.
- **Förslag:** LOG_PANEL till vänster (~60 % bredd, full HUD-höjd), VITALS+stats staplade
  ovanför ACTIONS till höger. Render-HALT: skiss/screenshot till Lucas före låsning.

#### B77 — Logga NÄR en status appliceras  · ✅ **KLAR** (nattbatch: STEG 0 — apply-raden fanns men var källös och statusar kan överleva från förra striden; nu bär core-raden källan "X is affected by poison (Plague Leap)." och battle färgar amber-mot-dig + röda DoT-ticks; 2 tester)
- **Lucas:** tick-raderna finns ("Hero took 3 poison damage") men själva appliceringen
  syns inte. **STEG 0:** hitta vilka apply-vägar som inte loggar (fiende-on-hit/procs
  misstänks; spelarens apply_status loggar "affected by"). En egen färgad rad per
  applicering: "You were poisoned by Quick Attack!" — källa (action/vapen) ska nämnas.
- **Acceptans:** varje status-applicering på spelaren ger en rad med källa; test.

#### B78 — Människoläsbara skill-/talent-texter  · ✅ **KLAR** (nattbatch: STAT_LABELS/PERCENT_STATS/STATUS_LABELS i talent_text — 'buff +50 damage_dealt_mod' → '+50% damage dealt for 3 rounds'; mitigation/stun/DoT-fraser; skills-hint kortad + _fit_text i båda kolumnrubrikerna = kollisionen borta; 3 tester låser att råa stat-namn aldrig når menyer)
- **Lucas (skärmdump):** "buff +50 damage_dealt_mod for 3 rounds (self); buff +25
  damage_taken_mod ..." är obegriplig även för byggarna.
- **Förslag:** central **formatter** i presentationen (effekt-spec → spelartext, t.ex.
  "Aktiv: +50 % skada men +25 % tagen skada i 3 rundor · 7 mana · kräver Bloodlust")
  + valfritt `description`-override-fält i talents.json/actions.json för specialfall.
  Samma formatter återanvänds av B40:s hover-tooltips (S4/S5) — bygg den FÖRE/i den slicen.
- **Även:** skills-skärmens rubrik-kollision ("Equipped 1/4 …" skriver över "Talent
  points: …") fixas här eller i B40 S-slicen — en av dem äger fixen, inte båda.

#### B79 — Bestiarium: scrollbar roster + sedda-räknare  · ✅ **KLAR** (nattbatch: STEG 0 visade att fönstret redan följer selektionen och Seen X/Y fanns — det som saknades var mushjuls-bläddring + "^/v N more"-indikatorer; båda byggda, 2 tester)
- **Lucas:** listan är låst till de ~14 första; man vill scrolla och få känsla för hur
  många man INTE sett. **Förslag:** hjul-/piltangent-scroll i rostern (markören driver
  visningsfönstret som i shop-listor) + "Sedda X/Y"-rad i panelhuvudet.

#### B80 — Boss-lya efter seger  · ✅ **KLAR** (nattbatch: `_sync_lairs` äger block/avblock genom init/seger/load — fälld boss försvinner HELT, tilen avblockeras, E gör inget; husk-koden borttagen; test låser hela kedjan)
- **BESLUT (Lucas 2026-07-06):** "har inga bra assets, vi tar bara bort den helt sålänge"
  → **(a) fälld boss försvinner helt**. Implementationsnot: lya-tilen måste AVBLOCKERAS
  efter seger (annars osynlig vägg) — blocked-settet justeras vid seger + vid load för
  redan fällda; E på tom tile gör inget ("lair lies silent"-raden utgår). Husk-koden tas
  bort. Kan återbesökas med prop-kvarleva när bättre assets finns.
- ~~Alternativ: (b) kvarleva-prop, (c) mörk siluett.~~

#### B81 — Kistor: minska sprite-storleken 15 %  · ✅ **KLAR** (nattbatch: `CHEST_SCALE=0.85` vid sprite-load; kollision/E oförändrad)
- Ren render-skalning (target-höjd ×0.85 i chest-ritningen); kollision/E-interaktion
  oförändrad. Render-verifieras headless.

#### B83 — Player walk/idle-animationer i overworld  · ✅ **KLAR** (nattbatch 2026-07-06→07)
- **KLAR:** Lucas's huvfigur ersätter gula kvadraten. `build_player_sheet`-verktyget
  color-keyar review-arket (grå bg + r0-r8-etiketter) och auto-klipper cellerna →
  rena `player_walk.png` (8 riktningar × 4 frames, r0..r7 = N NE E SE S SW W NW) +
  `player_idle.png` (front/blink). Runtime: 8-vägs facing ur rörelsevektorn
  (diagonaler används), gång 7,5 fps / idle 4 fps (Lucas-låst), 1,5 tiles hög med
  fötterna på tilen, y-sorterad med byggnader som förut; gul-kvadrat-fallback om
  arken saknas. 5 tester.

#### B82 — Chatt-flikarna får inte skymma vitals  · ✅ **KLAR** (nattbatch: chipsen bor nu INUTI panelen som header-remsa, texten börjar under; en synlig rad spenderas på remsan; test låser chip⊂panel)
- **Lucas (skärmdump):** [All][Combat]-chipsen ligger ovanpå XP-baren. **Regel:**
  HP/Mana/XP ska ALDRIG ockluderas av loggen/chipsen. **Förslag:** rita chipsen INUTI
  loggpanelens övre kant (overlay på panelens första rad) i stället för ovanför panelen;
  alternativt sänk loggpanelen chip-höjden. Render-verifieras mot vitals-rects (test:
  chip-rect ∩ vitals-rect = tom).

*Kopplingar: menytext-glitcharna i Inventory ("Everything you own…"-raden krockar med
kategorirubriken) och Character ("Gold" krockar med "Stats"-headern, truncerad
Damage-rad) läggs som KONKRETA fixlistor på **B40 S2 (inventory) + S4 (character)** —
det är exakt de skärmarna apply-slicarna skriver om; ingen separat punkt.*

### Playtest-tasks (2026-07-10) — nattbatch 2026-07-10→11

#### B84 — Tome-lärd skill oanvändbar i strid (PRIO HÖG)  · ✅ **KLAR** (b8efb4b: gating var AVSEDD; UI-fix — kompakt dimm-skäl + ui.fit på battle-knappar)
- **Vad:** Fighter köper+lär `holy_strike` via tome, equipar den — visas utgråad i strid.
- **STEG 0-fynd (nattbatch):** AVSETT beteende — `holy_strike` har
  `requires_weapon_category: "magic"`; fighterns melee-vapen uppfyller aldrig kravet
  (`combat.blocked_action_reason`, combat.py). Mana räcker (16 ≥ 7). Tome→learn→equip-kedjan
  är korrekt.
- **Avsikt:** Spelaren ska aldrig undra VARFÖR en skill är dimmad, och inte kunna köpa en
  tome utan att se vapenkravet.
- **Acceptans:** dimmad skill i strid visar skälet synligt; tome-shoppen visar vapenkrav
  före köp (kopplar B89); test för fighter+holy_strike-fallet.

#### B85 — Turnerings-DoT hänger kvar mellan motståndare  · ✅ **KLAR** (03a83ef: statuses rensas i intermission)
- **Vad:** DoT/debuffar applicerade i match 1 tickar vidare i match 2.
- **STEG 0-fynd:** `active_statuses` rensas ingenstans i turneringsvägen; bara cooldowns
  (`_begin_encounter`) och HP/mana (`recover_between_matches`) nollställs/fylls.
- **Avsikt:** Varje turneringsmatch startar utan stridsknutna statusar; HP/mana-persistensen
  mellan matcher lämnas EXAKT som idag (design).
- **Acceptans:** DoT applicerad i match 1 tickar inte i match 2; test.

#### B86 — Counter-mekaniken: utredning  · ✅ **UTREDD + rank-no-op FIXAD** (f28e62a; loggrads-/multi-hit-otydligheter → rapport)
- **Vad:** Playtest upplever counter som förvirrande. Utred vilka skills/fiender som har
  den, hur den resolvas (timing, skada, vem träffas) och vad som loggas.
- **Acceptans:** rapport med bedömning + repro; fix endast vid entydig bugg (med test).

#### B87 — Diagonal rörelse normaliseras  · ✅ **KLAR** (4738d74)
- **Vad:** Diagonal input ger full hastighet i båda axlarna (√2× snabbare än kardinal).
- **Avsikt:** Samma fart i alla riktningar; tile-snapp/kollision oförändrad.
- **Acceptans:** hastighetsvektorns längd lika för diagonal och kardinal rörelse; test.

#### B88 — DoT-applicering som egen loggrad  · ✅ **KLAR** (e94fd31)
- **Vad:** När en DoT läggs på någon skrivs en egen typ-färgad rad med källa+typ:
  "Hero was poisoned by Giant Spider's Poison Sting!".
- **Not:** B77 lade status-appliceringar med källa — täpp bara luckan, dubbellogga inte.
- **Acceptans:** varje DoT-applicering ger exakt en rad med källa+typ; test.

#### B89 — Tome-tooltips visar vad skillen GÖR  · ✅ **KLAR** (83b1459; renders docs/nightly/)
- **Vad:** Hover i tome-shoppen, inventoryts consumables-flik och talent-/skilldetaljen
  visar skillens effekt (skada/heal, skadetyp, mana, cooldown, duration, vapenkrav) —
  återanvänder talent detail-textbygget (B78-formattern).
- **Acceptans:** alla tre ytorna visar effekttext; headless-renders till docs/nightly/.

#### B90 — Rank-beskrivningar i absoluta tal  · ✅ **KLAR** (cf06643; renders docs/nightly/)
- **Vad:** Talent detail visar ALLA ranker med beräknade värden ur datan ("Rank 1: 1.4x
  damage, heal 30% · Rank 2: 1.75x …"), aldrig "x1.25 magnitude". Nuvarande rank markerad.
  Gäller aktiva skills OCH passiva noder.
- **Acceptans:** beräknat (round_half_up där tal visas), ej handskrivet; renders till
  docs/nightly/; test.

#### B91 — Sälj miscellaneous i alla butiker  · ✅ **KLAR** (e6cbe37)
- **Vad:** "miscellaneous" i sell-settet för alla butikstyper med sälj-UI; köp-sortiment orört.
- **Acceptans:** test per butikstyp.

#### B92 — Settings-paritet startmeny vs in-game  · ✅ **KLAR** (faf87b9; delad OPTIONS-definition)
- **Vad:** Startmenyns Settings visar SAMMA alternativ som in-game-overlayn, via en delad
  options-definition så ytorna aldrig divergerar igen.
- **Acceptans:** samma options-lista på båda ytorna; renders till docs/nightly/; test.

#### B93 — Smartare fiende-AI kring DoT  · ✅ **KLAR** (d9c1844)
- **Vad:** Om målet redan har en aktiv DoT väljer AI:n en annan handling om någon finns.
- **Acceptans:** deterministiskt, seedat test; inga andra AI-ändringar.

#### B94 — DoT-styrka upp  · ✅ **KLAR** (d8cda25; spell-DoTs trimmade IN i bandet, flats/fiender höjda — se nattrapport)
- **Vad:** DoT:ars totala skada över durationen ska ligga ~1.3–1.6× jämförbar direktskada
  för samma kostnad; en enskild tick ej under ~4–6 % av on-level standardfiendes HP.
  Symmetriskt (spelar- och fiende-DoTs). Justeras i data, sim-verifieras.
- **Acceptans:** sim-matris före/efter; HALT om en DoT ensam flippar en matchup >30 pp.

#### B95 — Talangparitet inom träden  · ✅ **KLAR** (e71b549; sentinel/duelist-rest i rapporten)
- **Vad:** Frenzy dominerar strikt över Precision/Sunder-vägen. Gå igenom ALLA klassers träd
  och åtgärda strikt dominerade val — endast skills-/talangdata (magnitud, kostnad, cooldown,
  sekundäreffekter), inte fiender/basstats/trädstruktur. Hellre nisch än sifferkapplöpning.
- **Acceptans:** sim gren-A vs gren-B per klass, ingen strikt dominans kvar; ändringslista
  med motiveringar i rapporten.

### Playtest-tasks (2026-07-11) — dagbatch 2026-07-11

#### B96 — Reflect-polish: loggrad namnger källan + multi-hit-utredning  · ✅ **KLAR** ((a) 56b08b7; (b) beslut kväll 2026-07-11)
- **Beslut B96b (Lucas, kväll 2026-07-11): BEHÅLL per-delträff-reflect.** Dagbatchens
  sim-utredning (per-delträff vs en-gång-per-attack) motiverade ingen regeländring:
  per-delträff är det etablerade, testlåsta beteendet och gör reflect till en meningsfull
  motvikt mot multi-hit-kit. Detaljmatrisen finns i dagbatchrapporten (extern).
- **B96b-siffror (för spårbarhet):** med realistisk mana var winrate-skillnaden mellan
  per-delträff och en-gång-per-attack **0,0 pp**; först vid TVINGAD reflect/multi-hit-
  överlapp syntes skillnad: fighter 21 → 100 % (+79 pp), rogue +8,5 pp. Beslut:
  **BEHÅLL per-delträff.**
- **Vad:** (a) Reflect-loggraden namnger sin källa: "Hero's Counter reflected 6 damage to
  Dire Wolf." i st. f. generiska "X reflected N damage to Y." — härlett ur statusens
  ursprungs-skill, ej hårdkodat. (b) Multi-hit-reflect: ÄNDRA INTE beteendet — sim (N≥200)
  nuvarande per-delträff vs hypotetiskt en-gång-per-attack, rapportera winrate-skillnaden
  för matchups där reflects förekommer. HALT: rapport + rekommendation till Lucas.
- **Not:** Följer B86-utredningens otydligheter (loggrad + multi-hit).
- **Acceptans:** loggrad med källnamn, test; sim-rapport för multi-hit-frågan.

#### B97 — Wight/skeleton-kitflytt  · ⏸ **FLYTTAD till progressionsrundan** (beslut kväll 2026-07-11)
- **Beslut (Lucas, kväll 2026-07-11): Variant B LÅST** — cursed_wight får frostfire +
  wight_curse + power enligt 3-kit-normen; skeleton_warrior får `shield_slam` som fysisk
  bruiser. Men exekveras FÖRST i progressionsrundan, gated mot dess NYA målkurvor —
  ingenting byggs innan målkurvorna är beslutade. Se posten under "Progressionsrundan".

#### B98 — Sprite-nedskalningskvalitet + tier-map-täckning  · ✅ **KLAR** (5d66b90)
- **Vad:** enemy_sprite använder smoothscale (eller stegvis halvering) när nedskalnings-
  faktorn överstiger ~2x; nearest behålls för uppskalning (pixel-art förblir skarp). Lägg
  cursed_wight, skeleton_warrior och övriga omappade fiender i ENEMY_SPRITE_TIER — förslag
  large för L8+-eliter men välj per sprite-proportion, rapportera valen.
- **Acceptans:** före/efter-renders (minst cursed_wight) i docs/nightly/; tester.

#### B99 — Tangentbordsnavigering i menyer  · 🟢 **S1 KLAR** (4730a2f) · **S2 GO** (Lucas, kväll 2026-07-11 — körs i kvällsbatchen)
- **Vad:** Fokus-modell som DELAD mekanism i ui.py (B40-menyspecens anda): pil upp/ner
  flyttar fokus inom sektion, vänster/höger (eller Tab) hoppar mellan sektioner/kolumner,
  Enter aktiverar, Esc backar som idag. Musen fortsätter fungera parallellt; fokusmarkering
  återanvänder hover-stilen. Lucas primärfall: slippa musen.
- **Slices:** (1) inventory + Skills & Talents-skärmen (HALT för Lucas-review efteråt);
  (2) övriga menyer efter godkänd S1.
- **Acceptans:** tester på fokusflytt/aktivering; renders till docs/nightly/.

#### B100 — Loot-flik i loggen  · ✅ **KLAR** (2cecf62)
- **Vad:** Tredje tabb "Loot" bredvid All/Combat (B44-strukturen). Varje item-/guldförvärv
  loggas med källa: "Looted Greatsword from Cave Bear." / "Opened chest: 2x HP Potion." /
  "Bought Tome: Sun Flare." Käll-metadata följer loot-flödet i core; presentationen färgar
  per källtyp. Bara framåtriktat (ingen retroaktiv historik).
- **STEG 0:** mät ALLA vägar där items/guld når spelaren (enemy drop, chest, shop-köp,
  event, tome-studie, turneringsbelöning, ev. fler).
- **Acceptans:** test per källväg; renders.

#### B101 — Broarnas kanttiling  · ✅ **KLAR + GODKÄND av Lucas** (c34467c; kväll 2026-07-11 — behålls)
- **Vad:** Bro-däcket får vänsterkant-/mitt-/högerkant-varianter: mitt-tilen genereras ur
  befintlig tile med räckespixlarna borttagna via deterministisk transform (parametrar
  dokumenteras); kantvarianter behåller ETT räcke vardera. Variantval efter grannskap
  (render-tid eller tile-data — den väg som inte rör kartformatet).
- **Acceptans:** före/efter-renders av bron i skärmdumpens läge till docs/nightly/ för
  Lucas review (revert billig om utseendet underkänns).

#### B102 — Progression-audit (MÄT-ONLY)  · ✅ **KLAR** (1eef733; rapport docs/nightly/b102_report.md — designrunda hos Lucas)
- **Vad:** Underlag till Lucas designrunda om svårighetskurvan — INGA data-/konstant-
  ändringar. (a) Spelarkurva per klass L1–L12: HP + förväntad DPS med default- och
  realistiskt optimerad loadout; dekomponera L3–4-spiken (vapen-tier/talent-ranks/basstats).
  (b) Fiendekurva per zon: HP, flat damage, SKILL-magnituder vid zonens levelband — mät
  explicit om skill-effekter skalar med rullad level (nyckelfrågan), efter
  ENEMY_HP_MULTIPLIER 2.0 + HP_GROWTH 0.20 + DAMAGE_GROWTH 0.12. (c) Möteskvalitet per zon
  vid avsedd spelarlevel: TTK, DTK, skada tagen per strid som % av spelar-HP; inkludera
  slutmatrisens kända outliers (tank-skadegolv/timeouts, 100 %-celler, cleric vs cave_bear,
  mage vs shade). (d) Rapport: matplotlib-PNG:er i docs/nightly/ + 3–5 strukturproblem med
  FÖRSLAG på målkurvor. Förslag — besluten är Lucas.
- **Acceptans:** kurvor + problemlista + målkurveförslag; commit endast för sim-/plottverktyg.

#### B106 — Meny-textstil  ⭐ · 🟢 **AKTIV** (mockup GODKÄND av Lucas kväll 2026-07-11 — körs i kvällsbatchen)
- **Vad:** Textstilregler som DELADE hjälpare i ui.py, applicerade på alla menyer:
  inga parentes-hjälptexter (hotkeys som badge-brickor i egen kolumn, kostnader
  högerställda), Settings "Combat FX" → "Combat animations" + Controls-tabell i två
  kolumner, trunkering + tooltip vid platsbrist (text får aldrig rinna utanför sin yta),
  statusprefix [LEARNED]/[LOCKED]/[CAN LEARN] → kompakta markörer (punkt/bock + dimm).
- **Acceptans:** före/efter-renders av varje berörd skärm i docs/nightly/ — visuell accept.

#### Parguillas-kulissen  ⭐ designbärande · ✅ **BESLUT C (Lucas, kväll 2026-07-11) — byggs i nattbatch 2026-07-11→12**
- **Vad:** Designval för Parguillas: (A) shrine får en funktion / (B) dörrlös kuliss /
  (C) shrine får kyrkans respawn-funktion. Lucas väljer väg innan byggarbete.
- **Beslut: alternativ C.** Shrine tas ur COSMETIC_BUILDINGS, får respawn-relocation-
  funktionen (BUILDING_FUNCTION shrine→relocate_respawn), titel "Shrine", dörr/cobble via
  befintligt template-maskineri.

### Playtest-tasks (2026-07-11 kväll) — kvällsbatch 2026-07-11

#### B103 — Passiv-/effekttext-rendering (beräknad, mänsklig text för ALLA effekt-typer)
- **Vad:** Playtest-fynd: "bonus damage under a condition" (Combustion) och råa
  identifierare som "elemental_attack_mod" (Flametongue/Rimeblade) når skärmen. Varje
  effekt-typ i actions-/talents-datan får en renderare som producerar BERÄKNAD mänsklig
  text ur datans fält — Combustion: "Fire damage +20% vs burning targets" (rank-skalat),
  Flametongue: "+4 fire damage on attacks" per rank. Rank-raderna (B90) delar renderaren.
- **Acceptans:** guard-test som failar när en effekt-typ i datan saknar renderare (luckan
  kan aldrig återuppstå); renders av tidigare trasiga tooltips i docs/nightly/.

#### B104 — Encounter-cooldown efter strid (rörelsetid, inte väggklocka)
- **Vad:** Efter avslutad strid krävs 1 sekund ACKUMULERAD RÖRELSETID (stillastående
  räknar inte ner) innan nytt encounter kan trigga. Läggs i core (testbar), inte i skalet.
  Gäller även events (B67 delar encounter-slotten).
- **Acceptans:** seedat test — steg under cooldown ger aldrig encounter; första rollen
  efter cooldown beter sig som idag.

#### B105 — Talanglistans gruppering per gren (ENDAST presentation)
- **Vad:** Skills & Talents-listan grupperas per gren med grenrubrik (Pyromancer /
  Cryomancer / …), noder i order-följd. Tvär-passiver som är egna en-nods-grenar
  (flametongue/rimeblade-mönstret) visas UNDER sin krävda grens sektion med markering
  ("↳ requires Frostbolt") — inte som egna kolumner/sektioner. Char creation-trädet får
  samma logik. Träddatan rörs INTE.
- **Acceptans:** renders före/efter (mage = värsta fallet) i docs/nightly/; tester.

#### B107 — Battle feel (Battle Screen Mock = spec) · ✅ **S1 KLAR + GODKÄND** (98dde1c, Lucas GO 2026-07-12) · S2 väntar
- **Vad:** Battle-scenens presentation lyfts enligt Lucas godkända design-export
  ("Battle Screen Mock"): (a) hjälte-idle-sprite (hero_idle_right_native.png, 4 frames
  20×29, loop A-B-C-B 0,9 s) ersätter placeholder-boxen; (b) attack-koreografi för
  spelarens skadeactions i tre viktklasser (quick/normal/power) med dash, FX-ark över
  fienden (fx_quick/fx_normal/fx_power.png), fiende-skak + brightness-flash, viktklassade
  stigande skadesiffror, dödsfade; (c) allt bakom "Combat animations"-togglen, skip-klick
  snabbspolar; mockens hotkey-brackets som B106-badges.
- **Scope:** ENDAST presentation i pygame_battle — noll rng-draws ur motorströmmen.
  Fiendens attacker och skill-specifika FX = S2.
- **Slices:** (1) hero idle + spelar-attack-koreografi (render-HALT: GIF:er till
  docs/nightly/); (2) fiende-koreografi + skill-specifika FX.
- **Acceptans:** headless GIF-renders quick/normal/power + dödsfade; determinismtest;
  mappningstabell actions→viktklass i rapporten.
- **S2-asset-status (2026-07-12 kväll):** 32 animerade fiende-idle-sheets committade i
  `assets/sprites/generated/enemies/animated/*_idle_sheet.png` (b72bf66). De är bara
  assets — S2 måste slice:a varje sheet i frames (frame-layout ospecificerad, kräver
  Lucas-input) och köra dem som fiende-idle i pygame_battle.
- **⛔ BEROENDE — sprite-mappflytt ej pushad:** kvällsbatchens enhet 1 (peka om `SPRITE_DIR`
  till `generated/enemies/`) HALTades: de spårade fiende-sprites ligger fortfarande i
  `generated/*.png`; `enemies/*.png` är bara otrackade lokala dubbletter. **Lucas måste
  committa+pusha omorganisationen först**, sedan kan SPRITE_DIR pekas om + ~10 tester
  uppdateras.

### Progressionsrundan (efter B102-audit — Lucas beslutar målkurvor först)

#### Progression: delta-modellen  ⭐ designbärande · **LÅST (Lucas, kväll 2026-07-11)**
- **Gameloop-målbild:** trygghetspunkt → utflykt → hem starkare → längre utflykt.
- **Svårighet = DELTA-KURVA:** svårigheten definieras av (spelarlevel − fiendelevel),
  inte av zonkonstanter. Zonernas roll är GEOGRAFISK: geografin ger zongradienten
  (levelband stiger med avstånd från trygghetspunkter), deltat ger balansen.
- **Målgates (MEDIAN-loadout, N≥200):** Δ0 neutral matchup 70–90 % winrate / TTK 3–6
  rundor / kostnad 20–35 % HP · Δ0 dålig matchup golv 25–30 % · Δ+3 ≥95 % men TTK ≥2 ·
  Δ−2 = 35–60 % · Δ−4 ≤15 % · OPTIMIZED ≤ +15 pp över median, DEFAULT ≥ −15 pp under ·
  Cainos-undantag (nybörjarzon): Δ0 85–100 %, TTK ≥2 · inga timeout-celler.
- **Tank:** får basdamage-tillväxt per level (egen skadeväg); mål L12-DPS-gap mot
  fighter/hunter ≤2× (från 4–5×). Tanken förblir seg — blir inte fighter.
- **Dödsstraffet RÖRS INTE** i denna runda.
- **Loadout-policys i sim:** DEFAULT (startkit) / MEDIAN (halva guldet spenderat,
  girig-men-icke-optimal talentspend, inga tomes) / OPTIMIZED (B102-policyn) — gates
  uttrycks mot MEDIAN.

#### Klassidentitetsmodellen  ⭐ designbärande · **LÅST (Lucas, 2026-07-12)**
- **Arketyper:** fighter/hunter = **glass cannon** (hög skada, LÅG HP & armor);
  rogue = **utility + skada** (skadan BOOSTAS); tank/cleric = **defensiva** av olika
  natur (rörs INTE defensivt). Inom glass cannon-trion differentieras skörheten:
  någon får lite mer HP men mindre armor, vice versa — ingen får bådadera.
- **Skada:** fighter/hunter trimmas NÅGOT (mål: spridning ~2×, inte paritet); rogue
  UPP något; cleric DPS-lyfts INTE (defensiv identitet, korridoren absorberar).
- **Arketyp-korridorer ersätter gemensam TTK-gate:** glass cannon TTK 3–5, rogue 4–6,
  tank/cleric 5–8. Kostnadskorridor 20–35 % HP vid Δ0 för alla; defensiva får ligga
  10–25 % (deras kostnad är tid/mana).
- **HP_GROWTH_PER_LEVEL** får flyttas 0.20 → inom **0.28–0.38** (den saknade
  Δ-lutningshävstången från nattens HALT).
- **Känsla > perfektion:** cross-class (se nedan) river ändå upp balansen framöver —
  residual-fails dokumenteras hellre än jagas.
- **Slutgates v2 (arketyp-korridorer, MEDIAN, N≥200):** Δ0 neutral 70–90 % · Δ0 dålig
  matchup ≥25 % · Δ+3 ≥95 % TTK ≥2 · Δ−2 35–60 % · Δ−4 ≤15 % (glass cannons FÅR ≤10 —
  skörhet är designen) · kostnadskorridorer per arketyp · inga timeouts.

#### Cross-class / secondary class  ⭐ designbärande · **FRAMTIDA (parkerad, egen designrunda)**
- **Vad:** En andraklass ovanpå primärklassen (talang-/skill-blandning över klassgränsen).
- **Konsekvens NU:** motiverar "känsla över perfektion" i klassidentitetspasset —
  cross-class kommer riva upp den finjusterade balansen ändå, så residualer i delta-
  matrisen dokumenteras hellre än jagas till noll fails. Egen designrunda innan bygge.

#### B109 — Fiende-basskade-passet (Δ0-gapet)  · ⛔ **HALT (2026-07-12 kväll)** · ⭐ **RESIDUAL ACCEPTERAD (2026-07-12 natt): strukturell, maskin-taggad, omvärderas vid cross-class/mage-lyft**
- **Mål (från kvällsbatchen):** höj fiende-basskada roster-brett så on-level-striden (Δ0)
  landar i arketyp-korridoren (70–90 % vinst) i stället för ~100 %.
- **STEG 0-mätning (`rpg_game/tools/roster_delta0.py`, committad):** vid Δ0 är den per-klass
  MEDIANA vinsten fastlåst hög av de TÅLIGA klasserna (tank 219 HP, fighter, cleric-heal
  vinner on-level nästan oavsett fiende-skada), medan golvet ALLTID är **mage** (låg sim-
  single-target-DPS + glass-cannon-HP; mage 0 % finns REDAN vid nuvarande baser, t.ex.
  mire_lurker). Cost-mätningen visar dessutom att 2/3 av rostern REDAN kostar 20–75 % HP
  vid Δ0 — bara ~10 äkta steamrolls kostar <20 %.
- **Tre sim-varianter (N=150–200) bevisar taket:** (a) aggressiv höjning → Δ−4 stängs men
  **cainos glider ur mild-korridoren** (HALT-villkor) + frail-klasser kraschar; (b) mild
  höjning → cainos bevaras men Δ−2 regrerar (19→23 fails) och Δ0-medianen rör sig inte;
  (c) riktat pass på bara steamrolls → 94/172, **fortfarande sämre än v2 (92/172)**. Varje
  knapp byter en gate mot en annan; ingen bas-skadeändring förbättrar totalen.
- **Slutsats:** Δ0-medianen (70–90 %) är ouppnåelig via fiende-skada så länge rostern
  spänner tank(219 HP)↔mage(85 HP, låg DPS). Δ0-stängning är **klass-sido-arbete**, inte
  ett fiende-pass. Inget data committades (ingen gissning som regrerar gaten).
- **Rekommendation till Lucas (välj väg):** (1) lyft mage (sim- ELLER spel-DPS/överlevnad)
  så den slutar vara <25 %-golvet — då tål rostern en skadehöjning utan att auto-förlora
  mage; ELLER (2) byt Δ0-gaten från delad median-vinst till **per-arketyp** vinst + gate på
  KOSTNAD (tåliga klasser SKA vinna on-level — deras identitet — men betala tid/HP); ELLER
  (3) acceptera att cross-class ändå river upp det och lämna Δ0 som dokumenterad residual.
  När vägen är vald kan fiende-baser trimmas mot den nya gaten med samma verktyg.
- **⭐ BESLUT (Lucas, 2026-07-12 natt): väg (3) — acceptera Δ0 som strukturell residual.**
  Δ0-medianvinst-gaten lämnas som den är; vi vet varför den failar (tåliga klasser
  dominerar medianen + förexisterande mage-golv, kostnaden redan hög 20–75 % HP), och
  cross-class river ändå upp balansen. Ingen `enemies.json`- eller konstant-ändring.
  De kända Δ0-cellerna + de närbesläktade Δ−2-cellerna (samma basstat-tak) — samt de
  övriga progressionspass-residualerna (Δ+3 fast-kills, Δ−4-tak, default-kit-gap) — är nu
  **maskin-taggade** i `rpg_game/tools/delta_curve.py` (`KNOWN_RESIDUAL_CHECKS`, fryst hela
  baslinjen 92/172, identisk vid N=120 och N=200). Sim-rapporten skriver
  "X kända residualer + Y NYA fails" så en **framtida regression syns som en ny fail** i
  stället för att drunkna i de 92. Omvärderas när mage lyfts eller cross-class landar;
  regenerera baslinjen och frys om efter en avsiktlig balansändring. Mätning:
  `rpg_game/tools/roster_delta0.py`. Låst av `tests/test_delta_residuals.py`.

#### B108 — Fysiska dörrar för apothecary/stable  · 🟢 **AKTIV** (2026-07-12)
- **STEG 0-fynd (nattbatch):** apothecary/stable står kvar i `COSMETIC_BUILDINGS` trots
  `BUILDING_FUNCTION`-poster (brew/fast_travel) — de saknar fysiska dörr-tiles i
  `door_index` och nås bara via `do_action`. Ser ut som en B8 2b-rest.
- **Vad:** samma prejudikat som shrine/church C (36e20bc): ut ur `COSMETIC_BUILDINGS`,
  fysiska dörr-tiles via template-maskineriet, menyerna nås via dörr som allt annat.
- **Acceptans:** render av en stad med båda dörrarna; tester.

#### B97 — Wight/skeleton-kitflytt (Variant B LÅST, exekveras FÖRST i rundan)
- **Beslut (Lucas, kväll 2026-07-11): Variant B** — cursed_wight får frostfire_strike +
  wight_curse + power enligt 3-kit-normen; skeleton_warrior får `shield_slam` som FYSISK
  bruiser (svärd+sköld-art). Ingen ny action authoras.
- **Gating:** byggs som FÖRSTA punkt i progressionsrundan, sim-verifierad mot rundans NYA
  målkurvor (inte dagens ±10 pp-band). Ingenting byggs innan målkurvorna är beslutade.
- **Acceptans:** sim N≥200 per fiende före/efter mot de nya målkurvorna; bestiary-text
  uppdaterad vid behov; tester.

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

#### B12 — Encounter-skalning: faror mot avstånd + nivåtak nära start  · ✅ **KLART (bägge halvor)** — se arkiv
- **Rate-halvan KLAR:** se arkiv-posten **B12-rate** (`dd66afc`) — heatmap 0 på stad+granne,
  ramp över 3 tiles, ×0.6 path-tiles.
- **Nivåtak-halvan medvetet PARKERAD (Lucas-beslut, dokumenterat i samma arkivpost):**
  fasta regionala fara-band behålls — L5 nära start är MENINGEN, inte world-scaling.
  Denna aktiva post låg kvar som "höjd prioritet" efter att båda halvorna redan var
  avgjorda; städat ikväll så B12 inte STEG-0:as igen av misstag.
- **Vad (bevarad, historisk):** Stad + närmsta rutor säkra; encounter-rate stiger med
  avstånd; path-tiles sänker raten. Tillägg från playtest: ett tak på fiendenivå nära
  startområdet — inte bara lägre rate, utan svagare fiender nära start.

#### B8 — Städerna som funktionsdrivna kluster  ⭐ designbärande  · 🟢 **Slice 2b KLAR** (per-stad butik + apothecary/stable-dörrar + snabbresa) · Lucas-tuning av roster/priser kvar
- **Slice 2a KLAR** (`78cbce0`/`e74ffd2`/`17f6207`, Lucas-godkänd render): kluster generaliserat
  till ALLA 17 städer, tier-styrt (capital|city|town|village) läst ur core_zone (`tier`/`shop_category`/
  `prop` = PROVISORISK seed för 2b). `town_cluster.CLUSTER_TEMPLATES` + `resolve_template()` lägger ut
  mallarna; capital byte-identisk. Varje stad har exakt EN rest-dörr (inn / cottage i by); town_hall
  endast där turnering finns (burg_5/67/146/121); kuliss-byggnader renderar men saknar dörr/cobble.
  Sprites nycklade på (id,facing). B32 encounters=0 på alla kluster; reachability + ingen-footprint-i-vatten
  verifierad på riktiga kollisionen för alla 17. 637 tester gröna.
- **2b KLAR (våg 3):** (1) **Per-stad butiker:** alla 13 butiksstäder har författade sortiment
  (default-fyran borta) — kategori-städer säljer BARA sin kategori, capital+city allt; vapen i butik =
  endast common-rarity, inga greater pots, ingen t5-gear (bossbelöningar); capital orörd.
  (2) **Gear-priser tier-skalade** (`GEAR_TIER_VALUE` 20/55/140/280/480 + rarity): gamla platta
  26–72g gav bort t3–t5; nu ≈2–3 fights i hemzonen per del. **Omkörd B62-sim (N=300):** netto
  11,6 → 57,8 → 65,3 → 116,0 g/fight (kurvan intakt, sälj-inflödet +2–8g av gear-värdena).
  (3) **Apothecary-dörren:** BUILDING_FUNCTION apothecary→brew; interim-knappen i general-shopen
  BORTA (B68-flytten klar). (4) **Stable→snabbresa:** coach-nät mellan UPPTÄCKTA stall (fog-gated);
  pris = core-regel `progression.fast_travel_cost(dist, avresezon)` ankrad i B62-netton
  (FAST_TRAVEL_ZONE_NET 11/56/59/108, grannhopp ≈ 2 fights, "dyrare söderut" via avresezonen);
  `engine.fast_travel` äger guld+platsbyte; `economy_zone_for_tile` (heath = y-band 4).
  (5) **Prop-roster v4 (mitt UTKAST — Lucas tunar):** torn 117/67/105 (+146 dött fält) för
  tome/armour-täckning N+S; stall 235 (N-skog)/200 (NE "Estables")/54 (V)/53 (SE); apotek 219
  (mire)/149 (heath-city). Shrines 293/320 orörda (B22).
- **Tuning-noter till Lucas (2b-restlista):** (a) cainos/skog saknar apotek och cainos saknar
  stall — slot-bristen är verklig (11 prop-slots, 5 tjänstefamiljer); tier-uppgradering av t.ex.
  burg_235→town skulle ge fler slots. (b) burg_121 (Alherralba, by + turnering) har butiksdata men
  INGEN butiksdörr (village-@flex äts av town_hall) — förslag: tier→town. (c) capital-mallen är
  låst byte-identisk → inget stall i startstaden; närmsta nod = Jinosa (106,44).
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

#### B11 — Karta + fog of war  · ✅ **Slice 1 KLAR** (`01ee74d`/`9ec6f0c`) · minimap = Slice 2 (öppen, se nedan)
- **Vad:** Karta + fog of war för obesökta platser. **Avsikt:** orientering; utforskande
  belönas. **Not:** besökt-tracking (sparas) delas med B12. **Acceptans:** besökt-data
  persisterar; kart-vy; obesökt döljs, återbesök avtäcker; test.
- **KLAR (Slice 1):** fog-of-war-state (avtäck vid gång + persistens) + fullskärms-kart-overlay
  (M) med fog, pins och you-are-here. Kvar = **minimap (Slice 2)**, se "B11 (tillägg)" nedan.

#### B2 — Broarna  · ✅ **LÖST** (`b56f195`/`c76ef2b`)
- Broarna omarbetade: seam-övergångar = en bred railless-däck (Lucas pick B, idx0), lake/river-broar
  borttagna. Tidigare plank-skin + hav-verifiering (`45401b0`). Kvar (valfri polish): gräs-ändkapslar.

### Strid, progression & ekonomi

#### B24 — Balans-pass från playtest (fiende-abilities, skadetyp, drop-rate)  · ✅ **KLAR** (`59e2cfb` + flagga `7f083ec`)
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

#### Odöd-pool-densitet  · ✅ **MÄTT (nattbatch 2026-07-09) — ingen ändring**
- **Mätmetod:** grid-samplade `pool_at()` (B48-modellen) var 2:a tile över hela 240×208-
  kartan, viktad andel av `undead`-taggade fiender (traits, `enemies.json`) per
  pool-region (`burg_54`=cainos, `burg_146`=mork_skog, `burg_320`=cursed_mire,
  `burg_121`=grave_heath). Engångsskript, ej incheckat (mätning, ingen produktionskod).
- **Resultat:** cainos 27,0 % · mork_skog 0,0 % · cursed_mire 13,8 % · **grave_heath 80,6 %**.
- **Tolkning:** den gamla ~⅓-siffran (mätt före B48) är inaktuell — B48:s finkorniga
  per-område-auktorering har redan spritt om odöd-tätheten: mork_skog har nu INGEN odöd
  (rent beast/plant), cursed_mire är utspädd till 13,8 % (bara `bog_wraith`). Grave heaths
  80,6 % är HÖG men **avsiktlig tematik**, låst av Lucas i B48:s heath-skiss (zonen heter
  "grave heath", huserar Barrow King) — och `gravewarden_blade` är medvetet placerad DÄR
  (cursed_wights tabell + chest_heath_4) som melee-spelarens Barrow King-förberedelse,
  inte ett läckage. B24:s holy-nerf (2.0→1.5×) + `rare_tier_cap` (tier-5 ej droppbar <L5)
  gäller fortfarande ovanpå. **Ingen ytterligare åtgärd** — stänger frågan mät-only, i
  linje med B25:s presedens.

#### B35 — Level-up: välj main-stat (Spår A)  · ✅ **KLAR** (`c600efc`)
- Vid varje level-up väljer spelaren EN main-stat av **{HP, Mana, Damage, Crit}** (Speed
  slopas som val). **Universellt + FLAT** — ingen nivå-scaling, ingen per-klass-skillnad.
- Varje level får ALLA stats sin baslinje; den valda main-staten får sitt main-värde i st.:
  - HP: bas **+2**, main **+8**   ·   Mana: bas **+2**, main **+8**
  - Damage: bas **+1**, main **+4**   ·   Crit: bas **+1**, main **+4**
  - Ex: HP main → HP+8, Mana+2, Crit+1, Damage+1.  Crit main → Crit+4, HP+2, Mana+2, Damage+1.
- **Ersätter** de fasta HP/dmg-ökningarna. **Modal-UI** vid level-up (4 val).
- **Absorberar B25:** mage kan välja Mana (+8/lvl) → löser den tidiga mana-bristen själv.

#### B36 — Talent-ranger (upp till 3 steg)  · ✅ **KLAR** (`1d7322a`/`7a83fdc`/`8c9dd3b`/`d458281`)
- **KLAR:** `max_rank` per talent-nod i data (24 active / 17 passiva skalbara / 10 binära);
  `talent_ranks`-state + learn-or-upgrade-allokering (1 point/steg); passiv rang-skalning +
  skill-magnitud/duration skalas av rang i combat (`rank_mult`); talents-UI visar rang + Learn/
  Upgrade. HALT-fyndet nedan löstes genom att skala de skalbara mekanikerna per rang och lämna de
  binära noderna som 1-stegs.
- Talents kan rankas upp i **upp till 3 steg**; **modest** ökning per rang (t.ex.
  1.6× → 1.8× → 2.0× damage). Mindre behov av många skills/talents — investera klokt i få.
- Talent-points spenderas på ranger; skills/talents-overlay (K) visar rang + tillåter upprankning.
- **HALT-fynd (STEG 0, bevarad kontext):** talangmodellen matchar INTE "1.6×→2.0× damage"-exemplet. 33/51 noder är
  **active** (ger en skill) utan power-skalnings-väg; 18 passiva spänner över 6 effekt-mekaniker
  (stat_bonus, conditional_damage_mod-multiplikatorer, elemental_attack_mod, immunity,
  applied_status_mod). Rankning kräver (a) per-rang-skala för var och en av dessa + (b) en HELT NY
  per-spelare skill-power-mekanik för de 33 active-noderna = klass-bred ombalansering. **Designval
  för Lucas:** vilka effekt-typer rankas, per-rang-skalning, och hur active/skill-talanger skalar.

#### B37 — Item-damage-rebalans + item-upgrades (Spår A / #2)  · ✅ **Slice 1 + Slice 2 KLARA**
- **Slice 2 KLAR** (`b1ba224`/`c8c09b6`/`ffbc53c`/`eeef40c`/`403c096` + stationer `754ca7b`/`83a714e`):
  levererades som ett **item-upgrade-recept-system**, INTE den ursprungliga "epic-rarity + socket".
  Item-kind `junk`→`miscellaneous`; rarity-graderade material + enemy-drops; upgrade-core (recept,
  deltas, exclusions, persistens i `upgrades.json`); stationer (blacksmith=vapen, mage tower=rustning);
  upgrade-UI med *Upgradable*-tagg. B24-flaggan (låg-level rare-cap) löstes separat (`7f083ec`).
  - **Kvar (design-pivot, ej gissat):** den specifika **epic-rarity `consecrated_maul`** är INTE gjord
    (upgrades täcker steel_greatsword/worgfang/iron_cuirass). Om epic-rarity fortfarande önskas = egen
    liten runda. De 8 material-fillers-vapnens **placering** (butiker/loot) = world-pass, fortf. kvar.
- **Slice 1 KLAR** (`ba5af71`/`2f7733b`/`ad5cf9d`/`05a83b8`): tier HÄRLEDS ur damage (ceil/5, ingen
  hand-satt tier), required_level FRIKOPPLAD (t0-2→L1, t3→L3, t4→L5, t5→L8, t6→L11, t7+→L14).
  worn_shortsword 2→0 (osåld), venomfang→poison(25), worgfang→25; 8 materialstege-fillers
  (iron/steel-svärd, willow/maple/yew-bågar, adept_wand) → granulär tidig stege 0→3→5→8→9→13→14.
  Weapon-aware sim tillagd (`best_weapon_for`).
  - **Sim-resultat (200 trials, best-weapon+skills+B35+trait-matris, L1→10):** jämn ~100% on-level,
    inga spiky-väggar kvar (gamla L3 22-51% / L7 0% borta). Vapenstege fighter L6 vs treant:
    steg ≤4pp (94→95→95→95→96→100), inga 3×-hopp. Mage-med-mana **livsduglig** (L3 vs cave_bear:
    attack-only 98%, skills 100% — mot gamla 0%). Holy mot undead: cleric smite dödar undead på
    **3 rundor** men 0% mot neutral cave_bear utan dmg-vapen → stark specialist, ej trivialiserande
    (alla 6 klasser slår undead on-level → ej holy-gated). **Ingen data-nudge behövdes.**
  - **Kvar (flaggat, ej gissat):** de 8 fillers är ännu **ej åtkomliga** (ej i butiker/loot) —
    placering per ort/drop = world-design, görs i en placerings-pass. *(Slice 2 landade som
    upgrade-system — se B37-headern ovan; epic-rarity `consecrated_maul` blev EJ gjord.)*

##### B37 (ursprunglig HALT-kontext — bevarad)  · ⚠️

- **Sänk damage-nivån rejält** och gör tidig kurva **granulär**: dagens vapen-uppgraderingar
  ger ~3× direkt (hårt före, trivialt efter). Behåll befintliga items men **+2 tiers på alla**,
  och lägg **nya t1–2-fillers** (små, mindre intressanta uppgraderingar för L1–4).
- `consecrated_maul` → **egen epic-rarity + stats som matchar namnet** (topp-belöning, ej L3-drop).
- **Konsekvens krävs överallt:** droptables, `rare_tier_cap`, **differentierade butikers**
  inventarier, turnerings-belöningar — alla refererar tiers.
- **Sim:as MOT B35:s nya spelar-kurva** (kombinerad, alla 6 klasser, representativa builds, L1→7).
  B35 + B36 + B37 är EN power-curve — verifieras ihop.
- **STEG 0-mätning (baseline, B35-tillväxt × NUVARANDE items, attack-only):** kurvan är SPIKIG, ej
  jämn — L3 cave_bear = vägg (tank 22% / rogue 51% / hunter 48%), L4 plague_acolyte trivial (100%),
  L6 treant hård (0–63%), L7 hollow_worg omöjlig (0%). Bekräftar problemet; fiende-ladder själv ojämn.
- **HALT-fynd / designval för Lucas (3 st):** (1) "+2 tiers på alla" krockar med
  `weapon_required_level = max(1, tier-2)` och `rare_tier_cap`-trösklarna — kräver beslut om
  required-level-formeln så tidigt spel förblir åtkomligt. (2) "Epic-rarity" är en NY rarity —
  definition (label, gating, pris, plats vs legendary) behövs. (3) "Jämn svårighet inkl. mage med
  Mana" kräver en **skill-medveten sim** (attack-only kan ej mäta mage-med-mana); den harnessen finns
  ej. Full ombalansering (8+ data/kod-filer + epic-rarity + iterativ 6-klass-tuning) = stort
  designbärande projekt → committar ingen gissning; mätningen + planen levererad för granskning.


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

#### B39 — Chatbox-logg v3 (dedup + word-wrap) + HUD Lv/Gold + tjockare barer  · ✅ **KLAR** (`416c997`, `c1e6a50`, `f0eb6dd`)
- **Dedup:** battle-end loggade dubbelt (core-narration *och* presentations-rader). Suppress
  core-dubbletterna i `BattleApp._consume_result` och ta bort verbose "X dropped: …" → loggen
  visar exakt: Victory! / +N XP / +N gold / Loot: item [rarity]. Core RETURNERAR fortsatt sina
  events (tester orörda); "Gained N level(s)." behålls (ingen dubblett).
- **Word-wrap:** `_draw_log` radbryter via `_wrapped_lines_pixels` (ingen `_fit_text`-trunkering);
  synliga rader + `_log_scroll_max` räknas i *visuella* rader (en wrappad rad = sina renderade rader).
- **HUD:** `_draw_vitals` ritar "Lv N    Gold G" (inget namn) ovanför HP/Mana/XP-barerna; bar_h 12→18
  så inline-texten ryms centrerad. Läser `snapshot.player.level/.gold`.
- **Tester:** drop → en "Loot:"-rad, ingen "dropped:"-rad, battle-end ej dubblerad; lång rad → >1
  visuell rad utan "…"; vitals visar Lv/Gold + bandet ryms ovanför chatboxen. 622 OK (system + venv).

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

#### B16 — Overworld-logg (RuneScape-lik)  · ✅ **KLAR** (`17d5156`, se arkiv) — *stale duplikat städad ikväll*
- **Fynd (nattbatch 2026-07-09):** denna aktiva post beskrev exakt det arkivet redan
  visar byggt — deque, nere till vänster, combat/drops/level/heal — men blev aldrig
  flyttad ut ur "Aktiva punkter" när den landade. Ingen kod ändrad; ren backlog-hygien
  så punkten inte STEG-0:as/byggs om av misstag. Se arkivposten **B16** längre ner.

#### B16.1 — Combat-logg i overworld-loggen + flikar (ALL/Combat)  · ✅ **KLAR (ihop med B44)**
- **KLAR (2026-07-06):** alla battle-rader kanal-taggas `combat` (delade dequen gör
  att de redan överlevde till overworld); **[All][Combat]-flikchips** på loggpanelens
  överkant filtrerar (klickbara endast i free-walk, read-only under overlays — samma
  regel som scroll; fikbyte nollar scrollen). **Playtest-notisen verifierad redan
  fixad:** heal-raden är i dag "Undead Priest healed 18 HP." — rätt subjekt och
  belopp (lagades på vägen av B58-handler-arbetet); ingen ändring behövdes.
- Combat-rader överlever battle→overworld; flikar filtrerar. **Playtest-notis:** städa
  heal-loggningen — `priest_heal` loggar spelarens HP som "target", förvirrande; visa
  vem som healas och hur mycket.

#### B18 — Klassvals-skärmen omarbetad (fluid-layout)
- Inzoomad/dålig text. Gör ihop med fluid-migration (character_creation). STEG 0: varför
  inzoomad; var renderas texten.

### Innehåll & värld (kreativ expansion)

#### B27 — Innehålls-variation: nya skills, vapen, stats  · ✅ **KLAR (nattbatch 2026-07-10→11, fffe3e0)** — 9 skills (6 t5-noder + 3 tomes), 7 vapen (commons i butik, rares loot-only per B8-regeln); ekonomikontroll i nattrapporten · **Tolkning GODKÄND (Lucas 2026-07-11):** rare-vapen är loot-only, butiker toppar på commons/t5
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

#### B28 — Världsexpansion: större karta, glesare städer, kluster i alla (#3)  · ✅ **KLAR** (karta 240×208 + kluster i alla 17 via B8 Slice 2a — se dess arkivpost)
- **KLART (`960d0a3`/`1985e10`):** kartan expanderad 80×56 → **240×208 med parametrisk terräng
  (option A)** — `overworld_layout.py` härleder zon-band (cainos/mork_skog/cursed_mire nord,
  grave_heath söder om seam y≈100), organisk kust som tätar kanten utom gate-mynningar, seam-kanal,
  EN nordfödd flod → central hed-sjö, och **broar härledda ur verkliga inter-stads-rutter** (fyra
  seam-övergångar spridda V→Ö, inkl. två östliga). `regenerate_overworld.py` målar layouten i TMX:en;
  `core_zone.json` bär de 17 städerna på godkända koordinater + remappade gates/ground_themes/
  wild_regions. B8-klustren (burg_5, burg_67) är procedurella → följde med + renderar intakt.
  Verifierat: alla 17 städer + 3 gates nåbara (spel-sidans kollision), ingen stad i vatten, zoner rätt,
  vatten ett sammanhängande område, TMX-laddtid ~0.55s. world.json (meny-resa) orört. 630 tester gröna.
- **Kluster i alla städer: KLART** via **B8 Slice 2a** (tier-styrt kluster i alla 17, Lucas-
  godkänd render) — denna posts "kvar"-rad var inaktuell, städad ikväll (nattbatch 2026-07-09).
  Nya ZONER (tema/svårighet per band) förblir designbärande, egen runda — ej rört.

##### B28 ursprunglig kontext (bevarad)
- **Vad (#3):** **Förstora kartan** (idag 80×56 → t.ex. ~120×84) och **sprid ut stads-
  prickarna** så att de relativt stora kluster-städerna får plats utan att krocka (det var
  därför B28-batchen fick diskvalificera Alherralba/Rotequero — för trångt), och **bygg
  kluster i ALLA städer** med tiered storlek (hub/medium/by). = i praktiken B8 Slice 2 + större karta.
- **Nu GUIDAD, inte obevakad:** strukturellt + visuellt, kräver render-granskning per stad.
- **STEG 0 (kritiskt):** en regen av en större karta kan flytta befintliga koordinater —
  kartlägg vad som bryts: burg_5:s ankare (26,18), gates, place_ids, turneringar, seam.
- **Verifierade kriterier finns** (entré-test, ingen-cobble-i-vatten, `footprints ∩ water == ∅`,
  reachability, multi-hub disjunkthet) → automatisk korrekthet; estetik = Lucas per stad.
- **Nya ZONER** (terräng/tema/svårighet) = designbärande → egen runda, bygg inte blint.
- **Acceptans:** större karta utan att bryta befintliga ankare/gates/turneringar; alla städer
  som kluster i rätt storlek; alla stads-tester + reachability gröna; renders per stad.

#### B38 — Skill-förvärv: skill-tomes vid mage tower  · ✅ **KLAR** (core + UI, render-verifierad)
- **UI KLAR:** mage-tower-byggmenyn har "Study skill tomes" → tome-shop-vy (`_draw_tome_shop`) som
  listar alla 8 tomes (sorterade på Lv, med skill/Lv-krav/pris), dimmar redan-kända + oköpbara,
  köp via `buy_tome`. Köpt tome hamnar i inventoryns **consumables**-flik som **användbar** rad →
  klick lär skillen (level-gated). Headless-renderad + verifierad av mig; 4 pygame-tester (venv). 790 gröna.
- **Design låst med Lucas:** **skill-tomes** (item) + **level-krav**, sålda vid **mage tower**,
  förbrukas vid användning → lär skillen (Lucas invände mot "inga tomes" → tomes infört).
- **Core KLAR (denna natt):** 8 tomes (kind `tome`, `teaches`+`level_req`, tier/pris skalat mot
  skill-styrka: zap L2 100g … incineration L8 500g). Ny `learned_skill_ids`-pool (icke-talang),
  `unlocked_skill_ids` inkluderar den. `tomes.py`: mage-tower-gated shop (building_id `tower`/
  `mage_tower`, speglar upgrade-stationen). `game.tomes_for_sale`/`buy_tome`; `use_consumable`
  hanterar tome→learn (level-gate, dedup, förbrukas). Persist i save/load. **Lärande auto-equippar
  INTE** — equip via skill-skärmen inom max-4. 12 tester (data/shop/learn/gate/dedup/equip/persist).
- **Kvar (render-review):** pygame mage-tower-menyn ska visa/köpa tomes (öppnar idag `upgrade_station`).
  Engine-API:t är klart för UI:t att anropa. Turnerings-belöningar som tome-källa = valfri framtida.
- **Kopplar:** B27 (poolen får äntligen en väg in), B30 (byggnadsmenyer).




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

#### B25 — Klassbalans-granskning (skill-användande sim)  · ✅ **MÄTT** (mät-only, inga nerfs)
- **Fråga besvarad:** i **skill-medveten** sim (best weapon + skills, on-level) är **fighter INTE
  en outlier** — attack-only-gapet var till stor del en sim-artefakt. Matris (60 trials):
  - **L3** (giant_rat/undead/cave_bear) & **L5** (goblin_shaman/plague_acolyte/razortusk_boar):
    **alla 6 klasser 100 %** on-level.
  - **L7:** mest 100 %; avvikelser = *signaler, ej enemy-buggar*: **mage 0 % vs mire_lurker**
    (caster-skörhet: mana slut + låg HP → förlorar DPS-race mot tanky standard); **cleric 22 %
    vs treant** (holy neutralt mot plant + treant tålig = specialist-svaghet); physical-resistenta
    elites (bog_hag: tank 35 %, mage 20 %) svåra för fysiska/sköra, cleric 100 % (avsedd "rätt verktyg").
- **Rekommendation:** **inga enemy-/klass-nerfs nu.** Överväg en separat **caster-sustain/mana-
  ekonomi-pass** (mage L7-skörhet mot tanky standards) om det bekräftas i playtest. Fighter behöver
  ingen justering.
- **Not:** mät-only per punktens krav; ingen kod ändrad.

#### B13 — Tournaments: svårighet (KLART, se arkiv)
- Löst: Frenzy-CD (root-fix) + diversifierade turneringsbuffar. Fortsättning = B26.

---

## Föreslagna kluster & ordning

1. **Spår A — power-curve-trilogin: ✅ KLAR.** **B35 ✅** (`c600efc`) · **B36 ✅**
   (`1d7322a`…`d458281`, talent-ranger) · **B37 Slice 1+2 ✅** (`ba5af71`… + `b1ba224`…`403c096`,
   vapen-rework + upgrade-system) · **Wisdom A+B ✅** · **B31 ✅** (`faac4ca`). Kvar i spåret:
   **B25** (klassbalans-sim, mät-only) + ev. epic-rarity `consecrated_maul` om önskat.
2. **Spår B — Världsexpansion #3: ✅ KLAR** (`960d0a3`/`1985e10`, 240×208 parametrisk karta —
   vatten-forken löstes via **option A**: flod/bro/kust härledda parametriskt). **B8 Slice 2a ✅**
   (kluster i alla 17). Kvar: **B8 Slice 2b** (per-stad butik + tjänste-triggrar) + nya ZONER
   (designbärande, egen runda). **Skill-aware sim-harness ✅** (`d79dfeb`).
3. **Innehållets syfte:** **B38** ⭐ (skill-förvärv: mage tower/belöningar) — ger B27-poolen
   en väg in. Sedan **B22** ⭐ (enchant-vendors), **B23** ⭐ (quests/notice boards).
4. **Kollision:** ⭐**B21** (sub-tile — fixar vatten/fences/gates).
5. **Progression-djup:** ⭐**B3.1** (dual-class, HALT) → **B3**.
6. **Värld/utforskande:** **B11 Slice 1 ✅** (karta + fog, `9ec6f0c`); kvar = **minimap (Slice 2)**.
7. **UI/skärmar:** **B40 apply-slices S2–S5** (render-HALT/skärm); **B18** (klassvals-skärm fluid);
   CHARACTER_SCREEN-polish; **B10** (shop-UI).

> Designrunda-först (öppna ⭐): B21/B22/B23/B38/B41/B47/B3.1. Autonom-vänligt (öppet): odöd-densitet,
> B42, B46, B43, B25, B44, B11-minimap, B16.1.
> Klart sedan sist (se arkiv): B35/B36/B37/Wisdom A+B/#3-karta/B8-2a/B11-S1/B40-S1/B24-flag/B2/B39.

---

### Menyer & UI (nytt program)

#### B40 — Menyprogram: enhetlig menyspec över ALLA skärmar  ⭐ designbärande  · ✅ **KLAR (S1–S5)** · render-verifierad headless (våg 3)
- **Vad:** En single source of truth för hur alla menyer ser ut/beter sig, så menyerna slutar vara bespoke per skärm. Låst 7-punktsspec:
  1. **Progressiv disclosure** — rader visar bara namn + åtgärds-relevant siffra (t.ex. kostnad); sekundär detalj bara på hover.
  2. **Hover-tooltip** (>1 s) → panel med stats + kort förklarande text; EN delad komponent, aktiverad per meny.
  3. **Inga parentetiska härledda värden** någonstans (visa "Wisdom 4", inte "(Mana 16)").
  4. **Tomma kategorier dämpade** (shop "kan ej köpa"-stil), INGA "(N)"-räknare.
  5. **Inga redundanta underrubriker** ("Allt du äger…").
  6. **Enhetlig chrome** — en delad Button / list-stil / font / spacing.
  7. **Rarity via färg** (konsekvent med chatt-paletten).
- **Avsikt:** Menyerna blir läsbara, konsekventa och informativa; beslut (köp/equip) fattas informerat via hover.
- **Not:** STEG 0: idag TVÅ Button-dataclasses (pygame_overworld ~435: rect/label/on_click/enabled/restricted; pygame_battle ~119: +hotkey/sublabel), ingen hover/tooltip-infra. Slice-först; varje apply-slice = render-HALT.
- **Slices:**
  - **S1 (grund, HALT-fri):** ✅ **KLAR** (`3b8db9a`/`8d46df3`/`d0673b9`/`866c448`, + unified chatbox `9083dac`). Delad `ui.py`: Button (superset rect/label/on_click/enabled/restricted/hotkey/sublabel) + HoverTracker/Tooltip + MenuRow/draw_menu_row (rarity-färgade namn). Beteende-bevarande migrering klar. **← S2 härnäst.**
  - **S2 (inventory):** ✅ **KLAR** (`697d24b`). item_text.py (delade tooltip-byggare, B41-procs i klartext, säljvärden via core-regler); ui.Button bär value/label_color/tooltip och overworldens _draw_buttons ritar ALLA knappar via draw_menu_row (punkt 6 för alla skärmar på en gång). Hint-strängar borta (kollisionen med), kategorier utan "(N)" + tomma dämpade-men-klickbara, rader = rena namn i rarity-färg + xN/+dmg/equipped som value, stats/pris på hover. Fynd i render-självinspektion: draw_tooltip wrappade inte stat-rader (fixat i ui) + "Back (Esc)" trunkerades (breddat).
  - **S3 (shop):** ✅ **KLAR** (`3d918bf`). Buy/sell-rader som menyrader (pris i value, "xN · Yg" på säljsidan), stat-texten flyttad från under-rad-blits till hover (rad 56→34 px + "v N more v" vid overflow), "Vs equipped"-delta för vapen/gear, oköpbara = restricted (klick förklarar), tome-shopen samma idiom. Död _blit_item_stats borta.
  - **S4 (character):** ✅ **KLAR** (`91fe4e8`). 3-raders header + regioner under (_CHAR_HEADER_H) = Gold/Stats-krocken strukturellt omöjlig (geometritest); "(+weapon N)" bort från Damage-raden → hover ("Weapon bonus: +5 (Sword)"); alla stat-rader har hover-förklaring (T.stat_help, Wisdom läser MANA_PER_WISDOM); slot-rader utan "(N)" (xN-value bara på TOMMA slots, 280px-kolumn); options-rader = namn + beslutssiffra (delta/needs Lv/equipped) som value. B37-chipen pensionerad (krockade med value) → tooltip-rad + stationslistor.
  - **S5 (creation):** ✅ **KLAR**. STEG 0-fynd: start_new_game lärde REDAN ut default-skillens talang gratis → "1 av 2" byggd som **swap**, inte tillägg: start_new_game(starter_talent_id=...) ersätter klassdefaulten (fortfarande exakt EN gratis rank-1-talang, skillen equipped); utelämnad → default (terminal/sims oförändrade). Creation returnerar (name, class, starter); default förvald (Enter-through = gammalt beteende); hela trädet som read-only-preview per gren med hover-tooltips (talent_text.node_preview_lines, B78-formattern); "(Mana X)" borta (Wisdom-hover förklarar).
- **Acceptans:** 7-punktsspecen uppfylld på alla fyra skärmarna; hover >1 s ger tooltip överallt; renders i docs/b40_renders/ (Lucas-review efteråt per nattbatch-mönstret); 1017 tester gröna.

#### B11 (tillägg) — Minimap = Slice 2  · 🟢 **BYGGD** (render-review)
- **Vad:** Fullskärmskarta + fog (M) är Slice 1 (KLAR, `9ec6f0c`). **Slice 2 = en alltid-synlig minimap** i hörnet, återanvänder fog-bitset + terräng-texturen. **Not:** presentation-only ovanpå B11-infran. **Acceptans:** minimap visar avtäckt terräng + spelarmarkör; togglas; test.
- **BYGGD:** `_draw_minimap` (top-left, ~44×33 tiles = 3.5× walk-vyn) återanvänder den **fog-maskade
  map-kompositen** (obesökt = MAP_FOG, exakt samma fog som M-kartan → "varit där"-regeln gratis) +
  spelarmarkör; **N** togglar (default på). Ren framing-helper `fog.minimap_origin` (centrering +
  kant-clamp) testad. **Render-review i morgon** (pygame-ritning; systempython saknar pygame).

### Strid, vapen & innehåll (nytt)

#### B41 — On-hit elemental-proc-familj (status-on-hit som vapenmekanik)  · ✅ **KLAR** (v1: fire/poison/frost + holy-heal)
- **KLAR:** `Weapon.on_hit` (data) + `combat.apply_weapon_on_hit`-hook efter basattack som träffat
  (bara `base_attack` — skills proccar ej; fiender proccar ej). Resistensmatrisen gatar status-procs
  (odöd shruggar toxin, "immune"-event). Seedat per Lucas beslut: **fire→burn** (apprentice/adept/ember/
  pyre, 20-35% mag 3-8), **poison→toxin** (venomfang 35% mag6), **frost→chill+låg freeze** (rimebrand
  35% speed−3 / 10% skip-turn), **holy→Searing** = matris ×1.5 (redan i skada) **+ liten heal-on-hit**
  (consecrated_maul/gravewarden_blade 25% heal 5-6). **Lightning avvaktar** (inga bärare; skadetyp finns
  bara på skills). Sim: proc-vapnen (rares) starka men spränger ej kurvan. 8 tester; 786 gröna (venv).
- **Vad (bevarad):** Låt vapen bära en **on-hit-effekt** (idag kommer status bara från skills). Föreslagen familj på befintliga status-primitiv:
  - **Fire → Ignite** (burn-DoT), **Poison → Toxin** (DoT, respekterar resistensmatrisen), **Frost → Chill** (speed-debuff) + låg **Freeze**-chans (skip-turn), **Lightning → Shock** (låg accuracy-debuff), **Holy → Searing** (mest via matris ×1.5 vs odöda, ev. liten heal-on-hit).
- **Avsikt:** "Elementala vapen" känns distinkta; kopplar till item-upgrade-systemet (proc som primär-effekt ett recept kan ge).
- **Not:** NY vapenmekanik — hook i basattack-resolutionen som rullar vapnets on-hit-effekt. Primitiven (DoT/speed/skip/accuracy) finns; det är wiring. v1 seedar **fire/poison/frost**; lightning/holy senare (deras skadekomponent funkar ändå). Siffror = platshållare, INTE simmat (sim endast om något spränger kurvan).
- **Acceptans:** basattack med proc-vapen applicerar rätt status; resistensmatrisen respekteras (odöd immun mot toxin osv.); test för hook + de tre seedade elementen.

#### B42 — Nya fiender: 4-zon-roster (balans + loot + placering + caster-actions)  · ✅ **KLAR**
- **KLAR:** hela 4-zon-rostern ur Lucas skärmdump byggd: 14 fiender utfyllda + **6 nya**
  skogsfiender (goblin_raider, thornling, razortusk_boar, goblin_shaman, broodmother_spider,
  strangling_vine, placeholder-sprites). Roll-baserade stats (trash/standard/elite/mini-boss),
  16 nya signatur-/caster-actions ur befintliga primitiv, traits→vekheter matchar skärmdumpen.
  **Placering:** de 4 wild-region-poolerna satta (cainos→burg_54 per-fiende-band; mork_skog→
  burg_146 4-9 rare strangling_vine; cursed_mire→burg_320 5-10 rare bog_hag; grave_heath→burg_121
  6-12 rare cursed_wight mini-boss), befintliga fiender infällda i matchande zon. **Loot**
  differentierad (trash=salvage+pots, elit=rare-access+unique tier 3-4). ENEMIES.md omskriven,
  turneringen (rotequero_wildblood_pit) uppdaterad till mork_skog-rovdjur. 762 tester gröna.
- **Designnot (motiverat beslut):** spirit/cursed = physical ×0.65 (trait-design) → shade/
  cursed_wight är "ta-rätt-verktyg"-specialister (sim: fighter ~20 %, rogue 60-100 %, cleric 100 %),
  medvetet inte en vägg. **Kvar:** riktig sprite-art för de 6 nya (placeholder nu).
- **Not:** Sim fångade två väggar (shade/cursed_wight 0% melee) → tunade ned hp/dmg, behöll resistensen.

#### B46 — Wisdom på gear & vapen  · ✅ **KLAR** (gear-only)
- **KLAR:** 6 wisdom-bärande gear-pjäser över caster-slots (acolyte_charm/seer_pendant amulett,
  runed_circlet head, oracle_loop/archon_signet ring, mystic_robe chest), tier 1–3, wisdom +1..+4.
  Equip höjer härledd mana (wisdom×`MANA_PER_WISDOM`) + `spell_source_value` — verifierat i test.
- **Motiverat beslut:** **gear-only** — vapen saknar `stat_modifiers`-fält (wisdom-på-vapen =
  kodändring, ej content), och casters skalar redan spell via magic-vapnets damage_bonus, så
  wisdom-på-vapen vore delvis redundant. Wisdom-vapen = egen liten runda om önskat.
- **Not:** per-pjäs wisdom ≤4 + rares → modest, ingen sim behövdes. Reachability: stockas i B43-butiker.
- **Acceptans:** ✅ 6 items med wisdom; härledd mana + spell svarar; 5 tester.

### Overworld & värld (nytt)

#### B45 — Minisjö att gå runt  · ✅ **KLAR (våg 3)** · kirurgisk regenerering (diff-verifierad)
- **KLAR:** `MINI_LAKE = (44, 76, 1.5, 1.5)` i overworld_layout (cainos-ängen SV om huvudstaden) —
  16 renderade vattenceller med **2×2 blockerande kärna** + gångbar strandring (majority-water-
  kollisionen håller kant-tiles gåbara, så en smalare damm gick att gå IGENOM — first cut fångad
  av eget test). Platsen probad innan bygge: ≥11 tiles från varje rak stadsrutt (ingen bro karvas
  genom den), fritt från vatten/kistor/lairs/städer, och pocket-rng:n (Random(83)) opåverkad.
  `_one_water_body` seedar nu från BÅDA sjöarna (medveten andra vattenkropp). **Diff-verifierad
  regenerering: exakt 16 ändrade celler (walls-lagret, bbox 42–45×74–77), 0 drift i pockets/
  stenar/buskar/broar.** Reachability grön; 4 tester (kärna blockerar, ring gåbar, konstant låst);
  ZONE_MAP.png omgenererad. **Vad (bevarad):** En liten insjö som landmärke/omväg (Lucas-önskad).

#### B47 — Zonfärgs-övergångar (palett)  · ✅ **KLAR** (nattbatch: production-blenden byggd som **draw-time-overrides** — 2305 förblandade tiles byggda EN gång vid load, layer-datan orörd (väg-scan/M-karta/gid-konsumenter opåverkade), `ZONE_BLEND_BAND=4` (0=av), mild deterministisk jitter; matchar PoC-utseendet Lucas godkände; renders i docs/b47_poc/b47_production_*.png; 4 tester)
- **PoC (2026-07-06):** `docs/b47_poc/` — före/efter för cainos↔skog, skog↔mire och
  heath-sömmen. Teknik: **alpha-crossfade av ground-tiles** i ett ±4-tiles-band
  (8 alfasteg; förblandade tile-bilder som syntetiska gids byggda EN gång vid
  kartladdning → noll per-frame-kostnad, ~121 extra bilder, rör inga seeds, ingen
  PNG-retusch). **Bedömning:** klart mjukare på båda vertikala sömmarna; heath-sömmen
  följer till stor del en flod och behöver knappt åtgärd. Skavank: svag kolumn-
  bandning — production lägger hash-jitter ±1 alfasteg per tile. **Beslut:** (a) bygg
  production-varianten (liten slice, load-time pass bakom konstant `BLEND_BAND`),
  (b) acceptera hårda gränser.
- **Vad:** Zon-till-zon-färgskiften (gul kärna / mörkgrön skog / grågrön swamp) upplevs hackiga. **Not:** paletten är **inbränd i tema-PNG:erna** → INTE fixbart via tile-placering. Öppet beslut: retuscha tema-PNG-paletterna för mjukare övergång, eller acceptera. **Acceptans:** beslut fattat; om åtgärd — mjukare zon-gräns verifierad i render.

### Chatt/HUD (nytt)

#### B44 — Chatt-logg v4-polish: segment-färg + per-träff skada  · ✅ **KLAR (ihop med B16.1)** · render-verifierad headless
- **KLAR (2026-07-06, Lucas-GO):** chatlog v4 — payload kan vara `Segments`
  ((text, färg), …) med segment-medveten word-wrap; `ChannelText` (str-subklass)
  taggar rader med kanal utan att bryta någon konsument. **Synligt:** skada MOT
  spelaren renderas röd (colourizer mot core-narrationens kanoniska form — matchar
  den inte passerar raden oförändrad), heal-rader gröna, victory ger EN rad
  "+XP +guld" i varsin färg, loot-raden färgar BARA itemnamnet (rarity), kist-rader
  slår ihop guld+loot på en rad. Beslut: core-events förblir strängar (ingen
  parallell result-väg); färg åker på formen, test-låst. 13 nya tester.
- **Vad:** Två uppskjutna förbättringar i den unifierade loggen: (a) **segment-färg per rad** (item-namn i rarity-färg + guld-belopp i amber på samma rad, inte hela raden en färg); (b) **per-träff skada i rött** (skada mot spelaren).
- **Not:** Båda kräver en rikare log-modell: (a) rader som färgade **segment** i stället för en färg/rad; (b) **strukturerade combat-events** (skadetyp/mål) i stället för färdig-formaterad text. **Acceptans:** loot-rad visar färgat itemnamn + amber guld; skada-mot-spelare renderas röd; tester för segment-rendering + event→färg.

#### B43 — Butiksinnehåll för de nyaktiverade store-städerna  · ✅ **KLAR**
- **KLAR:** 10 städer som bar default-fyran fick kurerat, kategori-lämpligt sortiment (weapons/
  armor/general per core_zone shop_category), + burg_146 (armor) trimmad. **Lucas-regel enforced
  globalt: max 1 rare/shop** — "prestera snarare än köpa": shops fyller luckor/små uppgraderingar,
  inte topp-gear. Varje butik bär nu båda lesser-pots + ≥1 weapon/gear/consumable, inga greater-pots,
  ingen osåld worn_shortsword. Wisdom-gear (B46) seedad i caster-shops (acolyte_charm/seer_pendant/
  oracle_loop) för reachability. **Acceptans:** ✅ ingen default-fyra kvar; ≤1 rare/shop; test låser
  regeln för ALLA stores. 765 tester gröna.

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
  entré-kriterium. *Slice 2 (alla 17 + funktions-triggrar) kvarstår — guidad session.*- **B26** (`e855806`+`c3dd6b7`) — zone-2-turnering (Rotequero Wildblood Pit), opponents ur
  zon-2-poolen, diversifierad buff; belöning = antidote+mana+hp-potion (ej guld).
- **B27** (`4adb57c`+`df9415b`) — innehåll: ranged/magic mid-tier-vapen + caster/ranged-gear;
  **8 elementala skills som oanvänd pool** (zap/thunder_strike/incineration/holy_strike/
  frost_shard/earthen_smash/plague_ooze/immolate), alla ≤ fireball, kopplade till ingen klass.
  *Förvärvs-väg = B38.*
- **B28-städer** (`6ca427b`) — hub-modellen generaliserad; Fongorinos som andra hub;
  `MultiHubPlacementTest`. *(Större karta + alla städer = #3, nu B28 guidad.)*
- **Differentierade butiker** (`d32dafe`) — blacksmith→vapen, barracks→rustning, shop→allmänt.
- **Stads-fixar** (`49c62d3`/`128624f`/`b84db91`) — cobble = riktiga vägtiles (cainos_grass),
  per-dörr-interaktion, flytande ortsnamn bort → indikator uppe-höger.
- **B16** (`17d5156`) — overworld-logg (deque, nere till vänster, combat/drops/level/heal).
- **B29** (`2e10206`) — chatbox v2: all text in i loggen (inga toasts), scrollback (200),
  skalbar 5–18 rader, dubblett-fix (`8865543`).
- **B30** (`68a773d`) — titlade byggnads-menyer; ingen tjänst körs förrän spelaren valt.
- **B31** (`4ba41fa`) — HUD: topp-rad + namn/guld/level bort; HP/Mana/XP-bars ovanför chatboxen;
  stadsnamn uppe-höger utan mörk bakgrund. *(Kontrast på ljusa tiles = ev. lätt polish.)*
- **B32** (`6680714`) — hela stadsklustret + 2 tiles marginal = encounter-fritt.
- **B33** (`3151780`) — fighter startar med `worn_shortsword` (dmg 2), ej `sword` (dmg 5).
- **B34** (`2859ba7`) — sammanhängande broar via genererade halv-däck-tiles (1- och 2-bred),
  inga gamla ramper, över nytt vatten.
- **UI Slice A** (`4ba5134`/`a124736`) — shop visar item-stats per rad; character-skärm visar
  compare-mot-utrustat-delta. *(B10:s shop-compare avstått medvetet — bara stats i shop.)*
- **B27 skill-pool** (`df9415b`) — 8 data-only elemental-skills (zap/thunder/incineration/
  holy_strike/frost_shard/earthen_smash/plague_ooze/immolate), kopplade till ingen klass/talent.
- **B35** (`c600efc`) — level-up main-stat-val (HP/Mana/Damage/Crit, ej Speed); flat universell
  bundle (main +8/+8/+4/+4, övriga bas +2/+2/+1/+1); 4-vals-modal i battle-shellen; persist.
- **B31-polish** (`faac4ca`) — svag halvtransparent platta bakom stadsnamnet (kontrast på ljusa tiles).
- **trait-resistanser** (`03fc905`) — fiende-`traits` (max 2) = sanningskälla; `resistances` härleds
  vid load (core/traits.py); pipelinen oförändrad. Avsiktliga feel-flips (cave_bear/mudcrab/tar_beast/…).
- **B39** (`416c997`/`c1e6a50`/`f0eb6dd`) — chatbox v3: battle-end dedup (en uppsättning rader, "dropped:"
  bort), word-wrap utan trunkering, HUD "Lv/Gold"-rad ovanför tjockare (18px) HP/Mana/XP-barer.
- **B37 Slice 1** (`ba5af71`/`2f7733b`/`ad5cf9d`/`05a83b8`) — vapen-omarbetning: tier härleds ur damage,
  required_level frikopplad (t-stege), worn=0/osåld, venomfang→poison, 8 materialstege-fillers,
  weapon-aware sim. Curve verifierad jämn; mage-med-mana livsduglig; holy stark-ej-trivial mot undead.
- **#3 världsexpansion 240×208** (`960d0a3`/`1985e10`) — parametrisk terräng (option A): härledda zon-band,
  kust, seam-kanal, nordfödd flod→sjö, broar ur rutter (4 seam-övergångar). 17 städer på nya koordinater,
  klustren följde med intakt. All reachability/zon/vatten verifierad; 630 tester gröna. Kvar: B8 Slice 2.
- **B8 Slice 2a** (`78cbce0`/`e74ffd2`/`17f6207`, Lucas-godkänd) — tier-styrt kluster i alla 17 städer
  (capital/city/town/village ur core_zone), resolve_template, en rest-dörr/stad, town_hall vid turnering,
  kuliss utan dörr, sprites (id,facing). 637 tester gröna. Kvar: 2b-tuning + tjänste-triggrar.
- **nya fiender + frostfire** (`1316ccc`/`02e6f90`) — 14 fiender registrerade som data (härledda
  resistanser, platshållar-stats, skeleton_warrior-elit), frostfire_strike-action, 14 sprite-PNG:er.
- **Wisdom Slice A (system)** (Lucas-godkänd) — ny `wisdom`-stat driver HÄRLEDD mana (wisdom×5+gear,
  ingen lagrad max_mana-bas); level-up-valet Mana→Wisdom; ny combat-scale `spell` =
  round(0.4×(dmg+magic-vapen) + 0.6×wisdom)×mod för spelar-magi (smite/firebolt/.../mend/DoTs + B27-pool).
  Fiender (ingen wisdom) → power-ekvivalent, oförändrade; ignite lämnad platt (delas med arena_mira).
  650 tester gröna (system + venv).
- **Wisdom Slice B** (`b3249fa`) — sim-tunad caster-skalning: wisdom-val +2/level, mana/wisdom 5→4,
  smite-mod 1.8. Balanserar spell-power mot power-curve-trilogin (B35/B36/B37).
- **B36** (`1d7322a`/`7a83fdc`/`8c9dd3b`/`d458281`) — talent-ranger: `max_rank` per nod (24 active /
  17 passiva skalbara / 10 binära), `talent_ranks`-state + learn-or-upgrade, per-rang skill/passiv-
  skalning (`rank_mult`), talents-UI visar rang + Learn/Upgrade.
- **B37 Slice 2** (`b1ba224`/`c8c09b6`/`ffbc53c`/`eeef40c`/`403c096` + stationer `754ca7b`/`83a714e`) —
  item-**upgrade-system** (INTE epic-rarity): junk→miscellaneous, rarity-graderade material + drops,
  upgrade-recept (deltas/exclusions/persistens i `upgrades.json`), stationer (blacksmith=vapen /
  mage tower=rustning), upgrade-UI med Upgradable-tagg. *Epic-rarity `consecrated_maul` blev EJ gjord.*
- **B24-flag** (`7f083ec`) — delad rare-table capad till tier 3 för wild-kills < L5 (consecrated_maul/
  venomfang/pyre_scepter ej dropp-bara L3–4; L6+ opåverkat). Stänger B24:s öppna flagga.
- **B11 Slice 1** (`01ee74d`/`9ec6f0c`) — fog-of-war (avtäck vid gång + persistens) + fullskärms-kart-
  overlay (M) med fog/pins/you-are-here. Minimap = Slice 2 (öppen).
- **B40 Slice 1** (`3b8db9a`/`8d46df3`/`d0673b9`/`866c448`, + unified chatbox `9083dac`) — delad `ui.py`:
  unifierad Button + HoverTracker/Tooltip + MenuRow/draw_menu_row (rarity-färgade namn). Beteende-
  bevarande migrering. Apply-slices S2–S5 (render-HALT per skärm) kvar.
- **B2** (`b56f195`/`c76ef2b`) — broar omarbetade: seam = en bred railless-däck (idx0), lake/river-broar
  borttagna. Tidigare plank-skin/hav-verifiering (`45401b0`).
- **Overworld-polish** (`631c87d`/`bab02eb`/`9182af0`/`ba6fe6a`/`9f6c65e`) — pocket-vegetation (busksnår/
  sten-ringar/blomsteräng), fullhöjds y-sorterade gravstenar (gå bakom), solida buskar + grå M-map-
  prickar, rena en-tile-buskar, stadscobble matchar zonens gräs.
- **has_store från core_zone** (`dd74c8b`) — has_store härleds ur core_zone (single source); rest/store-
  gating fixad. *(Kurerat butiksinnehåll för de 9 nyaktiverade stores = B43, öppen.)*




  ### Kodhälsa & infrastruktur (systemgenomlysning 2026-07-04, arkitekt)

#### B53 — CI-pipeline: compileall + båda testsviterna på varje push  · ✅ **KLAR** (`a79bdb0`)
- **KLAR:** `.github/workflows/tests.yml` — två jobb per push/PR: `core` (beroendefri python,
  presentation-tester skippar, 17s) + `full` (requirements + pygame headless via SDL dummy, 1m27s).
  Båda kör compileall först. Verifierat: grön på master; **avsiktligt trasig push på tempbranch → röd**
  (probe-branchen raderad). Acceptans uppfylld.
- **Vad:** GitHub Actions-workflow som på varje push/PR kör (a) `python3 -m compileall -q rpg_game tests`,
  (b) systemsviten (`python3 -m unittest discover -s tests`), (c) venv-jobbet med `requirements.txt`
  (pygame-beroende tester, headless via dummy-videodriver).
- **Avsikt:** 794 tester skyddar bara den som kör dem. Idag upptäcks en trasig push först vid nästa
  lokala körning — med två samarbetande parter (Lucas + Svante) och nattbatchar är det ett riskfönster.
- **Not:** STEG 0: verifiera att pygame-testerna kör headless (SDL_VIDEODRIVER=dummy) — annars markera
  vilka som kräver display och kör dem i venv-jobbet med dummy-driver. Ingen kodändring i spelet.
- **Acceptans:** grön/röd status på push i GitHub; båda sviterna + compileall körs; en avsiktligt
  trasig test-push blir röd.

#### B54 — Load-time cross-referens-validering av content (fail fast)  · ✅ **KLAR**
- **KLAR:** `_validate_content_refs` i data_loader validerar VARJE id-referens vid load: classes→
  vapen/skills, enemies→actions/ai-actions/loot/unique-items, rare_table→items, tomes→teaches,
  upgrades→target/material, talents→class/action, places→encounters/rare/store/connections. Policy
  beslutad per punkten: okänt id = ValueError vid load (runtime-guards i combat kvar som ofarligt
  försvar — kan inte längre dölja trasig data). Riktiga datan verifierad ren. 15 injicerings-tester
  (ett stavfel per kategori → namngivet fel). 809 gröna. *Not: core_zone→places-validering bor i
  presentation-lagret (ZoneConfig) och ingick ej.*
- **Vad:** `data_loader.load_content` validerar idag turneringar/gear men INTE: enemy `action_ids`,
  loot-tabellernas item-ids, tome-`teaches`, upgrade-receptens target/material-ids. Lägg samma
  `raise ValueError`-validering för dessa + besluta policyn: okänt id = fel vid load (ersätter dagens
  blandning av tyst skip i `combat.py:202,759` och KeyError-krasch i `combat.py:843`).
- **Avsikt:** Ett stavfel i enemies.json gör idag att en fiende ljudlöst tappar en skill — osynligt i
  test och spel. 42 fiender × 79 actions × växande content: fel ska smälla vid load, inte försvinna.
- **Not:** STEG 0: inventera ALLA id-referenser i datafilerna (enemies→actions/loot, loot→items/weapons/
  gear, upgrades→items/materials, tomes→actions, classes→skills/weapons) och lista vilka som saknar
  validering. Befintliga tester som medvetet använder trasiga ids kan behöva fixtures.
- **Acceptans:** varje id-referens i data valideras vid load; ett injicerat stavfel i varje kategori
  ger ValueError med tydligt meddelande; sviten grön.

#### B55 — Flytta encounter-taktningen till core  · ✅ **KLAR**
- **KLAR:** `core/encounters.py` äger B12-regeln (SAFE_RADIUS/RAMP/PATH_FACTOR + `EncounterMap`
  med town/safe/path-tiles som rena sets, `encounter_rate_at`, `should_encounter`) + journey-mätning
  för sim (`journey_encounter_load` deterministisk + `simulate_journey` seedad). Skalet fryser
  geometrin en gång (`_build_path_tiles` skannar ground-lagret vid init), delegerar rate-frågan och
  behåller `_on_path` som mockbar seam (`on_path`-override i core). **Beteende-identiskt:** rng-ström
  bevarad (i stad = inget drag; vildmark = exakt ett), alla 12 baseline-tester gröna OFÖRÄNDRADE.
  10 nya core-tester låser exakta kurvan (0 → 1/3 → 2/3 → full, ×0.6 väg). 829 gröna. Enabler för
  B48-authoring + B62/B67.
- **Vad:** `encounter_rate_at`, `_nearest_town_dist`, `_on_path` och slumpdragningen i `maybe_encounter`
  (pygame_overworld rad ~752–792) flyttas till core (t.ex. `core/encounters.py`), parametriserad på
  tile-position + stads-/väg-data. Presentationen frågar bara "encounter nu? (tile)" per steg.
- **Avsikt:** NÄR fiender dyker upp är spelregler, inte rendering. I core blir taktningen (a) simbar —
  sim kan äntligen mäta res-fara/encounters-per-resa, (b) delad med terminal-läget, (c) rätt lager för
  B12:s nivåtak-diskussion och B48:s spawn-authoring att bygga på.
- **Not:** STEG 0: mät nuvarande beteende (rate-värden per avstånd/väg) och lås det med tester FÖRE
  flytt — flytten ska vara beteende-identisk (samma rng-ström om möjligt; annars dokumentera skiftet).
  Kräver att core får tillgång till stads-positioner + path-tiles (finns i core_zone/TMX-data — avgör
  minsta dataryta som behöver exponeras). Enabler för B12/B48; bygg denna FÖRST.
- **Acceptans:** encounter-taktning i core med egna enhetstester; pygame-skalet anropar core;
  beteende-identiskt verifierat (rate-kurvan matchar uppmätt baseline); sim kan räkna encounters
  per simulerad resa.

#### B56 — Dela upp OverworldApp (gud-klass 2856 rader → moduler)  · ✅ **KLAR (extraktion 1-3)** · render-identiskt verifierad
- **KLAR (2026-07-06, Lucas-GO):** tre beteende-bevarande mixin-extraktioner, en per
  commit, verbatim-flytt via ast-radintervall (B58-metoden): **(1) `overworld_render`**
  (24 metoder: _draw_map/towns/graves/cobble/chests/lairs/broar, M-karta, minimap +
  42 visuella konstanter inkl. delade paletten), **(2) `overworld_buildings`** (24
  metoder: dörrmeny, store, tome-shop, apothecary, upgrade-station + service-
  tabellerna), **(3) `overworld_overlays`** (19 metoder: character/inventory/skills/
  system/settings/bestiarium + turnerings-/döds-/victory-skärmarna — B40 S2-S5
  redigerar nu EN modul). Skalet re-exporterar alla flyttade namn (testers imports
  intakta); delad chrome bor kvar i skalet och nås via self. **3423 → 1969 rader.**
  Render-identiskt: före/efter byte-identiska på stad/söm/lya/M-karta per extraktion.
  **HALT-hanterat mål:** ~1200-radersmålet nås inte av de tre namngivna extraktionerna
  ensamma — kvarvarande skal = loop/events/actions/HUD/världsklasser (= post (4) "kvar").
  Vidare slimning (start-meny-modul, Overworld/ZoneConfig-modul) = valfri uppföljning,
  bäst EFTER B40 S2-S5. 937 tester gröna genom alla tre stegen.
- **Vad:** `pygame_overworld.py` bär ≥12 ansvarskluster i en klass. Extrahera i steg: (1) kart-/terräng-
  rendering (map overlay, minimap, town/bridge/grave-draw) → egen modul; (2) byggnadsmenyer (tome-shop,
  upgrade-station, store) → egen; (3) overlays (character/inventory/skills/tournaments) → egen (naturligt
  ihop med B40 S2–S5 som ändå skriver om dem); (4) kvar: app-skal (loop, events, engine-wiring, HUD).
- **Avsikt:** Varje B40-apply-slice, varje ny byggnadsfunktion (B8 2b, B22, B23) och varje kart-feature
  landar idag i samma fil — merge-yta, lästid och regressionsrisk växer för varje slice.
- **Not:** REN refaktor, beteende-bevarande, en extraktion per commit. SAMORDNA med B40 S2–S5: gör
  extraktion (3) som del av respektive apply-slice i stället för dubbelarbete. STEG 0: rita beroende-
  kartan (vilka metoder delar state) innan snittet läggs. Inga nya features i denna post.
- **Acceptans:** pygame_overworld.py < ~1200 rader; extraherade moduler med tydliga gränssnitt;
  render-identiskt (referens-screenshots före/efter); sviten grön.

#### B57 — En text-wrap: konsolidera tre implementationer till ui  · ✅ **KLAR**
- **KLAR:** `ui.wrap` (word-wrap + teckenbrytning, aldrig tomma fragment) + `ui.fit` (ellipsis)
  är DEN enda implementationen; `chatlog.wrap_lines` och overworldens `_wrapped_lines_pixels`/
  `_fit_text` är tunna delegater (samma signaturer — alla call-sites + tester orörda). STEG 0-diff:
  kärnalgoritmen var identisk i alla tre; supersetet tog _wrapped_lines_pixels tomma-fragment-guard
  (skillnad bara i aldrig-förekommande enteckens-bredd-fall). 7 lås-tester (wrap/char-break/tomt/
  ellipsis/delegering). 836 gröna.
- **Vad:** `ui._wrap`, `chatlog.wrap_lines` och `pygame_overworld._wrapped_lines_pixels`/`_fit_text` är
  tre parallella wrap/trunkerings-implementationer. Gör `ui`-versionen till den enda (superset:
  word-wrap + teckenbrytning av överlånga ord + ellipsis-fit) och låt chatlog + overworld använda den.
- **Avsikt:** Samma buggklass (wrap-kanter, breda tecken) ska fixas på ETT ställe; B40-apply-slices
  bygger tooltips/rader ovanpå wrap och ska inte ärva tre beteenden.
- **Not:** STEG 0: diffa de tre (chatlog bryter över-långa ord per tecken; fit trunkerar med "…") och
  bygg supersetet med tester som låser alla tre beteendena innan bytet.
- **Acceptans:** en wrap-implementation i ui; chatlog + overworld delegerar; wrap-tester täcker
  ord-brytning, teckenbrytning, ellipsis; render-identiskt i logg + overlays.

#### B58 — Combat-resolutionens megafunktioner: dispatch per effekt-typ  · ✅ **KLAR**
- **KLAR:** `apply_effect` 209→23 rader dispatch; 11 handlers (`_effect_damage`…`_effect_elemental_
  attack_mod`) med enhetlig signatur + `EFFECT_HANDLERS`-tabell (damage/instant_damage delar handler).
  Grenarna flyttade VERBATIM via mekaniskt splice-script (dedent) → beteende-identiskt per konstruktion.
  `run_combat_turn` fasindelad med namngivna markörer (VALIDERING → ROUND-START-STATUSAR → INITIATIV →
  AKTIONER → ROUND-END+COOLDOWNS → UTFALL). Nya tester: tabell-totalitet över authored effekt-typer,
  unknown-raise, dispatch-spotchecks. **Sviten grön utan testdiffar** (befintliga combat-tester orörda).
  843 gröna.
- **Vad:** `apply_effect` (209 rader, 14 effekt-typer i en if/elif-kedja), `resolve_action` (~80) och
  `game.run_combat_turn` (114) fasindelas: effekt-typ → handler-tabell (`EFFECT_HANDLERS[type]`),
  turn-flödet → namngivna faser (initiativ → aktion → on-hit → statusar → cooldowns → utfall).
- **Avsikt:** Varje ny mekanik (B41-procs var senast) växer samma funktioner; en dispatch-tabell gör
  nästa effekt-typ till en isolerad handler + test i stället för en ny gren mitt i 209 rader.
- **Not:** REN refaktor, beteende-bevarande — 794 gröna tester är skyddsnätet; kör sviten per
  extraherad handler. INGA balansändringar i denna post. STEG 0: lista alla effekt-typer + var de
  konsumeras (combat + talents + upgrades delar EffectSpec).
- **Acceptans:** apply_effect < ~40 rader dispatch; en handler per effekt-typ med egna tester;
  run_combat_turn läsbart fasindelad; sviten grön utan testdiffar.

#### B59 — Save-schema-härdning  · ✅ **KLAR**
- **KLAR:** (a) `SAVE_VERSION=2` + `MIGRATIONS`-tabell (1→2 materialiserar de gamla ad-hoc-reglerna:
  last_rest_place_id→respawn, wisdom ur max_mana, ranks ur learned); (b) EN central `PLAYER_FIELDS`-
  tabell driver serialize+deserialize (39 fält) + `DERIVED_FIELDS` deklarerade (5: max_mana/gear_mods/
  talent_skill_ranks/upgrade_bonuses/weapon_components — rebuilds vid load verifierade i koden);
  (c) `verify_invariants` vid load (talent_ranks ↔ learned, namngivet fel → LoadResult(False));
  (d) coverage-test failar när nytt Player-fält saknar klassificering + round-trip genom RIKTIG JSON
  med icke-default i varje fält. STEG 0-fynd: upgrade-rebuilds sker via recompute_gear_modifiers→
  recompute_upgrade_modifiers (kommentarernas påstående verifierat). 10 nya tester; 2 legacy-fixtures
  uppdaterade till migrations-ingången. 819 gröna.
- **Vad:** (a) Bumpa `SAVE_VERSION` vid varje schemaändring + en migrations-tabell (version→migrering)
  i stället för ad-hoc-funktioner; (b) central serialize/deserialize-tabell för Players ~50 fält så nya
  fält inte kan glömmas i endera riktningen; (c) invariant-verifiering vid load (talent_ranks ↔
  learned_talent_ids; deriverade fält REBYGGS alltid: talent_skill_ranks, upgrade_stat_bonuses,
  weapon_upgrade_components); (d) round-trip-test som failar när ett nytt Player-fält saknar
  serialisering.
- **Avsikt:** Saven är spelarens hela progression. Schemat har vuxit kraftigt (ranks, upgrades, tomes,
  wisdom, fog-bitset) på version 1 med invarianter som bara lever i kommentarer — en glömd rad i
  persistence = tyst progressionsförlust.
- **Not:** STEG 0: inventera vilka Player-fält som persisteras vs deriveras idag (kommentarerna påstår —
  verifiera mot koden) och skriv round-trip-testet FÖRST så gapet syns. Bakåtkompatibilitet: gamla
  v1-saves ska fortsätta ladda (migrations-tabellen börjar med dagens migreringar).
- **Acceptans:** round-trip-test över alla persisterade fält; invariant-check vid load med tydligt fel;
  nytt-fält-utan-serialisering får testet att faila; gammal save laddar via migrations-tabellen.

#### B60 — Terminal-lagrets öde  · ✅ **BESLUTAT: (a) debug-/röktest-läge** (Lucas-GO på våg 1-planen)
- **Beslut:** alternativ (a) — terminal.py deklareras som **debug-/röktest-läge** med uttalad
  feature-frysning (nya features byggs i Pygame, porteras ej; terminal-hål = by design). Dokumenterat
  i CLAUDE.md (Status) + README (körnings-avsnittet, med exempel på vad läget saknar). Ingen kod ändrad.
- **Vad:** `terminal.py` (809 rader) är `__main__`-entrypoint och testad, men har driftat: saknar
  upgrade-stationer, tome-shop, minimap m.m. Besluta: (a) deklarera det som debug-/smoke-läge med
  uttalad feature-frysning (dokumentera vad det INTE stödjer i README/CLAUDE.md), eller (b) lyfta det
  till paritet, eller (c) pensionera det (entrypoint → pygame). Rekommendation: (a) — det är billigt,
  testbärande och bra för core-rök, men ska inte låtsas vara ett fullt spel-läge.
- **Avsikt:** Odefinierad status gör att varje ny feature tyst ökar driften och ingen vet om ett
  terminal-hål är en bugg eller by design.
- **Not:** Rent beslut + dokumentation vid (a); (b) är en egen större post och föreslås INTE nu.
- **Acceptans:** beslut fattat och dokumenterat; vid (a) en rad i CLAUDE.md om terminal-lägets scope.

#### B61 — Verktygs-hygien: worldgen-skripten ur repo-roten  · ✅ **KLAR**
- **KLAR:** 7 skript flyttade till `rpg_game/tools/worldgen/` (git mv); `generate_bridge_halfdecks.py`
  **raderad** (grep bekräftade 0 kod-/test-referenser — bara backloggens egen notis). README med
  regen-flöde + **determinism-varningen** (delad rp-ström → orelaterade dekor-diffar; granska TMX-diffen
  som helhet). Fixat vid flytt: `overworld_layout._DATA` (__file__-relativ → ../../data),
  `regenerate_overworld`s sibling-import + 3 test-importer → paket-sökvägar. Modul importerbar +
  datapath verifierad. Roten fri från .py-skript. 843 gröna. *Observation (utanför scope): `scratchpad/`
  ligger också spårad i roten — kandidat för egen städning.*
- **Vad:** Åtta skript i repo-roten (`regenerate_overworld.py`, `overworld_layout.py`, `recolor_themes.py`,
  `crispen_water.py`, `unify_overworld_theme.py`, `generate_water_autotiles.py`, `extend_verralda.py`,
  `generate_bridge_halfdecks.py`) flyttas till `rpg_game/tools/worldgen/` med en README som beskriver
  regen-flödet + determinism-varningen (regen shufflar delad rp-ström → orelaterade diffar).
  `generate_bridge_halfdecks.py` är orefererad — verifiera och radera eller dokumentera.
- **Avsikt:** Roten ska visa spel + dokumentation, inte engångs-verktyg; determinism-fällan har redan
  bitit oss en gång (bush-fixen) och ska stå skriven vid verktygen.
- **Not:** STEG 0: grep import-/doc-referenser per skript (uppmätt: bridge_halfdecks=0 refs) innan
  flytt/radering; uppdatera sökvägar i docs som pekar på dem.
- **Acceptans:** roten fri från worldgen-skript; tools/worldgen/README med regen-flöde + varning;
  inga trasiga referenser; orefererat skript raderat eller motiverat.

#### B62 — Sim-utökning: ekonomi- och loot-flödesmätning  · ✅ **KLAR**
- **KLAR (2026-07-06):** `simulate_economy_band` i `core/simulation.py` (mäter via
  RIKTIGA spawn-vägen `world.create_encounter` inkl. rare-rolls; deterministisk per
  seed; delat content → snabb) + CLI `python3 -m rpg_game.tools.simulate_economy`.
  Rapport per zon-band: win%, guld-in (kill + säljvärde av drops), drop-rate +
  rarity-fördelning, material-inflöde, rest-tryck (skada/fight → fights/rest →
  guld-ut/fight) och NETTO guld/fight. 5 tester (identitets-/formel-lås). **N=300-
  fynd (fighter, seed 42):** netto/fight 11→56→59→108g över banden; **säljvärdet av
  drops passerar kill-guldet från skogen** (59 vs 26g) — droptabellerna är ekonomins
  verkliga spak; **rest slutar vara en sink efter cainos** (~19-28g/fight mot 56-108g
  inflöde). Tuning-underlag till B8 2b/B22: late-sinks bör prisas mot ~50-100g/fight-
  överskott. Inga balansändringar (mätverktyg).
- **Vad:** Bygg ut `core/simulation.py` med en ekonomi-harness: simulera N resor/fights per level-band
  och rapportera guld in (drops, sälj) / guld ut (rest, potions, upgrades, resor), drop-rates per
  rarity/tier (N≥200), och material-inflöde (miscellaneous per zon). Encounter-delen förutsätter B55.
- **Avsikt:** B22 (enchant-priser), B8 2b (butiksinnehåll per stad) och framtida guld-sinks ska tunas
  mot mätdata, inte ögonmått — samma princip som weapon-aware-simmen gav B37.
- **Not:** MÄTVERKTYG, ingen balansändring. STEG 0: definiera rapportformatet med Lucas (vilka kolumner
  gör tuning-beslut möjliga). Tuning-poster som följer av mätningen skapas separat och märks *tuning*.
- **Acceptans:** en sim-körning ger guld-in/ut + drop-rate-tabell per level-band; deterministisk med
  seed; används i minst en verklig tuning-fråga (t.ex. rest-kostnad vs guld-inflöde) som beslutsunderlag.





  ### Nya system (expansionsdesign 2026-07-04, arkitekt)

#### B63 — Lootkistor i världen  · ✅ **KLAR (S1+S2)** · render-verifierad headless
- **KLAR:** 16 kistor (4/zon, BFS-verifierade vildmarks-tiles) i `chests.json` med per-zon
  guld-band + viktade tier-cappade tabeller (cainos cap2 → heath cap4; **chest_heath_4 cap5** =
  bortersta hörnets godbit med veteran_ring/yew_warbow). `core/chests.py` + `engine.open_chest`
  (samma LootDrop/collect-väg som enemy-drops, seedad rng); `opened_chest_ids` persist (B59-tabellen).
  **STEG 0-fyndet höll:** props-arken har BÅDE stängd (96,30,32,31) och öppen (96,76,32,49) kista i
  alla tema-recolours — ingen improviserad open-sprite behövdes. Kistor solida (blockerar), **E bredvid**
  öppnar (dörr-mönstret), logg: "You open the chest" + guld (amber) + "Loot: X" (rarity-färg).
  Load-validering à la B54 (`_validate_chests`). 13 tester (core/data/UI); 856 gröna. Headless-render
  verifierad stängd→öppen. *Kart-pin för öppnad kista = valfri framtida polish; B64 konsumerar systemet.*
- **Vad:** Placerade kistor i overworlden som spelaren går fram till och öppnar → loot-roll (guld,
  materials, ibland gear/vapen ur zonens tabell). Kistan byter till öppen sprite och förblir tömd
  (persisterad). Sex tema-varianter finns REDAN som färdig art (moss/swamp/neutral + snow/frost/ash
  för framtida zoner) — de saknar bara ett system. Spelarens upplevelse: fog-kartan avslöjar inte
  bara terräng längre; bakom udden kan det stå något att HITTA.
- **Avsikt:** Utforskning belönas idag bara med karta-avtäckning och encounters. Kistor ger fysiska
  upptäckter — skäl att gå den längre vägen, kolla vikar, runda minisjön (B45).
- **Not:** Hakar i: loot-/rarity-systemet (B6-droptables, authored rarity), persistens (öppnade kistor
  → save, jfr revealed_tiles-mönstret), fog/minimap (öppnad kista kan bli kart-pin), zonteman.
  Placering authoras i core_zone-stil (data). STEG 0: var i pipelinen props ritas + kollideras så
  kistan blir interagerbar à la dörr. Rarity-viktning per zon-band ska respektera rare_tier_cap.
  KONKURRENS: B64 (dungeons) vill använda samma kist-system som rums-belöning — bygg DENNA först,
  B64 konsumerar den.
- **Slices:** (1) kist-entitet + interaktion + loot-roll + persistens, 3–5 handplacerade kistor i
  cainos (render-HALT); (2) zon-utrullning med per-zon-tabeller + tema-sprites + kart-pin;
  (3) [valfri] sällsynt "låst kista" som kräver nyckel-item (drop från elit) → mini-mål.
- **Acceptans:** kista syns/öppnas/lootar/förblir tömd över save-load; loot respekterar zon + tier-cap;
  minst N kistor per zon; tester för roll + persistens.

#### B64 — Dungeons: instansierade interiörer med kurerade strider  · ⏸ **PARKERAD** (Lucas 2026-07-06: "Låt dungeons vara, vi återkommer till dem när vi har en map som stödjer detta") · *innehållssystem* · stor · risk MEDEL-HÖG
- **Vad:** Ingångar i världen (grotta/ruin/gravvalv) som leder till en egen liten karta (5–10 rum i
  eget TMX): kurerade encounters i stället för slump, ett tema (t.ex. spindelbo → vermin), en
  loot-kista (B63) i slutet och plats för en boss (B65). Spelaren kan lämna, men läkning är begränsad
  därinne → ett åtagande, inte en promenad. Upplevelsen: "jag går IN i något" — koncentrerad fara
  med tydlig payoff, mot overworldens strösslade encounters.
- **Avsikt:** All strid sker idag på samma yta med samma rytm. Dungeons ger loopen kadens:
  förberedelse (potions, rätt vapen mot temat via skadestegen) → åtagande → klimax → hemresa.
- **Not:** Hakar i: TMX-pipeline (Overworld-klassen kan sannolikt återanvändas för interiör-kartor —
  STEG 0: mät vad som är overworld-specifikt i den), encounter-taktning (kurerade rum i st. f. rate
  — bygger renare OVANPÅ B55 om den godkänns), B63-kistor, trait-teman (max 2 traits styr dungeonens
  identitet), B48-authoring (dungeon = extremfallet av per-område-spawn). Kräver interiör-tileset
  (Cainos har grott-/dungeon-set — verifiera licens/tillgång, annars begränsad ny asset-yta).
  STÖRSTA nya system i listan → egen designrunda före bygge (rum-graf? nycklar? respawn?).
- **Slices:** (1) interiör-kartladdning + in/ut-övergång med EN handbyggd testdungeon utan strid
  (render-HALT); (2) kurerade encounters per rum + begränsad läkning + kista i slutet; (3) första
  riktiga dungeonen (tema, 5–10 rum, authored i data); (4) boss-rum (kopplar B65).
- **Acceptans:** ingång→interiör→utgång stabil inkl. save inne; kurerade strider triggar per rum;
  temat läses (fiender+tileset); kistan i slutet lootar; reachability i interiören verifierad; tester.

#### B65 — Zonbossar + huvudmål (spelets ryggrad och slut)  · ✅ **KLAR (S1+S2+S3)** · render-verifierad headless
- **KLAR (2026-07-06, Lucas-GO "bygg som HALT-hanterare"):** 5 namngivna bossar
  (`bosses.json` + `enemies.json "boss": true`) — **Rotfang** (cainos L4, beast+vermin),
  **Briar Queen** (skog L8, plant), **Hagmother Yagra** (mire L10, cursed+swamp),
  **Barrow King** (heath L12, undead+cursed), **Pale Sovereign** (Pale Gate L13,
  spirit+cursed, kräver de fyra). Allt på befintliga primitiv: telegraph + `self_hp_below`-
  fas-AI + statusar + trait-matrisen (17 nya actions, inga nya mattesystem).
  `core/bosses.py` (challenge-gating, engångsbelöning, huvudmålsstatus) +
  `defeated_boss_ids` persisterat via B59-tabellen; `_validate_bosses` fail-fast
  (okänd fiende/reward/requires, boss i wild-pool, lya-kollision). **Overworld-lyor:**
  bossen står SYNLIG på sin tile (fälld = mörknad husk), E armar → E utmanar, stads-
  distans ≥8 verifierad; flee/död lämnar lyan öppen. **Slutet:** alla 4 → Pale Gate →
  victory-skärm (credits + Continue), visas EN gång. Guld-nameplate "[BOSS]", namngivna
  bossar utan artikel. **Sim N=200** (skills, bästa kategorivapen): rätt verktyg on-level
  41–96 %, fel verktyg 0–41 % — förberedelsen ÄR fajten; `sanctified_recurve` (ranged/
  holy, loot på heath-undead) täpper hunterns holy-lucka. **Kända fynd:** mage-skörheten
  (B25) gör L10+-bossar till sim-väggar för mage → eskalerad till klassbalansrundan;
  boss-belöningar = deterministisk lya-grant (ej droptabell; loot-policytest uppdaterat).
  Placeholder-art = kin-kopior (`boss_*.png` ×5) — Lucas genererar riktig art.
  19 nya tester; **919 gröna**. ENEMIES.md har boss-sektionen.
- **Vad:** En namngiven boss per zon (4 st) med signaturmekanik byggd på BEFINTLIGA primitiv — främst
  telegraferade laddningsattacker (charging_action_id finns redan i combat) + statusar + trait-matrisen
  (max 2 traits, fasta stegen: bossen är inget nytt mattesystem, bara en STARK, läsbar fiende med
  faser via hp_percent-AI som redan finns). Att fälla alla fyra öppnar slutkonfrontationen → spelet
  får ett SLUT med victory-skärm. Upplevelsen: en riktning ("jag är här för att...") och fyra
  minnesvärda väggar som kräver förberedelse.
- **Avsikt:** Loopen saknar mål — inget "klart", ingen anledning att bli stark UTÖVER att bli stark.
  Bossar ger progressionen en adress och zonerna varsin krona.
- **Not:** Hakar i: enemy-AI:ns ai_condition_met/hp_percent (fas-beteende), charging (telegraph),
  traits/resistanser (bossens svaghet lär spelaren skadestegen), turnerings-buffmönstret (stat-
  skalning finns), B64 (boss-rum är naturliga hem — men v1 kan bo i overworld-lyor för att inte
  blockeras av dungeons), B23-quests (huvudmålet KAN uttryckas som quest-kedja när B23 finns — inte
  ett beroende). Belönings-items = designbärande (HALT, Lucas väljer signatur). STEG 0: mät vad
  enemy-AI:n klarar idag (multi-fas? summon?) innan signaturmekanik låses.
- **Slices:** (1) boss-ramverk: elit-markering, fas-AI via hp-trösklar, telegraph-mönster + FÖRSTA
  bossen i en overworld-lya (render+balans-HALT); (2) bossar 2–4 med varsin signatur + zon-placering;
  (3) huvudmåls-arc: bossräknare, slutkonfrontation, victory-skärm + credits.
- **Acceptans:** varje boss har läsbar signatur (telegraph syns i loggen/UI), är klarbar on-level med
  förberedelse (sim N≥200 för extremer, playtest för känsla); alla fyra → slutstrid → victory-skärm;
  persistens av fällda bossar; tester för fas-AI.

#### B66 — Bestiarium (kunskaps-codex över fiender)  · ✅ **KLAR (S1+S2)** · render-verifierad headless
- **KLAR:** `core/bestiary.py` — mött/identifierat/kills på spelaren (3 nya persist-fält via
  B59-tabellen); **upplåsning = Identify EN gång ELLER 5 kills** (`KILL_UNLOCK`). Engine-hooks:
  `create_encounter`→seen, `_handle_victory`→kill-count, Identify→identified. **Codex-skärm på B**
  (overlay): vänster roster (32 vilda, sorterad på nivå; osedda = "???" dimmade via restricted-stilen,
  "> "-markör + Lv-band på upplåsta; piltangenter + klick), höger detaljer — sprite (silhuett tills
  upplåst: mörkfylld alpha-kopia), nivåband, kills, traits, **färgade svagheter** (Weak grön / Resists
  amber / Immune röd ur resistansmatrisen) + abilities. **Designval:** arena-duellanter exkluderade
  (människor ≠ vilda fauna; codex = 32 av 42). 11 tester; 867 gröna. *Slice 3 (samlar-belöning) = ej byggd.*
- **Vad:** En codex-skärm (meny-val) som fylls i medan man spelar: möt en fiende → namn+silhuett
  registreras; använd Identify (finns redan: identify_enemy/EnemyReveal) eller döda N st → traits,
  resistanser, skills och loot-tabell låses upp. Upplevelsen: skadestegen och trait-systemet — spelets
  taktiska kärna — blir SYNLIG kunskap man samlar, i stället för något man måste komma ihåg från
  stridsloggen.
- **Avsikt:** Trait/resistans-systemet är djupt men osynligt mellan strider; Identify är underanvänt.
  Bestiariet gör lärandet till progression och belönar att möta ALLT (42 fiender är värda att visa upp).
- **Not:** Hakar i: EnemyReveal (datat finns — det saknar bara persistens + skärm), enemy-sprites
  (porträtt = befintlig art nedskalad), B40-menyspecen (bygg skärmen MED den delade UI-grunden +
  hover-tooltips), save (sedda/identifierade per enemy_id). Ev. liten belöning vid komplett zon-
  sida (guld/titel) = valfri slice. STEG 0: vad EnemyReveal exponerar idag vs vad codexen vill visa.
- **Slices:** (1) persistens av mött/identifierat + codex-skärm med namn/sprite/nivåband (render-HALT);
  (2) upplåsning av traits/resist/loot via Identify-eller-N-kills + hover-detaljer enligt B40-spec;
  (3) [valfri] samlar-belöning per komplett zon.
- **Acceptans:** möt→syns, identifiera→detaljer; persisterar; skärmen följer menyspecen; tester för
  upplåsnings-regler.

#### B67 — Reshändelser (text-val i vildmarken)  · 🟢 **S1 KLAR** (e8dce81: event-motor + 3 cainos-events, 10% av slots) · ⏸ **S2 PARKERAD (Lucas-beslut 2026-07-11):** bygg INTE per-zon-tabeller tills vidare
- **Vad:** Sällsynt (i st. f. en encounter) triggas en text-händelse i loggen/panel med 2–3 val:
  "En övergiven kärra: rota igenom (loot, risk för bakhåll) / gå vidare" · "Ett vägaltare: offra 20
  guld (+buff till nästa strid) / vila blicken (+liten heal)" · "Skadad handelsman: hjälp (guld senare
  i staden) / ignorera". Utfall använder BEFINTLIGA primitiv: guld, items, statusar, encounter-start.
  Upplevelsen: vildmarken pratar — resor får smak och små beslut utan en enda ny asset.
- **Avsikt:** Mellan strider är resandet händelselöst; events ger variation och återspelbarhet till
  själva vandrandet — den aktivitet spelaren gör mest av.
- **Not:** Hakar i: encounter-rollen (event ersätter en encounter-slot — renast OVANPÅ B55 i core så
  sim kan räkna event-frekvens), chatlog/overlay-UI (valen som knappar via delade Button), economy,
  statussystemet (buff till nästa strid = ActiveStatus). Events authoras i data (events.json:
  villkor per zon, vikt, val→utfall). Ton/texter = Lucas godkänner (HALT på första batchen).
  STEG 0: var i maybe_encounter-flödet en event-gren renast hakar in.
- **Slices:** (1) event-motor (data-driven: trigger, val, utfall) + 3 handskrivna events i cainos
  (HALT på text+frekvens); (2) zon-specifika event-tabeller (~4–6/zon) + villkor (nivå, guld);
  (3) [valfri] kedje-event ("handelsmannen minns dig" vid stadsbesök).
- **Acceptans:** event triggas med authored frekvens; val ger deklarerade utfall; per-zon-tabeller;
  determinism med seed; tester för motor + utfall.

#### B68 — Alkemi: brygg potions av materials  · ✅ **KLAR (S1+S2)** · render-verifierad headless
- **KLAR:** `core/alchemy.py` + `brews.json` (6 recept: lesser_hp/hp/mana/antidote/greater_hp/
  greater_mana av rat_pelt/bone_dust/tattered_cloth/worg_tooth/grave_iron/chill_crystal/blessed_ash) —
  konsumera material+guld → potion. **Balansregel test-låst:** varje brygd billigare än butikspris
  (inkl. materialvärde) men aldrig gratis; greater-pots får en ny förvärvsväg (butiker säljer dem
  fortfarande inte — konsistent med mana-ekonomins regel). Load-validering (okänt output/material →
  ValueError). Apothecary-skärm: rad per recept med have/need per material + guld, dimmad tills
  bryggbar; klick bryggar + loggar. **Motiverat beslut (interim):** apothecary-byggnaden är kuliss
  utan dörr (B8 2b:s jobb) → bryggningen bor i general-shopens meny ("Brew potions") och flyttas till
  apothecary-dörren när den finns (en rad). 9 tester; 876 gröna. *Zon-resistans-brygder = framtida
  (kräver consumable→status-wiring).*
- **Vad:** Apothecary-byggnaden (finns som kuliss i B8) får en funktion: brygg potions av
  miscellaneous-materials + guld — recept i upgrade-receptens stil (venom_gland+bone_dust → antidote;
  2×herb → hp-potion; zonmaterial → resistans-brygd mot zonens skadetyp). Upplevelsen: dropp-högen
  med "skräp" blir råvaror, och förberedelse inför en svår strid (boss! dungeon!) får en verkstad.
- **Avsikt:** Materials har idag EN sink (item-upgrades, engångs). Alkemi ger en ÅTERKOMMANDE sink +
  gör consumable-ekonomin spelardriven i st. f. bara butiksköpt.
- **Not:** Hakar i: upgrade-systemets recept-mönster (samma dataform, annan output — STEG 0: mät hur
  mycket av upgrades.py som kan återanvändas rakt av), miscellaneous-items (B42 la zon-material),
  B8 2b (apothecary-triggern — kan bygga före eller efter), B63/B64/B65 (kistor/dungeons/bossar
  matar och motiverar brygderna). DESIGNUTRYMMES-KONKURRENS med B22 (enchant-vendors): båda är
  material+guld-sinks vid stationer. REKOMMENDATION: alkemi FÖRE enchants — mindre (consumables är
  enklare än permanenta item-modifikationer), återanvänder upgrade-mönstret rakare, och ger B65-
  bossarna förberedelse-djup direkt. B22 därefter med lärdomarna.
- **Slices:** (1) recept-data + brygg-core (konsumera→skapa, persistens ej nödvändig — potions är
  vanliga items) + tester; (2) apothecary-UI enligt B40-menyspecen (render-HALT); (3) recept-batch
  per zon (zonmaterial → zon-relevant brygd) + balans-pass mot droprates (sim/B62 om godkänd).
- **Acceptans:** recept konsumerar material+guld och ger item; UI visar krav/ägt (dämpat om ej
  råd, B40-spec); zonrecept känns zonknutna; ingen brygd trivialiserar (extremkoll via sim); tester.

#### B69 — Ljud: musik + effekter (pygame.mixer)  · ✅ **S1+S2 KLARA + musik-grund** (audio-HALT godkänd 2026-07-10)
- **KLART (`a7b54fe` + reglage `5afe898`):** `presentation/audio.py` — graceful mixer (tyst läge utan
  device; CI/dummy verifierad åt bägge håll), WAV-cache, reserverad walk-kanal, volym = master × sfx ×
  per-ljud-GAIN (walk/DoT lågt). 16 egengjorda ChipTone-SFX (CC0, se `ASSETS_LICENSES.md`) wirade:
  playback-ridande stridsljud (basattack = bara träffen; magic_cast båda sidor, physical_cast endast
  spelaren; potion-gulp ≠ skill-heal; DoT-tick; skip-flush tyst; level_up/die i finalen), encounter
  (vild/boss/turnering), menu_click överallt inkl. creation, walk var 2:a tile, chest/brew/sell/
  overworld-potions. **Musik:** `Pixel Heart.ogg` (tempo −10 % via ffmpeg atempo) loopar på
  mixer.music-strömmen från första skärmen, sömlös över shell-byten; `MUSIC_GAIN 0.48` efter Lucas
  lyssningsrunda. **B70 S2 samtidigt löst:** 0–100-reglage (klick/drag, live, persist på släpp) i
  Settings-overlayn; nya settings-nycklar sound_master/sound_sfx/sound_music. 32 tester i
  `test_b69_audio.py`.
- **Kvar (S3-rest, ny slice vid behov):** filer saknas för crit/seger/loot/köp/dörr/boss-telegraf;
  per-zon-/stridsmusik + crossfade (en global loop idag). OGG-källans licens: Lucas bekräftar.
- **Vad (ursprung):** Spelet är idag HELT tyst. Lägg ett tunt ljudlager: zonmusik (en loop per zon + stads-tema),
  stridsmusik, och effekter för de tunga ögonblicken (träff, crit, level-up, loot, kista, dörr,
  knapptryck). Upplevelsen transformeras för i princip varje minut av spel — tystnad → atmosfär.
- **Avsikt:** Känsla/atmosfär är loopens mest eftersatta dimension; ljud är den enskilt största
  förändringen per byggtimme som finns kvar i projektet.
- **Not:** Hakar i: pygame.mixer (finns i beroendet redan — ingen ny teknik), event-punkter som redan
  är tydliga i koden (resolve_battle_outcome, push_log-ögonblicken, level-up-modalen, dörr-interaktion).
  ASSET-KÄLLA = risken: CC0-bibliotek (Kenney/OpenGameArt/freesound) håller assetbördan rimlig för
  två personer — Lucas väljer/godkänner paletten (HALT på ljudval, precis som sprites). Volym-
  kontroll kräver B70 (bygg B70:s skelett först eller ihop). STEG 0: mixer-init headless-säkert
  (CI/tester får inte kräva ljuddevice — dummy-driver).
- **Slices:** (1) ljudmotor: init, kanaler, volym-API, graceful headless + 3 UI-ljud (HALT på känsla);
  (2) stridsljud (träff/crit/seger/nederlag) + level-up/loot; (3) musik: zon-loopar + strids-tema +
  crossfade vid battle-övergång.
- **Acceptans:** ljud spelar vid deklarerade händelser; volym justerbar (via B70); headless-körning
  tyst utan krasch; assets licens-dokumenterade; sviten grön.

#### B70 — Inställningsmeny  · ✅ **KLAR (S1)** · render-verifierad headless
- **KLAR:** `presentation/settings.py` (settings.json i roten, gitignorerad; defaults-merge, aldrig-
  krascha-skrivning, call-time-path för testbarhet). **Appliceras vid uppstart** (fullscreen före
  första display-mode; log-rader clampade; minimap). **Alla tre mutatorer persisterar direkt** (F11,
  +/-, N — och samma reglage i skärmen). **Två ingångar:** in-game Esc→System→Settings (overlay med
  Fullscreen/Log rows −+/Minimap + tangent-översikt) och **startmenyns Settings** (egen mini-loop,
  cykla-på-klick). Fullscreen-toggle-testet + b70-testerna isolerade mot tempfil (fångade en äkta
  test-föroreningsbugg: toggle-testet skrev riktiga settings.json). 7 tester; 893 gröna.
  *S2 ✅ KLAR med B69 (`5afe898`): musikvolym-reglage 0–100 i Settings-overlayn.*
- **Vad:** En Settings-skärm (från startmeny + ESC-meny): musik-/effektvolym (B69), fullskärm/fönster
  (toggle finns — får ett hem), loggstorlek (resize_log finns — får UI), och en läsbar tangent-
  översikt (M/K/C/I/ESC…). Inställningar persisteras i en settings.json separat från saven.
  Upplevelsen: spelet känns som en produkt, inte ett prototyp-fönster.
- **Avsikt:** Reglagen finns utspridda som tangenter utan upptäckbarhet; ljudet (B69) KRÄVER volym-
  kontroll. Billigaste "färdigt spel"-signalen i listan.
- **Not:** Hakar i: B40-menyspecen (byggs som första NYA skärm på delade grunden — bra stresstest av
  S1-komponenterna), pygame_canvas (fixed-layout-mönstret för startmenyn finns), B69 (volym-API).
  STEG 0: inventera alla runtime-reglage som idag bara nås via tangent.
- **Slices:** (1) settings-skärm + persistens (fullskärm, loggstorlek, tangent-översikt) (render-HALT);
  (2) volymreglage när B69 S1 finns.
- **Acceptans:** nås från start+ESC; ändringar tar effekt direkt + persisterar över omstart; följer
  B40-spec; tester för persistens.

#### B71 — Save-slots + autosave + dödsflöde  · ✅ **KLAR (S1+S2)** · render-verifierad headless
- **KLAR:** `core/saveslots.py` — 3 slots + autosave under `saves/` (gitignorerad) med billig metadata-
  peek (namn/klass/level/plats/**speltid** — nytt persisterat fält `playtime_seconds`, tickat av
  run-loopen). **Startmenyn** listar slots+autosave med metadata ("Slot 1 — Rt · Mage · Lv 7 · 2h 13m");
  ny "load:<path>"-val i `engine_from_start_choice` (legacy "load" + explicit-path-tester orörda);
  gamla root-`savegame.json` **migreras till slot 1** en gång. Nytt spel tar första lediga slot; manuell
  save skriver spelarens slot. **Autosave** vid stadsentré + efter segrad strid (loggad dimmat, ej vid
  uppstart-i-stad). **Dödsskärm** "You fell." — Rise at <plats> (straffet redan draget av core) / Load
  autosave / Load slot N, med resync av sprite. 13 tester (patchade tempdir-paths); 2 gamla lås
  uppdaterade till avsedda B71-beteendet. 886 gröna.
- **Vad:** Tre namngivna save-slots (i st. f. hårdkodade savegame.json) med metadata i menyn (namn,
  klass, level, plats, speltid) + AUTOSAVE vid stadsentré och efter strid (separat slot) + ett värdigt
  dödsflöde: "Du föll" → ladda senaste autosave / senaste manuella / huvudmeny. Upplevelsen: trygghet —
  experimentera, dö mot en boss (B65!), förlora minuter i stället för timmar.
- **Avsikt:** En slot + bara manuell save är riskabelt precis när spelet får farligare innehåll
  (bossar, dungeons). Skyddar spelarens tid.
- **Not:** Hakar i: persistence (ren utökning av path-hanteringen; RIDER på B59-härdningen om den
  godkänns — annars fristående), start_menu_options (slot-väljare ersätter binär new/load),
  resolve_battle_outcome (autosave-krok + dödsflödet bor där). STEG 0: mät nuvarande death→respawn-
  flöde innan dödsskärmen läggs på. Speltids-räknare = nytt litet persisterat fält.
- **Slices:** (1) slot-infra (3 slots + metadata + väljar-UI i startmenyn); (2) autosave-krokar
  (stadsentré, post-battle) + dödsskärm med laddningsval (render-HALT).
- **Acceptans:** tre slots med metadata; autosave triggar deklarerat; död → val fungerar; gamla
  savegame.json migreras till slot 1; tester för slot-IO + autosave-trigger.

#### B72 — Stridskänsla: flytande skadesiffror + träff-feedback  · ✅ **KLAR (S1+S2)** · frame-verifierad headless
- **KLAR:** per skade-komponent flyter "-N" upp och tonar ut (typ-färgad: physical vit / fire orange /
  frost isblå / poison grön / holy guld / lightning gul; **crit = stor font + "!" + skärmskak** 6 frames);
  heals flyter gröna "+N" över helaren; **målet blinkar vitt** 2 frames (enemy-sprite BLEND_RGB_MAX,
  hero-boxen ljus); **hit-pause 3 frames på dödsslag** (floaters fryser). Datat kommer ur
  `ActionResolution.damage_components` som förutsett — inga regeländringar. Skaken appliceras på
  canvasen FÖRE present() → skalningen intakt. **Av/på via `combat_fx`** i settings.json + rad i
  settings-skärmen (B70-kroken). 7 tester; 900 gröna. Frame-sekvens verifierad (flash+floater → norm+stigen).
- **Vad:** När skada landar: siffran flyter upp från målet och tonar ut (färg efter skadetyp/crit —
  återanvänd chatlog-paletten), målets sprite blinkar vit en frame, en kort skärmskakning på crits
  och tunga träffar, ~2 frames hit-pause på dödsslag. Upplevelsen: varje träff KÄNNS — striden får
  vikt utan en enda regeländring.
- **Avsikt:** Striden är mekaniskt djup men taktilt platt; detta är billigaste vägen till att varje
  strid (spelarens vanligaste aktivitet) känns bättre.
- **Not:** Hakar i: pygame_battle (sprite-rendering + en enkel partikel/float-lista i draw-loopen),
  ActionResolution/DamageComponent (siffror + typ finns i resultatet REDAN — per-träff-datat räcker
  för siffror även innan B44:s strukturerade LOGG-events; notera relationen: B44 handlar om loggen,
  detta om scenen), chatlog-paletten (färgkonsekvens). STEG 0: mät var i battle-draw ett flytande
  lager renast ligger + att skakning inte stör canvas-skalningen (pygame_canvas-offset).
- **Slices:** (1) flytande skadesiffror + vit blink (render-HALT); (2) skärmskak på crit + hit-pause
  på kill + [valfri] enkel partikel-puff vid död.
- **Acceptans:** siffror/blink/skak triggar rätt och stör inte layouten (canvas-skalning intakt);
  kan stängas av (krok för B70); render-review; sviten grön.

#### B73 — Zon-ambiens: partiklar + ljus-overlay per zon  · ✅ **S2 KLAR + ALLA PRESETS GODKÄNDA** (Lucas GO 2026-07-12: cainos/cursed_mire/grave_heath inkopplade ur utkastfilen; mork_skog sedan nattbatch) — preset-tabell + "Ambience"-toggle klara
- **Vad:** Ett tunt atmosfärslager i overworlden per zon: eldflugor/pollendamm i mork_skog, låg
  dimslöja som driver i cursed_mire, aska/gnistor i grave_heath, varmt dis i cainos — några dussin
  långsamma partiklar + en svag färg-overlay. Upplevelsen: zonerna FÅR sin stämning i rörelse, och
  det mildrar synligt de hårda zon-färgskarvarna (B47) utan att röra tema-PNG:erna.
- **Avsikt:** Zonerna skiljer sig i palett men känns statiska; ambiens ger identitet per zon och är
  delvis ett svar på B47:s öppna art-beslut på systemväg i stället för asset-väg.
- **Not:** Hakar i: _draw_map-pipelinen (partikellagret ovanpå världen, FÖRE HUD — STEG 0: mät fps-
  utrymme med viewport-culling + zoom, partiklar i skärmrymd inte världsrymd för billighet),
  zone_for_tile (val av preset), B47 (relationen: B73 mildrar, B47 löser grund-paletten — säg det
  öppet; B73 kan göra B47 onödig eller vice versa → Lucas väljer väg efter S1-render).
- **Slices:** (1) partikelmotor + EN zon (mork_skog eldflugor) (render+fps-HALT); (2) preset per zon
  + svag färg-overlay + av/på i settings (B70).
- **Acceptans:** partiklar per zon utan fps-tapp (mät före/efter); togglebar; zon-skarven upplevs
  mjukare (Lucas-review); render-review per zon.