# CLASSES: konkreta klass-träd

Detta dokument innehåller den *konkreta* per-klass-datan: stats, grenar,
noder, mana-kostnader och effekt-semantik. `COMBAT_DESIGN.md` är ramverket
(varför och hur motorn fungerar); detta är innehållet som hälls in i den.

Dokumentet växer en klass i taget. **Cleric** och **Tank** är fullt
specificerade; övriga fyra är stubbar som fylls i kommande slices.

Alla tal är startvärden avsedda att tunas i JSON.

## Effektvokabulär (motorns kontrakt)

Klass-träden får bara använda effekttyper ur denna slutna lista. Behöver en
nod något som inte finns här är det en *motorändring*, inte bara data — och
ska läggas till medvetet, inte improviseras.

Befintligt i motorn idag:

- **instant_damage** — direkt skada, bär `damage_type`, skalar från Power
  och/eller multiplier. Går genom resistenser; armor reducerar endast
  `physical`.
- **status: poison (dot)** — skada per runda i N rundor via tick-loopen.
  Modell: `{ type, magnitude, duration, tick_timing }`.

Läggs till i Cleric-slicen (generiska, återanvändbara):

- **instant_heal** — läker mål för ett belopp; **får aldrig överhela**
  (cappas vid `max_hp`).
- **drain** — instant_damage + läk källan för en andel av faktiskt utdelad
  skada (cappas vid `max_hp`).
- **status: regen** — heal per runda i N rundor. Samma modell som poison
  fast positiv magnitude; återanvänder *samma* tick-loop.
- **status: debuff** — sänker en namngiven stat (t.ex. Power) med ett belopp
  medan effekten är aktiv; återställs när den löper ut. Hanteras av
  status-livscykeln, inte nödvändigtvis per tick.
- **status: buff** — som debuff fast positiv (förbereder Tank/Fighter).

Passiva modifierare (inte actions — persistenta på entiteten, konsulteras av
resolvern):

- **stat_bonus** — platt påslag på en stat (t.ex. +max_mana).
- **applied_status_mod** — ändrar parametrarna på statuseffekter *som denna
  entitet applicerar* (t.ex. +1 duration, +2 magnitude på egna poisons).

Läggs till i Tank-slicen (defensiva motorhakar — återanvänds av fiender/bossar):

- **cooldown-system** — en action kan ha `cooldown_rounds`. Efter användning
  är den otillgänglig N rundor; räknas ned per runda; `available_actions`
  speglar det. (Komplement till mana — vissa skills gatas av cooldown, inte
  resurs.)
- **status: mitigation** — platt reduktion av *all* inkommande skada under N
  rundor. Lager: resist → armor (endast physical) → mitigation (all) → `max(1, …)`.
- **status: reflect** — när bäraren *tar* skada av en angripare delas skada
  tillbaka (flat för thorns, Power-skalad för counter). Reflekterad skada
  triggar ALDRIG ny reflect (ingen oändlig loop). Ingen reflect vid miss.
- **accuracy_mod** (nytt modifierbart fält) — fiendens träffslag använder
  `clamp(base_chance + accuracy_mod, 0, 100)`. Taunt sätter accuracy_mod via
  det befintliga debuff-maskineriet (ingen ny effekttyp).
- **passiv: immunity** — immun mot en tagg (t.ex. `debuff`, `flee_force`).

## Talang- och upplåsningsregel

Vald enkel lösning (löser `COMBAT_DESIGN.md`:s öppna fråga):

- Spelaren får **1 talangpoäng per level up**, utöver det befintliga
  stat-valet.
- Noder låses upp **linjärt inom en gren**: nod 2 kräver nod 1 i samma gren,
  osv. Poäng får fördelas fritt mellan de två grenarna.
- Kärnan exponerar `available_talents()` och `allocate_talent(node_id)` —
  presentationen driver valet. Detta speglar det befintliga
  `apply_stat_choice`-mönstret: **inget `input()` i kärnan.**
- Aktiva noder blir utrustningsbara skills. Regeln **max 4 utrustade skills**
  (från `COMBAT_DESIGN.md`) gäller fortfarande.

## Cleric

Resursklassen. Måttlig överlevnad, låg Power, lever på mana och timing. Bär
ett holy-vapen (mace). Två grenar: **Ljus** (smite, heal, support) och
**Pest** (poison, drain, curse).

### Basstats (startvärden)

| Stat | Värde |
|---|---:|
| HP / Max HP | 90 |
| Max Mana | 30 |
| Power | 10 |
| Armor | 0 |
| Speed | 10 |
| Startvapen | Mace (damage_type: holy) |

### Gren: Ljus

| Nod | Typ | Effekt | Mana |
|---|---|---|---:|
| L1 Smite | aktiv | instant_damage, holy, ~1.5× Power (finns redan) | 6 |
| L2 Mend | aktiv | instant_heal av self, +25 (cappas vid max_hp) | 8 |
| L3 Devotion | passiv | stat_bonus: +15 max_mana | — |
| L4 Sanctuary | aktiv | status regen på self: +8 HP/runda i 3 rundor | 10 |

### Gren: Pest

