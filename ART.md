# ART: stil, pipeline och ordning

Att ge spelet ett ansikte — riktiga sprites och tiles i stället för grå block och
färgade rutor. Det här är det sista stora spåret, och det enda som verkligen
*transformerar* upplevelsen snarare än utökar den.

**Status:** designskiss. Ingen sprite genereras förrän stil, palett och pipeline
är spikade — för art utan en sammanhållen riktning blir brus, och brus ser
*sämre* ut än ärliga grå block (blocken är åtminstone konsekventa).

## Den verkliga risken: konsekvens, inte kvalitet

Det är lätt att producera en hög bilder. Det svåra är att få dem att se ut som
*ett spel*. Du valde mix — färdiga packs för tiles, AI för unika fiender. Det är
rätt val (se nedan), men det skapar exakt konsekvens-risken: pack-tiles och
AI-sprites är ritade av olika "händer" och måste ändå höra ihop. Olika palett,
perspektiv, upplösning eller ljussättning → spelet ser ihopplockat ut.

**Limmet är paletten.** Om allt — pack-tiles OCH AI-sprites — tvingas ner i
*samma* begränsade färgpalett och samma pixelgrid, börjar de höra ihop även när
de ritats av olika källor. Palett-disciplin är den enskilt viktigaste hävstången
för att en mix ska se enhetlig ut. Allt annat i skissen tjänar det.

## Stil: 16-bitars dark fantasy pixel art

Rekommendation: **pixel art, 16×16 bas-tiles, mörk fantasy-palett.** Skäl,
grundade i projektet:

- **Lore:** "Förfallets gräns" — gravfält, odöda, mörk vildmark, kärr. En dyster
  16-bitars ton passar; en ljus/mysig stil vore tonalt fel.
- **Befintlig UI:** spelets paneler är redan mörkblå med monospace-font — retro
  och mörkt. Pixel art harmonierar med det du redan har i stället för att slåss
  mot det.
- **Pack-tillgång:** 16×16 är de facto-standarden för top-down-RPG-tiles; det
  finns gott om mörka fantasy-packs (Mystic Woods, Cursed Land, Forlorn
  Crypt-typ) att ankra stilen på.
- **AI-genomförbarhet:** AI är notoriskt dålig på *äkta* pixel art direkt (fel
  pixelgrid, anti-aliasing, spretig palett) — men en genererad bild kan
  **nedskalas (nearest-neighbor) + kvantiseras till en låst palett** så den blir
  äkta pixel art som matchar packen. Det är den disciplin som gör AI-halvan av
  mixen användbar.

Avvägning mot handmålat/högupplöst: AI är *bättre* på det, men sömlösa tiles blir
svåra att matcha, stilen driver mellan generationer, och det krockar med den rena
mörka UI:n. Pixel art är sämre för AI men bättre för *helheten* — och helheten är
det som räknas.

## Två vyer, två konstproblem

Vi har medvetet hållit isär två vyer hela projektet. De löses olika:

| | Overworld | Strid |
|---|---|---|
| Perspektiv | top-down | sidovy |
| Innehåll | terräng-tiles + gångsprite | fiende-/spelarsprites |
| Animation | 4-riktnings gångcykel | statiska (v1) |
| Källa | **färdiga packs** (16×16) | **AI** (unika varelser) |
| Varför | AI är dålig på sömlösa, kaklande tiles | packs saknar dina unika fiender (treant, bog wraith, hollow worg) |

Det här är precis mix-uppdelningen du valde, och den är rätt: pack-tiles för det
AI inte klarar (sömlös terräng), AI för det packs inte har (din specifika
bestiarie).

## Koherens-pipeline (limmet i praktiken)

1. **Anrka stilen på EN pack.** Välj ett mörkt fantasy-tileset-pack som
   stilreferens. Dess palett blir spelets palett. (Kolla licensen — vissa är
   CC0/gratis, andra kräver attribution eller köp; en publicerad titel måste ha
   rätt rättigheter. Flagga vald packs licens.)
2. **Lås paletten** (t.ex. 32–64 färger ur packen). Den är nu auktoritativ.
3. **AI-sprites tvingas in i paletten:** generera (gärna större), nedskala med
   nearest-neighbor, kvantisera till den låsta paletten, nyckla bort bakgrunden.
   Återanvänd den befintliga magenta-pipelinen (`split_sprites.py` +
   sprite-sheet-splitter-skillen) — den gör redan urklipp + transparens.
