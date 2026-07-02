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

**✅ Klart (senaste vågen, se arkivet):** hela power-curve-trilogin — **B35** (level-up
stat-val) · **B36** (talent-ranger) · **B37 Slice 1+2** (vapen-rework + upgrade-station-
system) — plus **Wisdom Slice A+B** (härledd mana + caster-tuning), **#3 världsexpansion**
(240×208 parametrisk karta), **B8 Slice 2a** (tier-styrt kluster i alla 17 städer), **B11
Slice 1** (fullskärmskarta + fog), **B40 Slice 1** (enhetlig meny-infra: Button/Tooltip/
HoverTracker/rad-helper), **unified chatbox** (en delad logg-komponent), **B24-flaggan**
(rare-table tier-cap 3 för låg-level wild). Äldre: B1/B5/B6/B7/B7.1/B9/B14/B15/B19/B20/B39.

**▶ Pågår:** **B40 apply-slices S2–S5** (applicera meny-infran på inventory/shop/character/
character-creation — varje = render-HALT) · **B8 Slice 2b** (per-stad butiksinnehåll +
tjänste-triggrar).

**Härnäst (öppet, ej byggt):** *Balans/content (autonom-vänligt):* odöd-pool-densitet ·
B42 (de 14 fiendernas balans/loot/caster-actions) · B46 (wisdom-gear) · B43 (butiks-
innehåll 9 nya stores) · B25 (klassbalans-sim, mät). *Visuellt:* B44 (chatt v4 segment-
färg) · B11 minimap (Slice 2) · B16.1 (combat-flikar). *Designbärande (⭐, designrunda
först):* B21 (sub-tile-kollision) · B22 (enchant-vendors) · B23 (quests) · B38 (skill-
förvärv) · B41 (on-hit-procs) · B47 (zon-färg) · B3.1→B3 (dual-class) · B10/B18 (UI).

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

#### B8 — Städerna som funktionsdrivna kluster  ⭐ designbärande  · 🟢 **Slice 2a KLAR** (system: tier-styrt kluster i alla 17) · 2b (tuning) + tjänste-triggrar kvar
- **Slice 2a KLAR** (`78cbce0`/`e74ffd2`/`17f6207`, Lucas-godkänd render): kluster generaliserat
  till ALLA 17 städer, tier-styrt (capital|city|town|village) läst ur core_zone (`tier`/`shop_category`/
  `prop` = PROVISORISK seed för 2b). `town_cluster.CLUSTER_TEMPLATES` + `resolve_template()` lägger ut
  mallarna; capital byte-identisk. Varje stad har exakt EN rest-dörr (inn / cottage i by); town_hall
  endast där turnering finns (burg_5/67/146/121); kuliss-byggnader renderar men saknar dörr/cobble.
  Sprites nycklade på (id,facing). B32 encounters=0 på alla kluster; reachability + ingen-footprint-i-vatten
  verifierad på riktiga kollisionen för alla 17. 637 tester gröna.
- **Kvar:** **2b** = slutlig tier-tilldelning + roster/orientering (mot per-stad-render) + per-stad VARIERAT
  butiks-INNEHÅLL (egen ekonomi-slice) + tjänster på kuliss (apothecary→potions, shrine→enchanter,
  stable→snabbresa, town_hall→board).
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

#### Odöd-pool-densitet  · *mätuppgift (bekräftad i playtest)*
- Loggen bekräftar den gamla öppna frågan: ~⅓ av encounters var undead/undead_priest i
  burg_54/146/320. Om avsiktligt tematiskt = okej, men det är det som gör holy-vapnet
  (B24) trivialiserande. **Mät** pool per region (sim/räkning); justera densitet om för
  hög. Liten, sim-verifierbar, autonom-vänlig.

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

#### B28 — Världsexpansion: större karta, glesare städer, kluster i alla (#3)  · 🟢 **Karta KLAR (240×208)** · kluster-i-ALLA = B8 Slice 2 kvar
- **KLART (`960d0a3`/`1985e10`):** kartan expanderad 80×56 → **240×208 med parametrisk terräng
  (option A)** — `overworld_layout.py` härleder zon-band (cainos/mork_skog/cursed_mire nord,
  grave_heath söder om seam y≈100), organisk kust som tätar kanten utom gate-mynningar, seam-kanal,
  EN nordfödd flod → central hed-sjö, och **broar härledda ur verkliga inter-stads-rutter** (fyra
  seam-övergångar spridda V→Ö, inkl. två östliga). `regenerate_overworld.py` målar layouten i TMX:en;
  `core_zone.json` bär de 17 städerna på godkända koordinater + remappade gates/ground_themes/
  wild_regions. B8-klustren (burg_5, burg_67) är procedurella → följde med + renderar intakt.
  Verifierat: alla 17 städer + 3 gates nåbara (spel-sidans kollision), ingen stad i vatten, zoner rätt,
  vatten ett sammanhängande område, TMX-laddtid ~0.55s. world.json (meny-resa) orört. 630 tester gröna.
- **Kvar:** kluster i ALLA städer med tiered storlek (hub/medium/by) = **B8 Slice 2** (egen guidad pass,
  render per stad). Nya ZONER (tema/svårighet per band) = designbärande, egen runda.

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

#### B40 — Menyprogram: enhetlig menyspec över ALLA skärmar  ⭐ designbärande  · 🟢 **Slice 1 KLAR** · S2–S5 (apply, render-HALT) kvar
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
  - **S2:** applicera inventory (bort med "Everything you own…", dämpade tomma kategorier utan "(N)", namn synligt / stats på hover).
  - **S3:** applicera shop (namn + kostnad synligt, stats/delta på hover).
  - **S4:** applicera character (inga parenteser, stats/förklaring på hover).
  - **S5:** character-creation — hela klassens talangträd som read-only förhandsvisning + starter-skill-val (1 av 2 tier-1 → learned rank 1) + enhetlig chrome + bort med "(Mana X)".
- **Acceptans (per apply-slice):** skärmen följer 7-punktsspecen; hover >1 s visar tooltip; render-HALT-godkänd av Lucas; tester.

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

#### B45 — Minisjö (5–8 tiles) att gå runt  · *nytt (vatten-/regenerate-lagret)*
- **Vad:** En liten insjö någonstans som landmärke/omväg (Lucas-önskad). **Not:** ligger i vatten-lagret (regenerate_overworld), inte prop-scattern → egen slice; flood-fill-verifieras. **Acceptans:** sjö placerad, gångbar runtom, reachability grön, test.

#### B47 — Zonfärgs-övergångar (palett)  ⭐ designbärande (art)  · *öppet beslut*
- **Vad:** Zon-till-zon-färgskiften (gul kärna / mörkgrön skog / grågrön swamp) upplevs hackiga. **Not:** paletten är **inbränd i tema-PNG:erna** → INTE fixbart via tile-placering. Öppet beslut: retuscha tema-PNG-paletterna för mjukare övergång, eller acceptera. **Acceptans:** beslut fattat; om åtgärd — mjukare zon-gräns verifierad i render.

### Chatt/HUD (nytt)

#### B44 — Chatt-logg v4-polish: segment-färg + per-träff skada  · *nytt (uppskjutet från chatt-unifieringen)*
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