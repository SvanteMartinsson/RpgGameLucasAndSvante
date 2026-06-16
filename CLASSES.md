# CLASSES: konkreta klass-träd

Detta dokument innehåller den *konkreta* per-klass-datan: stats, grenar,
noder, mana-kostnader och effekt-semantik. `COMBAT_DESIGN.md` är ramverket
(varför och hur motorn fungerar); detta är innehållet som hälls in i den.

Dokumentet växer en klass i taget. Just nu är **Cleric** fullt specificerad
som mall; övriga fem är stubbar som fylls i kommande slices.

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

## Stubbar (fylls i kommande slices)

Grennamn från `COMBAT_DESIGN.md`; noder definieras när respektive klass byggs.

| Klass | Gren A | Gren B | Mestadels nya effekttyper |
|---|---|---|---|
| Fighter | Berserker | Weaponmaster | lifesteal (=drain), buff, conditional dmg |
| Tank | Guardian | Sentinel | block/mitigation buff, thorns/reflect, taunt |
| Rogue | Assassin | Duelist | crit, execute (conditional), evasion, counter |
| Mage | Pyromancer | Cryomancer | fire/frost dmg (finns), freeze (skip-turn), burst |
| Hunter | (def. senare) | (def. senare) | mark-target, traps, type-bonus |

Vald byggordning efter Cleric: **Tank** härnäst (flest motor-nya defensiva
effekttyper — block, thorns, taunt), sedan Rogue (crit/execute/evasion),
därefter faller Fighter/Mage/Hunter mest på återanvändning.