4. **Fasta canvas-storlekar:** tiles 16×16; stridssprites en fast ruta som
   skalar rent mot tile-storleken (t.ex. 48×48 eller 64×64), så inget ser
   fel-skalat ut bredvid tiles.
5. **Harmoniera med UI:n,** rör den inte i onödan — den mörka panelstilen är
   redan en tillgång; arten ska sitta *i* den, inte krocka.

## Koppling till OVERWORLD.md

Overworld-arten bygger på den plan som redan står i `OVERWORLD.md`: Tiled för
författning, `pytmx` laddar kartorna med collision + custom properties, och en
`world.json` → Tiled-stub-generator kan spotta ut förkopplade tomma kartor som
man bara målar terräng på. Den här skissen ändrar inte den planen — den fyller
den med en faktisk stil och pipeline. Stridssprites är ett separat spår som inte
rör tilemap-arbetet.

## Asset-inventarie (vad som behövs)

**Overworld (packs):**
- Terräng-tiles per zon-tema: kärnan (gräs/väg/by), väster (mörk skog, gravfält,
  kärr). En mörk fantasy-pack täcker mycket; kärr/gravfält kan kräva en
  kompletterande pack i samma palett.
- Stad/by-tiles (Hordanita, Rotequero osv.), butik, interiör.
- 4-riktnings gångsprite för spelaren (animerad) — kan komma ur en
  character-pack i samma stil.

**Strid (AI, palett-kvantiserade):**
- Fiender vi har: giant_rat, undead, undead_priest, cave_bear, plague_acolyte,
  dire_wolf, wild_boar, treant, mutated_mudcrab, bog_wraith, tar_beast,
  hollow_worg, + arena-duellanterna.
- Spelarsprite i strid (ev. per klass-känsla, eller en generisk hjälte v1).
- Bakgrund/scen per strids-miljö (valfritt v1; en enkel bakgrund räcker först).

## Byggordning (koherens-först, slicead)

Anchra stilen innan AI rör något, och få EN zon snygg hela vägen innan resten:

1. **Spika stil + palett:** välj packen, lås paletten, verifiera licens. Inget
   spel-arbete än — beslutet är artefakten.
2. **Kärnzonens overworld:** lägg in terräng-tiles + animerad gångsprite via
   Tiled/`pytmx` för kärnan. Nu ser den första vyn man möter ut som ett spel.
3. **En liten strids-uppsättning, matchad mot paletten:** spelarsprite + 2–3
   vanliga fiender (giant_rat, undead), genererade och kvantiserade till
   paletten. Bekräfta att AI-sprites och pack-tiles ser ut att höra ihop INNAN
   hela bestiarien produceras. Det här är koherens-testet.
4. **Bredda:** väster-tiles (skog/gravfält/kärr) + resten av fiendespritesen i
   samma pipeline. Hollow Worg och de tematiska bestarna sist (mest unika).
5. **UI-harmonisering + polish:** små justeringar så art och paneler sitter ihop.

Varje steg är synligt och bedömbart för sig. Steg 3 är medvetet en *liten*
matchad uppsättning — för det är där vi ser om mixen är koherent, billigt, innan
vi bränt krediter på 13 fiender i fel stil.

## Ärlig scope-notis

- Art är **stort och pågående** — inte ett bygge utan ett spår man arbetar i över
  tid. Sikta på "EN zon snygg hela vägen" som första mål, inte "allt på en gång".
- **Behåll grå-block-fallback** tills en asset faktiskt ersatts, så spelet aldrig
  är trasigt mitt i art-arbetet (en fiende utan sprite → block, inte krasch).
- **Licens** på varje pack måste stämma för en titel du kan dela/publicera.
- **AI-pixel-art-fällan** (fel grid, spretig palett) är verklig — palett-
  kvantiseringen i pipelinen är försvaret; utan den blir AI-halvan inkonsekvent.
- Art rör **inte balans** — därför är det säkert att göra före tuning; det låser
  inga speltal.

## Utanför denna fas

- Stridsanimation (attack-rörelser, träff-frames) — statiska sprites först.
- Ljud/musik (eget spår).
- Partiklar/effekter (skadetal-popups finns; visuella spell-effekter senare).
- Per-klass spelarsprites i overworld (en generisk gångsprite först).
