# EQUIPMENT: slots, armor, ringar och stat-aggregering

Loot är idag tomt i nedre änden: junk, eller ett tier-3-vapen — inget mellan, inga
små tidiga uppgraderingar, inget att fylla på kroppen med. Det här systemet
förvandlar loot från "ett vapen ibland" till en pool av gear som fyller många
slots — och ger gråa fiender något värt att droppa. Det bygger på det vi redan
har (vapnens equip-väg, rarity/tier, drop-tabeller, stat-modellen), inte ett
nybygge.

**Status:** design. Detta är det sista stora *systemet* innan fokus skiftar till
innehåll och art.

## Princip: gear = stat-modifierare i slots

Vapnet behåller sin egna semantik (damage_type, category, skill-gating,
attack-bas) — vi rör det INTE. Armor och accessoarer är en ny, enklare sorts
föremål: de sitter i slots och bidrar med **stat-modifierare**. En spelares
*effektiva* stat = bas (klass + level) + summan av alla utrustade geardelars
modifierare.

## Slots (data-drivet)

Slot-listan är **data** så att lägga till/ta bort en slot blir config, inte kod.
Förslag v1:

| Slot | Antal | Typisk roll |
|---|---|---|
| Weapon | 1 | *befintligt system, oförändrat* |
| Head | 1 | armor, HP |
| Chest | 1 | armor, HP (störst) |
| Hands | 1 | armor, lite utility |
| Legs | 1 | armor, HP |
| Feet | 1 | armor, speed |
| Amulet | 1 | blandad utility |
| Ring | **3** | build-statsen (se nedan) |

Tio slots totalt. En geardel passar i exakt en slot-typ. Ringar har tre slots —
man kan bära tre samtidigt (olika slots).

## Stats som gear kan modifiera (v1)

Endast stats som redan finns i modellen, så vi inte uppfinner nya delsystem:
`max_hp`, `max_mana`, `armor`, `speed`, `crit_chance`, `damage`.

- `damage` adderas till **effektiv base_power** (samma hink som vapnets bonus, så
  den skalar med attack-multiplikatorn). Gear ger alltså inte en separat
  skadekomponent — den höjer din grundskada.
- `armor`, `speed`, `crit_chance`, `max_hp`, `max_mana` adderas till respektive
  bas-stat.
- Modifierare är heltal (ingen round-problematik).

> **Elementresistens på gear** (t.ex. +fire-resist) skjuts till framtiden: det
> kräver en resist-modell på FÖRSVARAR-sidan för spelaren, och en sån finns
> kanske inte än. STEG 0 i bygget ska verifiera; saknas den, lämna elementresist
> ute i v1. Ringar är ändå "exklusiva" via crit/speed/damage/mana — vi behöver
> inget nytt maskineri för det.

## Ringar = de exklusiva statsen

Ringar bär de build-definierande statsen — `crit_chance`, `speed`, `damage`,
`max_mana` — medan armor mest ger `armor` + `max_hp` (defensivt). Det ger ringar
identitet: det är där de roliga valen bor. Med tre ringslots blir ringuppsättning
ett eget litet bygge. Ringar är sällsyntare och har starkare/fler modifierare per
rarity än armor (se drops).

## Stat-aggregering (kärnans verkliga ändring)

Detta är hjärtat. **En enda funktion** `effective_stat(stat)` =
`bas + Σ modifierare från utrustad gear`. ALLT som läser en stat för spel-logik
(combat: armor-mitigering, crit-roll, skada, turordning via speed; HP/mana-tak;
stats-rutan) läser via den — aldrig en rå bas-stat direkt.

- Den centrala invarianten: **ingen spel-väg läser en rå bas-stat för gameplay;
  allt går genom effektiva stats.** Det är där risken ligger — att någon kodväg
  fortfarande läser `player.armor` istället för `effective_armor`. Bygget måste
  dra om alla sådana läsningar.
- Vapnets dmg-bonus ligger kvar i attack-uträkningen som idag; gear-`damage`
  matas in i samma base_power-term. Två källor, en hink.
