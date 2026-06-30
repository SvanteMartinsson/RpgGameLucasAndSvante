# OVERWORLD_BEAUTIFY_PLAN

Status: förslag (ej låst). Underlag för slice-sekvensen som ska göra overworlden
snygg. Grundad på rendering av HEAD `cc9c16b` + asset- och luma-mätningar i
sandbox-klonen. Inga ändringar gjorda ännu.

## Mål — vad "snygg" konkret betyder

En overworld som läser som *komponerad natur*, inte strössel på en färgyta:
skogar som ser ut som skogar, mark med djup, och zoner som glider in i varandra
som biom snarare än ihopklistrade bilder. Allt ur samma Cainos-DNA. Ingen
hand-Tiled — allt programmatiskt placerat, men *komponerat*, inte slumpat.

## Diagnos (mätt, inte gissat)

Fyra separerbara orsaker, olika sorters problem:

1. **Skogen läser som mossmatta, inte träd.** RÄTT pipeline är
   `regenerate_overworld.py` (INTE gamla `beautify_overworld.py`). Där är en
   "dunge" en solid cirkel (FORESTS-listan): varje cell skrivs `walls = canopy`
   (kollision — hela massan är en mur) + en krontile i `decor_over` vald av en
   marching-tiles-autotile. En enda kron-textur (mitten-tile idx 34) kaklas över
   cirkeln → platt grön ö, inga enskilda träd, inga synliga stammar, inget djup.
   Samma mekanism tätar även kartkanten (2-cells band). Spelaren ritas dessutom
   OVANPÅ kronan (kan ej gå under).
   - **Korrigerad modell (Lucas):** tät skog SKA vara ett ogenomträngligt hinder
     man går runt — kollisionen är rätt. Felet är bara *utseendet*. Enstaka/par
     träd på öppen mark är en annan sak: små hinder man går runt (stam blockerar,
     krona hänger över, man går under).
   - **Assets finns:** `TX Plant with Shadow.png` har tre hela träd (med stam +
     inbakad skugga), buskar, grästofsar; per-zon-tonade varianter finns.

2. **Marken är en platt färgyta.** Basgräset är en enda ton; detaljen
   (sten-/blomprickar) ligger glest ovanpå och läser som skräp/brus, inte flora.
   Saknar tonvariation i själva basen.

3. **Zon-övergången klyver kartan.** Mätt luma/RGB på temats grästile:
   - core (Cainos): luma 106, RGB (114,117,**27**) — knallgult, nästan blålöst
   - grave_heath: luma 88, RGB (91,91,**60**)
   - cursed_mire: luma 87, RGB (78,97,**59**)
   - mork_skog: luma 81, RGB (63,95,**58**)
   Gapet är **kulör mer än ljushet**: gult (B=27) mot svalt grågrönt (B~60).
   Går inte att fixa med tile-placering — sitter i tema-PNG:erna.

4. **Vattnet poppar för hårt.** Tealen är mer mättad/ljus än den dämpade marken
   och ser tecknad ut. Minst akut.

Plus kvarstående vatten-placering (ej estetik-system, fixas separat): floden
Salles–Urrequena omdragen i onödan; för liten bro över Guaredama; dubbelbro
under Fongorinos där en räcker.

## Fix-sekvens (slice-first, lägst risk + störst vinst först)

### Slice 1a — Tät skog ser ut som skog  ★ störst vinst, ren data, lägst risk
- Behåll kollisionen (massan är en mur man går runt) → reachability identisk,
  border-tätning oförändrad. INGEN renderar-ändring (man går aldrig in i massan).
- Få `decor_over`-kronan att läsa som tät skog i stället för utkaklad mitten-tile:
  utströdda hela trädtoppar ovanpå massan (jittrade positioner/storlekar → många
  kronor, inte en disk), synlig stam-/skuggfront i massans söderkant, mer
  kron-variation, oregelbunden organisk ytterkant, busk-frans utanför.
- Skilj **kantband** (måste förbli solid mur) från **inre dungar** i koden så ett
  framtida 1b inte råkar öppna kartkanten.
- Klart när: render visar en massa som läser som tät skog med djup, inte
  mossmatta; kollision/reachability/border byte-identiska mot före.

### Slice 1b — Enstaka träd att gå runt i det öppna  (senare; kräver renderar-touch)
- Nytt element: strö enskilda/par-träd på öppen mark. Stam = liten kollision
  (walls), krona = `decor_over` ritad EFTER spelaren så man går under.
- Renderar-ändring (liten, avgränsad): rita kron-lagret efter spelar-spriten.
  Respekterar logik/presentation-separationen.
- Klart när: man kan gå runt en ensam stam och passera under dess krona;
  reachability grön.

### Slice 2 — Marken får djup  ren skript-ändring
- Lägg tonvariation i *basen*: lågfrekvent brus som blandar in 2–3 grästoner i
  mjuka fläckar (inte strössel-på-platt).
- Tona om detaljscattern så den läser som flora: färre, mer klustrade, använd
  grästofs-sprites ur plant-arket istället för abstrakta prickar.
- Invarianter: walls/border/grindar orörda; reachability grön.

### Slice 3 — Zon-övergången  KRÄVER BESLUT (palett)
Tre vägar (kan kombineras):
- **(a) Tona om tema-PNG:erna** så core och hed delar kulörfamilj — lyft core:s
  blå (27 → ~45) bort från det neongula, ev. lyft heden lite. Skriptbar
  kurv-/hue-transform på arken. Stänger klashen vid källan.
- **(b) Bredda blandzonen** till en riktig gradient (flera mellanrader som mixar
  båda teman över ~6–10 tiles) i stället för en ditherrad. Mjukare, men
  ändpunkterna klashar ändå.
- **(c) Gör gränsen avsiktlig** — låt floden/skogen som redan ligger i sömmen
  bära biom-gränsen, så hårda linjen läser som geografi, inte söm.
- **Arkitektens rek:** (a) + (c). Krymp gapet vid källan och låt naturliga
  features bära resten. Rent palett-/placeringsjobb, ingen logik.

### Slice 4 — Vattnet seatas  ren asset-/skript-ändring, låg prio
- Avmätta/mörka vatten-tilesen lätt mot paletten så den slutar poppa.

### Städning — vatten-placering (separat, när som helst)
- Återställ Salles–Urrequena-floden; förstora bron vid Guaredama; ta bort
  dubbelbron under Fongorinos. Placering, inte system.

## Beroenden / ordning

- **Stadskluster placeras EFTER att terrängen är låst** — städer sitter på
  marken; placera dem inte och gör sen om gräset under dem.
- Fluid-layout-migrationen (character_creation → overworld → BattleApp) är ett
  separat spår och rör inte det här.
- Undead-i-heden-buggen (`zone_for_tile`) är parkerad som egen mätuppgift, ej
  beroende av detta.

## Vad vi INTE gör nu

- Ingen balanstuning (separat pass på stabil värld).
- Ingen hand-Tiled — allt förblir programmatiskt komponerat.
- Ingen ny art genereras (träd/buskar finns redan; bara ev. palett-transform på
  befintliga ark i slice 3).

## Beslut som behövs innan första build-prompten

1. **Skogsmodell:** LÅST. Tät skog = solid mur man går runt (utseende-fix, 1a);
   enstaka/par-träd = gå-runt-hinder med gå-under-krona (nytt, 1b).
2. **Startslice:** 1a (tät skog ser ut som skog) först — störst vinst, lägst
   risk, ren data. 1b efter.
3. **Zon-övergång:** väg (a) / (b) / (c) eller kombination — tas när vi når
   Slice 3. (Rek: a+c.)
