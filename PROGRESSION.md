# PROGRESSION: fiende-level, XP-skalning, gear-gating, identify

Fyra sammanhängande tillägg som ger djup och mystik. Fiende-level är navet: det
matar både XP-skalningen och vad Identify avslöjar. Bygger på loot/level-systemen
som redan finns.

**Status:** byggt och testat för fiende-level, level-skalad XP,
vapen-level-krav och Identify. Permanent bestiary är fortfarande framtida.

## 1. Fiende-level

Varje fiende får ett `level`-fält i `enemies.json`. Level är en **etikett +
indata** — den skalar INTE fiendens stats (de är authored), den används för
XP-multiplikatorn och visas via Identify.

| Fiende | Level (förslag, tunas) |
|---|---:|
| Giant Rat | 1 |
| Undead | 2 |
| Cave Bear | 3 |
| Undead Priest | 3 |
| Plague Acolyte | 4 |

## 2. Level-skalad XP

Man får **alltid** XP, men skalat mot level-skillnaden — svåra fights lönar sig,
safe fights ger ett konstant men lägre inflöde.

```
diff       = enemy.level − player.level
multiplier = clamp(1 + 0.25 × diff, 0.25, 2.0)
xp_awarded = round_half_up(base_xp × multiplier)
```

- jämn level → 1.0×
- +3 level → 1.75×, cap vid +4 → 2.0×
- −2 level → 0.5×, golv vid −3 och neråt → 0.25× (aldrig 0)

Gold påverkas inte i denna iteration (kan skalas senare om vi vill).

### Invarianter

- diff 0 ger exakt base_xp.
- positiv diff ger mer, negativ mindre; aldrig under 0.25× eller över 2.0×.
- xp_awarded är alltid ≥ 1 (avrundat, aldrig 0).

## 3. Vapen-level-krav

Man kan **äga** vilket droppat vapen som helst direkt, men inte **equippa** det
förrän man har rätt level. Så en tidig tier-5-drop är en morot, inte slöseri.

```
required_level = max(1, weapon.tier − 2)
equip tillåtet om player.level >= required_level
```

- tier 1–3 → kräver level 1 (alltid ok)
- tier 4 → level 2
- tier 5 → level 3
- tier 6 → level 4

Gäller alla equip-vägar: swap i strid, butiksköp-som-utrustar, ev. auto-equip.
Butiksvapen är tier ≤2 → alltid level 1 → ingen friktion i butiken.

### Invarianter

- equip/swap till ett vapen med för högt krav avvisas i kärnan; state oförändrat.
- ägande påverkas inte — vapnet ligger kvar i owned, bara ej equippbart.
- vid rätt level går equip igenom.
- butiksvapen (tier ≤2) är alltid equippbara på level 1.

## 4. Identify (stridsval)

Ett stridsval i menyn: **Identify**. Förbrukar rundan (fienden får sin
handling) och avslöjar fiendens **level, stats, type/tags och skills**.
Bygger ett mer mystiskt spel: okänt som standard, men man kan investera en runda
för att lära sig.

**Dolt som standard / synligt alltid:** namn och nuvarande HP visas alltid (man
ser vem och hur skadad). Level, Power/Armor/Speed, resistenser, tags och skills
är **dolda tills man identifierat**.

> **Beslut att stämma av:** jag låter avslöjandet gälla **för den aktuella
> striden** (minsta möjliga; matchar "investera en runda"). En *permanent*
> bestiary som minns varje identifierad fiendetyp är en ren uppgradering senare
> (ett `identified_enemy_ids`-set i state som serialiseras när save byggs). Vill
> du ha den permanent direkt, säg till — det är ett litet tillägg.

- Identify gör 0 skada, kostar ingen mana; kostnaden är tempot (fienden agerar).
- Resultatet returneras strukturerat så UI:t kan skriva ut ett stat-block.
- Statusraden visar fortsatt aktiva statusar som idag.

### Invarianter

- Identify förbrukar spelarens runda; fienden tar sin handling.
- Efter Identify exponerar combat-resultatet fiendens level/stats/tags/skills
  (för den aktuella striden i v1).
- Före Identify är de fälten inte synliga i UI:t (namn + HP är det).

## Byggordning

Kör **efter** vapentyp-slicen (WEAPONS.md), så Claude Code inte har två stora
ändringar igång samtidigt. Allt här är oberoende av vapentyperna utom att det
delar samma combat-loop.

Lämplig delning i commits:
1. Fiende-level + level-skalad XP (data + XP-beräkning).
2. Vapen-level-krav (equip-gating).
3. Identify (stridsval + reveal).

## Utanför denna slice

- **Permanent bestiary** (persistent identify) — noterad uppgradering.
- Level-skalning av fiendens *stats* (vi authorerar dem; level är bara etikett).
- Gold-skalning mot level.
- Level-krav på skills/talanger (bara vapen här).
