# Svantrenish RPG — Backlog

Fångade förbättringar/buggar att åtgärda. ID:n (B1–B15) matchar Lucas ursprungliga
lista så vi kan referera till dem i build-prompts. Varje punkt: **Vad** / **Avsikt**
(varför) / **Arkitekt-not** (beroende, storlek, vad som måste mätas först).

> Princip som gäller hela listan: flera punkter beskriver *nuvarande beteende* som vi
> inte säkert känner (drops, encounters, starter skills). Dessa kräver en STEG 0 som
> **mäter koden** innan vi ändrar — gissa inte.

---

## Rörelse & kamera

### B1 — Spelarhastighet + utzoomning
- **Vad:** Sänk spelarens hastighet något. Zooma ut ca 2 tiles (ser fler tiles).
- **Avsikt:** Bättre känsla/överblick när man roamar den nu större kartan.
- **Not:** Liten tuning. Zoomen är den adaptiva heltals-zoomen (`ZOOM_TARGET_TILES_W`,
  idag ~10 → testa ~12). Hastigheten är en rörelse-konstant. Båda är tunbara tal —
  enklast att justera + känна efter i ett playtest. Låg risk.

---

## Overworld & karta

### B2 — Broarna ser fel ut
- **Vad:** Broarna läser som grafiska *räcken på mark*, inte en *bro över vatten*.
- **Avsikt:** En bro ska tydligt spänna över floden.
- **Not:** Grafik/placerings-bugg från vatten-slicen (9c686e0). Bro-tiles (idx 13/14
  + ändar/stolpar) hamnade i `decor_over` över gräs — de behöver läsa som däck över
  *vatten*. Antingen fel tiles valda (räcke ≠ däck) eller fel komposition (saknar
  vatten under). STEG 0: kolla vilka bro-tiles i `water_bridge_32x32_crisp.png` som
  faktiskt är däck vs räcke/stolpe, och hur de ligger relativt vattnet under.

### B8 — Städerna behöver läsas in
- **Vad:** De stadskluster vi designat (packade 1–3-byggnaders-kluster av de nya
  husen) ska placeras/renderas på kartan.
- **Avsikt:** Städer = byggnads-kluster, inte markör-rutor.
- **Not:** Detta ÄR edge-fasens stads-slice (redan planerad, efter klippor/skog).
  Modell låst: packade kluster, beskuren tät kant, högre byggnader bak, ~3 tiles/hus,
  samlad kollisions-footprint (Model A nu → Model B/gångbar senare). Hänger ihop med
  B10 (vendor-skärm) och B4 (item-preview i butik).

### B11 — Karta + fog of war
- **Vad:** Lägg till en karta så man hittar tillbaka. Fog of war för platser man inte
  besökt.
- **Avsikt:** Orientering i den större världen; utforskande belönas (avtäckning).
- **Not:** Ny feature. Kräver: besökt-tracking per tile/region (sparas), en kart-vy
  (minimap eller fullskärm), och fog-rendering. Medelstort. Hänger ihop med B12
  (heatmap) — båda bygger på "var har spelaren varit".

---

## Strid & progression

### B3 — Talent tree är för tunt (8 talents/klass)
- **Vad:** Bara 8 talents totalt per klass — för få.
- **Avsikt:** Mer djup i progressionen.
- **Not:** Storlek beror helt på B3.1 nedan — bygg dual-class FÖRST, då behövs färre
  talents per main-klass. STEG 0: mappa nuvarande talent-data (var lagras de, hur
  väljs de, hur kopplar de mot abilities/vapen).

### B3.1 — Dual-class (main + secondary)  ⭐ designbärande
- **Vad:** Spelaren kombinerar en **main** + en **secondary** klass. Ursprunglig
  tanke, vill fortfarande bygga.
- **Avsikt:** Kombinationerna gör bygget roligt, OCH talents återanvänds över combos
  → vi behöver inte lika många talents per main-klass (löser delvis B3).
- **Not:** Större arkitektur-feature. Detta är hörnstenen — designa det INNAN vi
  utökar talent-trees, annars bygger vi talents som sen måste göras om. Påverkar:
  talent-systemet (B3), abilities (vilka kräver vilken klass-kombo), och vapen-krav
  (B4 — abilities som kräver vapentyp). Egen design-doc värd att skriva.

