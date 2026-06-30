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

#### B35 — Level-up: välj main-stat (Spår A)  · *nytt — progression*
- Vid varje level-up väljer spelaren EN main-stat av **{HP, Mana, Damage, Crit}** (Speed
  slopas som val). **Universellt + FLAT** — ingen nivå-scaling, ingen per-klass-skillnad.
- Varje level får ALLA stats sin baslinje; den valda main-staten får sitt main-värde i st.:
  - HP: bas **+2**, main **+8**   ·   Mana: bas **+2**, main **+8**
  - Damage: bas **+1**, main **+4**   ·   Crit: bas **+1**, main **+4**
  - Ex: HP main → HP+8, Mana+2, Crit+1, Damage+1.  Crit main → Crit+4, HP+2, Mana+2, Damage+1.
- **Ersätter** de fasta HP/dmg-ökningarna. **Modal-UI** vid level-up (4 val).
- **Absorberar B25:** mage kan välja Mana (+8/lvl) → löser den tidiga mana-bristen själv.

#### B36 — Talent-ranger (upp till 3 steg)  · *nytt — progression*  · ⚠️ **HALT (designbärande) — flaggad**
- Talents kan rankas upp i **upp till 3 steg**; **modest** ökning per rang (t.ex.
  1.6× → 1.8× → 2.0× damage). Mindre behov av många skills/talents — investera klokt i få.
- Talent-points spenderas på ranger; skills/talents-overlay (K) visar rang + tillåter upprankning.
- **HALT-fynd (STEG 0):** talangmodellen matchar INTE "1.6×→2.0× damage"-exemplet. 33/51 noder är
  **active** (ger en skill) utan power-skalnings-väg; 18 passiva spänner över 6 effekt-mekaniker
  (stat_bonus, conditional_damage_mod-multiplikatorer, elemental_attack_mod, immunity,
  applied_status_mod). Rankning kräver (a) per-rang-skala för var och en av dessa + (b) en HELT NY
  per-spelare skill-power-mekanik för de 33 active-noderna = klass-bred ombalansering. **Designval
  för Lucas:** vilka effekt-typer rankas, per-rang-skalning, och hur active/skill-talanger skalar.

#### B37 — Item-damage-rebalans + epic consecrated_maul (Spår A / #2)  · *nytt — ekonomi*  · ⚠️ **HALT (designbärande) — flaggad**
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

#### B28 — Världsexpansion: större karta, glesare städer, kluster i alla (#3)  · *guidad (var batch-kandidat)*
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

#### B38 — Skill-förvärv: mage tower / belöningar  ⭐ designbärande  · *nytt*
- **Vad:** B27-poolen (8 elementala skills) finns men **ingen väg att FÅ dem**. Designrunda:
  var/hur lär man sig dem — **mage tower-byggnad**? butik? turnerings-belöning? — och hur
  **gateas** de (guld/nivå/klass), hur lärs de in (tome-item? meny i huset?).
- **Kopplar:** B27 (poolen), B22 (stads-vendors), B30 (byggnads-menyer), de differentierade husen.
- **HALT:** förvärvs-modellen är designbärande → designrunda med Lucas före bygge.




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

1. **Spår A — batch NU (progression & power-curve, sim-gated):** **B35 ✅** (level-up stat-val,
   `c600efc`) · **B36 ⚠️ HALT** (talent-ranger — talangmodell-mismatch, designval) · **B37 ⚠️ HALT**
   (item-rebalans — +2-tiers/required-level + epic-rarity + skill-sim = designval; baseline mätt).
   + liten polish: **B31 stadsnamn-kontrast ✅** (`faac4ca`). Kombinerad kurva: B35-halvan klar +
   mätt; item-halvan (B37) väntar på Lucas designbeslut. Absorberar B25 (mage Mana-val finns nu).
2. **Spår B — Världsexpansion #3 (B28, GUIDAD):** större karta + glesare stads-prickar +
   kluster i alla städer. STEG 0 på vad regen bryter (ankare/gates/place_ids/turneringar).
   · ⚠️ **HALT (äkta fork, STEG 0 gjord):** hela vatten-systemet (seam y=36, två
   flod-polylinjer CORE_PTS/HEATH_PTS, 5 BRIDGES, hav-kustlinje, LAKE) är HÅRDKODAT till
   80×56 + nuvarande stads-koord — broarna är 2-breda lådor *assertade* på raka flod-
   korsningar nära städer. place_ids/turneringar/respawn är tile-oberoende (remappbara),
   men "större karta + sprid städer + ingen ny terräng" går INTE ihop: rivers/broar måste
   re-författas (= förbjuden terräng-design), och uniform skalning spräcker bro↔flod-
   invarianterna vid avrundning. **Designval för Lucas:** (A) parametriskt vatten-system
   (flod/bro härledda ur stads-grafen) = ny terräng-design, eller (B) uniform skala +
   manuell bro-omjustering (lätt terräng-tuning), eller (C) behåll 80×56, klustra bara de
   städer som får plats (inkrementell B8 Slice 2). Byggde ingen trasig karta.
   · **Skill-aware sim-harness KLAR** (`d79dfeb`) — låser upp B37 caster-tuning.
3. **Innehållets syfte:** **B38** ⭐ (skill-förvärv: mage tower/belöningar) — ger B27-poolen
   en väg in. Sedan **B22** ⭐ (enchant-vendors), **B23** ⭐ (quests/notice boards).
4. **Kollision:** ⭐**B21** (sub-tile — fixar vatten/fences/gates).
5. **Progression-djup:** ⭐**B3.1** (dual-class, HALT) → **B3**.
6. **Värld/utforskande:** **B11** (karta + fog; delar besökt-data med B12/B23).
7. **UI/skärmar:** **B18** (klassvals-skärm fluid); CHARACTER_SCREEN-polish.

> Mät-/designrunda-först: B35-B37 sim-gated; B21/B22/B23/B38/B3.1 ⭐ = designrunda; B28 #3 guidad.
> Klart sedan sist (se arkiv): B16/B26/B27/B28-städer/B29/B30/B31/B32/B33/B34/Slice A/butiker.

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