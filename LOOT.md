# LOOT: drops, inventory, bank, save

Anledningen att slåss och en progressionskurva. Bygger på `COMBAT_DESIGN.md`:s
grovdesign (du valde RuneScape-modellen: slump ur loot-pool + sällsynthetstier)
och på **vapen-ägandet** som lades in i korrigeringssvepen — utan ett "det här
äger jag"-begrepp betyder en drop ingenting.

**Status:** design. Bygg en slice i taget; varje har egna invarianter.

**Scope v1:** loot droppar **vapen och consumables** — de itemtyper som redan
finns. Rustnings-/accessoarslots är en senare expansion (kräver ett helt
utrustningssystem och tredubblar scopet).

## Princip

- **Guld köper bredd** (tier 1–2 i butik): täck hål, supplies, bekvämlighet.
- **Loot ger höjd** (tier 3–6, drop-only): de verkliga makt-uppgraderingarna.
- **Bästa lootet bakom svårare fiender**, inte de säkraste — spärren mot att
  grinda råttor till BIS.
- **Items är fasta** (RuneScape, inte Diablo): slumpen avgör *vilket* item som
  droppar, inte dess stats. Inga slumpade affixar i v1.

## Sällsynthetstiers

| Tier | Sällsynthet | Källa |
|---:|---|---|
| 1 | Common | butik / startvapen |
| 2 | Uncommon | butik |
| 3 | Rare | drop (vanliga loot-tabeller) |
| 4 | Epic | drop (delad rare-tabell, svårare fiender) |
| 5 | Legendary | drop (rare-tabell, djupare) |
| 6 | Mythic | drop (rare-tabell, sällsynt) |

Butik toppar på tier 2 (hårt tak). Tier 3+ är drop-only.

## Drop-modell

Varje fiende har en `loot_table` och en `drop_chance`:

```text
loot_table = [ { item_id, weight, rarity_tier }, ... ]
drop_chance = sannolikheten att NÅGOT droppar
```

Roll-ordning vid seger (efter XP/guld):

1. Rulla `drop_chance` — droppar något?
2. Om ja: viktad slumpdragning ur fiendens `loot_table`.
3. Plockas upp: vapen → ägda vapen; consumable → consumable-stack.

**Junk-loot** ligger i tabellen med hög vikt (säljbart skräp) → en guld-källa
utan makt. **Delad rare-tabell** (tier 4–6) nås ENDAST av fiender med
`rare_table_access` (arketyperna, inte grunts). **Tier-gate:** en fiende kan
bara rulla sällsynthet upp till sitt band — en råtta når aldrig tier 4+,
oavsett hur många man dödar.

## Bad-luck-skydd (beslut)

Ren slump på rare-tabellen skapar sin egen grind-tråk ("döda 80 gånger"). **v1
skeppar UTAN pity** för att hålla slicen liten — men drop-state designas så en
**pity-räknare** (stigande rare-chans per miss, nollas vid träff) kan läggas
till som första refinement. Det är min rekommenderade nästa-steg-finputs, inte
en v1-blockerare.

## Seed-items (tunas i JSON)

**Loot-only vapen** (forts. över butikens +14-tak), spridda över skadetyper så
de är situationellt starka (holy mot undead, fire mot beasts osv.):

| Item | Tier | Bonus | Typ |
|---|---:|---:|---|
| Steel Greatsword | 3 | +18 | physical |
| Emberwand | 3 | +16 | fire |
| Rimebrand | 3 | +16 | frost |
| Consecrated Maul | 4 | +24 | holy |
| Venomfang | 4 | +22 | physical |
| Pyre Scepter | 5 | +28 | fire |
| Gravewarden Blade | 5 | +28 | holy |
| Worldsplitter | 6 | +38 | physical |

**Consumables:** Greater HP Potion (heal 100), Mana Potion (restore mana),
Antidote (cure poison).

**Junk (säljbart):** Rat Pelt (~3g), Bone Dust (~5g), Tattered Cloth (~4g).

## Sälja (butik)

Butiken får ett **sälj-läge**: sälj junk och ovärda vapen för en andel av
värdet. Det är så junk-loot blir guld. Ingår i slice 1.

---

## Slice 1 — Loot drops + upplockning + sälj  *(det roliga, bygg först)*

- Lägg `loot_table` + `drop_chance` på fiender i `enemies.json`; lägg
  loot-only vapen, consumables och junk i data.
- `rare_table_access` på arketyperna (cave_bear, undead_priest,
  plague_acolyte); grunts (giant_rat, undead) saknar den.
- Implementera drop-rullningen i segerflödet (efter XP/guld), seedbar rng.
- Upplockning: vapen → ägda; consumable → stack; junk → ägda säljbara.
- Butikens sälj-läge.

### Invarianter

- Drop respekterar `drop_chance` (seedad rng): 0.0 → aldrig drop, 1.0 → alltid.
- Viktad dragning följer vikterna (seedad: känt seed → känt item).
- Tier-gate: en fiende utan `rare_table_access` kan aldrig droppa tier 4+.
- Rare-tabellen nås endast av fiender med `rare_table_access`.
- Upplockat vapen hamnar i ägda och kan equippas/swappas; en dubblett hanteras
  utan krasch.
- Sälj ger rätt guld och tar bort itemet; kan inte sälja utrustat vapen
  (eller avutrusta först — välj och testa det).
- Regression: alla tidigare tester gröna.

Commit: "Add loot drops, pickup, and shop selling".

## Slice 2 — Save/load  *(skydda progressen nu när loot är värt något)*

All state har hållits serialiserbar sedan `DESIGN.md` — nu löses den växeln in.

- `GameEngine.save(path)` / `load(path)`: serialisera hela GameState till JSON
  (spelare, ägda vapen, inventory, gold, level/xp, talanger, utrustade skills,
  nuvarande plats, world-state).
- "Save"- och "Load"-val i menyn (save var som helst eller i stad — välj).
- En enda sparfil i v1 räcker.

### Invarianter

- Spara → ladda återger identiskt state (round-trip-test: alla fält lika).
- Ladda en fil från en äldre struktur kraschar inte (saknade fält → default).
- Regression: alla tidigare tester gröna.

Commit: "Add save/load".

## Slice 3 — Bank/stash  *(förvaring, QoL)*

- Förvaring i butiks-städer (samma stad-service-mönster som rest/store).
- Deposit/withdraw vapen, consumables och guld.
- Banken är delad mellan platser (ett lager), inte per stad.

### Invarianter

- Deposit flyttar item från spelare till bank; withdraw tillbaka; inget
  tappas eller dupliceras.
- Bank nås endast på `has_store`-platser.
- Bankat innehåll överlever save/load (round-trip).
- Regression: alla tidigare tester gröna.

Commit: "Add bank/stash storage in towns".

---

## Utanför v1

- **Rustnings-/accessoarslots** + utrustningssystem (egen, senare expansion).
- **Pity-räknare** (slice 1.5-refinement; rekommenderad efter slice 1).
- Slumpade affixar / item-stats, set-bonusar (vi kör fasta items).
- Multipla sparfiler / sparplatser.
