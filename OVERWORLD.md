# OVERWORLD: rörelse och tile-kartor

Hur man rör sig i världen. `world.json` (se `DESIGN.md`) äger all logik;
detta dokument beskriver det promenerbara lagret ovanpå.

**Status:** design, Pygame-era. Inget av detta byggs förrän klasser, loot och
fiender står. Kontraktet kan förfinas när det faktiskt implementeras.

## Princip: grafen är logiken, tiles är rörelsen

`world.json` fortsätter äga vad som finns och hur det hänger ihop — platser,
connections, `danger_tier`, encounters, butiker. Tiled-kartorna är bara de
promenerbara rummen. Inget i `world.json` ersätts; tiles är ett rent
presentations- och rörelselager.

## Två sorters kartor (direkt ur grafen)

Grafen beskriver redan Pokémons två platstyper:

| Graf | Tile-karta | Man går där | Encounters |
|---|---|---|---|
| Nod (plats) | stadskarta | ja | normalt nej (trygg) |
| Kant (connection) | vägkarta mellan två platser | ja | ja |

## Kopplingskontrakt (Tiled custom properties)

Samma princip som `world.json`:s fältkontrakt. Tile-kartan bär *placering och
rörelse*; grafen bär *logik och egenskaper*; ett id syr ihop dem.

Karta-nivå:

- `place_id` (stadskarta) eller `route_id` = `"burg_5__burg_117"` (vägkarta,
  de två ändpunkterna).

Objekttyper i Tiled:

- `spawn` — spelarens startpunkt. Vägkartor har två (en per ände; du dyker upp
  vid den ände du kom ifrån).
- `exit` / `warp` — leder till grannkarta. Stadens exits → vägkartorna för dess
  connections; vägens ändar → stadskartorna. Drivs av grafens connections.
- `encounter_zone` — tiles som slumpar en fiende när man går på dem (vägkartor).
- `store` — öppnar butiken om platsens `has_store` är sann.
- `npc` / `interaction` — dialog/handling.

Lager:

- ett **collision-lager** (blockerat vs promenerbart).

## Encounters på vägar (ny datakonsekvens)

Idag bor encounters per *plats*. Vägarna behöver nu egna pooler.

**Vald enkel lösning:** härled vägens encounter-pool och frekvens ur de två
ändpunkternas `danger_tier` (t.ex. den högre av de två) — ingen ny
författning. Det blir nya fält på connections i `world.json`
(`encounters`, `encounter_rate`), som läggs till i `derive_world.py` när det
blir dags. `danger_tier` styr alltså både *vilka* fiender och *hur ofta*.

Stadskartor är normalt trygga (platsens `encounters` ofta tom). Faran bor på
vägen — vilket är exakt friktionen vi designade: lämna den trygga staden,
riskera vägen.

## Stub-generator (framtida verktyg)

Eftersom grafen redan finns kan en `world.json` → Tiled-stub-generator spotta
ut tomma, förkopplade kartor: en per plats och en per connection, taggade med
rätt `place_id`/`route_id`, spawns, exits till grannarna och encounter-zoner
dimensionerade efter `danger_tier`. Du målar bara terräng — aldrig wira logik
för hand. Det är det som gör ~21 städer + ~30 vägar hanterbart att författa,
och det återanvänder grafen fullt ut.

## Konst-implikation

- **Tilesets** (sömlös terräng) — använd ett befintligt pixel-art-tileset-pack,
  INTE magenta-AI-pipelinen; AI är dålig på sömlösa, kaklande tiles.
- **Top-down spelar-sprite** med 4-riktnings-gångcykel — animation, en ny sak
  jämfört med dina statiska sidovy-stridssprites.
- Striden använder fortfarande sidovy-sprites; overworld är top-down. Två vyer.

## Teknik

Tiled (mapeditor.org) för författning → JSON/TMX. `pytmx` laddar kartorna i
Pygame inklusive collision och custom properties; `pyscroll` för scrollande
rendering. Spelet laddar samma filer som Tiled skriver — ingen mellanhand.

## Fasning

Tilea startklustret först (några få städer + deras vägar), väx utåt. Du
författar inte alla kartor innan något är spelbart — samma princip som den
kurerade startvärlden.

## Utanför denna fas

Pygame-era, efter klasser/loot/fiender. Framåtblickande data som läggs till
när det byggs: `connection.encounters` + `encounter_rate` och
`place.tilemap` / `connection.tilemap`-referenser i `derive_world.py`. Inget
av detta byggs nu.