### B7 — Starter skills saknas för de flesta klasser
- **Status:** ✅ Klar (commit `68b7935`). Varje klass startar nu med sin signatur-
  l1-skill (samma mönster som Clerics smite): fighter frenzy, tank block, rogue
  backstab, mage firebolt, hunter aimed_shot. Data-only.
- **Vad:** Cleric har en starter skill vid klassval, men ingen annan klass.
- **Avsikt:** Alla klasser ska börja med en starter skill (konsekvens).
- **Not:** Trolig bugg/inkonsekvens. Liten. STEG 0: mät hur Clerics starter skill
  tilldelas → applicera samma mönster på övriga klasser. Hänger ihop med B3.1 (hur
  ser starter ut för en main+secondary-kombo?).

---

## Items & ekonomi

### B4 — Items & character screen: vapentyp + item-preview  ⭐ viktig
- **Vad:** Idag syns inte vilken *typ* av vapen man håller. Vill kunna klicka/skrolla
  till ett vapen, se en **preview** + läsa dess **stats**. T.ex.: är *Venomfang* eller
  *Pyrecore* en staff eller en mace?
- **Avsikt:** Med bara text att gå på är vapentyp osynlig — och det är *kritiskt* för
  att vissa abilities bara funkar med särskilda vapen.
- **Not:** UI + data. Vapentyp måste exponeras i character/inventory-skärmen, och en
  item-inspektions-vy (preview + stats) byggas. Hänger direkt ihop med B3.1 (vapen-
  beroende abilities) — vapentyp är den länken. STEG 0: mät hur items/vapen lagrar
  typ idag (finns fältet, visas det bara inte?).

### B5 — Store diversification
- **Vad:** Alla stores säljer samma saker. När en större itempool införs ska varje
  store ha *olika* simpel/medelbra gear.
- **Avsikt:** Roligt att gå runt och utforska vad varje store innehåller. Vi har många
  stores — utnyttja dem.
- **Not:** Beror på en utökad itempool (förutsättning). Hänger ihop med B6 (drops),
  B15 (pots-fördelning), B10 (vendor-skärm). Bör göras som en samlad item-/ekonomi-
  pass, inte styckevis. STEG 0: hur är store-inventory definierat idag (delad lista?).

### B6 — Droptables per enemy
- **Vad:** Varje fiende ska ha en egen droptable: **unika items** (t.ex. Hollow-worg
  har något specifikt man vill jaga) + ett **common-table** med vanligare items.
- **Avsikt:** Ge anledning att jaga specifika fiender.
- **Not:** Loot-system. STEG 0 (viktig — vet inte hur drops hanteras idag): delar alla
  fiender en pool, eller finns per-enemy redan? Mät innan design. Hänger ihop med B5
  (itempool) och B15 (greater pots som drops).

### B15 — Mana items/stats + mana pots
- **Vad:** Mana-items/stats behövs. Mana-pots känns idag som rare. Förslag: **lesser**
  health & mana pots i vissa stores; **greater** health & mana pots reserverade till
  tournament-rewards & drops.
- **Avsikt:** Balansera ekonomin runt mana; göra greater pots till eftertraktade
  belöningar.
- **Not:** Item/ekonomi. Tier-system (lesser/greater) × (health/mana) × distribution
  (store vs reward/drop). Hänger ihop med B5 (stores), B6 (drops), B13/B14 (tournament-
  rewards). Del av den samlade item-passen.

---

## Städer & UI

### B10 — Swords-and-Sandals-liknande vendor-skärm i stadsmenyer
- **Vad:** En skärm inne i en stads menyer med olika **vendors** som representerar
  vilket **hus/funktion** man besöker.
- **Avsikt:** Ge städerna karaktär; koppla funktion till plats/byggnad.
- **Not:** Town-UI. Hänger direkt ihop med stads-modellen (B8) och byggnad→funktion-
  mappningen vi låste (shop→Store, inn→Rest, church→respawn, tower→Mage Tower). Detta
  är i praktiken steget mot **Model B** (gångbara städer där man går till rätt vendor).
  Medelstort. Bygg efter att städerna är inlästa (B8).