| Nod | Typ | Effekt | Mana |
|---|---|---|---:|
| P1 Plague Bolt | aktiv | status poison på mål: 6/runda i 3 rundor (finns redan) | 7 |
| P2 Drain | aktiv | drain, holy, ~1.2× Power; läk self 50% av utdelad skada | 9 |
| P3 Virulence | passiv | applied_status_mod: egna poisons +1 duration, +2 magnitude | — |
| P4 Curse | aktiv | status debuff på mål: Power −4 i 3 rundor | 8 |

### Invarianter att låsa i test (Cleric-slicen)

- **Mend** läker exakt +25 och överhelar aldrig (cappas vid max_hp).
- **Sanctuary** läker +8/runda i exakt 3 rundor via tick-loopen, sen slut
  (bevisar att positiv status återanvänder samma loop).
- **Drain** delar ut skada D och läker self `round_half_up(D × 0.5)`,
  self-heal cappas vid max_hp.
- **Curse** sänker målets Power med 4 i 3 rundor och återställer det när
  effekten löper ut.
- **Virulence**: en poison som appliceras *efter* att Virulence tagits har
  +1 duration och +2 magnitude jämfört med utan.
- **Talang-prereq**: L2 kan inte tas före L1; allokering över tillgängliga
  poäng avvisas.
- **max 4 utrustade skills** upprätthålls.
- **Regression**: befintliga Smite + Fighter/Tank-attacker oförändrade.

## Tank

Mitigeringsklassen. Hög överlevnad, låg Power, gör det jobbigt för fienden
att få igenom skada. Liten mana-pool — lutar sig på cooldowns för sina
defensiva stances. Två grenar: **Guardian** (aktiv mitigering: block, thorns,
taunt) och **Sentinel** (sustain, counter, immunitet).

### Basstats (startvärden)

| Stat | Värde |
|---|---:|
| HP / Max HP | 130 |
| Max Mana | 15 |
| Power | 8 |
| Armor | 4 |
| Speed | 7 |
| Startvapen | Mace (damage_type: physical) |

### Gren: Guardian

| Nod | Typ | Effekt | Kostnad |
|---|---|---|---|
| G1 Block | aktiv | status mitigation på self: −8 all inkommande skada i 1 runda | cooldown 2 |
| G2 Thorns | aktiv | status reflect på self: 3 rundor, reflektera 5 skada till den som träffar | 6 mana |
| G3 Bulwark | passiv | stat_bonus: +3 armor, +20 max_hp | — |
| G4 Taunt | aktiv | status debuff på mål: accuracy_mod −20 i 2 rundor | cooldown 3 |

### Gren: Sentinel

| Nod | Typ | Effekt | Kostnad |
|---|---|---|---|
| S1 Iron Stance | aktiv | status regen på self: +6 HP/runda i 3 rundor | 6 mana |
| S2 Counter | aktiv | status reflect på self: 2 rundor, vid träff slå tillbaka 1.0× Power (physical) | 8 mana |
| S3 Resolve | passiv | immunity mot `debuff` och `flee_force` | — |
| S4 Fortitude | passiv | stat_bonus: +5 armor, +20 max_hp | — |

### Invarianter att låsa i test (Tank-slicen)

- **Block** reducerar inkommande skada med exakt 8 under 1 runda (min 1 går
  alltid igenom), och löper ut korrekt.
- **Block-cooldown**: kan inte användas igen förrän cooldown gått ut;
  tillgänglig igen efter.
- **Thorns**: angriparen tar exakt 5 vid träff; reflekterad skada triggar inte
  ny reflect; ingen reflect vid miss.
- **Taunt**: målets effektiva träffchans sänks med 20 under 2 rundor och
  återställs sen.
- **Counter**: vid träff slår Tank tillbaka `round_half_up(1.0 × Power)`
  physical; bara medan buffen är aktiv; bara vid faktisk träff.
- **Iron Stance**: +6 HP/runda i exakt 3 rundor (återanvänder Clerics regen).
- **Resolve**: en debuff mot Tank avvisas/ger ingen effekt; tvingad flee
  misslyckas.
- **Bulwark/Fortitude**: stat_bonus appliceras och kvarstår.
- **Gating**: både cooldown och mana upprätthålls; avvisad användning muterar
  inte state.
- **Regression**: alla tidigare tester (Cleric, Fighter/Tank-attacker,
  combat-pipelinen) fortfarande gröna.

## Stubbar (fylls i kommande slices)

Grennamn från `COMBAT_DESIGN.md`; noder definieras när respektive klass byggs.

| Klass | Gren A | Gren B | Mestadels nya effekttyper |
|---|---|---|---|
| Rogue | Assassin | Duelist | crit, execute (conditional), evasion, counter (finns) |
| Fighter | Berserker | Weaponmaster | lifesteal (=drain), buff (finns), conditional dmg |
| Mage | Pyromancer | Cryomancer | fire/frost dmg (finns), freeze (skip-turn), burst |
| Hunter | (def. senare) | (def. senare) | mark-target, traps, type-bonus |

Vald byggordning nu: **Rogue** härnäst (crit/execute/evasion — de offensiva
varianterna; counter finns redan från Tank), sedan Fighter och Mage som mest
faller på återanvändning, Hunter sist.