- `max_hp`/`max_mana`: att utrusta något som höjer taket **läker inte** (current
  oförändrad, taket stiger). Att ta av något som sänker taket **clampar current**
  till nya max. Lås i test.

## Gear-föremål (data)

Authored pool (inte procedurellt genererat i v1 — enklare, testbart, matchar
data-ethosen). Ett gear-item:

```
{ id, name, slot_type, tier, rarity, level_req, stat_modifiers: { stat: värde, … } }
```

- `level_req` som vapen (t.ex. `max(1, tier−2)`) — kan ägas men inte utrustas före
  rätt level.
- Säljbart som vapen (återanvänd butikens sälj-väg).
- Procedurell generering (slumpade modifierare per drop) är en frestande framtida
  uppgradering men adderar RNG-komplexitet och svårtestad balans — **inte v1**.

## Drops (fyller den tomma nedre änden)

Gear läggs i drop-tabellerna bredvid vapen. Det är HÄR poängen betalar ut: en grå
fiende kan droppa en +2-armor-hjälm eller en ring med +1 crit — små men ÄKTA
uppgraderingar, exakt gapet vi såg i speldatan.

- **Tier** styr modifierarnas magnitud + level_req.
- **Rarity** styr antal/styrka: t.ex. common = 1 liten modifierare, uncommon =
  1–2, rare = 2–3 starkare. Det gör en rare-drop spännande — det vi ville.
- Låg-tier gear (tier 1–2) ska droppa tidigt så de första killsen ger något att
  fylla en slot med.

## Character-panel (presentation)

Panelen (C) ska visa:
- Alla slots och vad som sitter i dem (tom slot tydligt märkt).
- Effektivt stat-block: **bas → +gear → totalt**, så spelaren ser vad utrustningen
  gör.
- Välj slot → lista ägd gear som passar (respektera level_req + slot-typ) →
  utrusta; ta av → tillbaka till ägd. Samma kontrakt som vapen-equip (engine-väg,
  ingen ny logik i presentationen).
- *Valfri polish:* visa ±stat-jämförelse mot det som sitter i slotten när man
  hovrar/markerar en geardel. Trevligt, inte krav.

## Save/load

Utrustade slots + ägd gear måste serialiseras (utöka save-schemat; vapen
serialiseras redan — följ samma mönster). Lås i test att en sparad + laddad
karaktär behåller utrustning och ägd gear.

## Invarianter att låsa i test

- Effektiv stat = bas + Σ utrustad gear; ändras korrekt vid equip/unequip.
- INGEN gameplay-väg läser rå bas-stat (combat läser effektiv armor/crit/speed/
  skada; HP/mana-tak använder effektiva max).
- Equip respekterar slot-typ och level_req; fel slot/för hög level blockeras.
- Tre ringar kan bäras samtidigt (olika slots); fjärde ringen kräver att en tas av.
- `max_hp`/`max_mana`-modifierare läker inte vid equip; clampar current vid unequip.
- Gear droppar enligt tier/rarity; låg-tier gear kan falla tidigt; vapen-drops
  oförändrade.
- Save/load bevarar utrustade + ägda geardelar.
- Sälj fungerar för gear.

## Byggordning (för kommande prompt)

1. **Kärna**: data-drivna slots + `effective_stat`-aggregering + equip/unequip i
   slots + level_req + HP/mana-tak-hantering. Dra om alla stat-läsningar i combat/
   stats till effektiva stats. Save/load-schema. Commit: "Add equipment slots and
   stat aggregation".
2. **Data**: authored gear-pool (armor + amulet + ringar över tier/rarity) +
   drop-tabell-integration (inkl. låg-tier tidigt). Commit: "Add gear item pool
   and drops".
3. **Presentation**: Character-panelen visar alla slots + effektivt stat-block +
   equip/unequip; (ev. ±jämförelse). Commit: "Show equipment slots in character
   panel".

## Utanför scope (v1)

Set-bonusar, sockets/ädelstenar, enchanting, procedurellt genererad gear,
elementresistens på gear (väntar på spelar-resist-modell). Noterade som framtida
lager.