---

## Encounters

### B12 — Encounter-heatmap (avstånd från stad)
- **Vad:** Städer + närmaste tiles = **safe**. Encounter-rate **ökar** ju längre in i
  vildmarken man kommer. **Path-tiles** (stig-antydningarna) sänker encounter-rate
  något.
- **Avsikt:** Idag finns ingen anledning att inte bara springa runt samma stad om och
  om igen — heatmapen gör vildmarken farligare och resor meningsfulla.
- **Not:** Encounter-system. STEG 0 (vet inte hur encounter-logiken funkar idag): mät
  nuvarande `encounter_rate`/`wild_region`-logik. Bygger på avstånd-från-stad +
  path-tile-modifier. Hänger ihop med B11 (besökt-data) och stig-antydningarna vi just
  lade (de blir mekaniskt relevanta här). Påverkar INTE respawn (separat).

---

## Tournaments

### B13 — Tournaments: svårighet, priser, fler platser
- **Vad:** Tournament-fienderna är alldeles för lätta; priserna behöver justeras. Lägg
  till **fler tournaments** över hela världen.
- **Avsikt:** Göra tournaments till en anledning att utforska världen.
- **Not:** Balans + content. STEG 0: mät nuvarande tournament-fiende-nivåer + reward-
  tabeller. Fler platser knyter ihop med utforskande (B11/B12). Greater pots som
  reward kopplar till B15.

### B14 — Full HP efter tournament
- **Status:** ✅ Klar (commit `e53d9c2`). `complete_tournament` återställer HP+mana
  till fullt vid avslutad serie.
- **Vad:** Efter en tournament ska spelaren återställas till fullt HP.
- **Avsikt:** Kvalitetsfix.
- **Not:** Liten. Trolig enkel hook i tournament-avslut. STEG 0: var avslutas en
  tournament i koden.

---

## Dokumentation

### B9 — README är gammal
- **Status:** ✅ Klar (commit `be34ce2`). README speglar nu Pygame-overworlden,
  pygame/pytmx-beroendet, starter skills, respawn-regeln och full HP efter tournament.
- **Vad:** Uppdatera README — den är inaktuell.
- **Avsikt:** Korrekt onboarding/projektbild.
- **Not:** Doc-underhåll. Bör spegla nuvarande tillstånd (Pygame-spelet, 80×56-
  overworld, zoner, vatten, etc.). Lägg sist i en relaterad slice eller som egen
  städning. (Vi rensade redan falska "Pygame not implemented"-påståenden i 9f0bf6f —
  men mer har hänt sedan dess.)

---

## Föreslagna kluster & ordning (arkitekt-förslag, inte hugget i sten)

Punkterna är inte oberoende — flera vill göras tillsammans:

1. **Edge-fasen klar först** (pågår): klippor/skog/kant → städer inlästa (**B8**).
   Allt annat bygger på en färdig karta.
2. **Item-/ekonomi-pass** (samlat): **B4** (vapentyp + preview) → **B6** (droptables)
   → **B5** (store-diversifiering) → **B15** (pots-tiers). Gör inte styckevis; de delar
   itempoolen.
3. **Town-UI**: **B10** (vendor-skärm) efter B8 — steget mot gångbara städer (Model B).
4. **Progression**: **B3.1** (dual-class) FÖRST → sen **B3** (talents) + **B7** (starter
   skills). Designbärande, egen doc.
5. **Värld/utforskande**: **B11** (karta/fog) + **B12** (encounter-heatmap) — delar
   besökt-data.
6. **Tournaments**: **B13** (balans/fler) + **B14** (full HP) — ihop med B15-rewards.
7. **Småfixar när som helst**: **B1** (hastighet/zoom), **B2** (bro-grafik), **B14**,
   **B9** (README sist).

> Flera punkter (B6, B7, B12, B13, B14) börjar med "vet inte hur det funkar idag" →
> varje sådan slice inleds med en STEG 0 som mäter nuvarande kod innan vi designar.
