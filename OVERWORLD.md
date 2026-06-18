# OVERWORLD: fri gång och tile-kartor

Hur man rör sig i världen. `world.json` (se `DESIGN.md`) äger all logik;
detta dokument beskriver det promenerbara lagret ovanpå.

**Status:** byggt (Pygame). En spelbar kärnzon runt Hordanita finns; resten av
världen är gated som framtida expansion. Kontraktet kan förfinas vidare.

## Modell: fri gång (Modell B)

Spelaren går fritt med WASD/piltangenter över en sammanhängande, promenerbar
karta — inte nod-för-nod längs en graf. Tile-kartan är rörelselagret;
`world.json` är fortfarande logiken.

Tidigare designidé (kant-/vägkartor mellan platser, med restid härledd ur
avstånd) är **pensionerad för rörelse**. Vi reser inte längre via `travel()` och
`distance_km_approx` i overworld; man går dit man går. Grafens connections och
avstånd finns kvar i datan och kan användas av annat (t.ex. framtida fast-travel
eller kartlogik), men de styr inte fri gång.

## Princip: grafen är logiken, tiles är rörelsen

`world.json` fortsätter äga vad som finns och dess egenskaper — platser,
`danger_tier`, encounters, butiker, respawn. Inget i `world.json` ersätts. Det
promenerbara lagret pratar bara med motorn via befintliga `GameEngine`-metoder
och `build_snapshot()` (se `PRESENTATION_API.md`); det duplicerar inga
spelregler.

## Platser = lokationer man går in i

Platser ligger som markerade tiles på den gångbara kartan. När spelaren går in
på en stadstile sätter presentationen motorns lokation till den platsen.

Fri gång innebär godtycklig ankomst (det finns ingen "från"-plats att validera
mot), så motorn fick en minimal additiv metod:

- `GameEngine.enter_place(place_id)` — sätter `current_place_id` och respawn
  direkt, utan adjacens-gaten. Speglar `travel()` i övrigt; låsta platser nekas
  fortfarande. `travel()` finns kvar oförändrad för adjacens-baserad resa.

I en stad öppnar Enter location-menyn i Pygame. Den menyn är för lokala
tjänster, framför allt store/rest där platsen stödjer det. Det spelaren bär med
sig — character, inventory, skills/talents och system/save — ligger som
overworld-overlays ovanpå kartan:

- `C`: Character, stats och weapon equip.
- `I`: Inventory, consumables och junk.
- `K`: Skills & Talents, skill-loadout och hela talent tree.
- `Esc`: System, save och quit.

Overlays kan öppnas i stad och vildmark, men inte i battle. Samma tangent eller
Esc stänger aktuell overlay. Allt går via `build_snapshot()` och befintliga
engine-metoder; presentationen duplicerar inga regler.

## Encounters i vildmark

Faran bor mellan städerna. Stadstiles är trygga; vildmarkstiles kan trigga en
strid.

- En **chans per steg** (per ny tile man går in på i vildmark) rullas mot en
  tunbar frekvens (`encounter_rate_per_step` i zon-configen).
- Vid träff genererar motorns befintliga `create_encounter()` en fiende ur den
  aktuella regionens pool. Vildmarken pekar på en **region-plats** vars
  `encounters` definierar fienderna (`wild_region_place_id` i configen).

## Loop: overworld ↔ battle

1. Steg i vildmark → eventuell encounter.
2. Striden körs i battle-skalet (samma `GameEngine`-combat, ingen duplicerad
   stridslogik).
3. **Seger/flykt:** tillbaka till overworld på samma position.
4. **Förlust:** motorns respawn (Hordanita); spelar-spriten flyttas till hubbens
   stadstile.

## Gate: spelbar kärnzon nu, resten gated

Hela 21-platsersvärlden är *tänkt* men inte spelbar än. Den spelbara kärnan är
Hordanita (hub, `burg_5`) plus ett par närliggande platser, på placeholder-tiles
(grönt fält + grå block).

Vägarna ut mot resten av världen är **gated** — ej gångbara tiles vid kanterna,
var och en med en rad text som förklarar varför ("Vägen norrut är inte trygg
än …"). En spärr utan förklaring läses som en bugg; en med en rad text läses som
"mer att komma".

Gaten är **data, inte spridd logik**, och är avsedd att **FLYTTAS utåt** (öppna
fler tiles/städer) när en ny zon byggs — inte tas bort. Allt zon-specifikt
(town-tiles, gate-tiles + text, encounter-frekvens, region-pool, respawn) ligger
i `rpg_game/data/maps/core_zone.json`. Kärnzonens karta är
`rpg_game/data/maps/overworld.tmx`.

## Kollision

Ett **walls-lager** i TMX markerar blockerade tiles. Blockerat = walls-lagrets
tiles plus gate-tiles. Rörelsen löses per axel så att en vägg på ena axeln inte
dödar rörelse på den andra.

## Konst-implikation (framtid)

- **Tilesets** (sömlös terräng) — använd ett befintligt pixel-art-tileset-pack,
  INTE magenta-AI-pipelinen; AI är dålig på sömlösa, kaklande tiles. Nu körs
  enkla placeholder-tiles (grönt fält + grå block).
- **Top-down spelar-sprite** med 4-riktnings-gångcykel — en framtida sak;
  just nu en enkel markör.
- Striden använder sidovy; overworld är top-down. Två vyer.

## Teknik

Tiled (mapeditor.org) för författning → TMX. `pytmx` laddar kartorna i Pygame
inklusive collision-lager och custom properties. Vi **blittar tiles direkt** för
små, fasta kartor — `pyscroll` används medvetet inte (inaktivt, och onödigt utan
stora scrollande kartor). En enkel centrerad kamera med clamp räcker.

## Fasning

Kärnklustret runt Hordanita först; väx utåt genom att flytta gaten och lägga
till town-/gate-tiles i configen samt mer karta i TMX. Du författar inte alla
kartor innan något är spelbart.
